"""The hands under the skin: the fingers' bones in the fingers, and the fat's surface as the skin's own, moved in.

BoneHub's bones are placed from the CT with one fit for the whole skeleton, and the CT has a finger up to 5 mm
beside where the photographs have it: of the left little finger's bone 39 vertices stood out of the skin, by up
to 6.6 mm. While the fingers were one piece of skin that could be mended vertex by vertex, each drawn in along
the way the depth grows; with the fingers apart (fine_skin.body_outline) that puts a vertex into whichever
finger is nearer, as it did with the toes. So, as the toes' bones (feet.py): a finger's bones are moved as a
whole into the finger (nails.settle: any way, 6 mm at most, to where the fewest vertices lie at the skin or
outside it), and what of them is still too near the skin goes towards their own long axis (feet.to_axis).

The fat, as in the feet (feet.py, where the reasons are): from the labels, at 1.3 mm in triangles of 4 to 5 mm, a
finger's fat is a few blocks with the bone showing between them, and it reached the skin's surface on the hands'
backs. In the hands (what lies within REACH_MM of a hand's bones) the fat's surface is the level GLOVE_MM under
the fine outline, contoured at the outline's 0.66 mm; towards the wrist it sinks to RIM_MM, under the labels' fat,
which is kept from LAP_MM short of that reach. Under a finger that lies on the belly, the belly's skin is within
that reach too: there the surface is the belly's, under its skin, and stands in for the labels' fat taken out.

    hands.under(body, structures)                          # the skeleton, the muscles: nothing above the fat's surface
    hands.fat(body, structures, baker, occupancy, gloss)   # the fat layer: the gloves into "subcutaneous fat"
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import bonehub, feet, fine_skin, nails
from .common import FAT_SURFACE, Body, Structure, decimate_regions, taubin

UNDER_MM = 2.0                  # a hand's bones and muscles lie at least this far under the skin (under the fat's surface)
GLOVE_MM = 1.5                  # the fat's surface under the skin's
RIM_MM = 2.5                    # ... and this far where the glove ends, sinking to it over the last LAP_MM of its reach
REACH_MM = 24.0                 # the hand, for the fat: what lies within this of its bones
LAP_MM = 6.0                    # the labels' fat is kept from REACH_MM - LAP_MM of the bones outwards
EDGE_MM = 1.5                   # the glove's triangles
BLUR = (2.0, 1.5, 2.0)          # as feet.BLUR


def is_finger(name: str) -> bool:
    return name.startswith("phalanges of the ") and ("finger" in name or "thumb" in name)


def is_hand(name: str) -> bool:
    """A bone of a hand (its fingers', its palm's, its wrist's)."""
    return "toe" not in name and "metatarsal" not in name and any(key in name for key in fine_skin.HAND_BONES)


def bones_of(body: Body) -> dict:
    """{side: every vertex of that hand's bones (mm, the body's axes)}; empty without BoneHub's bones."""
    if not bonehub.cache_path(body).exists():
        return {}
    placed, _, _ = bonehub.load_or_build(body, None, lambda *_: None)
    out = {}
    for side in ("left", "right"):
        mine = [np.asarray(v, np.float64) for _, name, v, _ in placed if name.startswith(side + " ") or f" {side} " in name if is_hand(name)]
        if mine:
            out[side] = np.concatenate(mine)
    return out


SKIN_REACH_MM = 16.0            # a hand's own skin lies within this of its bones
FINGER_REACH_MM = 12.0          # ... and a finger's within this of the finger's


def own_skin(bones: np.ndarray, zyx_mm: np.ndarray, normals_zyx: np.ndarray, reach_mm: float = SKIN_REACH_MM) -> np.ndarray:
    """Which points of the skin (mm, the body's axes, with their outward normals) are a hand's own skin, 0..1,
    given the hand's bones' vertices (in the hand: a finger's as into_finger has them).

    Skin within `reach_mm` of a hand's bone is the hand's if it looks AWAY from that bone. The belly's skin under
    a finger that rests on it is as near the bone, and looks towards it."""
    out = np.zeros(len(zyx_mm))
    if len(bones) == 0 or len(zyx_mm) == 0:
        return out
    far, index = cKDTree(bones).query(zyx_mm, distance_upper_bound=reach_mm)
    near = np.flatnonzero(far < reach_mm)
    if len(near) == 0:
        return out
    away = zyx_mm[near] - bones[index[near]]
    cos = np.einsum("ij,ij->i", away, normals_zyx[near]) / np.maximum(np.linalg.norm(away, axis=1) * np.linalg.norm(normals_zyx[near], axis=1), 1e-9)
    out[near] = np.clip(cos / 0.3, 0.0, 1.0)
    return out


def skin_of(body: Body, v: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The hands' own skin among the skin's vertices (glTF metres, with their normals), and the fingers' alone:
    each 0..1 (own_skin), by the hands' bones with each finger's moved into its finger. Zeros without the bones
    or the fine outline.

    The labels do not tell it: they are 2.6 mm coarse where the skin's zones read them, and the two fingertips
    that rest on the belly's middle line were taken for belly (its hair grew on them)."""
    fine = fine_skin.load(body)
    none = np.zeros(len(v)), np.zeros(len(v))
    if fine is None or not bonehub.cache_path(body).exists():
        return none
    placed, _, _ = bonehub.load_or_build(body, None, lambda *_: None)
    palm, fingers = [], []
    for _, name, bv, _ in placed:
        if not is_hand(name):
            continue
        mm = np.asarray(bv, np.float64)
        if is_finger(name):
            fingers.append(mm + nails.settle(fine, mm[::max(1, len(mm) // 600)]))
        else:
            palm.append(mm)
    if not palm and not fingers:
        return none
    size = feet.size_of(body)
    normals = np.asarray(n, np.float64)
    points, facing = feet.to_mm(size, v), np.stack([-normals[:, 2], normals[:, 1], normals[:, 0]], axis=1)
    return (own_skin(np.concatenate(palm + fingers), points, facing),
            own_skin(np.concatenate(fingers), points, facing, FINGER_REACH_MM) if fingers else none[1])


def into_finger(fine: fine_skin.FineOutline, zyx_mm: np.ndarray):
    """A finger's bones (mm, the body's axes) -> (the bones in the finger, the move that was made of them as a
    whole)."""
    move = nails.settle(fine, zyx_mm[::max(1, len(zyx_mm) // 600)])
    return feet.to_axis(fine, zyx_mm + move, UNDER_MM), move


def under(body: Body, structures: list[Structure], log=print) -> int:
    """The skeleton's and the muscles' structures in the hands: each finger's bones moved into the finger and
    under its skin; what else lies in a hand (the palm's and the wrist's bones, the muscles) drawn in to UNDER_MM
    where it lies shallower. Returns how many vertices were moved singly."""
    fine = fine_skin.load(body)
    if fine is None:
        return 0
    size = feet.size_of(body)
    trees = {side: cKDTree(points[::4]) for side, points in bones_of(body).items()}
    moved, single = [], 0
    for s in structures:
        if s.streams or len(s.v) == 0:
            continue
        mm = feet.to_mm(size, s.v)
        if is_finger(s.name):
            new, move = into_finger(fine, mm)
            single += int((np.linalg.norm(new - mm - move, axis=1) > 0.05).sum())
            if move.any():
                moved.append(f"{s.name[len('phalanges of the '):]} {np.linalg.norm(move):.1f} mm")
            s.v = feet.to_gltf(size, new)
            continue
        new = mm.copy()
        for tree in trees.values():
            near = np.flatnonzero(tree.query(mm, distance_upper_bound=REACH_MM - LAP_MM)[0] < REACH_MM - LAP_MM)
            if len(near) >= 3:
                new[near] = fine_skin.drawn_under(fine, mm[near], UNDER_MM)
        far = np.linalg.norm(new - mm, axis=1) > 0.05
        if far.any():
            s.v = feet.to_gltf(size, new)
            single += int(far.sum())
    if moved or single:
        log(f"hands: the fingers' bones moved as a whole into their fingers: {'; '.join(moved) or 'none'}; {single} vertices drawn in singly")
    return single


def glove(fine: fine_skin.FineOutline, size: np.ndarray, bones: np.ndarray):
    """The fat's surface in one hand (glTF metres, triangles wound to look outwards): the level GLOVE_MM under the
    fine outline (RIM_MM at the end of its reach), of what lies within REACH_MM of the hand's bones (mm, the
    body's axes). Empty arrays when there is nothing."""
    from skimage import measure
    empty = np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint32)
    spacing, origin, shape = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64), np.array(fine.cover.shape)
    lo = np.maximum(np.floor((bones.min(axis=0) - REACH_MM - 4.0 - origin) / spacing).astype(int), 0)
    hi = np.minimum(np.ceil((bones.max(axis=0) + REACH_MM + 4.0 - origin) / spacing).astype(int), shape)
    if (hi - lo < 4).any():
        return empty
    block = np.asarray(fine.cover[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]) > 127
    if block.all() or not block.any():
        return empty
    # (beyond the box he goes on, an arm, a belly: what is at its faces is carried on)
    depth = ndimage.gaussian_filter(ndimage.distance_transform_edt(np.pad(block, 1, mode="edge"), sampling=spacing).astype(np.float32), BLUR)[1:-1, 1:-1, 1:-1]
    marks = np.ones(block.shape, bool)
    at = np.clip(np.floor((bones - origin) / spacing).astype(int) - lo, 0, np.array(block.shape) - 1)
    marks[at[:, 0], at[:, 1], at[:, 2]] = False
    far = ndimage.distance_transform_edt(marks, sampling=spacing).astype(np.float32)        # mm from the hand's bones
    field = depth - (GLOVE_MM + 0.4 + np.interp(far, (REACH_MM - LAP_MM, REACH_MM), (0.0, RIM_MM - GLOVE_MM))).astype(np.float32)
    if field.max() <= 0 or field.min() >= 0:
        return empty
    pv, pf, _, _ = measure.marching_cubes(field, 0.0)
    reach = ndimage.map_coordinates(far, pv.T, order=1, mode="nearest")
    inside = (reach < REACH_MM) & (pv > 1.5).all(axis=1) & (pv < np.array(block.shape) - 2.5).all(axis=1)
    pf = pf[inside[pf].all(axis=1)]
    if len(pf) == 0:
        return empty
    used, inverse = np.unique(pf, return_inverse=True)
    pv, pf = pv[used], inverse.reshape(-1, 3)
    mm = origin + (pv + lo + 0.5) * spacing
    # Wound to look out: away from where he is deeper.
    slope = np.stack([ndimage.map_coordinates(g, pv[pf[::7]].mean(axis=1).T, order=1, mode="nearest") for g in np.gradient(depth, *spacing)], axis=1)
    tri = mm[pf[::7]]
    if (np.einsum("ij,ij->i", np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), slope) > 0).mean() > 0.5:
        pf = pf[:, ::-1]
    v, f = decimate_regions(feet.to_gltf(size, mm), pf.astype(np.uint32), np.zeros(len(mm), np.int8), [EDGE_MM])
    edges, counts = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]).astype(np.int64), axis=1), axis=0, return_counts=True)
    weight = np.ones(len(v))
    weight[np.unique(edges[counts == 1])] = 0.0                          # its rim stays where it is
    return taubin(v, f, 8, weight=weight).astype(np.float32), f


def fat(body: Body, structures: list[Structure], baker, occupancy: np.ndarray, gloss: int, log=print) -> int:
    """Puts the gloves in place of the labels' fat in the hands (the structure feet.FAT of `structures`). Needs the
    fine outline and BoneHub's bones; without them nothing changes. Returns the gloves' triangles."""
    s = next((x for x in structures if x.name == feet.FAT), None)
    fine = fine_skin.load(body)
    hands = bones_of(body)
    if s is None or fine is None or not hands:
        return 0
    size = feet.size_of(body)
    v, f = np.asarray(s.v, np.float32), np.asarray(s.f)
    mm = feet.to_mm(size, v)
    mark = None if s.extra is None else np.asarray(s.extra, np.uint8)     # (the fat's marks: the gloves are its surface too)
    added, taken = 0, 0
    for side, bones in hands.items():
        gv, gf = glove(fine, size, bones)
        if len(gf) == 0:
            continue
        near = cKDTree(bones[::4]).query(mm, distance_upper_bound=REACH_MM - LAP_MM)[0] < REACH_MM - LAP_MM
        keep = ~near[f].all(axis=1)
        taken += int((~keep).sum())
        f = np.concatenate([f[keep], gf.astype(np.int64) + len(v)])
        v = np.concatenate([v, gv])
        mm = np.concatenate([mm, feet.to_mm(size, gv)])
        if mark is not None:
            mark = np.concatenate([mark, np.full(len(gv), FAT_SURFACE, np.uint8)])
        added += int(len(gf))
    if not added:
        return 0
    used, inverse = np.unique(f, return_inverse=True)
    s.v, s.f = v[used], inverse.reshape(-1, 3).astype(np.uint32)
    if mark is not None:
        s.extra = mark[used]
    s.bake = baker.colours(s.v, s.f, occupancy, gloss=gloss)
    s.info["hands"] = f"within {REACH_MM:.0f} mm of a hand's bones its surface is the level {GLOVE_MM} mm under the skin's outline (hands.py), not the labels' fat"
    log(f"hands: the fat's surface there is the level {GLOVE_MM} mm under the skin's outline: {added} triangles in place of {taken} from the labels")
    return added
