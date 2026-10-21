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
    --unity      body.raw / body.json in the Unity viewer's layout (x left, y up, z back) for the Anatomy Lab;
                 with --eye-slice also the eye positions and an eyelid map (lids.raw)

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


def find_eyes(vol: np.ndarray, eye_k: int, px: float) -> tuple[list[dict], np.ndarray]:
    """The two eyeballs (dark, grey vitreous in the orbits, within 30 slices of eye_k) and the eyelids: the tissue
    in front of each eyeball inside its outline seen from the front, 128 = upper lid, 64 = lower lid.
    Returns eyes in voxel units (x, row, slice index from the bottom) and the lid map (slices, rows, x)."""
    D, H, W, _ = vol.shape
    alpha = vol[..., 3] > 127
    k0, k1 = max(0, eye_k - 30), min(D, eye_k + 30)
    rgb = vol[k0:k1, ..., :3].astype(np.int16)
    lum, sat = rgb.mean(-1), rgb.max(-1) - rgb.min(-1)
    front = int(np.nonzero(alpha.any(axis=(0, 2)))[0][0])
    cand = alpha[k0:k1] & (lum < 115) & (sat < 50) & (rgb[..., 2] >= rgb[..., 0] - 12)
    cand[:, front + int(80 / px):, :] = False
    cand[:, :, : W // 2 - int(55 / px)] = False
    cand[:, :, W // 2 + int(55 / px):] = False
    lab, _ = ndimage.label(ndimage.binary_opening(cand, iterations=1))
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    eyes, lids = [], np.zeros((D, H, W), np.uint8)
    kk, rr, xx = np.mgrid[0:D, 0:H, 0:W]
    for i in np.argsort(sizes)[::-1][:2]:
        z, y, x = np.nonzero(lab == i)
        radius = (3 * sizes[i] * px * px * SLICE_MM / (4 * np.pi)) ** (1 / 3) + 2.0   # vitreous + wall, mm
        xc, rc, kc = float(x.mean()), float(y.mean()), float(z.mean() + k0)
        dx, dz = (xx - xc) * px, (kk - kc) * SLICE_MM
        inside = dx ** 2 + dz ** 2 < radius ** 2
        globe_front = rc * px - np.sqrt(np.clip(radius ** 2 - dx ** 2 - dz ** 2, 0, None))
        lid = inside & alpha & (rr * px < globe_front - 0.3)
        k_line = kc - 1.0 / SLICE_MM
        lids[lid & (kk >= k_line)] = 128
        lids[lid & (kk < k_line)] = 64
        skin_row = int(np.argmax(alpha[int(round(kc)), :, int(round(xc))]))
        eyes.append({"x": xc, "row": rc, "k": kc, "radius_mm": float(radius), "line_k": float(k_line),
                     "skin_row": skin_row, "vitreous_ml": round(float(sizes[i] * px * px * SLICE_MM / 1000), 2)})
    eyes.sort(key=lambda e: e["x"])                     # patient's right first
    return eyes, lids


SKIN_DEPTH_UNIT_MM = 0.25


def skin_depth(alpha: np.ndarray, px: float) -> np.ndarray:
    """Millimetres below the body's outer surface (slices, rows, x), in units of SKIN_DEPTH_UNIT_MM, 0 outside.
    The outer surface ignores the air spaces inside (sinuses, mouth): holes are filled slice by slice first, so a
    flap of skin and fat is measured from the skin, not from the inside of the nose. Capped at 63.75 mm."""
    outer = alpha > 127
    for k in range(outer.shape[0]):
        outer[k] = ndimage.binary_fill_holes(outer[k])
    depth = ndimage.distance_transform_edt(outer, sampling=(SLICE_MM, px, px))
    return np.clip(np.rint(depth / SKIN_DEPTH_UNIT_MM), 0, 255).astype(np.uint8)


def export_unity(vol: np.ndarray, meta: dict, out: Path, eyes: list[dict] | None = None,
                 lids: np.ndarray | None = None) -> dict:
    """The volume in the Unity viewer's texture layout: x = patient left (fastest), y = up, z = back, so texture
    axes and the body's local axes coincide (VolumeSpace, MaskGpu, MaskModel work unchanged).
    Writes body.raw (RGBA), depth.raw (skin depth, R8), lids.raw (R8, optional) and body.json; positions in metres,
    origin at the centre."""
    D, H, W, _ = vol.shape
    px, sz = meta["spacing_mm"][0], meta["spacing_mm"][2]
    np.ascontiguousarray(np.transpose(vol, (1, 0, 2, 3))).tofile(out / "body.raw")
    np.ascontiguousarray(np.transpose(skin_depth(vol[..., 3], px), (1, 0, 2))).tofile(out / "depth.raw")
    size = np.array([W * px, D * sz, H * px]) / 1000.0                      # metres: x left, y up, z back

    def local(x, row, k):
        return [float(((x + 0.5) / W - 0.5) * size[0]), float(((k + 0.5) / D - 0.5) * size[1]),
                float(((row + 0.5) / H - 0.5) * size[2])]

    body = {"dims": [W, D, H], "spacing_mm": [px, sz, px], "size_m": size.tolist(),
            "axes": {"x": "patient left (+)", "y": "up (+)", "z": "back (+)"}, "format": "RGBA8",
            "slices": meta.get("slices"), "credit": CREDIT, "licence": LICENCE, "eyes": [],
            "skin_depth": "depth.raw", "skin_depth_unit_mm": SKIN_DEPTH_UNIT_MM}
    for e in eyes or []:
        c = local(e["x"], e["row"], e["k"])
        body["eyes"].append({"centre_m": c, "radius_m": e["radius_mm"] / 1000,
                             "lid_line_y_m": local(e["x"], e["row"], e["line_k"])[1],
                             "skin_front_z_m": local(e["x"], e["skin_row"], e["k"])[2]})
    if lids is not None:
        np.ascontiguousarray(np.transpose(lids, (1, 0, 2))).tofile(out / "lids.raw")
        body["lids"] = "lids.raw"
    (out / "body.json").write_text(json.dumps(body, indent=2))
    return body


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", help="folder of colour photo DICOMs")
    ap.add_argument("out_dir")
    ap.add_argument("--first", type=int, required=True, help="top slice number (Visible Human numbering)")
    ap.add_argument("--last", type=int, required=True, help="bottom slice number")
    ap.add_argument("--factor", type=int, default=2, help="average N x N photo pixels (2 -> 0.66 mm)")
    ap.add_argument("--web", help="also write browser atlases into this folder")
    ap.add_argument("--unity", action="store_true", help="also write body.raw/json in the Unity viewer's layout")
    ap.add_argument("--eye-slice", type=int, help="slice number at eye level: find the eyes and eyelids (male: 1095)")
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
    if args.unity:
        eyes = lids = None
        if args.eye_slice:
            eyes, lids = find_eyes(vol, args.last - args.eye_slice, meta["spacing_mm"][0])
            print("eyes:", [(round(e["x"]), round(e["row"]), round(e["k"]), round(e["radius_mm"], 1)) for e in eyes])
        export_unity(vol, meta, out, eyes, lids)
    w, h, d = meta["dims"]
    print(f"{w} x {h} x {d} voxels at {meta['spacing_mm'][0]:.2f} x {meta['spacing_mm'][1]:.2f} x "
          f"{meta['spacing_mm'][2]:.1f} mm -> {out}")


if __name__ == "__main__":
    main()
