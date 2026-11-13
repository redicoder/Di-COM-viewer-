"""The eyelids as lids: a real slit where the closed lids meet, and what makes them open.

The scanned skin runs unbroken over the closed eyes. For a lid to be pinched open it has to be free of the other
lid and know how to move. So the skin mesh is cut along each lid line (zones.Face.lid_line, from the skin's own
relief), from a little inside the inner corner to a little inside the outer one: the vertices on the line are
moved onto it and doubled, the lower lid's triangles take the copies. Every vertex of a lid then carries how
much it follows the lid's edge: 1 on the edge at the middle of the eye, falling to 0 at the corners and at the
fold of the upper lid (11 mm up) or 6 mm down the lower. Unity's shaders turn each lid vertex about the eye's
centre by its weight times the opening (LabModel.shader, LabHair.shader for the lashes): the edge travels, the
skin behind it gathers into the fold, as a lid does. A strip of wet pink margin, 2.2 mm deep towards the eye,
gives the lid's edge its thickness when it is open.

Per vertex (Structure.data2, written as TEXCOORD_2): x = the weight, positive on the upper lid and negative on
the lower; y = 0.25 for the right eye, 0.75 for the left, 0 elsewhere.
"""
from __future__ import annotations

import numpy as np

from .zones import MM, Face, smooth

INNER, SPAN = -15.5, 29.0           # mm from the eye's centre to the inner corner, and the fissure's length
UPPER_FOLD, LOWER_FOLD = 11.0, 6.0  # mm of lid that moves, above and below the lid line
MARGIN = 4.0                        # mm: the lid edge's thickness (his lids are swollen: about 5 mm lie over the globe)
MARGIN_COLOUR = (196, 124, 118)
UPPER_DEGREES, LOWER_DEGREES = 42.0, 7.0     # how far the lids' edges turn about the eye's centre when fully open
SIDE_CODE = {"right": 0.25, "left": 0.75}


def lid_curve(face: Face, side: str, lid_w: float):
    """t (0 at the inner corner, 1 at the outer) for a u, and the lid line's height w at a t."""
    sign = -1.0 if side == "right" else 1.0
    ue = sign * face.half_ipd

    def t_of(u):
        return (sign * (np.asarray(u) - ue) - INNER) / SPAN

    def w_of(t):
        return lid_w - 1.0 + 2.2 * (2.0 * np.asarray(t) - 1.0) ** 2          # the corners sit a little higher than the middle

    return t_of, w_of


def cut(v: np.ndarray, f: np.ndarray, face: Face, lid_w: dict, eye_centres: dict, log=print):
    """Cuts the lid slits. Returns the new vertices and faces, `source` (for each new vertex the old vertex whose
    colour and bake it takes), data2 (n, 2), and a mask of the margin strips' inner vertices."""
    v = np.asarray(v, np.float64).copy()
    f = np.asarray(f, np.int64).copy()
    source = np.arange(len(v))
    lid = np.zeros(len(v))
    eye = np.zeros(len(v))
    margin = np.zeros(len(v), bool)
    for side in ("right", "left"):
        if lid_w.get(side) is None or side not in eye_centres:
            continue
        k0 = len(v)                                                          # the vertices so far (the other eye's cut included)
        u, w, d = face.local(v)
        t_of, w_of = lid_curve(face, side, lid_w[side])
        t = t_of(u)
        g = w - w_of(np.clip(t, 0.0, 1.0))                                   # mm above the lid line
        near = (t > -0.25) & (t < 1.25) & (np.abs(g) < 18.0) & (d > 4.0) & ~margin
        tri_near = near[f].all(axis=1)
        tri_t = t[f].mean(axis=1)
        tri_g = g[f].mean(axis=1)
        in_slit = tri_near & (tri_t > 0.04) & (tri_t < 0.96)
        up, down = in_slit & (tri_g > 0), in_slit & (tri_g <= 0)
        on_up = np.zeros(k0, bool)
        on_up[f[up].ravel()] = True
        on_down = np.zeros(k0, bool)
        on_down[f[down].ravel()] = True
        seam = on_up & on_down & (t > 0.04) & (t < 0.96)
        if seam.sum() < 8:
            log(f"lids: no slit for the {side} eye ({int(seam.sum())} vertices on its line)")
            continue
        # The seam's vertices onto the line itself, so the lid's edge is a clean curve and not the mesh's zigzag.
        v[seam] -= face.ey * (g[seam] * MM)[:, None]
        profile = np.sin(np.pi * np.clip(t, 0.0, 1.0)) ** 0.8
        upper = profile * smooth(g, UPPER_FOLD, 0.0) * (g >= 0) * near
        lower = profile * smooth(-g, LOWER_FOLD, 0.0) * (g < 0) * near
        upper[seam] = profile[seam]
        lid = np.where(upper > 0, upper, np.where(lower > 0, -lower, lid))
        eye = np.where((upper > 0) | (lower > 0), SIDE_CODE[side], eye)
        new_v, new_lid, new_src, new_margin = [], [], [], []
        # The lower lid takes copies of the seam's vertices.
        copy_of = np.full(k0, -1, np.int64)
        seam_ids = np.nonzero(seam)[0]
        copy_of[seam_ids] = k0 + np.arange(len(seam_ids))
        for i in seam_ids:
            new_v.append(v[i].copy())
            new_lid.append(-profile[i])
            new_src.append(int(source[i]))
            new_margin.append(False)
        lower_faces = f[down]
        swap = copy_of[lower_faces]
        f[down] = np.where(swap >= 0, swap, lower_faces)
        # The margins: from each cut edge a strip towards the eye, on both lids, seen from either side.
        centre = np.asarray(eye_centres[side], np.float64)
        edges = set()
        for tri in f[up]:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                if seam[a] and seam[b]:
                    edges.add((int(a), int(b)))
        inner_of = {}
        new_f = []

        def inner(i, top):
            """The margin's inner vertex under seam vertex i, of the upper lid (top) or the lower."""
            if (i, top) not in inner_of:
                inward = centre - v[i]
                inner_of[(i, top)] = k0 + len(new_v)
                new_v.append(v[i] + inward / np.linalg.norm(inward) * (MARGIN * MM))
                new_lid.append(profile[i] if top else -profile[i])
                new_src.append(int(source[i]))
                new_margin.append(True)
            return inner_of[(i, top)]

        for a, b in edges:
            for top in (True, False):
                a0, b0 = (a, b) if top else (int(copy_of[a]), int(copy_of[b]))
                a1, b1 = inner(a, top), inner(b, top)
                new_f += [(a0, b0, b1), (a0, b1, a1), (b0, a0, a1), (b0, a1, b1)]
        v = np.concatenate([v, np.array(new_v)])
        f = np.concatenate([f, np.array(new_f, np.int64)])
        lid = np.concatenate([lid, new_lid])
        eye = np.concatenate([eye, np.full(len(new_v), SIDE_CODE[side])])
        source = np.concatenate([source, np.array(new_src, np.int64)])
        margin = np.concatenate([margin, np.array(new_margin, bool)])
        log(f"lids: {side} eye cut along {len(seam_ids)} vertices, {len(edges)} edges")
    data2 = np.stack([lid, eye], axis=1).astype(np.float32)
    return v.astype(np.float32), f.astype(np.uint32), source, data2, margin


def lash_weights(face: Face, side: str, t: np.ndarray, upper: bool) -> np.ndarray:
    """The lid weight (signed) of lashes rooted at t along the lid line."""
    profile = np.sin(np.pi * np.clip(t, 0.0, 1.0)) ** 0.8
    return profile if upper else -profile
