"""
Inspect a DICOM folder before exporting it: what series are in there, their geometry,
whether the pixel data is readable, the HU range, and what the export will cost in memory.

    python tools/inspect_series.py data/kits_ct

Prints a recommended `python -m app.export` command at the end.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pydicom
from pydicom.uid import UID

# Unity holds the volume as float[] (4 B/voxel) plus an RHalf Texture3D (2 B/voxel),
# and the backend holds int16 (2 B/voxel). Stay well under GPU/CPU limits.
SOFT_LIMIT_VOXELS = 40_000_000     # ~320^3
HARD_LIMIT_DIM = 2048              # Unity Texture3D max


def scan(folder: Path):
    series = defaultdict(list)
    unreadable = 0
    for p in sorted(folder.rglob("*")):
        if not p.is_file() or p.name.upper() == "DICOMDIR":
            continue
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True)
        except Exception:
            unreadable += 1
            continue
        if "Rows" not in ds or "SeriesInstanceUID" not in ds:
            unreadable += 1
            continue
        series[str(ds.SeriesInstanceUID)].append((p, ds))
    return series, unreadable


def describe(uid: str, items: list) -> dict | None:
    p0, ds0 = items[0]
    n = len(items)
    modality = str(ds0.get("Modality", "?"))
    desc = str(ds0.get("SeriesDescription", "")).strip() or "(no description)"
    rows, cols = int(ds0.Rows), int(ds0.Columns)
    frames = int(ds0.get("NumberOfFrames", 1) or 1)
    ts: UID = ds0.file_meta.TransferSyntaxUID if hasattr(ds0, "file_meta") else None
    image_type = [str(s).upper() for s in ds0.get("ImageType", [])]

    print(f"\n  Series {uid[-12:]}  {modality}  {desc}")
    print(f"    files            : {n}")
    print(f"    in-plane         : {cols} x {rows}")
    if frames > 1:
        print(f"    frames per file  : {frames}  <-- MULTI-FRAME (Enhanced CT/MR), not supported yet")
    print(f"    transfer syntax  : {ts.name if ts else '?'}")

    blockers = []
    if frames > 1:
        blockers.append("multi-frame")
    if "LOCALIZER" in image_type:
        blockers.append("localizer (scout image)")
    if n < 2:
        blockers.append("fewer than 2 slices")

    # Can the pixels actually be decoded? Compressed syntaxes need pylibjpeg.
    hu_min = hu_max = None
    try:
        full = pydicom.dcmread(p0)
        arr = full.pixel_array
        slope = float(full.get("RescaleSlope", 1.0) or 1.0)
        intercept = float(full.get("RescaleIntercept", 0.0) or 0.0)
        vals = arr.astype(np.float32) * slope + intercept
        hu_min, hu_max = float(vals.min()), float(vals.max())
        print(f"    first slice range: {hu_min:.0f} .. {hu_max:.0f}"
              + ("  (HU)" if modality == "CT" and "RescaleIntercept" in full else "  (raw, NOT HU)"))
    except Exception as e:
        blockers.append(f"pixel decode failed: {type(e).__name__}: {e}")
        print(f"    PIXEL DECODE FAILED: {e}")
        if ts and ts.is_compressed:
            print("    -> compressed syntax; install: pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg")

    ps = ds0.get("PixelSpacing", None)
    sy, sx = (float(ps[0]), float(ps[1])) if ps else (1.0, 1.0)
    if ps is None:
        print("    PixelSpacing     : MISSING (will assume 1.0 mm)")

    # Slice spacing from real positions, not SliceThickness.
    sz = None
    if all("ImagePositionPatient" in d and "ImageOrientationPatient" in d for _, d in items) and n > 1:
        iop = np.asarray(ds0.ImageOrientationPatient, dtype=float)
        normal = np.cross(iop[:3], iop[3:])
        pos = np.sort([float(np.dot(np.asarray(d.ImagePositionPatient, dtype=float), normal)) for _, d in items])
        diffs = np.abs(np.diff(pos))
        diffs = diffs[diffs > 1e-3]
        if len(diffs):
            sz = float(np.median(diffs))
            spread = float(diffs.max() - diffs.min())
            print(f"    slice spacing    : {sz:.3f} mm"
                  + (f"   NON-UNIFORM (spread {spread:.3f} mm)" if spread > 0.05 * sz else ""))
            n_eff = len(diffs) + 1
        else:
            n_eff = n
        if not np.allclose(np.abs(np.column_stack([iop[:3], iop[3:], normal])), np.eye(3), atol=0.05):
            print("    orientation      : OBLIQUE / non-axial — axis mapping assumes a standard axial series")
    else:
        n_eff = n
        print("    slice spacing    : no position tags; will fall back to SliceThickness")
    if sz is None:
        sz = float(ds0.get("SpacingBetweenSlices", 0) or ds0.get("SliceThickness", 0) or 1.0)

    print(f"    in-plane spacing : {sx:.3f} x {sy:.3f} mm")
    fov = (cols * sx, rows * sy, n_eff * sz)
    print(f"    physical size    : {fov[0]:.0f} x {fov[1]:.0f} x {fov[2]:.0f} mm")

    if blockers:
        print(f"    USABLE           : NO ({'; '.join(blockers)})")
        return None

    print(f"    USABLE           : yes")
    return {"uid": uid, "n": n_eff, "cols": cols, "rows": rows, "fov": fov,
            "modality": modality, "native_min_spacing": min(sx, sy, sz),
            "description": desc, "body_part": str(ds0.get("BodyPartExamined", "")).strip()}


def choose_spacing(s: dict, voxel_limit: int = SOFT_LIMIT_VOXELS) -> tuple[float, list[int]]:
    """Finest isotropic spacing (in 0.05 mm steps) whose volume stays under voxel_limit.

    Never finer than the data actually is: that invents detail and wastes memory.
    """
    fov = s["fov"]
    floor = s["native_min_spacing"]
    # Start at the spacing that would exactly fill the budget, then step up until it fits after rounding.
    ideal = (float(np.prod(fov)) / voxel_limit) ** (1 / 3)
    spacing = max(np.ceil(max(ideal, floor) * 20 - 1e-6) / 20, 0.05)
    while True:
        dims = [max(1, round(f / spacing)) for f in fov]
        if np.prod(dims) <= voxel_limit and max(dims) <= HARD_LIMIT_DIM:
            return round(float(spacing), 2), dims
        spacing += 0.05


def recommend(s: dict, folder: Path) -> None:
    native = s["cols"] * s["rows"] * s["n"]
    spacing, dims = choose_spacing(s)
    vox = int(np.prod(dims))
    print(f"\n  Native voxels      : {native / 1e6:.1f} M"
          f"  ({'fine' if native <= SOFT_LIMIT_VOXELS else 'too big for a smooth 2-view render'})")
    print(f"  Recommended export : {spacing} mm isotropic -> {dims[0]}x{dims[1]}x{dims[2]} = {vox / 1e6:.1f} M voxels")
    print(f"                       raw {vox * 2 / 1e6:.0f} MB on disk, ~{vox * 6 / 1e6:.0f} MB in Unity (float + texture)")
    out = folder.name
    print(f"\n  python -m app.export {folder} out\\{out} --spacing {spacing} --max-dim {max(dims)}")
    if s["modality"] != "CT":
        print(f"\n  NOTE: {s['modality']} is not CT — values are not Hounsfield units. The HU transfer")
        print( "        function will not apply; VolumeLoader falls back to a generic ramp.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"Not a directory: {folder}")

    series, unreadable = scan(folder)
    print(f"\n{folder}: {len(series)} series, {unreadable} non-image/unreadable files skipped")
    if not series:
        sys.exit("No DICOM image files found. Is the zip extracted? Are the files nested deeper?")

    usable = [u for uid, items in sorted(series.items(), key=lambda kv: -len(kv[1]))
              if (u := describe(uid, items))]

    if not usable:
        sys.exit("\nNo usable series in this folder.")
    best = max(usable, key=lambda s: s["n"])
    if len(usable) > 1:
        print(f"\n  {len(usable)} usable series; app.export picks the largest by default"
              f" (--series-uid {best['uid']} to force it).")
    recommend(best, folder)


if __name__ == "__main__":
    main()
