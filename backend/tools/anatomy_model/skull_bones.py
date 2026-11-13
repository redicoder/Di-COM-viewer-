"""The skull in its bones: the frontal, the two parietals, the occipital, the temporals, the sphenoid, the maxillae,
the zygomatic bones and the small bones of the nose and the orbit, each its own named mesh.

His skull is one mesh (BoneHub's "cranium and maxilla", from his own CT); the sutures between its bones are finer
than the CT shows. Which part of it is which bone is carried across from an atlas that has the bones apart:
BodyParts3D 4.0 (a generic adult male; the LSDB Archive's copy). The atlas's skull is laid on his (axes, then a
similarity fit by closest points), then drawn onto it without tearing (closest points again, the pull smoothed over
a width that shrinks from 40 to 6 mm), and every triangle of HIS skull takes the name of the atlas bone that then
lies nearest. No vertex of the atlas enters the model: the shapes are his, only the lines between the bones are
the atlas's, and so they are where sutures lie on a skull of this shape, not where his own are.

Kept beside the export (model/skull_bones.npz): the fitted atlas points with their bones, so the atlas itself is
needed once only (build_model_meshes.py --atlas <folder>).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .common import Body, Structure, normals_of, outward

CACHE = "skull_bones.npz"
WHOLE = "cranium and maxilla"                          # BoneHub's name for his skull without the mandible
SIDED = ("parietal bone", "temporal bone", "maxilla", "zygomatic bone", "nasal bone", "lacrimal bone", "palatine bone", "inferior nasal concha")
SINGLE = ("frontal bone", "occipital bone", "sphenoid bone", "ethmoid", "vomer")
NAMES = list(SINGLE) + [f"{side} {name}" for name in SIDED for side in ("right", "left")]
SHOWN = {"ethmoid": "ethmoid bone"}                    # the atlas's name -> the name shown, where they differ
MIN_TRIANGLES = 60                                     # a bone with fewer triangles on his skull is given to its neighbour
PIECE_SHARE = 0.12                                     # of a bone's separate pieces, those under this share of its biggest go to the bone round them
SPREAD = 26                                            # rounds of spreading the votes over the mesh: the lines between bones run smooth
# A bone's own tint on the common bone colour (the same for a left and a right bone): enough to tell neighbours
# apart, not enough to look painted; all of them bone's own warm whites and greys, no two that touch alike.
PLAIN, YELLOWISH, GREYISH, PINKISH, DARKER = (1.00, 1.00, 1.00), (0.985, 0.975, 0.90), (0.955, 0.955, 0.965), (1.00, 0.955, 0.94), (0.95, 0.94, 0.90)
TINTS = {"frontal bone": PLAIN, "parietal bone": YELLOWISH, "occipital bone": GREYISH, "temporal bone": PINKISH, "sphenoid bone": DARKER, "zygomatic bone": YELLOWISH,
         "maxilla": GREYISH, "nasal bone": PINKISH, "ethmoid": YELLOWISH, "vomer": PLAIN, "palatine bone": YELLOWISH, "lacrimal bone": PLAIN, "inferior nasal concha": PINKISH}


def cache_path(body: Body) -> Path:
    return body.export / "model" / CACHE


def read_obj(path: Path):
    """Vertices (n, 3) and triangles of a Wavefront file (faces with more corners are fanned)."""
    v, f = [], []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            v.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            corners = [int(c.split("/")[0]) - 1 for c in line.split()[1:]]
            f += [(corners[0], corners[k], corners[k + 1]) for k in range(1, len(corners) - 1)]
    return np.array(v, np.float64), np.array(f, np.int64)


def read_atlas(folder: Path, log=print):
    """The atlas's skull bones: [(name, vertices, faces)] in the atlas's millimetres turned to the body's axes
    (array order z, y, x: back, up, to his left). The atlas has x across, y front to back, z up."""
    folder = Path(folder)
    table = folder / "isa_element_parts.txt"
    files = {p.stem: p for p in folder.rglob("*.obj")}
    if not table.exists() or not files:
        raise SystemExit(f"{folder}: BodyParts3D's isa_element_parts.txt and its .obj files are needed (see LICENSES.md for where they come from)")
    wanted = {}
    for line in table.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1].strip().lower() in NAMES:
            wanted.setdefault(parts[1].strip().lower(), []).append(parts[2].strip())
    bones = []
    for name in NAMES:
        ids = [i for i in wanted.get(name, []) if i in files]
        if not ids:
            log(f"skull bones: the atlas has no {name}")
            continue
        v, f = read_obj(files[ids[0]])
        bones.append((name, np.stack([v[:, 1], v[:, 2], v[:, 0]], axis=1), f))
    # Which way the atlas's x runs: its left parietal must come out on the body's left (greater x).
    middle = {n: v[:, 2].mean() for n, v, _ in bones}
    if "left parietal bone" in middle and "right parietal bone" in middle and middle["left parietal bone"] < middle["right parietal bone"]:
        bones = [(n, v * np.array([1.0, 1.0, -1.0]), f) for n, v, f in bones]
    return bones


def similarity(source: np.ndarray, target: np.ndarray):
    """Scale, rotation and shift that lay `source` on `target` (paired points) in the least squares sense (Umeyama)."""
    ms, mt = source.mean(axis=0), target.mean(axis=0)
    a, b = source - ms, target - mt
    u, d, vt = np.linalg.svd(b.T @ a / len(a))
    sign = np.sign(np.linalg.det(u @ vt))
    fix = np.diag([1.0, 1.0, sign])
    rotation = u @ fix @ vt
    scale = float((d * np.diag(fix)).sum() / (a ** 2).sum() * len(a))
    return scale, rotation, mt - scale * rotation @ ms


def lay_on(points: np.ndarray, target: np.ndarray, rounds: int = 40, keep: float = 0.85, log=print):
    """A similarity fit by closest points (the worst pairs left out each round). Returns the points laid on the
    target and the rotation that was applied in all (for their normals)."""
    tree = cKDTree(target)
    # To begin: middles together, sizes alike.
    out = (points - points.mean(axis=0)) * (target.std(axis=0).mean() / points.std(axis=0).mean()) + target.mean(axis=0)
    step = max(1, len(out) // 20000)
    turned = np.eye(3)
    for _ in range(rounds):
        distance, index = tree.query(out[::step])
        good = distance <= np.quantile(distance, keep)
        scale, rotation, shift = similarity(out[::step][good], target[index[good]])
        out = scale * out @ rotation.T + shift
        turned = rotation @ turned
    distance, _ = tree.query(out[::step])
    log(f"skull bones: the atlas laid on his skull as a whole: its points lie {np.median(distance):.1f} mm from his (median), {np.quantile(distance, 0.9):.1f} mm (9 in 10)")
    return out, turned


def draw_onto(points: np.ndarray, normals: np.ndarray, target: np.ndarray, target_normals: np.ndarray, widths=(40, 30, 22, 16, 12, 9, 7, 6, 6), log=print):
    """Draws the laid-on atlas onto his skull without tearing it. Each round every control point is pulled towards
    his nearest surface point that faces the same way, and his surface points pull their nearest control point; the
    pulls are averaged over a Gaussian width (mm) before they are applied, a narrower one each round, so first whole
    regions move and at last the detail. Returns the points drawn on."""
    out = points.copy()
    target_tree = cKDTree(target)
    rng = np.random.default_rng(5)
    control = rng.choice(len(out), min(9000, len(out)), replace=False)
    pullers = rng.choice(len(target), min(30000, len(target)), replace=False)
    for width in widths:
        c = out[control]
        pull = np.zeros_like(c)
        weight = np.zeros(len(c))
        distance, index = target_tree.query(c, k=4)
        facing = np.einsum("ij,ikj->ik", normals[control], target_normals[index]) > 0.2
        near = distance < 3.0 * width
        for k in range(4):                                                    # the nearest of the four that faces the same way
            take = facing[:, k] & near[:, k] & (weight == 0)
            pull[take] = target[index[take, k]] - c[take]
            weight[take] = 1.0
        control_tree = cKDTree(c)
        back_distance, back = control_tree.query(target[pullers])
        ok = (back_distance < 2.0 * width) & (np.einsum("ij,ij->i", target_normals[pullers], normals[control][back]) > 0.2)
        np.add.at(pull, back[ok], target[pullers][ok] - c[back[ok]])
        np.add.at(weight, back[ok], 1.0)
        pull /= np.maximum(weight, 1.0)[:, None]
        has = weight > 0
        # The pulls smoothed over the width, and handed to every point from the control points round it.
        smooth = _blur(c[has], pull[has], c, width)
        out += 0.85 * _blur(c, smooth, out, width * 0.5)
    distance, _ = target_tree.query(out[control])
    log(f"skull bones: the atlas drawn onto his skull: its points lie {np.median(distance):.2f} mm from his (median), {np.quantile(distance, 0.9):.2f} mm (9 in 10)")
    return out


def _blur(at: np.ndarray, values: np.ndarray, where: np.ndarray, width: float, k: int = 48) -> np.ndarray:
    """Values given at points, averaged with a Gaussian of `width` round each of `where` (from its k nearest)."""
    tree = cKDTree(at)
    distance, index = tree.query(where, k=min(k, len(at)))
    w = np.exp(-0.5 * (distance / width) ** 2) + 1e-12
    return (values[index] * w[..., None]).sum(axis=1) / w.sum(axis=1, keepdims=True)


def fit_atlas(body: Body, folder: Path, cranium_v: np.ndarray, cranium_f: np.ndarray, log=print):
    """Fits the atlas to his cranium (vertices in the body's millimetres) and keeps the fitted points with their bones."""
    bones = read_atlas(folder, log)
    points = np.concatenate([v for _, v, _ in bones])
    normals = np.concatenate([_normals(v, f) for _, v, f in bones])
    label = np.concatenate([np.full(len(v), k, np.uint8) for k, (_, v, _) in enumerate(bones)])
    names = [n for n, _, _ in bones]
    target = np.asarray(cranium_v, np.float64)
    target_normals = _normals(target, np.asarray(cranium_f, np.int64))
    laid, turned = lay_on(points, target, log=log)
    drawn = draw_onto(laid, normals @ turned.T, target, target_normals, log=log)
    path = cache_path(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, points=drawn.astype(np.float32), label=label, names=np.array(json.dumps(names)))
    log(f"skull bones: {len(names)} of the atlas's bones fitted to his skull, kept in {path.name}")
    return drawn, label, names


def _normals(v_mm: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Outward vertex normals of a closed mesh given in the body's array order (z, y, x), in that order."""
    g = np.stack([v_mm[:, 2], v_mm[:, 1], -v_mm[:, 0]], axis=1)
    n = normals_of(g, outward(g, f))
    return np.stack([-n[:, 2], n[:, 1], n[:, 0]], axis=1).astype(np.float64)


def load(body: Body):
    path = cache_path(body)
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as z:
        return z["points"].astype(np.float64), z["label"], json.loads(str(z["names"]))


def name_triangles(v_mm: np.ndarray, f: np.ndarray, points: np.ndarray, label: np.ndarray, count: int, log=print) -> np.ndarray:
    """A bone (index) for every triangle of his skull. Each vertex is voted for by the fitted atlas points nearest
    to it; the votes are spread over the mesh a little (so the line between two bones runs smoothly and not from
    triangle to triangle as the nearest point happens to fall); each triangle takes its corners' winner. Then the
    patches are tidied: of a bone's connected pieces only those of some size stand (a bone has an outer and an inner
    face, so more than one piece can be right); the rest go to the bone round them."""
    from scipy import sparse
    tree = cKDTree(points)
    _, index = tree.query(v_mm, k=5)
    votes = np.zeros((len(v_mm), count), np.float32)
    for k in range(5):
        np.add.at(votes, (np.arange(len(v_mm)), label[index[:, k]]), 1.0)
    pairs = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    pairs = np.concatenate([pairs, pairs[:, ::-1]])
    link = sparse.coo_matrix((np.ones(len(pairs), np.float32), (pairs[:, 0], pairs[:, 1])), shape=(len(v_mm), len(v_mm))).tocsr()
    link.data[:] = 1.0
    degree = np.maximum(np.asarray(link.sum(axis=1)).ravel(), 1.0)
    for _ in range(SPREAD):
        votes = 0.5 * votes + 0.5 * (link @ votes) / degree[:, None]
    tri = votes[f].sum(axis=1).argmax(axis=1)
    # Neighbours over an edge.
    edges = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    owner = np.tile(np.arange(len(f)), 3)
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges, owner = edges[order], owner[order]
    same = (edges[1:] == edges[:-1]).all(axis=1)
    a, b = owner[:-1][same], owner[1:][same]
    for _ in range(4):
        joined = sparse.coo_matrix((np.ones(int((tri[a] == tri[b]).sum()), np.int8), (a[tri[a] == tri[b]], b[tri[a] == tri[b]])), shape=(len(f), len(f)))
        _, root = sparse.csgraph.connected_components(joined, directed=False)
        size = np.bincount(root)
        biggest = np.zeros(count, np.int64)
        np.maximum.at(biggest, tri, size[root])
        small = (size[root] < MIN_TRIANGLES) | (size[root] < PIECE_SHARE * biggest[tri])
        if not small.any():
            break
        tally = np.zeros((int(root.max()) + 1, count), np.int32)
        for p, q in ((a, b), (b, a)):
            border = small[p] & ~small[q]                                     # an edge from a small patch to what stands
            np.add.at(tally, (root[p[border]], tri[q[border]]), 1)
        change = small & (tally.sum(axis=1) > 0)[root]
        tri = np.where(change, tally.argmax(axis=1)[root], tri)
    return tri


def split(body: Body, skull: Structure, log=print) -> list[Structure]:
    """His skull's mesh as its bones (the fitted atlas at hand: model/skull_bones.npz), or the skull as it is."""
    got = load(body)
    if got is None:
        return [skull]
    points, label, names = got
    v = np.asarray(skull.v, np.float64)
    f = np.asarray(skull.f, np.int64)
    v_mm = np.stack([-v[:, 2] * 1000.0 + body.size_mm[2] / 2, v[:, 1] * 1000.0 + body.size_mm[1] / 2, v[:, 0] * 1000.0 + body.size_mm[0] / 2], axis=1)
    tri = name_triangles(v_mm, f, points, label, len(names), log)
    # Where two bones meet: the line between them a little darker, as a suture is.
    least, most = np.full(len(v), len(names), np.int64), np.full(len(v), -1, np.int64)
    for corner in range(3):
        np.minimum.at(least, f[:, corner], tri)
        np.maximum.at(most, f[:, corner], tri)
    seam = most > least
    out, report = [], []
    for k, name in enumerate(names):
        mine = f[tri == k]
        if len(mine) == 0:
            continue
        used = np.unique(mine)
        remap = np.full(len(v), -1, np.int64)
        remap[used] = np.arange(len(used))
        bake = None if skull.bake is None else skull.bake[used].copy()
        if bake is not None:
            bake[seam[used], 0] = np.round(bake[seam[used], 0] * 0.74)
        tint = TINTS.get(name.replace("left ", "").replace("right ", ""), PLAIN)
        colour = tuple(float(c * t) for c, t in zip(skull.colour, tint))
        albedo = None if skull.albedo is None else skull.albedo[used]
        shown = SHOWN.get(name, name)
        out.append(Structure(shown, skull.layer, skull.v[used], remap[mine].astype(np.uint32), colour, bake=bake, albedo=albedo,
                             info={"class": "bone", "source": "BoneHub's cranium; the bone's outline from BodyParts3D 4.0 fitted to it", "part_of": skull.name}))
        report.append(f"{shown} {len(mine)}")
    log("skull bones (triangles): " + "; ".join(report))
    return out or [skull]
