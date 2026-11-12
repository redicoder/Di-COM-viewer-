"""The skeleton bone by bone, from BoneHub's labels of the Visible Human Male's CT.

BoneHub ("Visible-Human-3d-Models", Alavi and Asseln, Hugging Face 2026, doi:10.57967/hf/10464, CC BY 4.0; based
on Andreassen et al., Sci Data 10, 34 (2023), doi:10.1038/s41597-022-01905-2) labels 142 bones of this same man
on a CT grid of 520 x 552 x 1873 voxels at 0.9375 x 0.9375 x 1 mm: every limb, hand and foot bone, each vertebra
and rib, the cranium and the mandible. Our own labels name bones only in the torso and know the rest as one mass
found by a threshold, at 1.32 x 2 mm. So the skeleton layer takes its bones from BoneHub: finer, and named.

The files are 3D Slicer segmentations (.seg.nrrd): one or two label layers per file, each segment a value in a
layer. Each bone is meshed on its own block of the native grid; the grid is then fitted to the body by matching
BoneHub's bones as a whole to the export's own bone voxels (a shift along each axis, found by search), and the
vertices moved by that fit.

    bones = read(folder)             # [(name, vertices in BoneHub millimetres (x, y, z of its grid), faces)]
    fit = register(body, folder)     # how BoneHub's millimetres map to the body's (array order z, y, x)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from scipy import ndimage

from .common import Body, surface

FILES = ["SKULL", "SPINAL_COLUMN", "THORAX", "UPPER_EXTREMITY_LEFT", "UPPER_EXTREMITY_RIGHT", "LOWER_EXTREMITY_LEFT", "LOWER_EXTREMITY_RIGHT",
         "HAND_LEFT", "HAND_RIGHT", "FOOT_LEFT", "FOOT_RIGHT"]
SPACING = (1.0, 0.9375, 0.9375)                     # mm, the arrays' order: slices, rows, columns
DIGITS = {"1": "thumb", "2": "index finger", "3": "middle finger", "4": "ring finger", "5": "little finger"}
TOES = {"1": "great toe", "2": "second toe", "3": "third toe", "4": "fourth toe", "5": "little toe"}


def plain_name(code: str) -> str:
    """BoneHub's segment name as the labels name things: FEMUR_LEFT -> left femur, VERTEBRA_T4 -> thoracic vertebra T4."""
    side = ""
    m = re.search(r"_(LEFT|RIGHT)$", code)
    if m:
        side, code = m.group(1).lower() + " ", code[:m.start()]
    m = re.fullmatch(r"VERTEBRA_([CTL])(\d+)", code)
    if m:
        return {"C": "cervical", "T": "thoracic", "L": "lumbar"}[m.group(1)] + f" vertebra {m.group(1)}{m.group(2)}"
    m = re.fullmatch(r"RIB_(\d+)", code)
    if m:
        return f"{side}rib {m.group(1)}"
    m = re.fullmatch(r"(METACARPAL|METATARSAL)_(\d)", code)
    if m:
        return f"{side}{m.group(1).lower()} {m.group(2)}"
    m = re.fullmatch(r"PHALANGE_(HAND|FOOT)_(\d)", code)
    if m:
        return f"phalanges of the {side}{(DIGITS if m.group(1) == 'HAND' else TOES)[m.group(2)]}"
    special = {"SKULL_CRANIAL_MAXILLA": "cranium and maxilla", "SKULL_MANDIBLE": "mandible", "HIP": "hip bone", "SACRUM": "sacrum", "STERNUM": "sternum"}
    return side + special.get(code, code.lower().replace("_", " "))


def segments(path: Path):
    """Yields (name, mask block bool (slices, rows, columns), the block's first voxel) for every segment of a file."""
    import SimpleITK as sitk
    image = sitk.ReadImage(str(path))
    keys = set(image.GetMetaDataKeys())
    array = sitk.GetArrayFromImage(image)                     # (slices, rows, columns[, layers])
    if array.ndim == 3:
        array = array[..., None]
    table = []
    for key in keys:
        if key.endswith("_Name"):
            seg = key[:-5]
            table.append((image.GetMetaData(key), int(image.GetMetaData(seg + "_LabelValue")), int(image.GetMetaData(seg + "_Layer")) if seg + "_Layer" in keys else 0))
    for layer in sorted({t[2] for t in table}):
        volume = np.ascontiguousarray(array[..., layer])
        boxes = ndimage.find_objects(volume.astype(np.int32), max_label=int(volume.max()))
        for name, value, its_layer in table:
            if its_layer != layer or value < 1 or value > len(boxes) or boxes[value - 1] is None:
                continue
            box = boxes[value - 1]
            yield name, volume[box] == value, tuple(s.start for s in box)


def read(folder: Path, log=print):
    """Every bone as a mesh on BoneHub's own grid: [(code, plain name, vertices (n, 3) mm in the arrays' order, faces)],
    and the bones together as a coarse occupancy (every second voxel) for the fit."""
    folder = Path(folder)
    out, union = [], None
    for stem in FILES:
        path = folder / f"{stem}.seg.nrrd"
        if not path.exists():
            log(f"bonehub: {path.name} is missing")
            continue
        for code, block, origin in segments(path):
            if union is None:
                union = np.zeros((937, 276, 260), bool)
            z, y, x = np.nonzero(block[::2, ::2, ::2])
            zz, yy, xx = (z * 2 + origin[0] + 1) // 2, (y * 2 + origin[1] + 1) // 2, (x * 2 + origin[2] + 1) // 2
            ok = (zz < union.shape[0]) & (yy < union.shape[1]) & (xx < union.shape[2])
            union[zz[ok], yy[ok], xx[ok]] = True
            # One solid bone: marrow spaces and thin plates closed, a light blur, contoured at the voxels' own size.
            solid = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(block, 2), iterations=1))[2:-2, 2:-2, 2:-2] | block
            got = surface(solid, SPACING, 0.8, origin)
            if got is not None and len(got[1]) >= 8:
                out.append((code, plain_name(code), got[0], got[1]))
        log(f"bonehub: {stem}: {len(out)} bones so far")
    return out, union


class Fit:
    """BoneHub millimetres (arrays' order: slices, rows, columns) -> the body's millimetres (array order z, y, x)."""

    def __init__(self, order, sign, shift):
        self.order, self.sign, self.shift = tuple(order), tuple(sign), tuple(shift)

    def apply(self, v_mm: np.ndarray) -> np.ndarray:
        v = np.asarray(v_mm, np.float64)
        return np.stack([self.sign[k] * v[:, self.order[k]] + self.shift[k] for k in range(3)], axis=1)

    def to_json(self) -> dict:
        return {"order": list(self.order), "sign": list(self.sign), "shift_mm": [float(s) for s in self.shift]}

    @staticmethod
    def from_json(d: dict) -> "Fit":
        return Fit(d["order"], d["sign"], d["shift_mm"])


def register(body: Body, union: np.ndarray, log=print) -> tuple[Fit, float]:
    """The fit of BoneHub's grid to the body, and how well the bones then agree (Dice of the two bone masks).

    The two grids show the same man with the same axes up to direction: BoneHub's slices run along the body, its
    rows front to back, its columns across. For each of the eight ways of turning the axes round, the shift along
    each axis comes from matching where the bone lies along that axis; the turning whose bones agree best wins."""
    ours = np.isin(body.labels, [o["index"] for o in body.objects if o["layer"] == "bone"])
    our_spacing = np.array(body.spacing)                                  # z (back), y (up), x (left)
    their_spacing = np.array(SPACING) * 2.0                               # union is every second voxel
    # Their axis for each of ours: z (front-back) <- rows, y (along the body) <- slices, x (across) <- columns.
    order = (1, 0, 2)
    their = np.transpose(union, order)
    spacing = their_spacing[list(order)]
    step = 1.0                                                            # mm resolution of the profiles
    best = None
    for flips in np.ndindex(2, 2, 2):
        t = their
        for axis, flip in enumerate(flips):
            if flip:
                t = np.flip(t, axis)
        shifts, score = [], 0.0
        for axis in range(3):
            other = tuple(a for a in range(3) if a != axis)
            p_ours = ours.sum(axis=other).astype(np.float64)
            p_their = t.sum(axis=other).astype(np.float64)
            a = np.interp(np.arange(0, len(p_ours) * our_spacing[axis], step), (np.arange(len(p_ours)) + 0.5) * our_spacing[axis], p_ours)
            b = np.interp(np.arange(0, len(p_their) * spacing[axis], step), (np.arange(len(p_their)) + 0.5) * spacing[axis], p_their)
            a, b = a / max(a.sum(), 1e-9), b / max(b.sum(), 1e-9)
            corr = np.correlate(a, b, mode="full")
            lag = int(np.argmax(corr)) - (len(b) - 1)                     # ours = theirs moved by lag * step
            shifts.append(lag * step)
            score += float(corr.max()) / max(float(np.sqrt((a * a).sum() * (b * b).sum())), 1e-12)
        if best is None or score > best[0]:
            best = (score, flips, shifts)
    _, flips, shifts = best
    sign, shift = [], []
    for axis in range(3):
        length = their.shape[axis] * spacing[axis]
        # A flipped axis: position p becomes length - p.
        sign.append(-1.0 if flips[axis] else 1.0)
        shift.append(shifts[axis] + (length if flips[axis] else 0.0))
    fit = Fit(order, sign, shift)
    # Refine the shifts by a small search on the masks themselves, and measure the agreement.
    zz, yy, xx = np.nonzero(union)
    pts = np.stack([zz, yy, xx], axis=1)[::7] * (np.array(SPACING) * 2.0) + np.array(SPACING)
    dims = np.array(ours.shape)

    def overlap(f: Fit) -> float:
        idx = np.floor(f.apply(pts) / our_spacing).astype(np.int64)
        ok = ((idx >= 0) & (idx < dims)).all(axis=1)
        return float(ours[idx[ok, 0], idx[ok, 1], idx[ok, 2]].sum()) / max(1, len(pts))

    current, score = fit, overlap(fit)
    for radius in (4.0, 2.0, 1.0, 0.5):
        improved = True
        while improved:
            improved = False
            for axis in range(3):
                for delta in (-radius, radius):
                    s = list(current.shift)
                    s[axis] += delta
                    trial = Fit(order, sign, s)
                    value = overlap(trial)
                    if value > score + 1e-6:
                        current, score, improved = trial, value, True
    log(f"bonehub: fitted to the body: axes turned {flips}, shift {[round(s, 1) for s in current.shift]} mm, {score * 100:.0f} % of BoneHub's bone voxels fall on ours")
    return current, score


def cache_path(body: Body) -> Path:
    return body.export / "model" / "bonehub.npz"


def load_or_build(body: Body, folder: Path, log=print):
    """[(code, name, vertices in the body's millimetres (z, y, x), faces)] and the fit; cached beside the export."""
    path = cache_path(body)
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            table = json.loads(str(z["table"]))
            return [(e["code"], e["name"], z[f"v{k}"], z[f"f{k}"]) for k, e in enumerate(table["bones"])], Fit.from_json(table["fit"]), table["score"]
    bones, union = read(folder, log)
    fit, score = register(body, union, log)
    placed = [(code, name, fit.apply(v).astype(np.float32), f.astype(np.uint32)) for code, name, v, f in bones]
    arrays = {}
    for k, (_, _, v, f) in enumerate(placed):
        arrays[f"v{k}"], arrays[f"f{k}"] = v, f
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, table=np.array(json.dumps({"bones": [{"code": c, "name": n} for c, n, _, _ in placed], "fit": fit.to_json(), "score": score})), **arrays)
    return placed, fit, score
