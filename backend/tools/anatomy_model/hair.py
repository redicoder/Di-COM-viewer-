"""Hair as geometry: every hair a short ribbon grown from the skin (brows, lashes, stubble of scalp and beard,
the hair of chest, arms and legs).

A hair is far thinner than a pixel, so no texture can hold it and a card of painted hair reads as a flake at
close range; a strand of its own is the only form that holds up (docs/research/realtime_skin_hair.md). The body
does not move, so the strands are static. Each strand is a centre line of a few segments; both vertices of every
ring sit ON the centre line, and Unity's LabHair.shader pushes them apart to the hair's width facing the camera
(never under a pixel wide, with the coverage in alpha), so the file stores no width in its positions.

Per vertex: POSITION the centre line, NORMAL the skin's normal at the root (hair is lit and shadowed with the
skin it grows from), TANGENT the strand's direction, TEXCOORD_0 = (side -1/+1, distance along the strand 0..1),
TEXCOORD_1 = (width in mm at this point, the strand's random seed 0..1), COLOR_0 = the hair's colour (sRGB).

Roots are scattered by area and by the region's weight (zones.regions); directions follow the hair streams of
the body (Kidd 1903, via docs/research/skin_features_hair_maps.md): a whorl on the crown, down the cheeks and the
legs, along the brow towards the temple, towards the hand on the arm, down and towards the midline on the chest.
Densities are what a renderer needs to read as that hair, below the real follicle counts.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .common import Structure
from .zones import MM, Face

RIBBON_COLOUR_ALPHA = 255


@dataclass
class Kind:
    name: str
    density: float              # strands per cm2 where the region's weight is 1
    length: tuple               # mm, shortest and longest
    width_um: float             # at the root
    tip: float                  # width at the tip as a share of the root's (1 = cut stubble, 0.15 = a fine tip)
    segments: int
    tilt: float                 # degrees from the skin's normal at the root
    bend: float                 # how strongly the strand turns to lie along the stream
    colour: tuple               # sRGB 0..255
    curl_mm: float = 0.0        # radius of the helix at the tip
    turns: float = 0.0
    spread: float = 22.0        # degrees of random turn about the normal


KINDS = {
    "scalp": Kind("scalp", 110, (0.9, 2.0), 75, 1.0, 1, 42, 0.0, (72, 52, 36), spread=18),
    "beard": Kind("beard", 48, (0.4, 1.0), 120, 1.0, 1, 50, 0.0, (84, 58, 40), spread=25),
    "brow": Kind("brow", 130, (6.0, 11.0), 70, 0.2, 5, 68, 1.3, (58, 42, 30), spread=14),
    "chest": Kind("chest", 20, (14.0, 30.0), 70, 0.25, 7, 72, 0.5, (96, 70, 50), curl_mm=2.2, turns=1.4),
    "belly_line": Kind("belly_line", 22, (10.0, 22.0), 70, 0.25, 6, 72, 0.5, (96, 70, 50), curl_mm=1.8, turns=1.2),
    "forearm": Kind("forearm", 12, (9.0, 18.0), 55, 0.25, 5, 74, 0.6, (96, 70, 50), curl_mm=1.0, turns=0.5),
    "upper_arm": Kind("upper_arm", 7, (6.0, 14.0), 50, 0.25, 5, 74, 0.6, (96, 70, 50), curl_mm=1.0, turns=0.5),
    "thigh": Kind("thigh", 8, (11.0, 22.0), 65, 0.25, 5, 74, 0.6, (96, 70, 50), curl_mm=2.5, turns=0.5),
    "shin": Kind("shin", 6, (11.0, 22.0), 75, 0.25, 5, 74, 0.6, (96, 70, 50), curl_mm=2.5, turns=0.5),
}
LASH = Kind("lashes", 0, (7.0, 11.0), 95, 0.12, 6, 0, 0.0, (40, 29, 22))


def unit(a: np.ndarray) -> np.ndarray:
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-12)


def streams(v: np.ndarray, n: np.ndarray, info: dict) -> dict:
    """The direction hair grows in, per vertex and per region, before it is laid into the skin's tangent plane."""
    k = len(v)
    down = np.tile(np.array([0.0, -1.0, 0.0]), (k, 1))
    out = {"thigh": down, "shin": down}
    face: Face | None = info.get("face")
    if face is not None:
        u, w, _ = face.local(v)
        # The scalp: outward from the crown's whorl, turned about the normal (a clockwise spiral).
        radial = v - info["crown"]
        radial -= n * np.einsum("ij,ij->i", radial, n)[:, None]
        out["scalp"] = unit(radial) * np.cos(np.radians(35)) + np.cross(n, unit(radial)) * np.sin(np.radians(35))
        out["beard"] = np.tile(-face.ey + 0.2 * face.ez, (k, 1))
        # The brow: up at its head by the nose, towards the temple along its body, a little down at the tail.
        sign = np.where(u >= 0, 1.0, -1.0)
        along = np.clip((sign * u - face.half_ipd + 17.0) / 47.0, 0, 1)
        out["brow"] = sign[:, None] * face.ex * (0.35 + along)[:, None] + face.ey * np.clip(0.95 - 1.7 * along, -0.35, 0.95)[:, None]
    if "sternum" in info:
        notch_y, _, mid_x = info["sternum"]
        inward = -np.sign(v[:, 0] - mid_x)
        vertical = np.where(v[:, 1] > notch_y - 0.05, 1.0, -1.0)                 # the parting at the sternal angle
        out["chest"] = np.stack([0.45 * inward, vertical, np.zeros(k)], axis=1)
        out["belly_line"] = np.stack([0.8 * inward, -0.6 * np.ones(k), np.zeros(k)], axis=1)
        arm = np.zeros((k, 3))
        for side, is_side in (("left", v[:, 0] > mid_x), ("right", v[:, 0] <= mid_x)):
            if f"arm_{side}" in info:
                shoulder, wrist = info[f"arm_{side}"]
                arm[is_side] = unit(wrist - shoulder)
        out["forearm"] = out["upper_arm"] = arm
    return out


def ribbons(roots: np.ndarray, normals: np.ndarray, flow: np.ndarray, kind: Kind, rng: np.random.Generator, length_scale=None):
    """Strands from roots: (vertices (m, 3), streams dict, faces (t, 3)). All arrays float32 / uint32."""
    k, seg = len(roots), kind.segments
    n = unit(normals)
    d = unit(flow - n * np.einsum("ij,ij->i", flow, n)[:, None])
    s = np.cross(n, d)
    tilt = np.radians(kind.tilt + rng.normal(0, 6, k))
    az = np.radians(rng.normal(0, kind.spread, k))
    t = unit(n * np.cos(tilt)[:, None] + (d * np.cos(az)[:, None] + s * np.sin(az)[:, None]) * np.sin(tilt)[:, None])
    length = rng.uniform(kind.length[0], kind.length[1], k) * (1.0 if length_scale is None else length_scale) * MM
    points = [roots.astype(np.float64)]
    p = roots.astype(np.float64).copy()
    for _ in range(seg):
        p = p + t * (length / seg)[:, None]
        t = unit(t + (d * kind.bend - n * 0.25 * kind.bend) / seg)
        points.append(p.copy())
    pts = np.stack(points, axis=1)                                             # (k, seg + 1, 3)
    along = np.linspace(0.0, 1.0, seg + 1)
    if kind.curl_mm > 0:
        a = unit(np.cross(pts[:, -1] - pts[:, 0], n) + 1e-9)
        b = unit(np.cross(a, pts[:, -1] - pts[:, 0]))
        phase = rng.uniform(0, 2 * np.pi, k)[:, None] + 2 * np.pi * kind.turns * along[None, :] * rng.uniform(0.6, 1.3, k)[:, None]
        radius = (kind.curl_mm * MM * rng.uniform(0.5, 1.2, k))[:, None] * along[None, :]
        pts = pts + (np.cos(phase) * radius)[..., None] * a[:, None, :] + (np.sin(phase) * radius)[..., None] * b[:, None, :]
    # No hair may sink into the skin it grows from.
    height = np.einsum("ksj,kj->ks", pts - roots[:, None, :], n)
    floor = 0.00015 * np.minimum(1.0, along * seg)[None, :]
    pts = pts + (np.maximum(floor - height, 0.0))[..., None] * n[:, None, :]
    tangent = np.empty_like(pts)
    tangent[:, 1:-1] = pts[:, 2:] - pts[:, :-2]
    tangent[:, 0] = pts[:, 1] - pts[:, 0]
    tangent[:, -1] = pts[:, -1] - pts[:, -2]
    tangent = unit(tangent)
    width = (kind.width_um * 0.001) * (1.0 - (1.0 - kind.tip) * along ** 2)[None, :] * rng.uniform(0.8, 1.15, k)[:, None]
    seed = rng.uniform(0, 1, k)
    rings = seg + 1
    m = k * rings * 2
    pos = np.repeat(pts.reshape(k * rings, 3), 2, axis=0).astype(np.float32)
    side = np.tile(np.array([-1.0, 1.0], np.float32), k * rings)
    uv0 = np.stack([side, np.repeat(np.tile(along, k), 2)], axis=1).astype(np.float32)
    uv1 = np.stack([np.repeat(width.reshape(-1), 2), np.repeat(np.repeat(seed, rings), 2)], axis=1).astype(np.float32)
    tan4 = np.concatenate([np.repeat(tangent.reshape(k * rings, 3), 2, axis=0), np.ones((m, 1))], axis=1).astype(np.float32)
    nor = np.repeat(np.repeat(n, rings, axis=0), 2, axis=0).astype(np.float32)
    shade = rng.uniform(0.85, 1.12, k)                                         # no two hairs quite the same brown
    colour = np.clip(np.array(kind.colour, np.float64)[None, :] * shade[:, None], 0, 255)
    col = np.concatenate([np.repeat(np.repeat(colour, rings, axis=0), 2, axis=0), np.full((m, 1), RIBBON_COLOUR_ALPHA)], axis=1).astype(np.uint8)
    base = (np.arange(k)[:, None] * rings + np.arange(seg)[None, :]).reshape(-1) * 2
    faces = np.concatenate([np.stack([base, base + 1, base + 2], axis=1), np.stack([base + 1, base + 3, base + 2], axis=1)]).astype(np.uint32)
    return pos, {"NORMAL": nor, "TANGENT": tan4, "TEXCOORD_0": uv0, "TEXCOORD_1": uv1, "COLOR_0": col}, faces


def scatter(v, f, n, weight, density_cm2, rng):
    """Random roots on the mesh: by area and by the region's weight. Returns positions, normals, the triangle of
    each root and its barycentric weights."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area_cm2 = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2 * 1e4
    w = weight[f].mean(axis=1)
    counts = rng.poisson(area_cm2 * w * density_cm2)
    tri = np.repeat(np.arange(len(f)), counts)
    r1, r2 = np.sqrt(rng.uniform(0, 1, len(tri))), rng.uniform(0, 1, len(tri))
    bary = np.stack([1 - r1, r1 * (1 - r2), r1 * r2], axis=1)
    roots = (v[f[tri]] * bary[..., None]).sum(axis=1)
    normals = unit((n[f[tri]] * bary[..., None]).sum(axis=1))
    return roots, normals, tri, bary


def lashes(v, n, face: Face, lid_y: dict, rng) -> tuple | None:
    """The lashes of the closed eyes: roots along each lid line on the skin, the upper row over the lower."""
    u, w, d = face.local(v)
    front = (d > 5) & (np.abs(u) < 60) & (np.abs(w) < 30)
    if front.sum() < 100:
        return None
    tree = cKDTree(np.stack([u[front], w[front]], axis=1))
    index = np.nonzero(front)[0]
    roots, normals, flows, scale = [], [], [], []
    for side, sign in (("right", -1.0), ("left", 1.0)):
        ue, wl = sign * face.half_ipd, lid_y[side]
        for row, count, length_scale, pitch in (("upper", 120, 1.0, -0.35), ("lower", 60, 0.7, -0.9)):
            t = rng.uniform(0, 1, count)
            su = ue + sign * (-15.0 + 28.5 * t)                                   # inner corner to outer corner
            sw = wl - 1.0 + 2.2 * (2 * t - 1) ** 2 + rng.normal(0, 0.25, count) - (0.5 if row == "lower" else 0.0)
            _, near = tree.query(np.stack([su, sw], axis=1))
            vi = index[near]
            roots.append(v[vi] + (face.ex * (su - u[vi])[:, None] + face.ey * (sw - w[vi])[:, None]) * MM)
            normals.append(n[vi])
            fan = sign * (t - 0.5) * 0.9                                           # the lashes fan out from the middle
            flows.append(unit(face.ez + face.ey * pitch + face.ex * fan[:, None]))
            scale.append(length_scale * (0.6 + 0.4 * np.sin(np.pi * t)))           # shorter at the corners
    roots, normals, flows, scale = np.concatenate(roots), np.concatenate(normals), np.concatenate(flows), np.concatenate(scale)
    # A lash leaves the lid along its flow (not along the skin's normal) and curls: upper lashes up, lower down.
    k, seg = len(roots), LASH.segments
    length = rng.uniform(*LASH.length, k) * scale * MM
    t = unit(flows + normals * 0.35)
    curl = np.where(flows @ face.ey > -0.6, 1.0, -0.5)[:, None] * face.ey
    pts = [roots.copy()]
    p = roots.copy()
    for _ in range(seg):
        p = p + t * (length / seg)[:, None]
        t = unit(t + curl * (1.1 / seg))
        pts.append(p.copy())
    return _ribbon_arrays(np.stack(pts, axis=1), normals, LASH, rng)


def _ribbon_arrays(pts, n, kind: Kind, rng):
    """Ribbon streams for ready centre lines (k, rings, 3)."""
    k, rings = pts.shape[:2]
    seg = rings - 1
    along = np.linspace(0.0, 1.0, rings)
    tangent = np.empty_like(pts)
    tangent[:, 1:-1] = pts[:, 2:] - pts[:, :-2]
    tangent[:, 0] = pts[:, 1] - pts[:, 0]
    tangent[:, -1] = pts[:, -1] - pts[:, -2]
    tangent = unit(tangent)
    width = (kind.width_um * 0.001) * (1.0 - (1.0 - kind.tip) * along ** 2)[None, :] * rng.uniform(0.85, 1.1, k)[:, None]
    seed = rng.uniform(0, 1, k)
    m = k * rings * 2
    pos = np.repeat(pts.reshape(k * rings, 3), 2, axis=0).astype(np.float32)
    uv0 = np.stack([np.tile(np.array([-1.0, 1.0], np.float32), k * rings), np.repeat(np.tile(along, k), 2)], axis=1).astype(np.float32)
    uv1 = np.stack([np.repeat(width.reshape(-1), 2), np.repeat(np.repeat(seed, rings), 2)], axis=1).astype(np.float32)
    tan4 = np.concatenate([np.repeat(tangent.reshape(k * rings, 3), 2, axis=0), np.ones((m, 1))], axis=1).astype(np.float32)
    nor = np.repeat(np.repeat(unit(n), rings, axis=0), 2, axis=0).astype(np.float32)
    col = np.concatenate([np.tile(np.array(kind.colour, np.float64), (m, 1)), np.full((m, 1), RIBBON_COLOUR_ALPHA)], axis=1).astype(np.uint8)
    base = (np.arange(k)[:, None] * rings + np.arange(seg)[None, :]).reshape(-1) * 2
    faces = np.concatenate([np.stack([base, base + 1, base + 2], axis=1), np.stack([base + 1, base + 3, base + 2], axis=1)]).astype(np.uint32)
    return pos, {"NORMAL": nor, "TANGENT": tan4, "TEXCOORD_0": uv0, "TEXCOORD_1": uv1, "COLOR_0": col}, faces


def build(v, f, n, reg: dict, info: dict, covered: np.ndarray | None = None, lid_y: dict | None = None, seed: int = 7, log=print) -> list[Structure]:
    """The hair of the body as structures of the skin layer, one per region ("hair scalp", "hair brow", ...)."""
    rng = np.random.default_rng(seed)
    v = np.asarray(v, np.float64)
    flows = streams(v, n, info)
    out = []
    for name, kind in KINDS.items():
        if name not in flows or name not in reg:
            continue
        weight = reg[name] if covered is None else reg[name] * (1.0 - covered)
        if weight.max() <= 0.05:
            continue
        roots, normals, tri, bary = scatter(v, f, n, weight, kind.density, rng)
        if len(roots) == 0:
            continue
        flow = (flows[name][f[tri]] * bary[..., None]).sum(axis=1)
        root_weight = (weight[f[tri]] * bary).sum(axis=1)
        pos, data, faces = ribbons(roots, normals, flow, kind, rng, length_scale=0.65 + 0.35 * root_weight)
        out.append(Structure(f"hair {name}", "skin", pos, faces, tuple(c / 255 for c in kind.colour), streams=data, info={"hair": name, "strands": int(len(roots))}))
        log(f"hair {name}: {len(roots)} strands, {len(faces)} triangles")
    face = info.get("face")
    if face is not None and lid_y:
        got = lashes(v, n, face, lid_y, rng)
        if got is not None:
            pos, data, faces = got
            out.append(Structure("hair lashes", "skin", pos, faces, tuple(c / 255 for c in LASH.colour), streams=data, info={"hair": "lashes", "strands": int(len(pos) // (2 * (LASH.segments + 1)))}))
            log(f"hair lashes: {out[-1].info['strands']} strands")
    return out
