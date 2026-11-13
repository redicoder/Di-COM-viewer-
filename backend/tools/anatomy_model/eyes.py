"""The eyeballs behind the lids.

The photographs give each globe's centre and size (the export's "eyes"); no data here has the eye's inner parts,
so the globe is built: a sphere with the cornea's bulge, coloured per vertex (a dull white sclera a little red
towards the corners, a grey-brown iris with radial streaks, a wide pupil: a dead man's eye), glossy as an eye is.
The space cleared round each globe in the layers beneath is lined with pink conjunctiva (its own walls, a millimetre
in): the fissure is wider than the globe, and without the lining the fat shows at the corners of an opened eye.
It looks along the face's forward axis. Where it would show through the closed lids it is drawn back under the
skin, so the scanned lids stay the surface. It belongs to the organs layer and is there whichever layers are on.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from .common import Structure, normals_of
from .zones import MM

SCLERA = (226, 218, 208)
IRIS = (104, 84, 62)
PUPIL = (16, 14, 14)
IRIS_MM, PUPIL_MM, CORNEA_MM = 5.9, 2.6, 6.0          # radii across the eye's front
BULGE_MM = 1.6                                        # the cornea's rise over the sclera's sphere
LID_MM = 1.1                                          # the least skin kept over the eyeball
CONJUNCTIVA = (188, 112, 108)


def globe(centre: np.ndarray, radius: float, forward: np.ndarray, up: np.ndarray, rings: int = 72, segments: int = 96):
    """A sphere with its pole on the gaze: vertices, faces, and each vertex's angle from the gaze and round it."""
    forward = forward / np.linalg.norm(forward)
    right = np.cross(up, forward)
    right /= np.linalg.norm(right)
    up = np.cross(forward, right)
    alpha = np.linspace(0.0, np.pi, rings + 1)                              # from the gaze's pole to the back
    theta = np.linspace(0.0, 2 * np.pi, segments, endpoint=False)
    a, th = np.meshgrid(alpha, theta, indexing="ij")
    a, th = a.ravel(), th.ravel()
    # The cornea stands a little proud of the sphere.
    front_mm = radius * 1000.0 * np.sin(np.minimum(a, np.pi / 2))
    rise = BULGE_MM * np.clip(1.0 - (front_mm / CORNEA_MM) ** 2, 0.0, 1.0) * (a < np.pi / 2)
    r = radius + rise * MM
    direction = np.cos(a)[:, None] * forward + np.sin(a)[:, None] * (np.cos(th)[:, None] * right + np.sin(th)[:, None] * up)
    v = centre + direction * r[:, None]
    faces = []
    for i in range(rings):
        for j in range(segments):
            p, q = i * segments + j, i * segments + (j + 1) % segments
            faces += [(p, p + segments, q + segments), (p, q + segments, q)]
    return v, np.array(faces, np.int64), a, th


def lining(body, origin, pit: np.ndarray):
    """The conjunctiva: the walls of the space cleared round an eye (Body.eye_pits), a millimetre inside them and
    facing into it, without the side that is the skin. Whatever way one looks in through an opened eye, the look
    ends on the globe or on this, never on the fat or the muscle the space was cut from."""
    from .common import surface
    got = surface(pit, body.spacing, 1.2, origin)
    if got is None:
        return None
    v, f = body.to_gltf(*got)
    n = normals_of(v, f)                                                 # out of the space, into the tissue
    beyond = body.sample(body.depth_mm(), np.asarray(v, np.float64) + n * 0.003)
    keep = (beyond >= 1.5)[f].all(axis=1)                                # tissue behind the wall, not the skin or the air
    f = f[keep][:, ::-1]
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int64)
    remap[used] = np.arange(len(used))
    return (np.asarray(v, np.float64) - n * 0.0012)[used], remap[f]


def colour(radius: float, a: np.ndarray, th: np.ndarray, rng: np.random.Generator):
    front_mm = radius * 1000.0 * np.sin(np.minimum(a, np.pi / 2))
    front = a < np.pi / 2
    c = np.tile(np.array(SCLERA, np.float64), (len(a), 1))
    # The sclera: a little yellow and red away from the cornea, where the vessels are.
    away = np.clip((front_mm - IRIS_MM) / (radius * 1000.0 - IRIS_MM), 0.0, 1.0)
    c *= 1.0 - np.outer(away, (0.04, 0.10, 0.12))
    streak = 0.5 + 0.5 * np.sin(th * 46.0 + rng.uniform(0, 6.28)) * np.sin(th * 17.0 + 1.3)
    iris = np.array(IRIS, np.float64)[None, :] * (0.72 + 0.4 * streak * np.clip((front_mm - PUPIL_MM) / (IRIS_MM - PUPIL_MM), 0, 1))[:, None]
    in_iris = front & (front_mm < IRIS_MM)
    c[in_iris] = iris[in_iris]
    limbus = front & (np.abs(front_mm - IRIS_MM) < 0.45)
    c[limbus] *= 0.62
    c[front & (front_mm < PUPIL_MM)] = PUPIL
    # A dead eye's cornea is a little clouded: the iris and pupil greyed.
    cloud = front & (front_mm < IRIS_MM + 0.3)
    c[cloud] = c[cloud] * 0.82 + np.array([150.0, 152.0, 150.0]) * 0.18
    return np.round(np.clip(c, 0, 255)).astype(np.uint8)


def build(skin: Structure, log=print, surface: Structure | None = None, body=None) -> list[Structure]:
    """Both eyeballs, from what the skin layer recorded about the eyes (Structure.info["eyes"]). `surface` is the
    skin before the lids were cut (the cut skin has the lids' margins reaching in towards the eye)."""
    info = skin.info.get("eyes")
    if not info:
        return []
    forward, up = np.array(info["forward"], np.float64), np.array(info["up"], np.float64)
    whole = surface if surface is not None else skin
    sv = np.asarray(whole.v, np.float64)
    sn = normals_of(whole.v, whole.f)
    rng = np.random.default_rng(11)
    out = []
    for side in ("right", "left"):
        if side not in info["centres"]:
            continue
        centre, radius = np.array(info["centres"][side], np.float64), float(info["radius"][side])
        v, f, a, th = globe(centre, radius, forward, up)
        # Nowhere through the lids: a vertex in front of the skin's inner side goes back along the skin's normal.
        near = np.linalg.norm(sv - centre, axis=1) < radius * 2.2
        tree = cKDTree(sv[near])
        dist, idx = tree.query(v)
        skin_p, skin_n = sv[near][idx], sn[near][idx]
        height = np.einsum("ij,ij->i", v - skin_p, skin_n)                  # above the skin where positive
        push = np.clip(height + LID_MM * MM, 0.0, None) * (dist < 0.012)
        v = v - skin_n * push[:, None]
        albedo = colour(radius, a, th, rng)
        bake = np.tile(np.array([255, 255, 82, 235], np.uint8), (len(v), 1))  # open, thick, mild curvature, glossy
        out.append(Structure(f"{side} eyeball", "organs", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in SCLERA), bake=bake, albedo=albedo,
                             info={"class": "organ", "generated": True}))
        # The conjunctiva: the lining of the space cleared round this eye.
        pits = getattr(body, "eye_pits", None) or []
        if body is not None and pits:
            def middle(item):
                (z0, y0, x0), mask = item
                zz, yy, xx = (np.array(np.nonzero(mask)).mean(axis=1) + np.array([z0, y0, x0]) + 0.5) * np.array(body.spacing)
                return np.array([xx - body.size_mm[0] / 2, yy - body.size_mm[1] / 2, -(zz - body.size_mm[2] / 2)]) / 1000.0
            origin, pit = min(pits, key=lambda item: np.linalg.norm(middle(item) - centre))
            got = lining(body, origin, pit)
            if got is not None:
                cv, cf = got
                deep = np.clip(np.linalg.norm(cv - centre, axis=1) / (radius + 0.012), 0.0, 1.0)
                tone = np.array(CONJUNCTIVA, np.float64)[None, :] * (1.0 - 0.25 * deep)[:, None]
                cbake = np.tile(np.array([200, 255, 82, 215], np.uint8), (len(cv), 1))
                out.append(Structure(f"{side} conjunctiva", "organs", cv.astype(np.float32), cf.astype(np.uint32), tuple(c / 255 for c in CONJUNCTIVA),
                                     bake=cbake, albedo=np.round(tone).astype(np.uint8), info={"class": "organ", "generated": True}))
        moved = push > 1e-5
        log(f"eyes: {side} eyeball, radius {radius * 1000:.1f} mm; {int(moved.sum())} of {len(v)} vertices drawn back under the skin, by up to {push.max() * 1000:.1f} mm "
            f"(at {np.degrees(a[np.argmax(push)]):.0f} degrees from the gaze); the cornea's top lies {-height[np.argmin(a)] * 1000:.1f} mm under the skin")
    return out
