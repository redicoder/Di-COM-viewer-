"""The elbows' bones, read from the photographs.

BoneHub's bones are from the CT, and the CT's picture is 478 mm wide: narrower than he is at the elbows. The
arms' bones are cut by its edge: the humerus lengthwise over 85 mm (in the model a blade that ended in a point
above the elbow), the radius and the ulna at their upper ends; and the elbow itself, which lies wholly beyond
that edge, was not there at all. The photographs are wider (their frame cuts the arm 43 mm further out, where
the arm's skin ends in a flat face), and they hold the elbow: in every photograph through it the bone is pale,
deep in the dark muscle. The labels have no bone there (the pale tissue of the arms is "fat" to them).

So beyond the CT's edge the arm's bone is READ FROM THE PHOTOGRAPHS (fine_muscle's lightness, the fine skin's
outline; looked at on 2026-11-26: docs/research/under_layers.md, section 12):

- tissue that is not muscle-red (its coverage under PALE),
- deeper under the skin than DEEP_MM (the fat under the skin is pale too),
- within REACH_MM of the bones' own lines: the humerus's from above, the ulna's and the radius's from below,
  as BoneHub's whole parts have them, drawn on to where they meet (the pale fat of the flank lies beyond the
  CT's edge as well, where the arm lies against the trunk),
- without what is thinner than a film (FILM: the sheets of fascia between the muscles),
- in pieces of PIECE_CM3 and more, and no smaller than PIECE_SHARE of the largest (a scrap of 2.6 cm3 lay beside
  his left elbow's 125),
- with what a photograph's bone encloses (the marrow is red),
- and, of the bone so found, without what is thinner than SPUR (a peg and a ragged tail of pale tissue, 3 mm
  thick, stood on his left elbow's point).

What that gives is the elbow's bones as ONE mass, with their cartilage and with what tendon lies on them: where
one bone ends and the next begins the photographs' colour does not say, and it is not guessed (a wrong name on
the olecranon would be worse than none). It joins BoneHub's bones at the CT's edge, lapping OVERLAP_MM over
them, and it ends where the photographs do: flat, DEEP_MM under the arm's flat face.

Nothing of it is drawn.

BoneHub's arm bones do not lie where the photographs have the same bones: measured on the whole stretches next
to the elbows, 4 to 5 mm beside, steadily (the arm lay a little otherwise in the scanner, and the skeleton is
still the CT's size). Half a bone from the one and half from the other, 5 mm apart, was a humerus split along
its length. So before the elbow is read, each of the arm's three bones is MOVED ONTO THE PHOTOGRAPHS' BONE at
its cut end: in a few photographs next to the cut the bone is found (`bone_at`: the pale, deep piece lying on
BoneHub's section) and of the three nearest the cut the middle one of the distances is taken; the bone is moved
by it across its length, wholly there and on towards the elbow, by less and less towards its far end (the
shoulder; the wrist), which stays where it is: as turned about its far joint by a degree or two (`turned`).
Where the bone is not found clearly in three photographs it is left as it is.

    pieces, placed = elbows.read(body, placed)   # placed: bonehub.load_or_build's; given back with the arms' bones moved
                                                 # pieces: [(name, vertices in the body's mm (z, y, x), faces)]
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from scipy import ndimage

from . import fine_muscle, fine_skin
from .common import Body

PALE = 0.35                     # tissue whose muscle coverage is under this is not muscle
DEEP_MM = 6.0                   # ... and is bone only deeper under the skin than this
REACH_MM = 36.0                 # ... and within this of a bone's line (the elbow is 65 mm across)
FILM = 2                        # openings: what is thinner than 2.6 mm goes
PIECE_CM3 = 1.5                 # pieces smaller than this are left out,
PIECE_SHARE = 0.1               # ... and those smaller than this share of the largest
SPUR = 3                        # of the bone found: what is thinner than 4 mm goes
OVERLAP_MM = 1.0                # how far it laps over the CT's edge, onto BoneHub's bones
CLEAR_MM = 1.5                  # a bone's section nearer the CT's edge than this is cut by it
CUT_MM = 40.0                   # a humerus lying along its outermost plane for this much of its length is cut there (his: 84
                                # and 76 mm; the bones the edge does not cut touch their own outermost plane over 28 mm at most)
BEYOND_MM = 30.0                # a bone's line is drawn on this far past the joint (the olecranon lies past it)
BLUR_MM = 0.8
TRIANGLES = 16000               # each elbow's mesh in the model
# Where a bone is looked for in the photographs, to move BoneHub's onto it: from FIT_FROM_MM clear of its cut, every
# FIT_STEP_MM over FIT_OVER_MM, in a window of FIT_WINDOW_MM round BoneHub's section. The piece found is the bone if it
# is no more than FIT_WIDER_MM wider than the section (nearer the shoulder it runs together with the joint's pale
# tissue) and its middle no further than FIT_MOST_MM from the section's; FIT_LEVELS photographs must give one.
FIT_FROM_MM, FIT_STEP_MM, FIT_OVER_MM = 10.0, 10.0, 80.0
FIT_WINDOW_MM, FIT_WIDER_MM, FIT_MOST_MM, FIT_LEVELS = 45.0, 8.0, 12.0, 3
NAME = "bones of the {} elbow"
SOURCE = "the photographs: the pale tissue deep in the arm's muscle, where the scanner's picture ends (elbows.py); with its cartilage, not told apart into its three bones"
ARM = ("humerus", "ulna", "radius")


def line_of(points: np.ndarray):
    """The line through a stretch of bone: (a point on it, its direction)."""
    points = np.asarray(points, np.float64)
    centre = points.mean(axis=0)
    return centre, np.linalg.svd(points - centre, full_matrices=False)[2][0]


def cut_levels(v: np.ndarray, edge: float, inward: float, step: float = 4.0) -> list[float]:
    """The heights (mm) at which a bone's section comes within CLEAR_MM of the CT's edge (the plane x = `edge`;
    `inward`: +1 if the body lies at greater x, -1 if at less)."""
    out = []
    for y in np.arange(np.floor(v[:, 1].min()), v[:, 1].max(), step):
        at = np.abs(v[:, 1] - y) < step / 2
        if at.sum() >= 8 and ((v[at, 2] - edge) * inward).min() < CLEAR_MM:
            out.append(float(y))
    return out


def frame(bones: dict, side: str, lines_from: dict | None = None):
    """Where an arm's bones are cut by the CT's edge and where their lines run, from BoneHub's bones as placed
    (`bones`: name -> vertices, mm, z back, y up, x to his left). None if the arm's three bones are not all
    there, or the humerus is not cut (CUT_MM). Else a namespace: `edge` (mm), `inward` (+1: the body lies at
    greater x), `low`, `high` (mm up: the stretch in which bone is missing), `top` (the highest level at which
    the humerus is cut), `lows` (ulna, radius: the lowest level at which each is cut, or its upper end), `lines`
    (the segments bone lies along: pairs of points) and `joint` (where the humerus's and the ulna's lines pass
    nearest each other). Where the edge cuts is a fact of the CT and is read from `bones`; the lines are those
    of the same bones in `lines_from`, if given (the bones moved onto the photographs': `turned`, which does not
    change a vertex's height)."""
    try:
        h, u, r = (np.asarray(bones[f"{side} {k}"], np.float64) for k in ARM)
        hl, ul, rl = (np.asarray((lines_from or bones)[f"{side} {k}"], np.float64) for k in ARM)
    except KeyError:
        return None
    inward = 1.0 if side == "right" else -1.0                             # (x grows to his left: his right arm lies at the least x)
    edge = float(h[:, 2].min() if inward > 0 else h[:, 2].max())
    cut = {name: cut_levels(v, edge, inward) for name, v in (("humerus", h), ("radius", r), ("ulna", u))}
    if not cut["humerus"] or max(cut["humerus"]) - min(cut["humerus"]) < CUT_MM:
        return None
    # Each bone's line, from a stretch of it that is whole: the humerus's above its cut, the forearm's bones' below theirs.
    top = max(cut["humerus"])
    whole = hl[(h[:, 1] > top + 10.0) & (h[:, 1] < top + 100.0)]
    if len(whole) < 30:
        return None
    hc, ha = line_of(whole)
    ha = ha if ha[1] < 0 else -ha                                         # down the arm, to the elbow
    lines, forearm, lows = [], {}, {}
    for name, v, vl in (("ulna", u, ul), ("radius", r, rl)):
        low = min(cut[name]) if cut[name] else float(v[:, 1].max())
        part = vl[(v[:, 1] < low - 5.0) & (v[:, 1] > low - 75.0)]
        if len(part) < 30:
            return None
        c, a = line_of(part)
        forearm[name] = (c, a if a[1] > 0 else -a, low)                   # up the forearm, to the elbow
        lows[name] = low
    uc, ua, _ = forearm["ulna"]
    across = np.cross(ha, ua)
    if np.linalg.norm(across) < 1e-6:
        return None
    t = np.linalg.solve(np.stack([ha, -ua, across], axis=1), uc - hc)
    joint = (hc + t[0] * ha + uc + t[1] * ua) / 2.0
    start = hc + ((top + 10.0 - hc[1]) / ha[1]) * ha                      # the humerus's line from where it is whole
    lines.append((start, hc + (t[0] + BEYOND_MM) * ha))
    for name, (c, a, low) in forearm.items():
        begin = c + ((low - 5.0 - c[1]) / a[1]) * a
        reach = float((joint - c) @ a) + (BEYOND_MM if name == "ulna" else 0.0)
        lines.append((begin, c + max(reach, float((begin - c) @ a) + 1.0) * a))
    return SimpleNamespace(edge=edge, inward=inward, low=min(lows.values()) - 8.0, high=top + 8.0, top=top, lows=lows, lines=lines, joint=joint)


def from_lines(points: np.ndarray, lines: list) -> np.ndarray:
    """How far each point (..., 3) lies from the nearest of the segments `lines` (pairs of points)."""
    points = np.asarray(points, np.float64)
    best = np.full(points.shape[:-1], np.inf)
    for p, q in lines:
        d = q - p
        t = np.clip(((points - p) @ d) / max(float(d @ d), 1e-12), 0.0, 1.0)
        best = np.minimum(best, np.linalg.norm(points - (p + t[..., None] * d), axis=-1))
    return best


def mass(cover: np.ndarray, tissue: np.ndarray, depth: np.ndarray, allowed: np.ndarray, spacing) -> np.ndarray:
    """The bone in a block (z, y, x; y the photographs): what is tissue, not muscle-red (`cover` under PALE), deep
    under the skin (`depth` over DEEP_MM) and `allowed`; films taken out, small pieces left out (under PIECE_CM3,
    or under PIECE_SHARE of the largest: of their pale tissue, the marrow not counted), and what each photograph's
    bone encloses filled; then, of that, what is thinner than SPUR taken off, and the pieces counted once more.
    Bool."""
    pale = np.asarray(tissue, bool) & (np.asarray(cover) < PALE) & (np.asarray(depth) > DEEP_MM) & np.asarray(allowed, bool)
    cross = ndimage.generate_binary_structure(3, 1)

    def pieces(mask):
        parts, count = ndimage.label(mask)
        if count == 0:
            return np.zeros(mask.shape, bool)
        volume = np.asarray(ndimage.sum(mask, parts, range(1, count + 1))) * float(np.prod(spacing)) / 1000.0
        return np.isin(parts, 1 + np.flatnonzero((volume >= PIECE_CM3) & (volume >= PIECE_SHARE * volume.max())))

    big = pieces(ndimage.binary_opening(pale, structure=cross, iterations=FILM))
    solid = np.zeros_like(big)
    for k in range(big.shape[1]):
        solid[:, k, :] = ndimage.binary_fill_holes(big[:, k, :])
    solid |= ndimage.binary_closing(np.pad(solid, FILM), structure=cross, iterations=FILM)[FILM:-FILM, FILM:-FILM, FILM:-FILM]
    # Spurs: the first and the last photograph are laid on again before the opening (the block's own ends are not thin).
    ends = np.pad(solid, ((0, 0), (SPUR, SPUR), (0, 0)), mode="edge")
    return pieces(ndimage.binary_opening(ends, structure=cross, iterations=SPUR)[:, SPUR:-SPUR, :])


def section(v: np.ndarray, level: float, half: float = 1.5):
    """A bone's section at a height: (its middle (z, x), half its extent (z, x)), from the box round its vertices
    within `half` of the level; None where it has too few."""
    at = np.abs(v[:, 1] - level) < half
    if at.sum() < 8:
        return None
    low, high = np.array([v[at, 0].min(), v[at, 2].min()], np.float64), np.array([v[at, 0].max(), v[at, 2].max()], np.float64)
    return (low + high) / 2.0, (high - low) / 2.0


def bone_at(cover: np.ndarray, tissue: np.ndarray, inside: np.ndarray, spacing, origin, centre, half):
    """The bone in ONE photograph (arrays over z, x; `spacing`, `origin`: theirs, mm) at the place where BoneHub has
    a bone's section (`centre`, `half`: section's): the pale, deep piece (as `mass` takes it, films opened away)
    that most of the section lies on, with what it encloses. (Its middle (z, x), half its extent), both from the
    box round it; None if nothing of the kind lies on the section, or if what does is not the bone alone (more
    than FIT_WIDER_MM wider than the section, or its middle further than FIT_MOST_MM from the section's)."""
    spacing, origin, centre, half = (np.asarray(a, np.float64) for a in (spacing, origin, centre, half))
    first = np.maximum(0, np.floor((centre - FIT_WINDOW_MM - origin) / spacing)).astype(int)
    last = np.minimum(cover.shape, np.ceil((centre + FIT_WINDOW_MM - origin) / spacing)).astype(int)
    if (last - first).min() < 3:
        return None
    box = (slice(first[0], last[0]), slice(first[1], last[1]))
    within = np.asarray(inside[box], bool)
    depth = ndimage.distance_transform_edt(within, sampling=spacing)
    pale = np.asarray(tissue[box], bool) & within & (np.asarray(cover[box]) < PALE) & (depth > DEEP_MM)
    parts, count = ndimage.label(ndimage.binary_opening(pale, structure=ndimage.generate_binary_structure(2, 1), iterations=FILM))
    if count == 0:
        return None
    zz, xx = np.meshgrid(origin[0] + (np.arange(first[0], last[0]) + 0.5) * spacing[0], origin[1] + (np.arange(first[1], last[1]) + 0.5) * spacing[1], indexing="ij")
    on = ((zz - centre[0]) / max(half[0], 1e-6)) ** 2 + ((xx - centre[1]) / max(half[1], 1e-6)) ** 2 < 1.0
    share = np.asarray(ndimage.sum(on, parts, range(1, count + 1)))
    if share.max() <= 0:
        return None
    piece = ndimage.binary_fill_holes(parts == 1 + int(np.argmax(share)))
    low, high = np.array([zz[piece].min(), xx[piece].min()]) - spacing / 2, np.array([zz[piece].max(), xx[piece].max()]) + spacing / 2
    middle, extent = (low + high) / 2.0, (high - low) / 2.0
    if (2 * extent > 2 * half + FIT_WIDER_MM).any() or np.linalg.norm(middle - centre) > FIT_MOST_MM:
        return None
    return middle, extent


def turned(v: np.ndarray, offset, hold: float, far: float) -> np.ndarray:
    """A bone moved across the body's length by `offset` (z, x; mm): wholly at the height `hold` and on from there
    away from `far`, by less and less towards the height `far`, where (and beyond which) it stays. Heights are
    not changed. For the few millimetres it is used for, the bone turned about its far end."""
    v = np.asarray(v)
    w = np.clip((v[:, 1].astype(np.float64) - far) / (hold - far), 0.0, 1.0)
    out = v.astype(np.float64)
    out[:, 0] += w * float(offset[0])
    out[:, 2] += w * float(offset[1])
    return out.astype(v.dtype)


def onto_photographs(fine, skin, bones: dict, side: str, fr, log=print) -> dict:
    """{name: vertices} for those of an arm's three bones (`bones`, as placed) that are found in the photographs
    next to their cut ends: moved onto the photographs' bone there (the module's text). `fr`: the arm's frame."""
    sp, origin = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64)
    out = {}
    for name in ARM:
        v = bones[f"{side} {name}"]
        steps = FIT_FROM_MM + np.arange(0.0, FIT_OVER_MM + 0.5, FIT_STEP_MM)
        levels = fr.top + steps if name == "humerus" else fr.lows[name] - steps      # the whole stretch next to its cut
        far = float(v[:, 1].max() if name == "humerus" else v[:, 1].min())             # the shoulder; the wrist
        found = []
        for level in levels:
            k = int((level - origin[1]) / sp[1])
            at = section(v, level)
            if at is None or not 0 <= k < fine.cover.shape[1]:
                continue
            cover, tissue = fine_muscle._slab(fine, k, k + 1, with_tissue=True)
            got = bone_at(cover[:, 0, :], tissue[:, 0, :], np.asarray(skin.cover[:, k, :]) > 127, sp[[0, 2]], origin[[0, 2]], *at)
            if got is not None:
                found.append((level, got[0] - at[0]))
        if len(found) < FIT_LEVELS:
            log(f"elbows: his {side} {name} is found in {len(found)} of the {len(levels)} photographs next to its cut: left where BoneHub has it")
            continue
        nearest = found[:FIT_LEVELS]                                       # (the levels run from the cut outwards: the join is at the cut)
        offset = np.median([d for _, d in nearest], axis=0)
        hold = float(np.median([y for y, _ in nearest]))
        out[f"{side} {name}"] = turned(v, offset, hold, far)
        apart = [float(np.linalg.norm(d)) for _, d in found]
        left = [float(np.linalg.norm(d - np.clip((y - far) / (hold - far), 0.0, 1.0) * offset)) for y, d in found]
        log(f"elbows: his {side} {name} lay {min(apart):.1f} to {max(apart):.1f} mm from the photographs' bone in {len(found)} photographs next to its cut "
            f"({levels.min():.0f} to {levels.max():.0f} mm up): moved by {offset[0]:+.1f} mm back and {offset[1]:+.1f} mm to his left at {hold:.0f} mm up "
            f"({np.linalg.norm(offset):.1f} mm), by nothing at its far end ({far:.0f} mm up); in those photographs {max(left):.1f} mm at the most are left")
    return out


def read(body: Body, placed: list, log=print):
    """(pieces, placed): `pieces` [(name, vertices in the body's mm (z, y, x), faces)], each elbow's bones as the
    photographs show them where BoneHub's are cut by the CT's edge; and `placed` (bonehub.load_or_build's list)
    with the arms' bones moved onto the photographs' at their cut ends (the module's text). Needs the muscles'
    fine outline and the skin's; without them, or where an arm's bones are not cut, no pieces and `placed` as
    it was."""
    from skimage import measure
    fine = fine_muscle.load(body)
    skin = fine_skin.load(body)
    if fine is None or skin is None:
        return [], placed
    bones = {name: np.asarray(v) for _, name, v, _ in placed if any(k in name for k in ARM)}
    if getattr(fine, "lower", None) is None:
        fine_muscle.calibrate(body, fine, getattr(body, "original_labels", None), log=lambda *_: None)
    sp = np.array(fine.spacing, np.float64)
    origin = np.array(fine.origin_mm, np.float64)
    out, moved = [], {}
    for side in ("right", "left"):
        cut = frame(bones, side)
        if cut is None:
            continue
        eased = onto_photographs(fine, skin, bones, side, cut, log)
        moved.update(eased)
        fr = frame(bones, side, lines_from={**bones, **eased})
        # A bone moved inwards leaves the photographs' bone bare between the CT's edge and its own cut face: read too.
        inwards = max([0.0] + [float(((v[:, 2].astype(np.float64) - bones[name][:, 2]) * fr.inward).max()) for name, v in eased.items()])
        a = max(0, int((fr.low - origin[1]) / sp[1]))
        b = min(fine.cover.shape[1], int((fr.high - origin[1]) / sp[1]) + 1)
        xs = origin[2] + (np.arange(fine.cover.shape[2]) + 0.5) * sp[2]
        beyond = (xs - fr.edge) * fr.inward < OVERLAP_MM + inwards         # the columns the CT does not have (and a lap over its edge)
        wide = (xs - fr.edge) * fr.inward < OVERLAP_MM + inwards + 40.0    # (with room to measure the depth under the arm's other sides)
        x0, x1 = int(np.flatnonzero(wide).min()), int(np.flatnonzero(wide).max()) + 1
        cover, tissue = fine_muscle._slab(fine, a, b, with_tissue=True)
        cover, tissue = cover[:, :, x0:x1], tissue[:, :, x0:x1]
        inside = np.asarray(skin.cover[:, a:b, x0:x1]) > 127
        depth = ndimage.distance_transform_edt(inside, sampling=sp)
        zz, yy, xx = np.meshgrid(origin[0] + (np.arange(cover.shape[0]) + 0.5) * sp[0], origin[1] + (np.arange(a, b) + 0.5) * sp[1], xs[x0:x1], indexing="ij", sparse=True)
        near = np.zeros(cover.shape, bool)
        for k in range(cover.shape[1]):                                   # (photograph by photograph: the whole block's points at once are a gigabyte)
            pts = np.stack(np.broadcast_arrays(zz[:, 0, :], yy[:, k, :], xx[:, 0, :]), axis=-1)
            near[:, k, :] = from_lines(pts, fr.lines) < REACH_MM
        solid = mass(cover, tissue & inside, depth, near & beyond[None, None, x0:x1], sp)
        if not solid.any():
            log(f"elbows: no bone found in the photographs beyond the CT's edge at his {side} elbow")
            continue
        field = ndimage.gaussian_filter(np.pad(solid, 2).astype(np.float32), [BLUR_MM / s for s in sp])
        v, f, _, _ = measure.marching_cubes(field, 0.5, spacing=tuple(sp))
        v = v + origin + (np.array([0, a, x0]) - 2 + 0.5) * sp
        out.append((NAME.format(side), v.astype(np.float32), f))
        parts, count = ndimage.label(solid)
        pieces = np.sort(np.asarray(ndimage.sum(solid, parts, range(1, count + 1))) * np.prod(sp) / 1000.0)[::-1]
        log(f"elbows: his {side} elbow's bones read from the photographs beyond the CT's edge (x = {fr.edge:.0f} mm), {fr.low:.0f} to {fr.high:.0f} mm up: "
            f"{solid.sum() * np.prod(sp) / 1000.0:.0f} cm3 in {count} pieces ({', '.join(f'{x:.1f}' for x in pieces[:6])} cm3), {len(f)} triangles; "
            f"the joint at {np.round(fr.joint, 0).astype(int).tolist()} (z, y, x)")
    return out, [(code, name, moved.get(name, v), f) for code, name, v, f in placed]
