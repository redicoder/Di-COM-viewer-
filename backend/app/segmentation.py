"""
Label-volume helpers shared by tools/segment_organs.py (.venv-seg) and tools/build_body.py (.venv).
Only numpy and scipy, so both environments can import it.

Grids: a box in millimetres in a source volume's frame, (z, y, x) = (superior, posterior, patient left), with the
source volume's outer corner at 0. Voxel i of a grid with spacing s covers [corner + i*s, corner + (i+1)*s], centre
at corner + (i + 0.5)*s: the same convention as the viewer's VolumeSpace, so grids of any spacing line up.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class Grid:
    corner_mm: tuple[float, float, float]     # (z, y, x)
    spacing_mm: float                         # isotropic
    shape: tuple[int, int, int]               # (nz, ny, nx)

    @property
    def size_mm(self) -> np.ndarray:
        return np.array(self.shape) * self.spacing_mm

    @staticmethod
    def covering(lo_mm, hi_mm, spacing_mm: float) -> "Grid":
        """The grid of `spacing_mm` voxels that covers the box lo..hi, centred on it."""
        lo, hi = np.asarray(lo_mm, float), np.asarray(hi_mm, float)
        shape = np.maximum(np.ceil((hi - lo) / spacing_mm - 1e-6), 1).astype(int)
        corner = (lo + hi) / 2 - shape * spacing_mm / 2
        return Grid(tuple(float(c) for c in corner), float(spacing_mm), tuple(int(n) for n in shape))

    def to_json(self) -> dict:
        return {"corner_mm_zyx": list(self.corner_mm), "spacing_mm": self.spacing_mm, "shape_zyx": list(self.shape)}

    @staticmethod
    def from_json(d: dict) -> "Grid":
        return Grid(tuple(d["corner_mm_zyx"]), float(d["spacing_mm"]), tuple(d["shape_zyx"]))


def sample(data: np.ndarray, data_grid_corner, data_spacing_zyx, grid: Grid, order: int,
           cval: float = 0.0, output=None) -> np.ndarray:
    """Values of `data` (a volume whose outer corner is at data_grid_corner, voxel size data_spacing_zyx per axis)
    at the centres of `grid`'s voxels. order 1 = trilinear (CT), 0 = nearest (labels).
    Outside the data: nearest edge value for order 1 (callers keep boxes inside the scan), cval for order 0."""
    src_sp = np.asarray(data_spacing_zyx, float)
    scale = grid.spacing_mm / src_sp
    offset = (np.asarray(grid.corner_mm) - np.asarray(data_grid_corner, float) + 0.5 * grid.spacing_mm) / src_sp - 0.5
    return ndimage.affine_transform(data, np.diag(scale), offset=offset, output_shape=grid.shape,
                                    order=order, mode="nearest" if order else "constant", cval=cval,
                                    output=output if output is not None else data.dtype)


def drop_fragments(labels: np.ndarray, min_fraction: float = 0.005, min_voxels: int = 30) -> tuple[np.ndarray, int]:
    """Remove stray pieces of each label: connected pieces smaller than min_fraction of the label's volume or
    smaller than min_voxels (the largest piece always stays). TotalSegmentator leaves a few dozen voxels of, say,
    "hip bone" at the knee; real second pieces (a rib crossing the scan's edge, left and right pulmonary veins,
    the colon) are far bigger. Returns the cleaned labels and the number of voxels removed."""
    out = labels.copy()
    removed = 0
    for k, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None:
            continue
        own = labels[box] == k
        pieces, n = ndimage.label(own, structure=np.ones((3, 3, 3), bool))
        if n < 2:
            continue
        sizes = np.bincount(pieces.ravel())
        sizes[0] = 0
        small = sizes < max(min_fraction * sizes.sum(), min_voxels)
        small[0] = small[int(sizes.argmax())] = False
        drop = small[pieces]
        out[box][drop] = 0
        removed += int(drop.sum())
    return out, removed


def smooth_labels(labels: np.ndarray, sigma: float = 1.0, keep: float = 0.25) -> np.ndarray:
    """Blur each label's mask and give every voxel to the label with the strongest blurred value.

    A voxel joins a label above 0.5 (fills the notches of a voxel staircase) and keeps its original label above
    `keep` (so thin tubes such as carotids, airways and adrenals survive; only stray corners drop).
    Works label by label inside its bounding box, so memory stays at a few hundred MB.
    """
    best = np.zeros(labels.shape, dtype=np.float32)
    out = np.zeros_like(labels)
    pad = int(np.ceil(3 * sigma)) + 1
    for k, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None:
            continue
        box = tuple(slice(max(0, s.start - pad), min(n, s.stop + pad)) for s, n in zip(box, labels.shape))
        own = labels[box] == k
        score = ndimage.gaussian_filter(own.astype(np.float32), sigma)
        win = ((score > 0.5) | (own & (score > keep))) & (score > best[box])
        best[box][win] = score[win]
        out[box][win] = k
    return out
