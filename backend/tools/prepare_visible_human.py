"""
Stitch an NLM Visible Human CT, scanned in parts, into one head-to-toe volume (NRRD) for build_body.py.

    # 1. download the CT series from NCI Imaging Data Commons (in .venv-seg, which has idc-index),
    #    collection nlm_visible_human_project, one sub-folder per series:
    #      female (demo body): PatientID VHP-F, StudyDescription "Normal" (fresh cadaver), both CT series
    #                          -> data/vhp_female_normal/<one folder per series>
    #      male:               PatientID VHP-M, StudyDescription "Frozen", series 2, 3 and 4 -> data/vhp_male_frozen/...
    # 2. stitch:
    .venv\\Scripts\\python.exe tools\\prepare_visible_human.py data\\vhp_female_normal data\\visible_human_female.nrrd

Why stitching is needed: each body was scanned in parts (head-first down to the thighs, feet-first for the
legs), each with its own scanner coordinates. The DICOM SliceLocation tag holds the original Visible Human slice
number (female 1001..2734, male 1006..2882; 1 mm apart, head to toe), which orders all slices into one
continuous stack. The head and neck were reconstructed with smaller fields of view, so every slice is resampled
by its own pixel size and position onto one common grid. At each join the table position changed slightly, so
the in-plane shift between the last slice of one part and the first of the next is measured (best overlap of
the body outlines) and applied to all slices of the later parts.

Data: U.S. National Library of Medicine, Visible Human Project, "National Library of Medicine Terms and
Conditions; May 21, 2019". Required credit: "Courtesy of the U.S. National Library of Medicine".
"""
from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

import numpy as np
import pydicom

BODY_HU = -400        # outline threshold for the alignment search
SEARCH_PX = 64        # maximum shift searched at each join, in pixels (0.94 mm each)


def read_part(folder: Path) -> dict[int, Path]:
    files = {}
    for f in folder.rglob("*.dcm"):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        files[int(round(float(ds.SliceLocation)))] = f
    return files


def hu(path: Path) -> tuple[np.ndarray, pydicom.Dataset]:
    ds = pydicom.dcmread(path)
    return ds.pixel_array.astype(np.float32) * float(ds.RescaleSlope) + float(ds.RescaleIntercept), ds


def best_shift(a: np.ndarray, b: np.ndarray, search: int = SEARCH_PX) -> tuple[int, int, float]:
    """Integer (dy, dx) that, applied to b, best overlaps the body outlines (intersection over union).
    Searched on 2x-downsampled masks, then refined at full resolution."""
    ma, mb = a > BODY_HU, b > BODY_HU

    def iou(m1, m2, dy, dx):
        m2s = np.roll(m2, (dy, dx), axis=(0, 1))
        union = (m1 | m2s).sum()
        return (m1 & m2s).sum() / union if union else 0.0

    da, db = ma[::2, ::2], mb[::2, ::2]
    coarse = max(((iou(da, db, dy, dx), dy, dx) for dy in range(-search // 2, search // 2 + 1)
                  for dx in range(-search // 2, search // 2 + 1)), key=lambda t: t[0])
    best = max(((iou(ma, mb, 2 * coarse[1] + ddy, 2 * coarse[2] + ddx), 2 * coarse[1] + ddy, 2 * coarse[2] + ddx)
                for ddy in (-2, -1, 0, 1, 2) for ddx in (-2, -1, 0, 1, 2)), key=lambda t: t[0])
    return best[1], best[2], best[0]


def to_grid(img: np.ndarray, ds: pydicom.Dataset, grid_origin_xy, grid_spacing: float, grid_shape) -> np.ndarray:
    """Resample one slice into the common in-plane grid using its physical position and pixel size.

    The head and neck were reconstructed with smaller fields of view (0.53 mm and 0.78 mm pixels, different
    ImagePositionPatient); stacking them unchanged would shrink and shift the head. Pixel (r, c) of a slice sits
    at (IPPx + c * spacing, IPPy + r * spacing)."""
    from scipy import ndimage

    sp = float(ds.PixelSpacing[0])
    ix, iy = float(ds.ImagePositionPatient[0]), float(ds.ImagePositionPatient[1])
    if abs(sp - grid_spacing) < 1e-4 and abs(ix - grid_origin_xy[0]) < 1e-3 and abs(iy - grid_origin_xy[1]) < 1e-3:
        return img
    scale = grid_spacing / sp
    offset = ((grid_origin_xy[1] - iy) / sp, (grid_origin_xy[0] - ix) / sp)   # (row, col)
    return ndimage.affine_transform(img, np.diag([scale, scale]), offset=offset, output_shape=grid_shape,
                                    order=1, mode="constant", cval=-1024.0)


def shifted(img: np.ndarray, dy: int, dx: int, fill: float = -1024.0) -> np.ndarray:
    out = np.full_like(img, fill)
    h, w = img.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = img[ys, xs]
    return out


def write_nrrd(path: Path, vol_zyx: np.ndarray, spacing_xyz: tuple[float, float, float], origin_lps) -> None:
    """int16 volume, numpy (z, y, x) = file axes (x fastest), LPS space, gzip."""
    sx, sy, sz = spacing_xyz
    nz, ny, nx = vol_zyx.shape
    header = (
        "NRRD0004\n"
        "# Visible Human male (frozen CT), stitched by tools/prepare_visible_human.py\n"
        "# Courtesy of the U.S. National Library of Medicine\n"
        "type: short\ndimension: 3\nspace: left-posterior-superior\n"
        f"sizes: {nx} {ny} {nz}\n"
        f"space directions: ({sx},0,0) (0,{sy},0) (0,0,{sz})\n"
        "kinds: domain domain domain\nendian: little\nencoding: gzip\n"
        f"space origin: ({origin_lps[0]},{origin_lps[1]},{origin_lps[2]})\n\n"
    )
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=4) as gz:
            for z in range(nz):
                gz.write(np.ascontiguousarray(vol_zyx[z]).astype("<i2").tobytes())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts_folder", help="folder with one sub-folder per downloaded series (s2, s3, s4)")
    ap.add_argument("out_nrrd")
    args = ap.parse_args()

    parts = [read_part(p) for p in sorted(Path(args.parts_folder).iterdir()) if p.is_dir()]
    parts = [p for p in parts if p]
    parts.sort(key=lambda p: min(p))                       # head part first (lowest slice number)
    for p in parts:
        print(f"part: slices {min(p)}..{max(p)} ({len(p)})")
    for p, q in zip(parts, parts[1:]):
        if min(q) != max(p) + 1:
            sys.exit(f"Parts are not contiguous: {max(p)} -> {min(q)}")

    # Common in-plane grid: the most frequent reconstruction (largest field of view, 0.94 mm pixels).
    from collections import Counter
    geoms = Counter()
    for p in parts:
        for f in p.values():
            ds = pydicom.dcmread(f, stop_before_pixels=True)
            geoms[(round(float(ds.PixelSpacing[0]), 6), round(float(ds.ImagePositionPatient[0]), 3),
                   round(float(ds.ImagePositionPatient[1]), 3), int(ds.Rows), int(ds.Columns))] += 1
    (grid_sp, gx0, gy0, ny, nx), _ = geoms.most_common(1)[0]
    for g, n in sorted(geoms.items()):
        print(f"  reconstruction {g[0]} mm pixels, origin ({g[1]}, {g[2]}): {n} slices")

    def slice_on_grid(path):
        img, ds = hu(path)
        return to_grid(img, ds, (gx0, gy0), grid_sp, (ny, nx))

    # Shifts at each join, accumulated so every later part lines up with the head part.
    shifts = [(0, 0)]
    for p, q in zip(parts, parts[1:]):
        dy, dx, score = best_shift(slice_on_grid(p[max(p)]), slice_on_grid(q[min(q)]))
        prev = shifts[-1]
        shifts.append((prev[0] + dy, prev[1] + dx))
        print(f"join {max(p)}/{min(q)}: shift dy={dy} dx={dx} px (outline overlap {score:.2f})")

    locations = [loc for p in parts for loc in sorted(p)]
    nz = len(locations)
    vol = np.empty((nz, ny, nx), dtype=np.int16)
    # Slice numbers grow towards the feet; the volume's z grows towards the head (LPS superior).
    for p, (dy, dx) in zip(parts, shifts):
        for loc in sorted(p):
            img = slice_on_grid(p[loc])
            vol[locations[-1] - loc] = np.clip(np.rint(shifted(img, dy, dx)), -1024, 3071).astype(np.int16)
        print(f"  part {min(p)}..{max(p)} loaded with shift {dy, dx}")

    sx = sy = grid_sp
    origin = (gx0, gy0, -float(locations[-1]))
    out = Path(args.out_nrrd)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_nrrd(out, vol, (sx, sy, 1.0), origin)
    print(f"Wrote {out} ({nx}x{ny}x{nz}, {sx:.4f} x {sy:.4f} x 1.0 mm, {out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
