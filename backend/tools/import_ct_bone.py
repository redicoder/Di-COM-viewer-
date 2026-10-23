"""Bone from his frozen CT onto a photographed-body export. The Visible Human male was CT-scanned frozen before
he was cut: 1 mm slices with the same slice numbers as the photographs (1006-2882, three series), 0.9375 mm
pixels, rows front to back and columns right to left like the photographs after prepare_photo_volume.py
flips them. Bone is unmistakable in CT (over BONE_HU) where it is not in the photographs at 1.3 mm (red or
yellow marrow inside a thin white shell), so the skull, the arm and leg bones and everything the SIO does
not cover come from here.

Each CT slice is placed on its photograph as the SIO was (import_sio_labels.py): the body's outline in the CT
(every piece of it: both legs, both arms) slid over the export's own tissue outline painted on the
photograph's frame, on every slice; slices that match badly take their neighbours' place and a running
median keeps the steps between the specimen's blocks. The bone mask is resampled onto the export's grid (nearest voxel) and written into its
labels as "bone (from CT)" (layer bone) wherever the voxel is tissue and not already named by the SIO.

Usage: python tools/import_ct_bone.py data/vhp_male_frozen out/photo_body
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.signal import fftconvolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_photo_volume as ppv  # noqa: E402
from import_sio_labels import body_only  # noqa: E402
from transfer_eyes import Frame  # noqa: E402

BONE_HU = 250.0
BODY_HU = -400.0
GRID_MM = 1.0


def index_ct(folder: Path) -> dict[int, Path]:
    """Slice number -> CT file, over every series folder under `folder`."""
    import pydicom
    out = {}
    for f in folder.rglob("*.dcm"):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        out[int(round(float(ds.SliceLocation)))] = f
    return out


def read_ct(path: Path) -> tuple[np.ndarray, float]:
    """HU image (rows front to back, columns right to left) and its pixel size in mm."""
    import pydicom
    ds = pydicom.dcmread(path)
    hu = ds.pixel_array.astype(np.float32) * float(getattr(ds, "RescaleSlope", 1.0)) + float(getattr(ds, "RescaleIntercept", 0.0))
    return hu, float(ds.PixelSpacing[0])


def to_grid(mask: np.ndarray, px_mm: float) -> np.ndarray:
    """A mask resampled to GRID_MM pixels."""
    return ndimage.zoom(mask.astype(np.float32), px_mm / GRID_MM, order=1) > 0.5


def big_pieces(mask: np.ndarray, px_mm: float, min_mm2: float = 1500.0) -> np.ndarray:
    """Every piece of a mask at least min_mm2 (both legs, both arms; not the scanner's table or specks)."""
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel()) * px_mm * px_mm
    keep = sizes >= min_mm2
    keep[0] = False
    return keep[lab]


def export_tissue_on_photo(alpha_slice: np.ndarray, frame: Frame, photo_shape=(1216, 2048), photo_px: float = ppv.PIXEL_MM) -> np.ndarray:
    """The export's own tissue (the label card and the gelatin already removed, both legs kept) painted onto the
    photograph's frame at GRID_MM: the outline the CT is matched against."""
    out = np.zeros((int(round(photo_shape[0] * photo_px / GRID_MM)), int(round(photo_shape[1] * photo_px / GRID_MM))), bool)
    vox_mm = frame.factor * photo_px
    small = ndimage.zoom((alpha_slice > 0).astype(np.float32), vox_mm / GRID_MM, order=1) > 0.5
    r0, c0 = int(round(frame.rows * photo_px / GRID_MM)), int(round(frame.cols * photo_px / GRID_MM))
    h = min(small.shape[0], out.shape[0] - r0)
    w = min(small.shape[1], out.shape[1] - c0)
    if h > 0 and w > 0:
        out[r0:r0 + h, c0:c0 + w] = small[:h, :w]
    return out


def register(photo_mask: np.ndarray, photo_px: float, ct_mask: np.ndarray, ct_px: float) -> tuple[float, float, float]:
    """Where the CT slice's top-left corner lies on the photograph (row, col in mm from the photograph's
    top-left), by sliding one outline over the other at GRID_MM. Returns (row_mm, col_mm, agreement).
    photo_px = GRID_MM means the photo mask is already on the grid."""
    a = to_grid(photo_mask, photo_px) if photo_px != GRID_MM else photo_mask
    b = to_grid(ct_mask, ct_px)
    A = a.astype(np.float32) - a.mean()
    B = b.astype(np.float32) - b.mean()
    pad = max(b.shape)
    big = np.zeros((a.shape[0] + 2 * pad, a.shape[1] + 2 * pad), np.float32)
    big[pad:pad + a.shape[0], pad:pad + a.shape[1]] = A
    c = fftconvolve(big, B[::-1, ::-1], mode="full")
    k = np.unravel_index(int(c.argmax()), c.shape)
    row = (k[0] - B.shape[0] + 1 - pad) * GRID_MM
    col = (k[1] - B.shape[1] + 1 - pad) * GRID_MM
    score = float(c.max() / np.sqrt((A * A).sum() * (B * B).sum() + 1e-9))
    return float(row), float(col), score


def resample_slice(mask: np.ndarray, ct_px: float, offset_mm: tuple[float, float], frame: Frame,
                   photo_px: float = ppv.PIXEL_MM) -> np.ndarray:
    """One CT slice's mask onto the export's (z, x) grid (rows front to back): nearest CT pixel."""
    w, _, h = frame.dims
    col_mm = (frame.cols + (np.arange(w) + 0.5) * frame.factor) * photo_px     # photograph mm, from its left
    row_mm = (frame.rows + (np.arange(h) + 0.5) * frame.factor) * photo_px     # from its front
    cs = np.round((col_mm - offset_mm[1]) / ct_px - 0.5).astype(int)
    rs = np.round((row_mm - offset_mm[0]) / ct_px - 0.5).astype(int)
    out = np.zeros((h, w), bool)
    okc = (cs >= 0) & (cs < mask.shape[1])
    okr = (rs >= 0) & (rs < mask.shape[0])
    if okc.any() and okr.any():
        out[np.ix_(okr, okc)] = mask[np.ix_(rs[okr], cs[okc])]
    return out


def bone_mask(hu: np.ndarray, px_mm: float) -> np.ndarray:
    """Bone in a CT slice: dense voxels, specks under a few mm^2 dropped, small holes (marrow) kept as bone
    only where they are enclosed by a shell on this slice."""
    bone = hu > BONE_HU
    lab, n = ndimage.label(bone)
    if n:
        sizes = np.bincount(lab.ravel())
        keep = sizes >= max(int(4.0 / (px_mm * px_mm)), 2)
        keep[0] = False
        bone = keep[lab]
    return ndimage.binary_fill_holes(bone)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ct", help="folder with the frozen CT series (any depth of subfolders)")
    ap.add_argument("export")
    ap.add_argument("--smooth", type=int, default=15, help="running median over this many slices' offsets")
    ap.add_argument("--min-agreement", type=float, default=0.6, help="slices matched worse than this take their neighbours' offset")
    args = ap.parse_args()
    export = Path(args.export)
    photo = json.loads((export / "photo.json").read_text())
    body = json.loads((export / "body.json").read_text())
    frame = Frame(photo, body)
    W, D, H = body["dims"]
    ct = index_ct(Path(args.ct))
    print(f"{len(ct)} CT slices {min(ct)}-{max(ct)}; export slices {frame.bottom - (D - 1) * frame.every}-{frame.bottom}")

    slices = [int(round(frame.bottom - k * frame.every)) for k in range(D)]
    alpha_all = np.memmap(export / "body.raw", np.uint8, "r", shape=(H, D, W, 4))[..., 3]
    fits, masks, px = {}, {}, None
    for i, n in enumerate(slices):
        if n not in ct:
            continue
        hu, px = read_ct(ct[n])
        ct_body = big_pieces(hu > BODY_HU, px)
        photo_body = export_tissue_on_photo(np.asarray(alpha_all[:, i, :]), frame)
        if not ct_body.any() or not photo_body.any():
            continue
        fits[n] = register(photo_body, GRID_MM, ct_body, px)
        masks[n] = bone_mask(hu, px)
        if i % 100 == 0:
            print(f"  slice {n}: CT corner at photo ({fits[n][0]:.0f}, {fits[n][1]:.0f}) mm, agreement {fits[n][2]:.3f}")
    if not fits:
        raise SystemExit("no CT slice matches the export")
    ns = sorted(fits)
    good = [n for n in ns if fits[n][2] >= args.min_agreement]
    if not good:
        raise SystemExit("no slice matched well enough")
    rows = np.interp(ns, good, [fits[n][0] for n in good])
    cols = np.interp(ns, good, [fits[n][1] for n in good])
    rows = ppv.running_median(rows, args.smooth)
    cols = ppv.running_median(cols, args.smooth)
    offsets = {n: (float(r), float(c)) for n, r, c in zip(ns, rows, cols)}
    corners = sorted(set((round(r), round(c)) for r, c in offsets.values()))
    print(f"registration: {len(ns) - len(good)} slices below agreement {args.min_agreement} take their neighbours'; "
          f"corners span rows {min(c[0] for c in corners)}..{max(c[0] for c in corners)}, cols {min(c[1] for c in corners)}..{max(c[1] for c in corners)} mm; "
          f"mean agreement {np.mean([fits[n][2] for n in good]):.3f}")

    labels_path = export / body["labels"] if body.get("labels") else export / "labels.raw"
    table = json.loads((export / body["label_table"]).read_text()) if body.get("label_table") else \
        {"dims": [W, D, H], "format": "uint8 object index, 0 = none; layout as body.raw (x left fastest, y up, z back)", "objects": []}
    labels = np.memmap(labels_path, np.uint8, "r+" if labels_path.exists() else "w+", shape=(H, D, W))
    alpha = np.memmap(export / "body.raw", np.uint8, "r", shape=(H, D, W, 4))[..., 3]
    old = [o["index"] for o in table["objects"] if o["name"] == "bone (from CT)"]     # an earlier run's bone is redone
    table["objects"] = [o for o in table["objects"] if o["name"] != "bone (from CT)"]
    index = max([o["index"] for o in table["objects"]], default=0) + 1
    if index > 255:
        raise SystemExit("no room for another object")
    sio_named = np.zeros(256, bool)
    for o in table["objects"]:
        sio_named[o["index"]] = bool(o.get("sio_labels"))
    count = 0
    for k, n in enumerate(slices):
        if n not in masks:
            continue
        bone = resample_slice(masks[n], px, offsets[n], frame)
        lab = np.asarray(labels[:, k, :])
        if old:
            lab[np.isin(lab, old)] = 0
        put = bone & (np.asarray(alpha[:, k, :]) > 0) & ~sio_named[lab]
        lab[put] = index
        labels[:, k, :] = lab
        count += int(put.sum())
    labels.flush()
    table["objects"].append({"index": index, "name": "bone (from CT)", "sio_labels": [], "layer": "bone", "voxels": count})
    table["ct_bone"] = {"source": "NLM Visible Human male frozen CT (same slice numbers)", "bone_hu": BONE_HU,
                        "corners_mm_by_slice": {str(n): [round(offsets[n][0], 1), round(offsets[n][1], 1)] for n in ns},
                        "mean_agreement": round(float(np.mean([fits[n][2] for n in ns])), 3)}
    (export / "labels.json").write_text(json.dumps(table, indent=2))
    body["labels"] = "labels.raw"
    body["label_table"] = "labels.json"
    (export / "body.json").write_text(json.dumps(body, indent=2))
    print(f"bone from CT: {count} voxels -> {labels_path}")


if __name__ == "__main__":
    main()
