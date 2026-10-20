"""
Lungs-only view: keep the lungs and airways (with the vessels and bronchial walls inside them) and
replace everything else with air, so a transfer function can show the bronchial and vascular tree
without the chest wall, heart and ribs in front of it.

Pulmonary vessels (~+40 HU) have the same density as muscle, so this cannot be done with a transfer
function alone; it needs a mask. The mask is a plain threshold + connected-components heuristic,
good enough for a visualisation, not a clinical segmentation.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy import ndimage

from .body import body_mask
from .dicom_loader import Volume

AIR_HU = -1024
LUNG_THRESHOLD_HU = -400      # lung parenchyma and airways are below this, soft tissue above
MIN_SECOND_LUNG_FRACTION = 0.1


def lung_mask(hu: np.ndarray, spacing: tuple[float, float, float], margin_mm: float = 0.0) -> np.ndarray:
    """Boolean mask (nz, ny, nx) of lungs + airways, with enclosed vessels filled.

    margin_mm > 0 grows the mask, but that wraps the lungs in a shell of chest wall that renders as an
    opaque skin with rib imprints, hiding the vessel tree; the default keeps the mask tight.
    """
    # Only air inside the patient: the body mask has the lungs filled in slice by slice. (Air connected to
    # the image border is not a usable test: with the head in the scan the airways reach the room air
    # through the nose and mouth.)
    labels, n = ndimage.label((hu < LUNG_THRESHOLD_HU) & body_mask(hu))
    if n == 0:
        raise ValueError("No air-density regions inside the body; is this a chest CT?")
    sizes = np.bincount(labels.ravel(), minlength=n + 1)
    sizes[0] = 0

    # Lungs: the largest internal air region, plus the second one when the two lungs are not connected
    # through the airways. Bowel and stomach gas are much smaller and are dropped.
    order = np.argsort(sizes)[::-1]
    if sizes[order[0]] == 0:
        raise ValueError("No internal air region found; is this a chest CT?")
    keep = [order[0]]
    if len(order) > 1 and sizes[order[1]] >= MIN_SECOND_LUNG_FRACTION * sizes[order[0]]:
        keep.append(order[1])
    mask = np.isin(labels, keep)

    # Vessels and bronchial walls are holes in the air mask; fill them slice by slice.
    for z in range(mask.shape[0]):
        mask[z] = ndimage.binary_fill_holes(mask[z])

    if margin_mm <= 0:
        return mask
    sx, sy, sz = spacing
    radius = [max(1, int(round(margin_mm / s))) for s in (sz, sy, sx)]
    struct = np.zeros([2 * r + 1 for r in radius], dtype=bool)
    zz, yy, xx = np.ogrid[-radius[0]:radius[0] + 1, -radius[1]:radius[1] + 1, -radius[2]:radius[2] + 1]
    struct[(zz / radius[0]) ** 2 + (yy / radius[1]) ** 2 + (xx / radius[2]) ** 2 <= 1.0] = True
    return ndimage.binary_dilation(mask, structure=struct)


def lungs_only(vol: Volume) -> Volume:
    if not vol.is_hu:
        raise ValueError("Lungs-only export needs CT data in Hounsfield units")
    mask = lung_mask(vol.data, vol.spacing)
    data = np.where(mask, vol.data, np.int16(AIR_HU)).astype(np.int16)
    fraction = mask.mean()
    return replace(
        vol,
        data=data,
        value_range=(int(data.min()), int(data.max())),
        warnings=vol.warnings + [f"Lungs-only: kept {fraction:.1%} of the volume (lungs + airways), rest set to air"],
    )
