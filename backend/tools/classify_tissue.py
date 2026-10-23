"""Tissue classes for the parts of a photographed body that have no labels (the head, the legs; and the head
export on its own), learnt from the parts that have them. The SIO organ labels (import_sio_labels.py) cover
the torso: some twenty million voxels whose layer (skin, fat, muscle, bone, organ) and photographed colour
are both known. That is a training set. A voxel's class is read from a table indexed by its smoothed colour
(6 bits a channel), how far it lies under the skin (three bands) and how uneven the colour is around it
(three bands: bone is white cortex round red marrow, fat is even); the table holds, per cell, how often each
class was seen there in the labelled torso, smoothed across neighbouring colours so that colours never seen
borrow from their neighbours. Every fourth labelled slice is held out to report how often the table is right.

The classes go into labels.raw as three more objects ("skin (by colour)", "fat (by colour)", "muscle (by
colour)", with their layer), only where the export had no label. Bone and organs cannot be told by colour at
this size (a bone is its marrow, an organ looks like muscle): what the table calls bone or organ is written
as muscle, bone comes from the CT (import_ct_bone.py) and the brain, eyes and the like wait for names from
it. The predicted classes are cleaned with a small 3D vote so single voxels do not speckle.

Usage:
  python tools/classify_tissue.py out/photo_body                 # learn from its torso, class the rest of it
  python tools/classify_tissue.py out/photo_head --from out/photo_body   # learn from the body, class the head
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

CLASSES = ["skin", "fat", "muscle", "bone", "organ"]       # learnt and scored
WRITTEN = ["skin", "fat", "muscle"]                          # written into the export (bone from the CT, organs named later)
BITS = 6                                 # colour quantisation per channel
DEPTH_EDGES = (2.0, 8.0)                 # mm under the skin: skin band, near, deep
STD_EDGES = (9.0, 20.0)                  # local colour unevenness (std of grey over 3 x 3 x 3)
WHITE_EDGES = (0.02, 0.15)               # share of cortex-white voxels within WHITE_MM: bone is marrow inside a white shell
WHITE_MM = 4.0
SMOOTH_MM = 1.2                          # colour smoothing in the plane before quantising
CHUNK = 32


def layer_lut(table: dict) -> np.ndarray:
    """Object index -> class id (1..5), 0 for none / unknown."""
    lut = np.zeros(256, np.uint8)
    for o in table["objects"]:
        if o.get("layer") in CLASSES and 0 < o["index"] < 256:
            lut[o["index"]] = CLASSES.index(o["layer"]) + 1
    return lut


def features(rgba: np.ndarray, depth_mm: np.ndarray, px_mm: float) -> np.ndarray:
    """Per voxel of a block (Y x H x W): the table's cell index (int64), -1 outside the tissue."""
    tissue = rgba[..., 3] > 0
    sig = SMOOTH_MM / px_mm
    cols = []
    for c in range(3):
        v = rgba[..., c].astype(np.float32)
        w = tissue.astype(np.float32)
        num = ndimage.gaussian_filter(v * w, (0, sig, sig))
        den = ndimage.gaussian_filter(w, (0, sig, sig))
        cols.append(np.clip(num / np.maximum(den, 1e-6), 0, 255))
    q = [np.minimum((cc / 256.0 * (1 << BITS)).astype(np.int64), (1 << BITS) - 1) for cc in cols]
    grey = rgba[..., :3].astype(np.float32).mean(-1)
    mean = ndimage.uniform_filter(grey, 3)
    sq = ndimage.uniform_filter(grey * grey, 3)
    std = np.sqrt(np.maximum(sq - mean * mean, 0.0))
    s = np.digitize(std, STD_EDGES)
    d = np.digitize(depth_mm, DEPTH_EDGES)
    rgb = rgba[..., :3].astype(np.int16)
    white = (grey > 170) & ((rgb.max(-1) - rgb.min(-1)) < 50) & tissue
    r = max(int(round(WHITE_MM / px_mm)), 1)
    share = ndimage.uniform_filter(white.astype(np.float32), (max(r // 2, 1) * 2 + 1, 2 * r + 1, 2 * r + 1))
    wsh = np.digitize(share, WHITE_EDGES)
    cell = ((q[0] << (2 * BITS)) | (q[1] << BITS) | q[2]) * 27 + d * 9 + s * 3 + wsh
    cell[~tissue] = -1
    return cell


BANDS = 27                               # depth x unevenness x white share
N_CELLS = (1 << (3 * BITS)) * BANDS


def count_cells(cell: np.ndarray, cls: np.ndarray, counts: np.ndarray) -> None:
    """Adds a block's labelled voxels to the table (N_CELLS x classes)."""
    m = (cell >= 0) & (cls > 0)
    np.add.at(counts, (cell[m], cls[m] - 1), 1)


def smooth_table(counts: np.ndarray) -> np.ndarray:
    """Counts smoothed over neighbouring colours (the depth and unevenness bands kept apart): where a colour was
    seen rarely, its class comes from colours near it. Returns class probabilities per cell (float32)."""
    n = 1 << BITS
    grid = counts.reshape(n, n, n, BANDS, len(CLASSES)).astype(np.float32)
    near = ndimage.gaussian_filter(grid, (1.0, 1.0, 1.0, 0, 0))
    far = ndimage.gaussian_filter(grid, (3.5, 3.5, 3.5, 0, 0))
    total_near = near.sum(-1, keepdims=True)
    probs = np.where(total_near > 5.0, near / np.maximum(total_near, 1e-6), far / np.maximum(far.sum(-1, keepdims=True), 1e-6))
    return probs.reshape(N_CELLS, len(CLASSES))


def predict(cell: np.ndarray, probs: np.ndarray) -> np.ndarray:
    """Class id per voxel (1..5), 0 outside the tissue, after a 3D vote over 3 x 3 x 3 neighbours."""
    out = np.zeros(cell.shape, np.uint8)
    m = cell >= 0
    if not m.any():
        return out
    p = np.zeros(cell.shape + (len(CLASSES),), np.float32)
    p[m] = probs[cell[m]]
    p = ndimage.uniform_filter(p, (3, 3, 3, 1))
    out[m] = p.argmax(-1)[m] + 1
    return out


SPECK_VOXELS = 60


def unspeckle(pred: np.ndarray, cls: int, instead: int) -> np.ndarray:
    """Pieces of a class smaller than SPECK_VOXELS on their slice become `instead`."""
    out = pred.copy()
    for k in range(pred.shape[0]):
        m = pred[k] == cls
        if not m.any():
            continue
        lab, n = ndimage.label(m)
        sizes = np.bincount(lab.ravel())
        small = sizes < SPECK_VOXELS
        small[0] = False
        out[k][small[lab]] = instead
    return out


def open_export(folder: Path):
    body = json.loads((folder / "body.json").read_text())
    W, D, H = body["dims"]
    vol = np.memmap(folder / "body.raw", np.uint8, "r+", shape=(H, D, W, 4))
    depth = np.memmap(folder / body["skin_depth"], np.uint8, "r", shape=(H, D, W))
    unit = body.get("skin_depth_unit_mm", 0.25)
    return body, vol, depth, unit


def learn(folder: Path, hold_every: int = 4) -> tuple[np.ndarray, dict]:
    """The table from an export's labelled slices; every hold_every-th labelled slice is held out and scored."""
    body, vol, depth, unit = open_export(folder)
    table = json.loads((folder / body["label_table"]).read_text())
    W, D, H = body["dims"]
    labels = np.memmap(folder / body["labels"], np.uint8, "r", shape=(H, D, W))
    lut = layer_lut(table)
    px = body["spacing_mm"][0]
    counts = np.zeros((N_CELLS, len(CLASSES)), np.int32)
    labelled = [k for k in range(D) if np.asarray(labels[:, k, :]).any()]
    held = set(labelled[::hold_every])
    train = [k for k in labelled if k not in held]
    print(f"learning from {len(train)} labelled slices of {folder.name}, {len(held)} held out")
    for k0 in range(0, len(train), CHUNK):
        ks = train[k0:k0 + CHUNK]
        rgba = np.stack([np.asarray(vol[:, k]) for k in ks])
        dep = np.stack([np.asarray(depth[:, k]) for k in ks]).astype(np.float32) * unit
        cls = np.stack([lut[np.asarray(labels[:, k, :])] for k in ks])
        count_cells(features(rgba, dep, px), cls, counts)
    probs = smooth_table(counts)
    # Score on the held-out slices.
    hit = np.zeros(len(CLASSES)); seen = np.zeros(len(CLASSES)); confusion = np.zeros((len(CLASSES), len(CLASSES)), np.int64)
    ks = sorted(held)
    for k0 in range(0, len(ks), CHUNK):
        kk = ks[k0:k0 + CHUNK]
        rgba = np.stack([np.asarray(vol[:, k]) for k in kk])
        dep = np.stack([np.asarray(depth[:, k]) for k in kk]).astype(np.float32) * unit
        cls = np.stack([lut[np.asarray(labels[:, k, :])] for k in kk])
        pred = predict(features(rgba, dep, px), probs)
        m = (cls > 0) & (pred > 0)                       # labels the SIO put just outside our tissue are not scored
        np.add.at(confusion, (cls[m] - 1, pred[m] - 1), 1)
    for c in range(len(CLASSES)):
        seen[c] = confusion[c].sum(); hit[c] = confusion[c, c]
    report = {CLASSES[c]: {"voxels": int(seen[c]), "right": round(float(hit[c] / max(seen[c], 1)), 3)} for c in range(len(CLASSES))}
    report["overall"] = round(float(hit.sum() / max(seen.sum(), 1)), 3)
    report["confusion_rows_true_cols_predicted"] = confusion.tolist()
    for c in range(len(CLASSES)):
        print(f"  {CLASSES[c]:7s} {int(seen[c]):9d} voxels held out, {hit[c] / max(seen[c], 1) * 100:5.1f} % right")
    print(f"  overall {report['overall'] * 100:.1f} %")
    return probs, report


def apply(folder: Path, probs: np.ndarray, report: dict, learnt_from: str) -> None:
    """Classes for every tissue voxel of the export that has no label, written into its labels."""
    body, vol, depth, unit = open_export(folder)
    W, D, H = body["dims"]
    px = body["spacing_mm"][0]
    if body.get("labels"):
        table = json.loads((folder / body["label_table"]).read_text())
        labels = np.memmap(folder / body["labels"], np.uint8, "r+", shape=(H, D, W))
    else:
        table = {"dims": [W, D, H], "format": "uint8 object index, 0 = none; layout as body.raw (x left fastest, y up, z back)",
                 "objects": [], "source": "", "licence": "", "credit": ""}
        labels = np.memmap(folder / "labels.raw", np.uint8, "w+", shape=(H, D, W))
        labels[:] = 0
    old = [o["index"] for o in table["objects"] if o["name"].endswith("(by colour)")]   # an earlier run is redone
    table["objects"] = [o for o in table["objects"] if not o["name"].endswith("(by colour)")]
    base = max([o["index"] for o in table["objects"]], default=0)
    if base + len(WRITTEN) > 255:
        raise SystemExit("no room for five more objects")
    idx = {c: base + 1 + i for i, c in enumerate(WRITTEN)}
    counts = {c: 0 for c in WRITTEN}
    for k0 in range(0, D, CHUNK):
        ks = list(range(k0, min(D, k0 + CHUNK)))
        rgba = np.stack([np.asarray(vol[:, k]) for k in ks])
        dep = np.stack([np.asarray(depth[:, k]) for k in ks]).astype(np.float32) * unit
        lab = np.stack([np.asarray(labels[:, k, :]) for k in ks])
        if old:
            lab[np.isin(lab, old)] = 0
        pred = predict(features(rgba, dep, px), probs)
        free = (lab == 0) & (pred > 0)
        # Bone and organs by colour are marrow and dark vessels that fooled the table: they are muscle here;
        # bone comes from the CT.
        muscle = CLASSES.index("muscle") + 1
        for c in ("bone", "organ"):
            pred[pred == CLASSES.index(c) + 1] = muscle
        for i, c in enumerate(WRITTEN):
            sel = free & (pred == CLASSES.index(c) + 1)
            lab[sel] = idx[c]
            counts[c] += int(sel.sum())
        for j, k in enumerate(ks):
            labels[:, k, :] = lab[j]
        if (k0 // CHUNK) % 8 == 0:
            print(f"  slices {k0}-{ks[-1]} of {D}")
    labels.flush()
    for c in WRITTEN:
        table["objects"].append({"index": idx[c], "name": f"{c} (by colour)", "sio_labels": [], "layer": c, "voxels": counts[c]})
    table["by_colour"] = {"learnt_from": learnt_from, "held_out_score": report, "classes": CLASSES, "written": WRITTEN}
    (folder / "labels.json").write_text(json.dumps(table, indent=2))
    body["labels"] = "labels.raw"
    body["label_table"] = "labels.json"
    (folder / "body.json").write_text(json.dumps(body, indent=2))
    print("classed by colour:", {c: counts[c] for c in WRITTEN}, f"-> {folder / 'labels.raw'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", help="the export to class (its unlabelled tissue)")
    ap.add_argument("--from", dest="source", help="the labelled export to learn from (default: the export itself)")
    args = ap.parse_args()
    target = Path(args.export)
    source = Path(args.source) if args.source else target
    probs, report = learn(source)
    apply(target, probs, report, source.name)


if __name__ == "__main__":
    main()
