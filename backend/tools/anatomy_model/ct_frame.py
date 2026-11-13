"""The frozen CT of the head and neck on one grid, and where its voxels lie in the body.

The CT (data/vhp_male_frozen, one slice per millimetre, SliceLocation = the photographs' slice number) changes
its pixel size down the body: 0.527 mm over the head (slices 1006..1236), 0.781 mm to 1260, 0.9375 mm below.
`volume` resamples a range of slices onto one grid in the scanner's own millimetres (x to the patient's left,
y to his back, as DICOM has them), for tools that want one volume (TotalSegmentator: head_layers.py).

Where a CT point lies in the body: tools/import_ct_bone.py matched each CT slice to its photograph by sliding the
body's outlines over each other, and stored where the CT image's corner fell (labels.json, "ct_bone"). The match
is a shift only, but the CT's millimetres are not quite the photographs': the frozen body in the scanner
measures SCALE times what the photographs' nominal 0.33 mm pixels say (out/photo_head/ct_registration.json found
0.968 on the head; `check` measures it again). A shift that matches two outlines of different size matches
their middles, so a CT point is placed from the outline's centroid in its slice, scaled:
    photograph mm = shift + centroid + (point - centroid) / SCALE
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from .common import Body

GRID_MM = 0.9375
GRID_ORIGIN = (-240.0, -240.0)          # the scanner's x, y of the grid's first pixel's corner (the wide series' own)
GRID_SIZE = 512
BODY_HU = -400.0
SCALE = 0.968


def _tools():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import import_ct_bone
    import prepare_photo_volume as ppv
    return import_ct_bone, ppv


@dataclass
class CtVolume:
    hu: np.ndarray              # int16 (slices, rows, columns): slices down the body, rows front to back, columns to his left
    first: int                  # the first slice's number
    corner: np.ndarray          # (slices, 2): each source image's corner in the scanner's x, y (mm)
    centroid: np.ndarray        # (slices, 2): the body outline's centroid in the scanner's x, y (mm), smoothed down the body

    @property
    def spacing(self):
        return (1.0, GRID_MM, GRID_MM)


def volume(ct_dir: Path, first: int, last: int, cache: Path | None = None, log=print) -> CtVolume:
    if cache is not None and cache.exists():
        with np.load(cache) as z:
            if int(z["first"]) == first and len(z["hu"]) == last - first + 1:
                return CtVolume(z["hu"], first, z["corner"], z["centroid"])
    import pydicom
    ct, _ = _tools()
    files = ct.index_ct(Path(ct_dir))
    n = last - first + 1
    hu = np.full((n, GRID_SIZE, GRID_SIZE), -1024, np.int16)
    corner = np.zeros((n, 2))
    centroid = np.full((n, 2), np.nan)
    centres = GRID_ORIGIN[0] + (np.arange(GRID_SIZE) + 0.5) * GRID_MM          # the grid's pixel centres, x and y alike
    for k in range(n):
        path = files.get(first + k)
        if path is None:
            continue
        ds = pydicom.dcmread(path)
        image = ds.pixel_array.astype(np.float32) * float(getattr(ds, "RescaleSlope", 1.0)) + float(getattr(ds, "RescaleIntercept", 0.0))
        px = float(ds.PixelSpacing[0])
        x0, y0 = float(ds.ImagePositionPatient[0]) - px / 2, float(ds.ImagePositionPatient[1]) - px / 2      # the first pixel's corner
        corner[k] = (x0, y0)
        rows = (centres - y0) / px - 0.5
        cols = (centres - x0) / px - 0.5
        if px < GRID_MM * 0.9:                                                  # finer than the grid: averaged down, not picked
            image = ndimage.uniform_filter(image, GRID_MM / px)
        rr, cc = np.meshgrid(rows, cols, indexing="ij")
        hu[k] = np.round(ndimage.map_coordinates(image, [rr, cc], order=1, mode="constant", cval=-1024.0)).astype(np.int16)
        body = ct.big_pieces(ndimage.binary_fill_holes(hu[k] > BODY_HU), GRID_MM)
        if body.any():
            r, c = np.nonzero(body)
            centroid[k] = (GRID_ORIGIN[0] + (c.mean() + 0.5) * GRID_MM, GRID_ORIGIN[1] + (r.mean() + 0.5) * GRID_MM)
        if k % 50 == 0:
            log(f"ct: slice {first + k} ({k + 1}/{n}), pixel {px:.3f} mm")
    good = ~np.isnan(centroid[:, 0])
    for axis in range(2):
        centroid[:, axis] = np.interp(np.arange(n), np.nonzero(good)[0], centroid[good, axis])
        centroid[:, axis] = ndimage.gaussian_filter1d(centroid[:, axis], 3.0)
    out = CtVolume(hu, first, corner, centroid)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, hu=hu, first=first, corner=corner, centroid=centroid)
    return out


class CtToBody:
    """The scanner's millimetres (slice number, y, x) -> the body's millimetres (array order z, y, x)."""

    def __init__(self, body: Body, vol: CtVolume, scale: float = SCALE):
        _, ppv = _tools()
        table = json.loads((body.export / body.meta.get("label_table", "labels.json")).read_text())
        shifts = table["ct_bone"]["corners_mm_by_slice"]                      # where each CT image's corner fell on its photograph: row, column (mm)
        numbers = np.array(sorted(int(k) for k in shifts))
        values = np.array([shifts[str(k)] for k in numbers], np.float64)
        photo = json.loads((body.export / "photo.json").read_text())
        self.crop_mm = (photo["crop_photo_px"]["rows"][0] * ppv.PIXEL_MM, photo["crop_photo_px"]["cols"][0] * ppv.PIXEL_MM)
        self.bottom, self.every = photo["slices"][1], int(round(photo["spacing_mm"][2] / ppv.SLICE_MM))
        slices = vol.first + np.arange(len(vol.hu))
        # Where the scanner's own origin falls on each photograph: the image's shift less its corner. The images
        # change their corner where the pixel size changes (slices 1237 and 1261) and the shift changes with it;
        # their difference does not, so that is what is interpolated and smoothed down the body (the shifts were
        # found to the millimetre, on every second slice).
        inside = (numbers >= vol.first) & (numbers <= vol.first + len(vol.hu) - 1)
        numbers, values = numbers[inside], values[inside]
        corner = vol.corner[numbers - vol.first]                              # x, y
        origin = np.stack([values[:, 0] - corner[:, 1], values[:, 1] - corner[:, 0]], axis=1)      # row (y), column (x)
        self.origin = np.stack([ndimage.gaussian_filter1d(np.interp(slices, numbers, origin[:, a]), 2.0) for a in range(2)], axis=1)
        self.vol, self.scale = vol, scale

    def __call__(self, slice_number: np.ndarray, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        k = np.clip(np.asarray(slice_number, np.float64) - self.vol.first, 0, len(self.vol.hu) - 1)
        index = np.arange(len(self.vol.hu))

        def at(table):
            return np.interp(k, index, table)

        # About the outline's centroid in its slice, all in the scanner's millimetres.
        cx, cy = at(self.vol.centroid[:, 0]), at(self.vol.centroid[:, 1])
        col_mm = at(self.origin[:, 1]) + cx + (np.asarray(x, np.float64) - cx) / self.scale
        row_mm = at(self.origin[:, 0]) + cy + (np.asarray(y, np.float64) - cy) / self.scale
        z = row_mm - self.crop_mm[0]
        xx = col_mm - self.crop_mm[1]
        yy = (self.bottom - np.asarray(slice_number, np.float64)) + self.every / 2.0
        return np.stack([z, yy, xx], axis=-1)

    def grid_points(self, zyx_index: np.ndarray) -> np.ndarray:
        """Voxel coordinates of the CtVolume's grid (slices, rows, columns; a voxel's centre at index + 0.5) -> body mm."""
        p = np.asarray(zyx_index, np.float64)
        return self(self.vol.first + p[:, 0], GRID_ORIGIN[1] + p[:, 1] * GRID_MM, GRID_ORIGIN[0] + p[:, 2] * GRID_MM)


def check(body: Body, vol: CtVolume, scales=(1.0, SCALE), slices=None, log=print) -> dict:
    """How well the CT's body outline, placed in the body, agrees with the body's own voxels (Dice), per scale."""
    lab = body.labels > 0
    spacing = np.array(body.spacing)
    out = {}
    slices = slices or range(vol.first + 20, vol.first + len(vol.hu) - 5, 30)
    for scale in scales:
        to_body = CtToBody(body, vol, scale)
        dice = []
        for n in slices:
            k = n - vol.first
            mask = ndimage.binary_fill_holes(vol.hu[k] > BODY_HU)
            r, c = np.nonzero(mask[::2, ::2])
            if len(r) < 100:
                continue
            pts = to_body.grid_points(np.stack([np.full(len(r), k + 0.5), r * 2 + 0.5, c * 2 + 0.5], axis=1))
            idx = np.floor(pts / spacing).astype(int)
            j = int(np.clip(np.median(idx[:, 1]), 0, lab.shape[1] - 1))
            ours = lab[:, j, :]
            theirs = np.zeros_like(ours)
            ok = (idx[:, 0] >= 0) & (idx[:, 0] < ours.shape[0]) & (idx[:, 2] >= 0) & (idx[:, 2] < ours.shape[1])
            theirs[idx[ok, 0], idx[ok, 2]] = True
            theirs = ndimage.binary_fill_holes(ndimage.binary_closing(theirs, iterations=2))
            dice.append(2.0 * (ours & theirs).sum() / max(1, ours.sum() + theirs.sum()))
        out[scale] = float(np.mean(dice)) if dice else 0.0
        log(f"ct in the body at scale {scale}: outlines agree {out[scale]:.3f} (Dice over {len(dice)} slices)")
    return out
