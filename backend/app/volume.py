"""
Post-processing: resampling and packing into the byte layout Unity expects.

Unity / UnityVolumeRendering layout
-----------------------------------
A Texture3D is filled x-fastest, then y, then z, and UnityVolumeRendering maps
texture (x, y, z) onto the cube's local (X right, Y up, Z forward).  Unity is
Y-up, so the patient's superior axis must become texture y, and the patient's
posterior axis (away from the viewer when the patient faces you) becomes texture z:

    texture x  <-  DICOM x  (patient right -> left,   viewer's left -> right)
    texture y  <-  DICOM z  (inferior -> superior,    down -> up)
    texture z  <-  DICOM y  (anterior -> posterior,   towards viewer -> away)

In numpy terms the (nz, ny, nx) HU array is transposed to (ny, nz, nx) and
written C-contiguous, little-endian int16.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy import ndimage

from .dicom_loader import Volume


def resample(vol: Volume, target_spacing_mm: float | None = None, max_dim: int = 512) -> Volume:
    """Resample to isotropic `target_spacing_mm` (trilinear) and/or cap the largest dimension."""
    sx, sy, sz = vol.spacing
    nz, ny, nx = vol.data.shape

    if target_spacing_mm:
        zoom = np.array([sz, sy, sx]) / target_spacing_mm        # per axis (z, y, x)
    else:
        zoom = np.ones(3)

    new_shape = np.rint(np.array([nz, ny, nx]) * zoom)
    if new_shape.max() > max_dim:
        zoom *= max_dim / new_shape.max()
        new_shape = np.rint(np.array([nz, ny, nx]) * zoom)

    if np.allclose(zoom, 1.0, atol=1e-3):
        return vol

    # Interpolate straight from int16: a float32 copy of the input would double peak RAM on big volumes.
    out = ndimage.zoom(vol.data, zoom, output=np.float32, order=1, mode="nearest")
    out = np.rint(out).astype(np.int16)
    oz, oy, ox = out.shape
    new_spacing = (sx * nx / ox, sy * ny / oy, sz * nz / oz)
    return replace(
        vol,
        data=out,
        spacing=new_spacing,
        value_range=(int(out.min()), int(out.max())),
        warnings=vol.warnings + [f"Resampled {(nx, ny, nz)} -> {(ox, oy, oz)}"],
    )


def pack_for_unity(vol: Volume) -> tuple[bytes, dict]:
    """Return (raw little-endian int16 bytes in Unity texture order, metadata dict)."""
    u = np.ascontiguousarray(np.transpose(vol.data, (1, 0, 2)))   # (ny, nz, nx)
    sx, sy, sz = vol.spacing
    dim_z, dim_y, dim_x = u.shape
    meta = {
        "dim_x": int(dim_x),
        "dim_y": int(dim_y),
        "dim_z": int(dim_z),
        "spacing_mm": [float(sx), float(sz), float(sy)],   # per texture axis (x, y, z)
        "size_mm": [float(sx * dim_x), float(sz * dim_y), float(sy * dim_z)],
        "format": "int16",
        "endianness": "little",
        "byte_length": int(u.nbytes),
        "value_min": vol.value_range[0],
        "value_max": vol.value_range[1],
        "is_hu": vol.is_hu,
        "modality": vol.modality,
        "axes": {"x": "patient left (+)", "y": "superior (+)", "z": "posterior (+)"},
        "warnings": list(vol.warnings),
    }
    return u.astype("<i2", copy=False).tobytes(), meta
