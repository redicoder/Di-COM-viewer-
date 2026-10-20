"""
NRRD (.nrrd / .nhdr) loader, for volumes exported from 3D Slicer and research datasets.

Produces the same Volume as dicom_loader.load_series: int16 (nz, ny, nx) in DICOM patient axes
(x = patient left, y = posterior, z = superior), so resample / lungs_only / pack_for_unity apply unchanged.

The data is streamed: compressed chunks are decoded and narrowed to int16 one at a time, so a 2 GB int32
whole-body CT needs ~1 GB of RAM instead of several. Axis permutations and flips (RAS or LPS, any axis
order) are undone so the result is always standard axial; oblique volumes are loaded with a warning.
"""
from __future__ import annotations

import bz2
import logging
import zlib
from pathlib import Path

import numpy as np

from .dicom_loader import CT_HU_MAX, CT_HU_MIN, SeriesError, Volume

log = logging.getLogger(__name__)

NRRD_SUFFIXES = (".nrrd", ".nhdr")

_TYPES = {
    "int8": "i1", "signed char": "i1", "int8_t": "i1",
    "uchar": "u1", "unsigned char": "u1", "uint8": "u1", "uint8_t": "u1",
    "short": "i2", "short int": "i2", "signed short": "i2", "signed short int": "i2", "int16": "i2", "int16_t": "i2",
    "ushort": "u2", "unsigned short": "u2", "unsigned short int": "u2", "uint16": "u2", "uint16_t": "u2",
    "int": "i4", "signed int": "i4", "int32": "i4", "int32_t": "i4",
    "uint": "u4", "unsigned int": "u4", "uint32": "u4", "uint32_t": "u4",
    "float": "f4", "double": "f8",
}

# Sign flips that take each named space to LPS (DICOM patient coordinates).
_SPACES = {
    "left-posterior-superior": (1, 1, 1), "lps": (1, 1, 1),
    "right-anterior-superior": (-1, -1, 1), "ras": (-1, -1, 1),
    "left-anterior-superior": (1, -1, 1), "las": (1, -1, 1),
}

_CHUNK_BYTES = 32 * 1024 * 1024


def is_nrrd(path: str | Path) -> bool:
    return Path(path).suffix.lower() in NRRD_SUFFIXES


def read_header(path: Path) -> tuple[dict, Path, int]:
    """Returns (fields, data file, byte offset of the data in it)."""
    with open(path, "rb") as f:
        magic = f.readline()
        if not magic.startswith(b"NRRD"):
            raise SeriesError(f"{path.name} is not an NRRD file")
        fields: dict[str, str] = {}
        while True:
            line = f.readline()
            if not line or line in (b"\n", b"\r\n"):
                break
            text = line.decode("latin-1").rstrip("\r\n")
            if text.startswith("#") or ":=" in text:
                continue
            key, _, value = text.partition(":")
            fields[key.strip().lower()] = value.strip()
        offset = f.tell()

    data_file = path
    if "data file" in fields or "datafile" in fields:
        name = fields.get("data file", fields.get("datafile"))
        if name.upper().startswith("LIST") or "%" in name:
            raise SeriesError("NRRD with multiple data files is not supported")
        data_file = (path.parent / name).resolve()
        offset = 0
    if int(fields.get("line skip", fields.get("lineskip", "0"))) != 0:
        raise SeriesError("NRRD 'line skip' is not supported")
    offset += max(0, int(fields.get("byte skip", fields.get("byteskip", "0"))))
    return fields, data_file, offset


def _vectors(text: str) -> list[np.ndarray | None]:
    out = []
    for part in text.replace(") (", ")|(").split("|") if "(" in text else text.split():
        part = part.strip()
        out.append(None if part == "none" else np.array([float(v) for v in part.strip("()").split(",")]))
    return out


def _stream_int16(data_file: Path, offset: int, encoding: str, dtype: np.dtype, count: int) -> tuple[np.ndarray, int, int]:
    """Decode `count` voxels into an int16 array (clipped), returning (array, raw min, raw max)."""
    if encoding in ("gzip", "gz"):
        dec = zlib.decompressobj(zlib.MAX_WBITS | 32)   # gzip or zlib header, auto-detected
    elif encoding in ("bzip2", "bz2"):
        dec = bz2.BZ2Decompressor()
    elif encoding == "raw":
        dec = None
    else:
        raise SeriesError(f"NRRD encoding '{encoding}' is not supported (raw, gzip and bzip2 are)")

    out = np.empty(count, dtype=np.int16)
    lo, hi = np.inf, -np.inf
    pending, pos, item = b"", 0, dtype.itemsize
    with open(data_file, "rb") as f:
        f.seek(offset)
        while pos < count:
            chunk = f.read(_CHUNK_BYTES)
            if not chunk:
                break
            pending += dec.decompress(chunk) if dec else chunk
            n = min(len(pending) // item, count - pos)
            if n == 0:
                continue
            values = np.frombuffer(pending, dtype=dtype, count=n)
            lo, hi = min(lo, values.min()), max(hi, values.max())
            if values.dtype.kind == "f":
                values = np.rint(values)
            out[pos:pos + n] = np.clip(values, -32768, 32767)
            pos += n
            pending = pending[n * item:]
    if pos < count:
        raise SeriesError(f"NRRD data ended early: {pos} of {count} voxels")
    return out, int(lo), int(hi)


def load_nrrd(path: str | Path) -> Volume:
    path = Path(path)
    fields, data_file, offset = read_header(path)

    dim = int(fields.get("dimension", "0"))
    sizes = [int(v) for v in fields.get("sizes", "").split()]
    if dim != 3 or len(sizes) != 3:
        raise SeriesError(f"Only 3D scalar NRRD volumes are supported (dimension {dim}, sizes {sizes})")
    type_name = fields.get("type", "").lower()
    if type_name not in _TYPES:
        raise SeriesError(f"NRRD type '{type_name}' is not supported")
    dtype = np.dtype(_TYPES[type_name])
    if dtype.itemsize > 1:
        dtype = dtype.newbyteorder(">" if fields.get("endian", "little").lower() == "big" else "<")

    warnings: list[str] = []
    space = fields.get("space", "").lower()
    flip_to_lps = np.array(_SPACES.get(space, (1, 1, 1)), dtype=float)
    if space not in _SPACES:
        warnings.append(f"NRRD space '{space or 'unspecified'}' assumed to be left-posterior-superior; check orientation")

    if "space directions" in fields:
        dirs = _vectors(fields["space directions"])
        if len(dirs) != 3 or any(d is None for d in dirs):
            raise SeriesError("NRRD 'space directions' must give one vector per axis")
        dirs = [d * flip_to_lps for d in dirs]
    else:
        spacings = [float(v) for v in fields.get("spacings", "1 1 1").split()]
        dirs = [np.eye(3)[i] * spacings[i] for i in range(3)]
        warnings.append("NRRD has no 'space directions'; assuming axis-aligned LPS")

    # For each file axis (fastest first): the patient axis it runs along, its sign and spacing.
    patient_axis, sign, spacing = [], [], []
    for d in dirs:
        a = int(np.argmax(np.abs(d)))
        patient_axis.append(a)
        sign.append(1 if d[a] > 0 else -1)
        spacing.append(float(np.linalg.norm(d)))
    if sorted(patient_axis) != [0, 1, 2]:
        raise SeriesError("NRRD axes do not map onto distinct patient axes")
    unit = np.array([d / np.linalg.norm(d) for d in dirs])
    if not np.allclose(np.abs(unit), np.abs(unit).round(), atol=0.05):
        warnings.append("Oblique NRRD volume; loaded as the nearest axial orientation")

    count = sizes[0] * sizes[1] * sizes[2]
    log.info("Reading %s: %s %s, %d voxels", path.name, type_name, fields.get("encoding"), count)
    flat, raw_lo, raw_hi = _stream_int16(data_file, offset, fields.get("encoding", "raw").lower(), dtype, count)

    # numpy axis n holds file axis 2 - n. Reorder to (z, y, x) = patient axes (2, 1, 0), then flip negatives.
    arr = flat.reshape(sizes[::-1])
    order = [2 - patient_axis.index(p) for p in (2, 1, 0)]
    arr = np.transpose(arr, order)
    for m, p in enumerate((2, 1, 0)):
        if sign[patient_axis.index(p)] < 0:
            arr = np.flip(arr, axis=m)
    arr = np.ascontiguousarray(arr)
    sx, sy, sz = (spacing[patient_axis.index(p)] for p in (0, 1, 2))

    # NRRD carries no modality. CT spans lung/air (strongly negative) to bone; MR and PET are never negative.
    is_hu = raw_lo <= -500 and raw_hi >= 200
    if is_hu:
        np.clip(arr, CT_HU_MIN, CT_HU_MAX, out=arr)
    else:
        warnings.append("Values do not look like CT Hounsfield units; colours will use the generic ramp")

    vol = Volume(
        data=arr,
        spacing=(sx, sy, sz),
        origin=tuple(float(v) for v in _vectors(fields["space origin"])[0]) if "space origin" in fields else (0.0, 0.0, 0.0),
        direction=np.eye(3),
        modality="CT" if is_hu else "OT",
        is_hu=is_hu,
        series_uid=path.stem,
        value_range=(int(arr.min()), int(arr.max())),
        warnings=warnings,
    )
    log.info("Loaded NRRD %s: %s voxels (x,y,z), spacing (%.3f, %.3f, %.3f) mm, HU=%s",
             path.name, vol.shape_xyz, sx, sy, sz, is_hu)
    return vol


def describe_nrrd(path: str | Path) -> dict:
    """Header-only summary in the same shape as tools/inspect_series.describe()."""
    path = Path(path)
    fields, _, _ = read_header(path)
    sizes = [int(v) for v in fields.get("sizes", "").split()]
    if len(sizes) != 3:
        raise SeriesError(f"Only 3D NRRD volumes are supported (sizes {sizes})")
    if "space directions" in fields:
        spacing = [float(np.linalg.norm(d)) for d in _vectors(fields["space directions"])]
    else:
        spacing = [float(v) for v in fields.get("spacings", "1 1 1").split()]
    # File axes are usually x, y, z already; the summary only needs the extents.
    fov = tuple(n * s for n, s in zip(sizes, spacing))
    return {"uid": path.stem, "n": sizes[2], "cols": sizes[0], "rows": sizes[1], "fov": fov,
            "modality": "CT", "native_min_spacing": min(spacing),
            "description": path.name, "body_part": "", "nrrd": str(path)}
