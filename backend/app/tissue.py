"""
Tissue classes from CT numbers for the dissection layers (no licensed AI model needed).

Inside the body (HU > -500, the patient's connected region, holes filled slice by slice), every voxel that
TotalSegmentator did not label gets one of:

    skin         the outer 3 mm shell of the body
    fat          -190 .. -30 HU
    muscle         30 .. 100 HU
    bone          > 200 HU (bones TotalSegmentator does not name: forearm, hand, lower leg, foot, ...)
    soft tissue  everything else denser than gas: fluid, glands, connective tissue, fat/muscle boundaries

Gas inside the body (sinuses, mouth, bowel gas outside the labelled bowel) stays 0 = empty.
Fat and muscle are judged on a lightly smoothed copy of the CT so scanner noise does not become speckle; bone
uses the CT itself (its edges are sharp and far above the noise).

The thresholds hold for fresh or living tissue. Frozen bodies (the Visible Human male's frozen CT) compress
fat and muscle to within ~25 HU of each other and need their own thresholds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import ndimage

from .label_table import BONE, FAT, MUSCLE, SKIN, SOFT_TISSUE

GAS_HU = -190.0


@dataclass(frozen=True)
class Thresholds:
    body: float = -500.0
    skin_mm: float = 3.0
    fat: tuple[float, float] = (-190.0, -30.0)
    muscle: tuple[float, float] = (30.0, 100.0)
    bone: float = 200.0
    smooth_mm: float = 1.0

    def to_json(self) -> dict:
        return asdict(self)


LIVING = Thresholds()


def skin_shell(body: np.ndarray, voxel_mm: float, depth_mm: float) -> np.ndarray:
    """Body voxels within depth_mm of the outside. The volume's own faces do not count as outside, so a region
    cut out of a body gets no skin on its cut faces."""
    r = depth_mm / voxel_mm
    n = max(1, int(np.floor(r)))
    g = np.mgrid[-n:n + 1, -n:n + 1, -n:n + 1]
    ball = (g ** 2).sum(axis=0) <= max(r, 1.0) ** 2
    return body & ~ndimage.binary_erosion(body, structure=ball, border_value=1)


def tissue_classes(hu: np.ndarray, voxel_mm: float, body: np.ndarray, labelled: np.ndarray | None = None,
                   th: Thresholds = LIVING) -> np.ndarray:
    """uint8 tissue class ids (app.label_table) for body voxels not in `labelled`; 0 elsewhere."""
    free = body if labelled is None else body & ~labelled
    out = np.zeros(hu.shape, dtype=np.uint8)

    smooth = ndimage.gaussian_filter(hu.astype(np.float32), th.smooth_mm / voxel_mm) if th.smooth_mm > 0 \
        else hu.astype(np.float32)
    out[free & (smooth > GAS_HU)] = SOFT_TISSUE
    out[free & (smooth >= th.fat[0]) & (smooth <= th.fat[1])] = FAT
    out[free & (smooth >= th.muscle[0]) & (smooth <= th.muscle[1])] = MUSCLE
    del smooth
    out[free & (hu > th.bone)] = BONE
    out[skin_shell(body, voxel_mm, th.skin_mm) & free] = SKIN
    return out
