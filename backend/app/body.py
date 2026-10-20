"""
Scanner-table removal: keep the patient, turn the table, mattress, cushions and positioning aids into air.

In 3D the table shows up as bright stripes running the whole length of the scan, behind the patient.
It is separated from the body by low-density mattress foam, so the patient is the largest connected
region of tissue denser than TISSUE_HU. Holes inside it (lungs, airways, bowel gas) are filled slice by
slice so their real values are kept for the lung presets.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy import ndimage

from .dicom_loader import Volume

AIR_HU = -1024
TISSUE_HU = -400


def body_mask(hu: np.ndarray) -> np.ndarray:
    labels, n = ndimage.label(hu > TISSUE_HU)
    if n == 0:
        raise ValueError("No tissue found in the volume")
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    mask = labels == int(sizes.argmax())
    del labels
    for z in range(mask.shape[0]):           # axial slices: fill lungs, airways, bowel gas
        mask[z] = ndimage.binary_fill_holes(mask[z])
    return mask


def crop_to_body(vol: Volume, margin_mm: float = 6.0, probe_mm: float = 4.0) -> Volume:
    """Crop to the patient's bounding box (plus a margin), before resampling.

    Scans include a lot of air around the patient (the round field of view, space above the head, under
    the table). Cropping it first lets the same voxel budget buy a finer resampling grid. The body is
    found on a coarse copy (about probe_mm per voxel), so this costs well under a second.
    """
    if not vol.is_hu:
        return vol
    sx, sy, sz = vol.spacing
    step = [max(1, int(round(probe_mm / s))) for s in (sz, sy, sx)]
    coarse = vol.data[::step[0], ::step[1], ::step[2]]
    try:
        mask = body_mask(coarse)
    except ValueError:
        return vol
    nz, ny, nx = vol.data.shape
    slices, kept = [], 1.0
    for axis, (n, st, sp) in enumerate(zip((nz, ny, nx), step, (sz, sy, sx))):
        idx = np.nonzero(mask.any(axis=tuple(a for a in range(3) if a != axis)))[0]
        pad = int(np.ceil(margin_mm / sp))
        lo, hi = max(0, idx[0] * st - pad), min(n, (idx[-1] + 1) * st + pad)
        slices.append(slice(lo, hi))
        kept *= (hi - lo) / n
    data = vol.data[tuple(slices)]
    return replace(vol, data=data,
                   warnings=vol.warnings + [f"Cropped to the patient: {kept:.0%} of the scanned volume kept"])


def remove_table(vol: Volume) -> Volume:
    if not vol.is_hu:
        return replace(vol, warnings=vol.warnings + ["Table removal skipped: not CT"])
    mask = body_mask(vol.data)
    outside = ~mask & (vol.data > TISSUE_HU)
    removed = int(outside.sum())
    data = np.where(mask, vol.data, np.int16(AIR_HU)).astype(np.int16)
    total = int((vol.data > TISSUE_HU).sum())
    return replace(
        vol,
        data=data,
        value_range=(int(data.min()), int(data.max())),
        warnings=vol.warnings + [f"Table removed: {removed / max(total, 1):.1%} of the dense voxels were outside the patient"],
    )
