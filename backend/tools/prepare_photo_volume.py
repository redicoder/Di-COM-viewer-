"""
Visible Human colour cryosection photos -> one RGBA volume (the "photographed body").

    .venv-seg\\Scripts\\python.exe tools\\prepare_photo_volume.py data\\vhp_male_head_photos out\\photo_head ^
        --first 1001 --last 1225 --factor 2 --web out\\photo_head\\web

Input: a folder of the colour photo DICOMs (one per 1 mm slice; RGB, 2048 x 1216 pixels of 0.33 mm, the body in
blue gelatin; see tools/download_visible_human.py). Each slice's SliceLocation is its Visible Human slice number,
the same numbering as the frozen CT.

Output (x = patient left, rows = front to back, slices = bottom to top; the CT's layout):
    photo.raw    uint8 RGBA, x fastest. RGB = the photo; A = tissue (0 = outside, gelatin-filled air spaces)
    photo.json   dims, spacing, slice range, crop in photo pixels, licence and credit
    --web DIR    the same volume as JPEG colour atlases + PNG alpha atlases for the browser sample

Steps: rows flipped (the photo's rows run back to front); a coarse pass finds the body's 3D box; each slice is
cropped and averaged down by --factor (2 -> 0.66 mm); tissue = not blue and not the black frame, the largest 3D
piece, holes filled slice by slice; blue gelatin inside the body (sinuses, airways, bowel) is air in life and stays
empty; gelatin voxels take the colour of the nearest tissue, so filtering at the surface does not pull in blue.
Exposure is not corrected: the grey card in every photo varies by ~1 % across the head.

Data: U.S. National Library of Medicine, Visible Human Project. Credit: "Courtesy of the U.S. National Library of
Medicine".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pydicom
from scipy import ndimage

PIXEL_MM = 0.33
SLICE_MM = 1.0
CREDIT = "Courtesy of the U.S. National Library of Medicine"
LICENCE = "National Library of Medicine Terms and Conditions; May 21, 2019"


def tissue_mask(rgb: np.ndarray) -> np.ndarray:
    """Body tissue in a photo: redder than blue (the gelatin is blue) and not the black frame."""
    r, b = rgb[..., 0].astype(np.int16), rgb[..., 2].astype(np.int16)
    return (r > b + 8) & (r > 45)


def gel_mask(rgb: np.ndarray) -> np.ndarray:
    r, b = rgb[..., 0].astype(np.int16), rgb[..., 2].astype(np.int16)
    return b > r + 8


def block_mean(rgb: np.ndarray, f: int) -> np.ndarray:
    if f == 1:
        return rgb
    h, w = rgb.shape[0] // f * f, rgb.shape[1] // f * f
    return rgb[:h, :w].reshape(h // f, f, w // f, f, -1).mean(axis=(1, 3)).astype(np.uint8)


def index_slices(folder: Path) -> dict[int, Path]:
    out = {}
    for f in folder.glob("*.dcm"):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        out[int(round(float(ds.SliceLocation)))] = f
    return out


def read_photo(path: Path) -> np.ndarray:
    """RGB with rows running front to back, like the CT (the photo's own rows run back to front)."""
    return pydicom.dcmread(path).pixel_array[::-1]


def largest_piece(mask: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(mask)
    if n == 0:
        raise ValueError("No tissue found in the photos")
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == sizes.argmax()


def body_box(files: list[Path], coarse: int = 6, margin_px: int = 12) -> tuple[slice, slice]:
    """Rows and columns (full-resolution photo pixels) of the body's 3D box, from a coarse pass."""
    stack = np.stack([tissue_mask(block_mean(read_photo(f), coarse)) for f in files])
    body = largest_piece(stack)
    ys = np.nonzero(body.any(axis=(0, 2)))[0]
    xs = np.nonzero(body.any(axis=(0, 1)))[0]
    return (slice(max(0, int(ys[0]) * coarse - margin_px), (int(ys[-1]) + 1) * coarse + margin_px),
            slice(max(0, int(xs[0]) * coarse - margin_px), (int(xs[-1]) + 1) * coarse + margin_px))


def build(files: list[Path], factor: int) -> tuple[np.ndarray, dict]:
    """RGBA volume (slices bottom to top) from photo files ordered bottom to top."""
    rows, cols = body_box(files)
    rgb = np.stack([block_mean(read_photo(f)[rows, cols], factor) for f in files])
    tissue = largest_piece(tissue_mask(rgb))
    for k in range(tissue.shape[0]):
        tissue[k] = ndimage.binary_fill_holes(tissue[k])
    tissue &= ~gel_mask(rgb)
    for k in range(tissue.shape[0]):                     # gelatin takes the nearest tissue colour
        if tissue[k].any():
            _, (iy, ix) = ndimage.distance_transform_edt(~tissue[k], return_indices=True)
            rgb[k] = rgb[k][iy, ix]
    px = PIXEL_MM * factor
    sigma = (0.8, 0.6 * SLICE_MM / px, 0.6 * SLICE_MM / px)       # 0.8 mm up-down (softens the 1 mm steps), 0.6 mm across
    alpha = (np.clip(ndimage.gaussian_filter(tissue.astype(np.float32), sigma), 0, 1) * 255).astype(np.uint8)
    vol = np.concatenate([rgb, alpha[..., None]], axis=-1)
    meta = {"dims": [vol.shape[2], vol.shape[1], vol.shape[0]], "spacing_mm": [px, px, SLICE_MM],
            "crop_photo_px": {"rows": [rows.start, rows.stop], "cols": [cols.start, cols.stop]}}
    return vol, meta


def write_web(vol: np.ndarray, out: Path, per_file: int = 64, cols: int = 8, quality: int = 90) -> list[dict]:
    """Slices tiled into atlases: colour as JPEG (4:4:4), alpha as greyscale PNG."""
    from PIL import Image

    out.mkdir(parents=True, exist_ok=True)
    d, h, w, _ = vol.shape
    files = []
    for i, s in enumerate(range(0, d, per_file)):
        chunk = range(s, min(s + per_file, d))
        n_rows = (len(chunk) + cols - 1) // cols
        rgb = np.zeros((n_rows * h, cols * w, 3), np.uint8)
        alpha = np.zeros((n_rows * h, cols * w), np.uint8)
        for j, k in enumerate(chunk):
            y0, x0 = (j // cols) * h, (j % cols) * w
            rgb[y0:y0 + h, x0:x0 + w] = vol[k, ..., :3]
            alpha[y0:y0 + h, x0:x0 + w] = vol[k, ..., 3]
        Image.fromarray(rgb).save(out / f"colour_{i}.jpg", quality=quality, subsampling=0)
        Image.fromarray(alpha).save(out / f"alpha_{i}.png", optimize=True)
        files.append({"colour": f"colour_{i}.jpg", "alpha": f"alpha_{i}.png", "first": s, "count": len(chunk)})
    return files


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", help="folder of colour photo DICOMs")
    ap.add_argument("out_dir")
    ap.add_argument("--first", type=int, required=True, help="top slice number (Visible Human numbering)")
    ap.add_argument("--last", type=int, required=True, help="bottom slice number")
    ap.add_argument("--factor", type=int, default=2, help="average N x N photo pixels (2 -> 0.66 mm)")
    ap.add_argument("--web", help="also write browser atlases into this folder")
    args = ap.parse_args()

    found = index_slices(Path(args.photos))
    locs = list(range(args.last, args.first - 1, -1))               # bottom to top
    missing = [loc for loc in locs if loc not in found]
    if missing:
        raise SystemExit(f"{len(missing)} slices missing, e.g. {missing[:5]}")
    vol, meta = build([found[loc] for loc in locs], args.factor)
    meta.update({"slices": [args.first, args.last], "layout": "RGBA uint8, x = patient left (fastest), "
                 "rows = front to back, slices = bottom to top", "credit": CREDIT, "licence": LICENCE,
                 "source": "NLM Visible Human male, colour cryosection photographs (NCI Imaging Data Commons)"})
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    vol.tofile(out / "photo.raw")
    if args.web:
        meta["web"] = {"cols": 8, "files": write_web(vol, Path(args.web))}
        (Path(args.web) / "photo.json").write_text(json.dumps(meta))
    (out / "photo.json").write_text(json.dumps(meta, indent=2))
    w, h, d = meta["dims"]
    print(f"{w} x {h} x {d} voxels at {meta['spacing_mm'][0]:.2f} x {meta['spacing_mm'][1]:.2f} x "
          f"{meta['spacing_mm'][2]:.1f} mm -> {out}")


if __name__ == "__main__":
    main()
