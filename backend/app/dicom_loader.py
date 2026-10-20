"""
Read a DICOM series folder into a 3D numpy volume.

Output convention (DICOM patient axes, LPS):
    data     int16, shape (nz, ny, nx)
             nz = slices, sorted along the slice normal (inferior -> superior for axial)
             ny = rows   (anterior -> posterior for a standard axial series)
             nx = cols   (patient right -> patient left)
    spacing  (sx, sy, sz) in mm

No patient-identifying header fields are copied into the Volume object.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError

log = logging.getLogger(__name__)

# Fixed HU window for CT so the Unity normalisation (min..max -> 0..1) is predictable:
# normalised = (HU + 1024) / 4095
CT_HU_MIN, CT_HU_MAX = -1024, 3071


@dataclass
class Volume:
    data: np.ndarray                     # int16, (nz, ny, nx)
    spacing: tuple[float, float, float]  # (sx, sy, sz) mm
    origin: tuple[float, float, float]   # ImagePositionPatient of first slice (mm, LPS)
    direction: np.ndarray                # 3x3; columns = row_dir, col_dir, slice_normal (LPS)
    modality: str
    is_hu: bool
    series_uid: str
    value_range: tuple[int, int]
    warnings: list[str] = field(default_factory=list)

    @property
    def shape_xyz(self) -> tuple[int, int, int]:
        nz, ny, nx = self.data.shape
        return nx, ny, nz


class SeriesError(ValueError):
    pass


# --------------------------------------------------------------------------- scanning

def _scan_folder(folder: Path) -> dict[str, list[tuple[Path, pydicom.Dataset]]]:
    """Read headers only and group files by SeriesInstanceUID."""
    series: dict[str, list] = defaultdict(list)
    for p in sorted(folder.rglob("*")):
        if not p.is_file() or p.name.upper() == "DICOMDIR":
            continue
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True)
        except (InvalidDicomError, OSError, Exception):  # not a DICOM file
            continue
        if "Rows" not in ds or "SeriesInstanceUID" not in ds:
            continue
        image_type = [str(s).upper() for s in ds.get("ImageType", [])]
        if "LOCALIZER" in image_type:
            continue
        if int(ds.get("NumberOfFrames", 1) or 1) > 1:
            log.warning("Skipping multi-frame file %s (enhanced CT/MR not supported yet)", p.name)
            continue
        series[str(ds.SeriesInstanceUID)].append((p, ds))
    return series


def _pick_series(series: dict, series_uid: str | None) -> tuple[str, list]:
    if not series:
        raise SeriesError("No readable single-frame DICOM images found in folder")
    if series_uid:
        if series_uid not in series:
            raise SeriesError(f"Series {series_uid} not found; available: {list(series)}")
        return series_uid, series[series_uid]
    uid = max(series, key=lambda k: len(series[k]))
    if len(series) > 1:
        log.info("Folder holds %d series; using the largest (%d slices)", len(series), len(series[uid]))
    return uid, series[uid]


# --------------------------------------------------------------------------- geometry

def _sort_slices(items: list, warnings: list[str]):
    """Sort by position projected on the slice normal (robust); fall back to InstanceNumber."""
    ds0 = items[0][1]
    has_geom = all("ImagePositionPatient" in ds and "ImageOrientationPatient" in ds for _, ds in items)

    if has_geom:
        iop = np.asarray(ds0.ImageOrientationPatient, dtype=float)
        row_dir, col_dir = iop[:3], iop[3:]
        normal = np.cross(row_dir, col_dir)

        def proj(ds):
            return float(np.dot(np.asarray(ds.ImagePositionPatient, dtype=float), normal))

        items.sort(key=lambda t: proj(t[1]))
        positions = np.array([proj(ds) for _, ds in items])

        # Drop exact duplicate positions (e.g. two acquisitions stored in one series)
        keep = np.concatenate([[True], np.abs(np.diff(positions)) > 1e-3])
        if not keep.all():
            warnings.append(f"Dropped {int((~keep).sum())} slices with duplicate positions")
            items = [it for it, k in zip(items, keep) if k]
            positions = positions[keep]
    else:
        warnings.append("Missing ImagePositionPatient/ImageOrientationPatient; sorted by InstanceNumber, assumed axial")
        items.sort(key=lambda t: int(t[1].get("InstanceNumber", 0)))
        row_dir, col_dir, normal = np.array([1., 0, 0]), np.array([0., 1, 0]), np.array([0., 0, 1])
        positions = None

    return items, positions, row_dir, col_dir, normal


def _slice_spacing(ds0, positions, warnings: list[str]) -> float:
    if positions is not None and len(positions) > 1:
        diffs = np.abs(np.diff(positions))
        sz = float(np.median(diffs))
        if np.any(np.abs(diffs - sz) > 0.05 * sz):
            warnings.append("Non-uniform slice spacing detected (gaps or variable thickness); using the median")
        return sz
    for tag in ("SpacingBetweenSlices", "SliceThickness"):
        if tag in ds0 and ds0.get(tag):
            return float(ds0.get(tag))
    warnings.append("No slice spacing information; assuming 1.0 mm")
    return 1.0


# --------------------------------------------------------------------------- pixels

def _read_pixels(items: list, is_hu: bool) -> np.ndarray:
    rows, cols = int(items[0][1].Rows), int(items[0][1].Columns)
    out = np.empty((len(items), rows, cols), dtype=np.int16)
    for i, (p, _) in enumerate(items):
        ds = pydicom.dcmread(p)
        arr = ds.pixel_array
        if arr.shape != (rows, cols):
            raise SeriesError(f"{p.name}: slice shape {arr.shape} != {(rows, cols)}")
        slope = float(ds.get("RescaleSlope", 1.0) or 1.0)
        intercept = float(ds.get("RescaleIntercept", 0.0) or 0.0)
        vals = arr.astype(np.float32) * slope + intercept
        lo, hi = (CT_HU_MIN, CT_HU_MAX) if is_hu else (-32768, 32767)
        out[i] = np.clip(np.rint(vals), lo, hi).astype(np.int16)
    return out


# --------------------------------------------------------------------------- public API

def load_series(folder: str | Path, series_uid: str | None = None) -> Volume:
    folder = Path(folder)
    if not folder.is_dir():
        raise SeriesError(f"Not a directory: {folder}")

    warnings: list[str] = []
    uid, items = _pick_series(_scan_folder(folder), series_uid)
    if len(items) < 2:
        raise SeriesError("Series has fewer than 2 slices")

    items, positions, row_dir, col_dir, normal = _sort_slices(items, warnings)
    ds0 = items[0][1]

    modality = str(ds0.get("Modality", "OT"))
    is_hu = modality == "CT" and "RescaleIntercept" in ds0
    if modality == "CT" and not is_hu:
        warnings.append("CT without RescaleIntercept: values are raw, not Hounsfield units")
    if modality not in ("CT",):
        warnings.append(f"Modality {modality}: intensities are not HU; use percentile-based windowing")

    ps = ds0.get("PixelSpacing", None)
    if ps is None:
        warnings.append("No PixelSpacing; assuming 1.0 mm")
        sy = sx = 1.0
    else:
        sy, sx = float(ps[0]), float(ps[1])     # DICOM order: [row spacing, column spacing]
    sz = _slice_spacing(ds0, positions, warnings)

    direction = np.column_stack([row_dir, col_dir, normal])
    if not np.allclose(np.abs(direction), np.eye(3), atol=0.05):
        warnings.append("Non-axial or oblique orientation; the Unity axis mapping assumes a standard axial series")
    elif not np.allclose(direction, np.eye(3), atol=0.05):
        warnings.append("Axial series with flipped axes; check left/right and anterior/posterior in Unity")

    data = _read_pixels(items, is_hu)
    origin = tuple(float(v) for v in ds0.get("ImagePositionPatient", [0, 0, 0]))

    vol = Volume(
        data=data,
        spacing=(sx, sy, sz),
        origin=origin,  # type: ignore[arg-type]
        direction=direction,
        modality=modality,
        is_hu=is_hu,
        series_uid=uid,
        value_range=(int(data.min()), int(data.max())),
        warnings=warnings,
    )
    log.info("Loaded series %s: %s voxels (x,y,z), spacing %s mm, HU=%s", uid[-8:], vol.shape_xyz, vol.spacing, is_hu)
    return vol
