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


def largest_piece(mask: np.ndarray, keep_fraction: float = 0.02) -> np.ndarray:
    """The body: the largest 3D piece of tissue and every piece that continues it along the stack. The specimen
    was cut into blocks and the photo at a block's end shows a sliver of him or nothing, which cuts the legs off
    the torso as a 3D piece (connectivity is judged with slices bridged two deep; a joint can be wider). The label
    card photographed beside him is tissue-coloured and runs through every photo, as big as a leg: it is told apart
    because it lies BESIDE the body over the same slices, while a leg lies BEYOND it."""
    if mask.ndim == 3 and mask.shape[0] > 1:
        bridged = ndimage.binary_dilation(mask, structure=np.ones((5, 1, 1), bool))
    else:
        bridged = mask
    labels, n = ndimage.label(bridged)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    main = int(np.argmax(sizes)) + 1
    keep = [main]
    if mask.ndim == 3:
        present = [np.flatnonzero((labels == i).any(axis=(1, 2))) for i in range(1, n + 1)]
        lo, hi = present[main - 1][0], present[main - 1][-1]
        for i in range(1, n + 1):
            if i == main or sizes[i - 1] < keep_fraction * sizes[main - 1] or len(present[i - 1]) == 0:
                continue
            a0, a1 = present[i - 1][0], present[i - 1][-1]
            overlap = max(0, min(hi, a1) - max(lo, a0) + 1)
            if overlap <= 0.2 * (a1 - a0 + 1):
                keep.append(i)
    return mask & np.isin(labels, keep)


def running_median(x: np.ndarray, size: int = 9) -> np.ndarray:
    half = size // 2
    padded = np.pad(x, half, mode="edge")
    return np.array([np.median(padded[i:i + size]) for i in range(len(x))])


def match_blocks(rgb: np.ndarray, tissue: np.ndarray, joints: np.ndarray) -> np.ndarray:
    """The specimen's blocks were photographed separately, so across a joint (a run of slices repair_gaps found)
    the colour steps. Each block below a joint is scaled, per channel, to match the block above it over the eight
    whole slices on either side; the running equalisation then has only a trend left to even out."""
    if not joints.any():
        return rgb
    out = rgb.astype(np.float32)
    runs = np.flatnonzero(np.diff(np.concatenate([[False], joints, [False]]).astype(int)))
    for lo, hi in zip(runs[::2], runs[1::2]):                      # each joint: slices lo..hi-1
        above = [k for k in range(hi, min(hi + 20, len(joints))) if not joints[k] and tissue[k].any()][:8]
        below = [k for k in range(lo - 1, max(lo - 21, -1), -1) if not joints[k] and tissue[k].any()][:8]
        if len(above) < 3 or len(below) < 3:
            continue
        mean_above = np.mean([out[k][tissue[k]].mean(axis=0) for k in above], axis=0)
        mean_below = np.mean([out[k][tissue[k]].mean(axis=0) for k in below], axis=0)
        gain = np.clip(mean_above / np.maximum(mean_below, 1.0), 0.6, 1.6)
        out[:lo] *= gain
        out[lo:hi] = out[hi] if hi < len(joints) else out[lo - 1]  # the joint itself: the block above's photo
    return np.clip(out, 0, 255).astype(np.uint8)


def repair_gaps(rgb: np.ndarray, tissue: np.ndarray) -> np.ndarray:
    """Slices at a block's end (a sliver of the body or nothing: under 80 % of the neighbours' tissue; the joint
    at the shins is six blank photos) take the photo of the nearest whole slice, so the seam between blocks is
    not a dark ring round the body. Returns the tissue mask and which slices were joints."""
    area = tissue.sum(axis=(1, 2)).astype(float)
    median = running_median(area, 25)                               # sees across a joint of up to 12 blank photos
    gap = (area < 0.8 * median) & (median > 0)
    good = np.flatnonzero(~gap & (area > 0))
    if gap.any() and len(good) > 0:
        for k in np.flatnonzero(gap):
            j = good[np.argmin(np.abs(good - k))]
            rgb[k] = rgb[j]
            tissue[k] = tissue[j]
    return tissue, gap


def body_box(files: list[Path], coarse: int = 6, margin_px: int = 12) -> tuple[slice, slice]:
    """Rows and columns (full-resolution photo pixels) of the body's 3D box, from a coarse pass."""
    stack = np.stack([tissue_mask(block_mean(read_photo(f), coarse)) for f in files])
    body = largest_piece(stack)
    ys = np.nonzero(body.any(axis=(0, 2)))[0]
    xs = np.nonzero(body.any(axis=(0, 1)))[0]
    return (slice(max(0, int(ys[0]) * coarse - margin_px), (int(ys[-1]) + 1) * coarse + margin_px),
            slice(max(0, int(xs[0]) * coarse - margin_px), (int(xs[-1]) + 1) * coarse + margin_px))


def build(files: list[Path], factor: int, slice_mm: float = SLICE_MM) -> tuple[np.ndarray, dict]:
    """RGBA volume (slices bottom to top) from photo files ordered bottom to top, slice_mm apart."""
    rows, cols = body_box(files)
    rgb = np.stack([block_mean(read_photo(f)[rows, cols], factor) for f in files])
    tissue = largest_piece(tissue_mask(rgb))
    tissue, joints = repair_gaps(rgb, tissue)
    rgb = match_blocks(rgb, tissue, joints)
    for k in range(tissue.shape[0]):
        tissue[k] = ndimage.binary_fill_holes(tissue[k])
    tissue &= ~gel_mask(rgb)
    # Photos beyond the body at either end (below the feet) are dropped.
    have = np.flatnonzero(tissue.any(axis=(1, 2)))
    lo, hi = (int(have[0]), int(have[-1]) + 1) if len(have) else (0, tissue.shape[0])
    rgb, tissue = rgb[lo:hi], tissue[lo:hi]
    for k in range(tissue.shape[0]):
        if not tissue[k].any():
            continue
        # The outermost pixel of tissue is a mix of skin and the gelatin round it (the photos are averaged in
        # blocks): it takes the colour of the tissue just inside it, and the gelatin takes the nearest tissue colour.
        inner = ndimage.binary_erosion(tissue[k])
        if inner.any():
            _, (iy, ix) = ndimage.distance_transform_edt(~inner, return_indices=True)
            rgb[k] = rgb[k][iy, ix]
        else:
            _, (iy, ix) = ndimage.distance_transform_edt(~tissue[k], return_indices=True)
            rgb[k] = rgb[k][iy, ix]
    px = PIXEL_MM * factor
    rgb = clean_skin_traces(rgb, tissue, px)
    rgb = equalise_slices(rgb, tissue)
    alpha = body_alpha(tissue, px, slice_mm)
    vol = np.concatenate([rgb, alpha[..., None]], axis=-1)
    meta = {"dims": [vol.shape[2], vol.shape[1], vol.shape[0]], "spacing_mm": [px, px, slice_mm],
            "crop_photo_px": {"rows": [rows.start, rows.stop], "cols": [cols.start, cols.stop]},
            "kept_files": [lo, hi]}
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


def clean_skin_traces(rgb: np.ndarray, tissue: np.ndarray, px: float) -> np.ndarray:
    """Gelatin that clung to the skin passes the tissue test here and there (grey-green streaks on the scalp):
    within 2 mm of the body's surface, light pixels greener than red and blue take the colour of the nearest pixel
    that is not. Deeper in, greenish tissue (bile, gut) is his own and stays; the eyes' dark grey, just behind the
    lids, is too dark to count."""
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    lum = (r + g + b) // 3
    trace = tissue & (g > r + 3) & (g >= b) & (lum > 100)             # light and green: not the eye's dark grey
    shell_px = max(1, int(round(2.0 / px)))
    out = rgb.copy()
    for k in range(rgb.shape[0]):
        if not trace[k].any():
            continue
        shell = tissue[k] & ~ndimage.binary_erosion(tissue[k], iterations=shell_px)
        fix = trace[k] & shell
        if not fix.any():
            continue
        sound = tissue[k] & ~trace[k]
        if not sound.any():
            continue
        _, (iy, ix) = ndimage.distance_transform_edt(~sound, return_indices=True)
        out[k][fix] = rgb[k][iy[fix], ix[fix]]
    return out


def equalise_slices(rgb: np.ndarray, tissue: np.ndarray) -> np.ndarray:
    """Each photo was exposed on its own, so neighbouring slices differ a little in brightness; on the rendered
    skin that shows as rings around the head. Every slice's tissue brightness is brought to the running median of
    its neighbours (gain within 0.75..1.33, so a slice that really is darker, through bone, keeps its look)."""
    lum = np.array([rgb[k][tissue[k]].mean() if tissue[k].any() else np.nan for k in range(rgb.shape[0])])
    ok = ~np.isnan(lum)
    if ok.sum() < 3:
        return rgb
    filled = np.interp(np.arange(len(lum)), np.flatnonzero(ok), lum[ok])
    smooth = running_median(filled)                                 # (median_filter misbehaves on short series)
    gain = np.clip(smooth / np.maximum(filled, 1.0), 0.75, 1.33)
    out = np.empty_like(rgb)
    for k in range(rgb.shape[0]):
        out[k] = np.clip(rgb[k].astype(np.float32) * gain[k], 0, 255).astype(np.uint8)
    return out


def body_alpha(tissue: np.ndarray, px: float, slice_mm: float = SLICE_MM) -> np.ndarray:
    """Tissue 0..255. The outline of each photo sits a fraction of a millimetre off its neighbours', which the
    renderer's normals turn into steps across the skin, so the body's OUTER surface is a 1.5 mm smoothing of the
    filled outline; inside it, the sharp mask (lightly softened) keeps sinuses, mouth and the cut edge of the
    neck exactly where the photos have them."""
    sharp_sigma = (0.8 / slice_mm, 0.6 / px, 0.6 / px)                  # 0.8 mm up-down (the steps between photos), 0.6 across
    sharp = np.clip(ndimage.gaussian_filter(tissue.astype(np.float32), sharp_sigma), 0, 1)
    filled = tissue.copy()
    for k in range(filled.shape[0]):
        filled[k] = ndimage.binary_fill_holes(filled[k])
    outer_sigma = (1.5 / slice_mm, 1.5 / px, 1.5 / px)
    outer = np.clip(ndimage.gaussian_filter(filled.astype(np.float32), outer_sigma), 0, 1)
    alpha = np.where(filled, np.minimum(outer, sharp), outer)
    return (alpha * 255).astype(np.uint8)


def skin_depth(alpha: np.ndarray, px: float, slice_mm: float = SLICE_MM) -> np.ndarray:
    """Millimetres below the body's outer surface (slices, rows, x), in units of SKIN_DEPTH_UNIT_MM, 0 outside.
    The outer surface ignores the air spaces inside (sinuses, mouth): holes are filled slice by slice first, so a
    flap of skin and fat is measured from the skin, not from the inside of the nose. Capped at 63.75 mm."""
    outer = alpha > 127
    for k in range(outer.shape[0]):
        outer[k] = ndimage.binary_fill_holes(outer[k])
    depth = ndimage.distance_transform_edt(outer, sampling=(slice_mm, px, px))
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
    np.ascontiguousarray(np.transpose(skin_depth(vol[..., 3], px, sz), (1, 0, 2))).tofile(out / "depth.raw")
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
    ap.add_argument("--every", type=int, default=1, help="use every Nth photo (2 -> 2 mm slices; the whole body)")
    ap.add_argument("--web", help="also write browser atlases into this folder")
    ap.add_argument("--unity", action="store_true", help="also write body.raw/json in the Unity viewer's layout")
    ap.add_argument("--eye-slice", type=int, help="slice number at eye level: find the eyes and eyelids (male: 1095)")
    args = ap.parse_args()

    found = index_slices(Path(args.photos))
    locs = list(range(args.last, args.first - 1, -1))[::args.every]  # bottom to top
    missing = [loc for loc in locs if loc not in found]
    if missing:
        raise SystemExit(f"{len(missing)} slices missing, e.g. {missing[:5]}")
    vol, meta = build([found[loc] for loc in locs], args.factor, SLICE_MM * args.every)
    lo, hi = meta.pop("kept_files")
    meta.update({"slices": [locs[hi - 1], locs[lo]], "layout": "RGBA uint8, x = patient left (fastest), "
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
