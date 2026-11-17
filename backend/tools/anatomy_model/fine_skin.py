"""The body's outline at twice the export's detail, straight from the photographs, for the skin's surface.

The whole-body export averages 4 x 4 photo pixels and uses every second photograph (1.32 x 2 x 1.32 mm): enough
for what lies inside, coarse for the skin a student looks at (the face, the fingers, the toes). The photographs
hold 0.33 mm pixels a millimetre apart. This module reads every photograph again at 2 x 2 pixels (0.66 mm) and
keeps only what the skin needs: how much of each voxel is body. The export's own cleaned mask guides it (which
pieces are him and not the label card or the gelatin), so each photograph only refines the outline within a few
millimetres of the coarse one, and a blank photograph at a joint between the specimen's blocks falls back to the
coarse outline.

The result is a COVERAGE, not a yes/no mask. The export's own tissue test (red well above blue) says which pixels
are body; the ring of pixels just outside them is part skin and part blue gelatin, and how red against blue each
is says how much. A yes/no outline moves in whole pixels from one photograph to the next and the surface built
from it is terraced like a map's contour lines; the ring places the outline within a pixel. Only that one ring is
measured: the frost round the frozen body is pale blue too, and counted further out it grows into warts.

    fine = extract(body, photos_dir)      # about twelve minutes; cached as <export>/model/skin_fine.npy + .json
    fine = load(body)                     # FineOutline or None (memory-mapped: slabs are read as they are used)

FineOutline.cover is uint8 0..255 (rows front to back, slices bottom to top, columns to the patient's left): the
Body's array order z, y, x, with spacing (0.66, 1.0, 0.66) mm. Its voxel (z, y, x) has its centre at
origin_mm + (index + 0.5) * spacing in the body's millimetres (array order).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from .common import Body

FACTOR = 2                      # photo pixels per fine voxel, in the plane: the outline is found at the photographs'
                                # own 0.33 mm pixels and kept as each 0.66 mm voxel's share of body
BAND = 4                        # fine voxels (2.6 mm) the fine outline may differ from the coarse one, either way
GEL, TISSUE = -130.0, 60.0      # red minus blue of the gelatin and of the tissue at the surface: a ring pixel's
                                # share of tissue is where its own value lies between the two
CACHE = "skin_fine.npy"


@dataclass
class FineOutline:
    cover: np.ndarray           # uint8 (z, y, x): how much of the voxel is body, 0..255
    spacing: tuple              # mm, array order z, y, x
    origin_mm: tuple            # array order z, y, x
    fallback: np.ndarray        # bool per y: the photograph was unusable there, the coarse outline stands in

    def slab(self, y0: int, y1: int) -> np.ndarray:
        """Slices y0..y1-1 as float32 0..1."""
        return np.asarray(self.cover[:, y0:y1, :], np.float32) * (1.0 / 255.0)


def _photo_tools():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import prepare_photo_volume as ppv
    return ppv


def ring_coverage(rgb: np.ndarray) -> np.ndarray:
    """How much of a pixel beside the tissue is tissue, 0..1, from how red against blue it is (the gelatin is blue)."""
    d = rgb[..., 0].astype(np.float32) - rgb[..., 2].astype(np.float32)
    return np.clip((d - GEL) / (TISSUE - GEL), 0.0, 1.0)


def whole_body(body: Body) -> np.ndarray:
    """Where he is, on the export's grid (bool, z, y, x): every labelled voxel, AND the space round the eyes that the
    labels were cleared of for the layers under the skin (Body.eye_pits: the globes and what lies before them are
    left to the eyeballs and the lids). That space is open to the front; taken for a hole in him, the skin's
    outline ran into the orbits and the face had two pits for eyes (seen when the outline was read again after the
    pits had come into the labels: it had first been read before there were any)."""
    guide = body.labels > 0
    for (z0, y0, x0), pit in getattr(body, "eye_pits", None) or []:
        guide[z0:z0 + pit.shape[0], y0:y0 + pit.shape[1], x0:x0 + pit.shape[2]] |= pit
    return guide


def extract(body: Body, photos_dir: Path, log=print) -> FineOutline:
    ppv = _photo_tools()
    photo = json.loads((body.export / "photo.json").read_text())
    coarse_factor = int(round(photo["spacing_mm"][0] / ppv.PIXEL_MM))
    every = int(round(photo["spacing_mm"][2] / ppv.SLICE_MM))
    scale = coarse_factor // FACTOR
    rows = slice(*photo["crop_photo_px"]["rows"])
    cols = slice(*photo["crop_photo_px"]["cols"])
    top, bottom = photo["slices"]                               # slice numbers: the head's end, the feet's end
    files = ppv.index_slices(Path(photos_dir))
    # The coarse guide: the body's own voxels, holes filled slice by slice (the outer envelope).
    guide = whole_body(body)                                   # (z, y, x)
    nz, ny, nx = guide.shape
    fz, fx = (rows.stop - rows.start) // FACTOR, (cols.stop - cols.start) // FACTOR
    n_slices = bottom - top + 1
    folder = body.export / "model"
    folder.mkdir(parents=True, exist_ok=True)
    cover = np.lib.format.open_memmap(folder / CACHE, mode="w+", dtype=np.uint8, shape=(fz, n_slices, fx))
    fallback = np.zeros(n_slices, bool)
    structure = ndimage.generate_binary_structure(2, 1)
    for k in range(n_slices):
        number = bottom - k
        kc = min(ny - 1, k // every)
        g = ndimage.binary_fill_holes(guide[:, kc, :])
        if every > 1 and k % every and kc + 1 < ny:            # a photograph the export skipped: between two coarse slices
            g |= ndimage.binary_fill_holes(guide[:, kc + 1, :])
        if not g.any():
            continue
        # The guide at the photographs' own pixels.
        g = np.repeat(np.repeat(g, coarse_factor, axis=0), coarse_factor, axis=1)
        g = np.pad(g, ((0, max(0, fz * FACTOR - g.shape[0])), (0, max(0, fx * FACTOR - g.shape[1]))), mode="edge")[:fz * FACTOR, :fx * FACTOR]
        path = files.get(number)
        a = t = None
        if path is not None:
            rgb = ppv.read_photo(path)[rows, cols][:fz * FACTOR, :fx * FACTOR]
            t, a = ppv.tissue_mask(rgb), ring_coverage(rgb)
        if t is None or (t & g).sum() < 0.6 * g.sum():
            cover[:, k, :], fallback[k] = g[::FACTOR, ::FACTOR].astype(np.uint8) * 255, True      # a blank or missing photograph
            continue
        allowed = ndimage.binary_dilation(g, structure, iterations=BAND * FACTOR)
        core = ndimage.binary_erosion(g, structure, iterations=BAND * FACTOR)
        m = ndimage.binary_fill_holes((t & allowed) | core)
        m = ndimage.binary_opening(m, structure, iterations=2)  # frost and threads of gelatin colour, a pixel or two wide
        parts, n = ndimage.label(m)
        if n > 1:
            seeds = core if core.any() else g
            keep = np.unique(parts[seeds & m])
            m = np.isin(parts, keep[keep > 0])
        # Solid where the tissue is, the measured share in the one ring of pixels round it, nothing beyond; then
        # each fine voxel's share is the mean of its photo pixels.
        a[m] = 1.0
        a[~ndimage.binary_dilation(m, structure)] = 0.0
        share = a.reshape(fz, FACTOR, fx, FACTOR).mean(axis=(1, 3))
        cover[:, k, :] = np.round(share * 255.0).astype(np.uint8)
        if k % 100 == 0:
            log(f"fine skin outline: photograph {number} ({k + 1}/{n_slices})")
    cover.flush()
    spacing = (ppv.PIXEL_MM * FACTOR, ppv.SLICE_MM, ppv.PIXEL_MM * FACTOR)
    # The export shows photograph (bottom - every * j) at y = (j + 0.5) * every mm: photograph (bottom - k) sits at
    # y = k + every / 2 mm, so the fine grid starts (every - 1) / 2 mm up.
    origin = (0.0, (every - ppv.SLICE_MM) / 2.0, 0.0)
    (folder / (CACHE + ".json")).write_text(json.dumps({"spacing_mm": spacing, "origin_mm": origin, "fallback": np.nonzero(fallback)[0].tolist(),
                                                         "slices": [top, bottom], "factor": FACTOR}))
    log(f"fine skin outline: {cover.shape} voxels at {spacing} mm, {int(fallback.sum())} photographs replaced by the coarse outline")
    del cover
    return load(body)


def inside_export(body: Body, fine: FineOutline, skin_mm: float = 1.4) -> np.ndarray:
    """The export's voxels that lie under the fine skin (bool, the Body's grid): at least half inside the fine
    outline and not in its outermost `skin_mm`. The export's own outline is a voxel or so wider than the fine
    one, so fat and bone meshed from its labels alone would show through the skin in places."""
    nz, ny, nx = body.dims
    step_y = int(round(body.spacing[1] / fine.spacing[1]))
    step = int(round(body.spacing[0] / fine.spacing[0]))
    fz, fy, fx = fine.cover.shape
    out = np.zeros(body.dims, bool)
    rounds = max(1, int(round(skin_mm / body.spacing[0])))
    structure = ndimage.generate_binary_structure(2, 1)
    for j in range(min(ny, fy // step_y)):
        block = np.asarray(fine.cover[:nz * step, j * step_y:(j + 1) * step_y, :nx * step], np.float32)
        share = block.reshape(nz, step, step_y, nx, step).mean(axis=(1, 2, 4)) / 255.0
        out[:, j, :] = ndimage.binary_erosion(share > 0.5, structure, iterations=rounds)
    return out


def load(body: Body) -> FineOutline | None:
    path = body.export / "model" / CACHE
    meta = path.with_name(CACHE + ".json")
    if not path.exists() or not meta.exists():
        return None
    info = json.loads(meta.read_text())
    cover = np.load(path, mmap_mode="r")
    fallback = np.zeros(cover.shape[1], bool)
    fallback[info["fallback"]] = True
    return FineOutline(cover, tuple(info["spacing_mm"]), tuple(info["origin_mm"]), fallback)
