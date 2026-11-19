"""The feet under the skin: the fat's surface there is the skin's own, moved in; bones and muscles lie under it.

Everywhere else the layers under the skin are meshed from the export's labels (voxels of 1.3 x 2 x 1.3 mm) and cut
back from the skin by a voxel (fine_skin.inside_export). In the feet that is not enough. A toe is 12 mm thick and
the clefts between the toes a millimetre and a half: the fat's surface from the labels, in triangles of 4 to 5 mm,
has the toes as blocks, webbed where two toes lie together, and it reached the skin's surface on the soles, the
heels and the toes' pads (yellow patches on the skin), while the toes' bones stood out between its blocks. Counting
the skin two voxels thick there cured the skin's look and spoiled the fat's (its toes went thin, the bones' tips
stood out of them); drawing its vertices in one by one left the webs.

So in the feet (the lowest UP_MM of him) the fat's surface is not taken from the labels: it is the skin's own
outline FAT_MM further in (the level of that depth under the fine outline, contoured at the outline's 0.66 mm), in
triangles of EDGE_MM. (Moving the skin's mesh in along its normals does the same on the foot's body and fails
between the toes: where two toes touch, the skin between them is a bridge thinner than twice that depth, and its
triangles were drawn out into threads from toe to toe.) That is true to him as far as it goes: under the skin of
a foot there is subcutaneous tissue everywhere, thin over its back and thick under the sole, and where it is thin
the labels have none of it. What it does not show is how thick the fat is; under it the muscles and the bones are
as before.

The labels' fat is kept down to LAP_MM below UP_MM, so the two overlap there, and over that stretch the sock's
surface sinks from FAT_MM to RIM_MM under the skin: its rim lies under the labels' fat. The bones and muscles of
the feet lie at least UNDER_MM under the skin (under the fat's surface), passing back to what they have elsewhere
over the last PASS_MM below UP_MM; a toe's bones are first moved as a whole to lie in their toe (fit), and what of
them is still too near the skin goes towards their own axis (to_axis).

    feet.fat(body, structures, baker, occupancy, gloss)    # the fat layer: the sock into "subcutaneous fat"
    feet.under(body, structures)                           # the muscles, the skeleton: nothing above the fat's surface
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import fine_skin
from .common import Body, Structure, decimate_regions, outward, taubin

UP_MM = 230.0                   # the feet, for this module: his lowest millimetres (to above the ankles)
FAT_MM = 1.5                    # the fat's surface lies this far under the skin's (2 mm left the small toes as stalks)
RIM_MM = 2.5                    # ... and this far at UP_MM, sinking to it over the last LAP_MM: its rim lies under the labels' fat
EDGE_MM = 2.0                   # its triangles
LAP_MM = 15.0                   # the labels' fat is kept down to UP_MM - LAP_MM
BLUR = (2.0, 1.5, 2.0)          # the depth is blurred by so many voxels (1.3 to 1.5 mm) before the level is contoured
UNDER_MM = 2.3                  # bones and muscles: at least this far under the skin,
PASS_MM = 30.0                  # up to UP_MM - PASS_MM; from there less and less, and from UP_MM as they are
TOES_MM = 80.0                  # a bone that lies wholly below this is a toe's: it may be moved as a whole to lie in its toe,
FIT_MM = 4                      # by so much at most, across the body
FAT = "subcutaneous fat"


def size_of(body: Body) -> np.ndarray:
    """The body's box in millimetres, in its arrays' order (z, y, x)."""
    return np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]], np.float64)


def to_mm(size: np.ndarray, v: np.ndarray) -> np.ndarray:
    """glTF metres -> the body's millimetres (z back, y up, x left)."""
    p = np.asarray(v, np.float64) * 1000.0
    return np.stack([-p[:, 2], p[:, 1], p[:, 0]], axis=1) + size / 2


def to_gltf(size: np.ndarray, mm: np.ndarray) -> np.ndarray:
    q = np.asarray(mm, np.float64) - size / 2
    return (np.stack([q[:, 2], q[:, 1], -q[:, 0]], axis=1) / 1000.0).astype(np.float32)


def wholly_in(body: Body, s: Structure) -> bool:
    """Whether a structure lies wholly in the feet (below UP_MM)."""
    return len(s.v) > 0 and float(np.asarray(s.v)[:, 1].max()) * 1000.0 + body.size_mm[1] / 2 < UP_MM


def _each_foot(v: np.ndarray):
    """The vertices of the right foot's side, then of the left's (the box that is measured stays one foot's)."""
    left = np.asarray(v)[:, 0] > 0
    return (~left, left)


def sock(fine: fine_skin.FineOutline, size: np.ndarray):
    """The fat's surface in the feet (glTF metres, triangles wound to look outwards): the level FAT_MM under the
    fine outline, contoured, of what lies below UP_MM. Empty arrays when there is nothing of him there.

    Each half of the picture by itself (a foot), in the box round it. The depth is counted from the voxels that
    are not him (below his feet there are none of him either: the end faces count) and blurred (BLUR: counted
    from voxels that are in or out, it has a step at every photograph, and blurred by one voxel the surface had
    them as fine rings round the ankle), so the surface is as smooth as the skin's, and where two toes touch it
    parts them. Over the last LAP_MM below UP_MM the level sinks to RIM_MM: the sock's rim lies under the labels'
    fat, which begins there, and does not stand on the shin as a cuff."""
    from skimage import measure
    spacing, origin = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64)
    spare = 6                                                   # slices above UP_MM that are read with it, and dropped again
    top = min(fine.cover.shape[1], int(np.ceil((UP_MM - origin[1]) / spacing[1])) + spare)
    solid = np.asarray(fine.cover[:, :top, :]) > 127
    half = solid.shape[2] // 2
    out_v, out_f, count = [], [], 0
    for first, last in ((0, half), (half, solid.shape[2])):
        part = solid[:, :, first:last]
        if not part.any():
            continue
        z, x = np.flatnonzero(part.any(axis=(1, 2))), np.flatnonzero(part.any(axis=(0, 1)))
        lo = np.array([max(z[0] - 2, 0), 0, max(x[0] - 2, 0)])
        block = part[lo[0]:z[-1] + 3, :, lo[2]:x[-1] + 3]
        block = np.pad(block, ((1, 1), (1, 0), (1, 1)), constant_values=False)      # not him: round the box and below it;
        block = np.pad(block, ((0, 0), (0, 1), (0, 0)), mode="edge")                # above it the leg goes on
        # (the distance is to a voxel's centre: the outline itself lies some 0.4 mm nearer)
        depth = ndimage.gaussian_filter(ndimage.distance_transform_edt(block, sampling=spacing).astype(np.float32), BLUR)
        height = origin[1] + (np.arange(depth.shape[1]) - 1 + 0.5) * spacing[1]
        depth -= (FAT_MM + 0.4 + np.interp(height, (UP_MM - LAP_MM, UP_MM), (0.0, RIM_MM - FAT_MM))).astype(np.float32)[None, :, None]
        if depth.max() <= 0:
            continue
        pv, pf, _, _ = measure.marching_cubes(depth, 0.0)
        mm = origin + (pv - 1.0 + lo + np.array([0, 0, first]) + 0.5) * spacing     # (the block's padding of one voxel taken off)
        pf = pf[(mm[:, 1] < UP_MM)[pf].all(axis=1)]
        if len(pf) == 0:
            continue
        used, inverse = np.unique(pf, return_inverse=True)
        gv = to_gltf(size, mm[used])
        out_v.append(gv)
        out_f.append(outward(gv, inverse.reshape(-1, 3)).astype(np.int64) + count)
        count += len(gv)
    if not out_v:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint32)
    v = np.concatenate(out_v)
    v, f = decimate_regions(v, np.concatenate(out_f).astype(np.uint32), np.zeros(len(v), np.int8), [EDGE_MM])
    # Smoothed once more as a mesh; its rim (the edges that belong to one triangle only) stays where it is.
    edges, counts = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]).astype(np.int64), axis=1), axis=0, return_counts=True)
    weight = np.ones(len(v))
    weight[np.unique(edges[counts == 1])] = 0.0
    return taubin(v, f, 8, weight=weight).astype(np.float32), f


def fat(body: Body, structures: list[Structure], baker, occupancy: np.ndarray, gloss: int, log=print) -> int:
    """Puts the sock in place of the labels' fat in the feet (the structure FAT of `structures`). Needs the fine
    outline; without it nothing changes. Returns the sock's triangles."""
    s = next((x for x in structures if x.name == FAT), None)
    fine = fine_skin.load(body)
    if s is None or fine is None:
        return 0
    size = size_of(body)
    sv, sf = sock(fine, size)
    if len(sf) == 0:
        return 0
    keep = (to_mm(size, s.v)[:, 1] > UP_MM - LAP_MM)[s.f].any(axis=1)
    used, inverse = np.unique(s.f[keep], return_inverse=True)
    v = np.concatenate([np.asarray(s.v, np.float32)[used], sv])
    f = np.concatenate([inverse.reshape(-1, 3), sf.astype(np.int64) + len(used)]).astype(np.uint32)
    log(f"feet: the fat's surface there is the level {FAT_MM} mm under the skin's outline: {len(sf)} triangles in place of {int((~keep).sum())} from the labels")
    s.v, s.f = v, f
    s.bake = baker.colours(v, f, occupancy, gloss=gloss)
    s.info["feet"] = f"below {UP_MM:.0f} mm its surface is the level {FAT_MM} mm under the skin's outline (feet.py), not the labels' fat"
    return int(len(sf))


def fit(fine: fine_skin.FineOutline, zyx_mm: np.ndarray) -> np.ndarray:
    """The move across the body (mm; z, 0, x: whole millimetres, FIT_MM at most) that leaves the fewest of the
    points less than UNDER_MM under the skin, the shortest of those that leave as few; none when under five are.

    For a toe's bones. They are placed from the CT, and a toe does not lie in the CT just where it lies in the
    photographs: a quarter of the left fourth toe's vertices lay in the skin, or in the cleft beside the toe.
    Drawn in one by one they went into whichever toe was nearer, and the bone's triangles then reached from toe
    to toe across the cleft: a speck of bone between the toes, seen through the skin."""
    field = fine_skin.depth_near(fine, zyx_mm, 8.0 + FIT_MM)
    none = np.zeros(3)
    if field is None:
        return none

    def shallow(move):
        return int((fine_skin.depth_at(fine, field, zyx_mm + move) < UNDER_MM).sum())

    best = (shallow(none), 0.0, none)
    if best[0] < 5:
        return none
    for dz in range(-FIT_MM, FIT_MM + 1):
        for dx in range(-FIT_MM, FIT_MM + 1):
            far = float(np.hypot(dz, dx))
            if 0 < far <= FIT_MM:
                move = np.array([dz, 0.0, dx])
                found = (shallow(move), far, move)
                if found[:2] < best[:2]:
                    best = found
    return best[2]


def to_axis(fine: fine_skin.FineOutline, zyx_mm: np.ndarray) -> np.ndarray:
    """A toe's bones: the points that lie less than UNDER_MM under the skin are moved towards the bones' own long
    axis, as far as it takes (to the axis itself, if it takes that).

    Not along the way the depth grows, as everything else is drawn in: beside a toe lies the next toe, a
    millimetre and a half away, and of a bone that is too thick for its toe one vertex went into the one and its
    neighbour into the other, the triangle between them across the cleft (23 of the left little toe's, 7 mm long,
    a speck of bone between the toes). Towards its own axis a bone gets thinner where the skin is near, and stays
    in its toe."""
    mm = np.asarray(zyx_mm, np.float64).copy()
    field = fine_skin.depth_near(fine, mm)
    if field is None or len(mm) < 3:
        return mm
    todo = np.flatnonzero(fine_skin.depth_at(fine, field, mm) < UNDER_MM)
    if len(todo) == 0:
        return mm
    centre = mm.mean(axis=0)
    along = np.linalg.svd(mm - centre, full_matrices=False)[2][0]
    foot = centre + ((mm[todo] - centre) @ along)[:, None] * along
    start, left = mm[todo].copy(), np.ones(len(todo), bool)
    for share in np.linspace(0.1, 1.0, 10):
        at = start + share * (foot - start)
        good = left & ((fine_skin.depth_at(fine, field, at) >= UNDER_MM) | (share == 1.0))
        mm[todo[good]] = at[good]
        left &= ~good
    return mm


def drawn_under(fine: fine_skin.FineOutline, size: np.ndarray, structures: list[Structure], log=None) -> dict:
    """Moves the vertices of `structures` that lie in the feet to at least UNDER_MM under the skin (less over the
    last PASS_MM below UP_MM). A toe's bones are first moved as a whole to lie in the toe (fit), and what of them
    is still too near the skin goes towards their own axis (to_axis). Returns {name: vertices moved}."""
    moved = {}
    for s in structures:
        if s.streams or len(s.v) == 0:
            continue
        mm = to_mm(size, s.v)
        if not (mm[:, 1] < UP_MM).any():
            continue
        if s.layer == "skeleton" and mm[:, 1].max() < TOES_MM:
            move = fit(fine, mm)
            new = to_axis(fine, mm + move)
            thinned = int((np.linalg.norm(new - mm - move, axis=1) > 0.05).sum())
            if move.any() or thinned:
                s.v = to_gltf(size, new)
                if thinned:
                    moved[s.name] = thinned
                if log and move.any():
                    log(f"feet: {s.name} moved as a whole by {move[0]:+.0f} mm back and {move[2]:+.0f} mm to his left, into its toe")
            continue
        new = mm.copy()
        for side in _each_foot(s.v):
            foot = side & (mm[:, 1] < UP_MM)
            if foot.sum() >= 3:
                new[foot] = fine_skin.drawn_under(fine, mm[foot], np.interp(mm[foot, 1], (UP_MM - PASS_MM, UP_MM), (UNDER_MM, 0.0)))
        far = np.linalg.norm(new - mm, axis=1) > 0.05
        if far.any():
            s.v = to_gltf(size, new)
            moved[s.name] = int(far.sum())
    return moved


def under(body: Body, structures: list[Structure], log=print) -> int:
    """The muscles' and the skeleton's structures: nothing of them above the fat's surface in the feet."""
    fine = fine_skin.load(body)
    if fine is None:
        return 0
    moved = drawn_under(fine, size_of(body), structures, log)
    if moved:
        log(f"feet: drawn under the fat's surface, {sum(moved.values())} vertices of {len(moved)} structures (the most: "
            + ", ".join(f"{name} {count}" for name, count in sorted(moved.items(), key=lambda item: -item[1])[:6]) + ")")
    return sum(moved.values())
