"""The hip's and the leg's muscles by name, the knee's ligaments and the joints' cartilage: from his own body.

The University of Denver's "3D Models of the Visible Human Male" (Andreassen et al., Sci Data 10, 34, 2023;
CC BY 4.0) has 38 muscles of each leg, from the pelvis to the ankle, segmented on the very cryosections this
body is made of, with the leg's bones, the joints' cartilage and the knee's four ligaments, as STL meshes. In
the labels this body came with, the legs' muscles are one unnamed mass.

Placing them. The meshes are in the Denver set's own millimetres (x to his left, y to his front, z down the
body). BoneHub's bones, which are already in the body (bonehub.py), were segmented on that same set's aligned
CT: so the Denver set's own leg bones are laid on BoneHub's (femur on femur, tibia on tibia, ...) by a
similarity fit through closest points, each bone with its own counterpart, and the muscles, ligaments and
cartilage go by the same fit. What then lies at or outside the skin is drawn under it.

Used: the muscles (not the iliacus, psoas and obturator internus, which the body's own labels already have,
whole), the cartilages and the ligaments. Not used: the bones (BoneHub's are in the body, each named).
The muscles' places are taken out of the body's unnamed muscle mass (`carve`), so each shows as itself.

Kept beside the export (model/du_legs.npz): the placed meshes, so the STL folder is needed once only
(build_model_meshes.py --legs <folder>).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import bonehub
from .common import Body, Structure, decimate
from .skull_bones import similarity

CACHE = "du_legs.npz"
# The set's file names are not spelt alike in its two folders; the names as they are shown.
SPELT = {"illiacus": "iliacus", "semitendonosus": "semitendinosus", "quadratisfemoris": "quadratus femoris", "quadratusfemoris": "quadratus femoris",
         "extensorhallicuslongus": "extensor hallucis longus", "flexorhallicuslongus": "flexor hallucis longus",
         "bicepsfemorislongus": "biceps femoris, long head", "bicepsfemorislong": "biceps femoris, long head", "bicepsfemorisshort": "biceps femoris, short head",
         "gastrocnemiuslateral": "gastrocnemius, lateral head", "gastrocnemiusmedial": "gastrocnemius, medial head", "peroneuslongus": "fibularis (peroneus) longus"}
PARTS = {"Cartilage_FemurDistal": "cartilage of the femur at the knee", "Cartilage_FemurHead": "cartilage of the femur's head", "Cartilage_Patella": "cartilage of the patella",
         "Cartilage_PelvisAcetabulum": "cartilage of the hip socket", "Cartilage_Talus": "cartilage of the talus", "Cartilage_TibiaDistal": "cartilage of the tibia at the ankle",
         "Cartilage_TibiaLateral": "lateral cartilage of the tibia at the knee", "Cartilage_TibiaMedial": "medial cartilage of the tibia at the knee",
         "Cartilage_TibialMedial": "medial cartilage of the tibia at the knee",
         "Ligament_ACL": "anterior cruciate ligament", "Ligament_PCL": "posterior cruciate ligament", "Ligament_MCL": "medial collateral ligament of the knee",
         "Ligament_LCL": "lateral collateral ligament of the knee"}
OURS = ("iliacus", "psoas major", "obturator internus")          # the body's own labels have these, whole
BONES = {"Femur": "femur", "Tibia": "tibia", "Fibula": "fibula", "Patella": "patella", "Pelvis": "hip bone"}       # the set's bone -> BoneHub's name
MUSCLE, CARTILAGE, LIGAMENT = (0.50, 0.23, 0.21), (0.82, 0.86, 0.88), (0.86, 0.80, 0.66)
TRIANGLES = 300_000                    # for all the muscles together
TINTS = [(1.00, 1.00, 1.00), (1.08, 0.98, 0.96), (0.93, 0.97, 1.00), (1.04, 1.05, 0.94), (0.95, 0.92, 0.97), (1.10, 1.04, 1.02), (0.90, 0.93, 0.92)]
MIN_TRIANGLES = 1200


def cache_path(body: Body) -> Path:
    return body.export / "model" / CACHE


def read_stl(path: Path):
    """Vertices (n, 3) and triangles of an STL file, binary or text; the triangles' shared corners joined."""
    raw = path.read_bytes()
    count = int(np.frombuffer(raw[80:84], np.uint32)[0]) if len(raw) >= 84 else -1
    if 84 + 50 * count == len(raw):
        corners = np.frombuffer(raw[84:], np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))["v"].reshape(-1, 3).astype(np.float64)
    else:
        words = np.array(raw.split())
        at = np.nonzero(words == b"vertex")[0]
        corners = np.stack([words[at + 1], words[at + 2], words[at + 3]], axis=1).astype(np.float64)
    v, index = np.unique(np.round(corners, 3), axis=0, return_inverse=True)
    f = index.reshape(-1, 3)
    return v, f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])]


def plain_name(side: str, kind: str, part: str) -> str | None:
    """('Left', 'Muscle', 'VastusLateralis') -> 'left vastus lateralis'; None for what is not used."""
    if kind == "Bone":
        return None
    if kind == "Muscle":
        name = SPELT.get(part.lower()) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", part).lower()
        return None if name in OURS else f"{side.lower()} {name}"
    name = PARTS.get(f"{kind}_{part}")
    return None if name is None else f"{side.lower()} {name}"


def to_body_axes(v: np.ndarray) -> np.ndarray:
    """The set's millimetres (x to his left, y to his FRONT, z down the body: his kneecap has the greater y, his
    buttock the lesser) -> the body's order (z back, y up, x left), still unplaced."""
    return np.stack([-v[:, 1], -v[:, 2], v[:, 0]], axis=1)


def files(folder: Path):
    """[(side, kind, part, path)] of the set's STL files under `folder`."""
    out = []
    for path in sorted(Path(folder).rglob("VHM_*_smooth.stl")):
        bits = path.stem.split("_")                                        # VHM, Left, Muscle, VastusLateralis, smooth
        if len(bits) >= 5 and bits[1] in ("Left", "Right"):
            out.append((bits[1], bits[2], bits[3], path))
    return out


def fit(body: Body, folder: Path, log=print):
    """Lays the set's leg bones on BoneHub's and returns (scale, rotation, shift) for the set's points in the
    body's axes, with what is left between the two sets of bones (mm, per bone)."""
    placed, _, _ = bonehub.load_or_build(body, None, log)
    target = {name: np.asarray(v, np.float64) for _, name, v, _ in placed}
    pairs = []
    for side, kind, part, path in files(folder):
        name = f"{side.lower()} {BONES.get(part, '')}"
        if kind == "Bone" and name in target:
            v, _ = read_stl(path)
            step = max(1, len(v) // 12000)
            pairs.append((name, to_body_axes(v)[::step], cKDTree(target[name]), target[name]))
    if len(pairs) < 4:
        raise SystemExit(f"{folder}: the Denver set's leg bones (VHM_Left_Bone_Femur_smooth.stl, ...) and BoneHub's bones are both needed to place the muscles")
    # To begin: the middles of the paired bones together (the two sets are in the same millimetres, turned alike).
    scale, rotation = 1.0, np.eye(3)
    shift = np.mean([t.mean(axis=0) - s.mean(axis=0) for _, s, _, t in pairs], axis=0)
    for _ in range(40):
        source, goal = [], []
        for _, s, tree, t in pairs:
            now = scale * s @ rotation.T + shift
            distance, index = tree.query(now)
            keep = distance <= np.quantile(distance, 0.85)
            source.append(s[keep])
            goal.append(t[index[keep]])
        scale, rotation, shift = similarity(np.concatenate(source), np.concatenate(goal))
    left = {name: float(np.median(tree.query(scale * s @ rotation.T + shift)[0])) for name, s, tree, _ in pairs}
    log(f"leg muscles: the Denver set's bones laid on BoneHub's: scale {scale:.4f}, between them (median mm): "
        + ", ".join(f"{k} {v:.1f}" for k, v in left.items()))
    return scale, rotation, shift, left


def load_or_build(body: Body, folder: Path | None, log=print):
    """[(name, kind, vertices in the body's millimetres (z, y, x), faces)], kept beside the export; None when
    neither the kept file nor the folder is at hand."""
    path = cache_path(body)
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            table = json.loads(str(z["table"]))
            return [(e["name"], e["kind"], z[f"v{k}"], z[f"f{k}"]) for k, e in enumerate(table["parts"])]
    if folder is None:
        return None
    scale, rotation, shift, left = fit(body, folder, log)
    raw = []
    for side, kind, part, stl in files(folder):
        name = plain_name(side, kind, part)
        if name is None:
            continue
        v, f = read_stl(stl)
        raw.append((name, kind.lower(), (scale * to_body_axes(v) @ rotation.T + shift), f))
    total = sum(len(f) for _, kind, _, f in raw if kind == "muscle")
    share = TRIANGLES / max(1, total)
    parts = []
    for name, kind, v, f in raw:
        goal = max(MIN_TRIANGLES, len(f) * min(1.0, share)) if kind == "muscle" else min(len(f), 2500)
        v, f = decimate(v.astype(np.float32), f, goal)
        parts.append((name, kind, np.asarray(v, np.float32), np.asarray(f, np.uint32)))
    arrays = {}
    for k, (_, _, v, f) in enumerate(parts):
        arrays[f"v{k}"], arrays[f"f{k}"] = v, f
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, table=np.array(json.dumps({"parts": [{"name": n, "kind": k} for n, k, _, _ in parts], "fit_left_mm": left, "scale": scale})), **arrays)
    log(f"leg muscles: {sum(1 for p in parts if p[1] == 'muscle')} muscles, {sum(1 for p in parts if p[1] == 'cartilage')} cartilages and "
        f"{sum(1 for p in parts if p[1] == 'ligament')} ligaments placed, {sum(len(p[3]) for p in parts)} triangles, kept in {path.name}")
    return parts


def solid(body: Body, v_mm: np.ndarray, f: np.ndarray):
    """A closed mesh (the body's millimetres) as voxels of the body's grid: (the block's first voxel, bool block).
    Its surface is marked from points on it no further apart than half a voxel, then each cross-section is filled."""
    from .face_muscles import _dense
    spacing = np.array(body.spacing)
    points = _dense(np.asarray(v_mm, np.float64), np.asarray(f, np.int64), float(spacing.min()) * 0.5)
    index = np.floor(points / spacing).astype(np.int64)
    lo = np.maximum(index.min(axis=0) - 1, 0)
    hi = np.minimum(index.max(axis=0) + 2, np.array(body.dims))
    index = index[((index >= lo) & (index < hi)).all(axis=1)] - lo
    block = np.zeros(tuple(hi - lo), bool)
    block[index[:, 0], index[:, 1], index[:, 2]] = True
    for j in range(block.shape[1]):                                        # the body's cross-sections: a muscle's outline there is a closed ring
        block[:, j, :] = ndimage.binary_fill_holes(block[:, j, :])
    return lo, block


def carve(body: Body, log=print) -> int:
    """Takes the named leg muscles' places out of the body's unnamed muscle mass, and what thin shells and fins
    of the mass are left between them. Returns how many voxels were freed."""
    parts = load_or_build(body, None, log)
    if not parts:
        return 0
    lab = body.labels
    mass = next((o["index"] for o in body.objects if o["name"] == "muscles"), None)
    if mass is None:
        return 0
    freed = 0
    low, high = np.array(lab.shape), np.zeros(3, np.int64)
    for name, kind, v, f in parts:
        if kind != "muscle":
            continue
        lo, block = solid(body, v, f)
        block = ndimage.binary_dilation(block)
        view = lab[lo[0]:lo[0] + block.shape[0], lo[1]:lo[1] + block.shape[1], lo[2]:lo[2] + block.shape[2]]
        hit = block & (view == mass)
        view[hit] = 0
        freed += int(hit.sum())
        low, high = np.minimum(low, lo), np.maximum(high, lo + np.array(block.shape))
    if (high > low).all():
        region = tuple(slice(int(max(0, a - 3)), int(min(d, b + 3))) for a, b, d in zip(low, high, lab.shape))
        left = lab[region] == mass
        thin = left & ~ndimage.binary_opening(left, structure=np.ones((3, 3, 3), bool))
        lab[region][thin] = 0
        freed += int(thin.sum())
    counts = np.bincount(lab.ravel(), minlength=256)
    for o in body.objects:
        o["voxels"] = int(counts[o["index"]])
    log(f"leg muscles: {freed} voxels of the unnamed muscle mass given to the named muscles of the hips and legs")
    return freed


def structures(body: Body, layer: str, baker, occupancy, log=print) -> list[Structure]:
    """The placed parts of one layer: the muscles (layer "muscles"), the cartilages and ligaments ("skeleton")."""
    parts = load_or_build(body, None, log)
    if not parts:
        return []
    from .head_layers import tuck_under_skin
    wanted = ("muscle",) if layer == "muscles" else ("cartilage", "ligament") if layer == "skeleton" else ()
    out = []
    order = sorted({name.split(" ", 1)[1] for name, kind, _, _ in parts if kind == "muscle"})
    for name, kind, v, f in parts:
        if kind not in wanted:
            continue
        g, faces = body.to_gltf(v, f)
        colour = MUSCLE if kind == "muscle" else CARTILAGE if kind == "cartilage" else LIGAMENT
        if kind == "muscle":                                              # a slight tint of its own (the same left and right), so neighbours read apart
            colour = tuple(float(c * t) for c, t in zip(colour, TINTS[order.index(name.split(" ", 1)[1]) % len(TINTS)]))
        out.append(Structure(name, layer, g, faces, colour, info={"class": "muscle" if kind == "muscle" else "bone", "kind": kind,
                                                                 "source": "University of Denver, 3D Models of the Visible Human Male (Andreassen et al. 2023), CC BY 4.0"}))
    if out:
        tuck_under_skin(body, out, least_mm=2.0, log=log)
        for s in out:
            s.bake = baker.colours(s.v, s.f, occupancy, gloss=128 if s.info["kind"] == "muscle" else 150)
        log(f"leg muscles: {len(out)} {'muscles' if layer == 'muscles' else 'cartilages and ligaments'} of the hips and legs, {sum(s.triangles for s in out)} triangles")
    return out
