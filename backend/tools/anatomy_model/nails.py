"""The nails: a thin plate on the end of every finger and toe. DRAWN, at places measured on him.

What the data holds (docs/research/nails.md): on the photographs a nail's plate is a pale arc one to three pixels
thick on the back of a digit's end, among the pale rim that every digit's skin has; it shows on some photographs
and cannot be told from that rim by a rule. So his own nails' outlines are not read. What is his: where each
digit ends, which way it points, which side its back is, how wide it is. From those and the usual proportions
of nails (docs/research/skin_features_hair_maps.md, C3) each nail is drawn:

- the digit's bones (BoneHub's `phalanges of the ...`, one mesh for a digit) are first moved as a whole into
  the digit (settle: the CT has a finger up to 5 mm beside where the photographs have it);
- its end is where the bones' middle line, carried on, leaves the skin soonest (tip), pointing the way the last
  quarter of that line points (along);
- its back looks the way the back of its foot or hand looks (limb_back: across the plane the long bones lie
  in, to the side where the skin is nearer them), made square to the digit; the thumb, which is turned against
  the fingers, by the side on which the skin lies nearest its bone (out); across = along x out. (That last rule
  alone, tried for every digit, failed on toes that lie pressed together: a toe's bone is no nearer its back
  than its sides.)
- the digit's width and thickness are those of its end as the skin has it: what lies within reach of the tip
  along the skin (a neighbouring toe is near, but not along the skin);
- the nail is as wide as the table says for that digit, but not more than WIDTH_SHARE of the digit there, as
  long in proportion, and ends INSET of the digit's thickness short of its end.

The plate is a grid in that frame, each point dropped onto the skin's own surface from the back and lifted ABOVE
it; towards the digit's end, where the skin turns down round the tip, the plate goes straight on (the free
edge), as a nail does. Its rim is turned down into the skin (SKIRT), so it has a thickness to look at. Under
it the skin takes the nail bed's colour and carries no hair (on_skin).

    found = nails.find(body, v, f)                  # the frames, on the skin as built (glTF metres)
    plate, fold = nails.on_skin(found, v, n)        # per skin vertex: under a nail, and in the fold round one
    structures = nails.plates(found, v, f)          # one structure a nail, layer "skin", named "nail of the ..."

Every nail's `info` says that it is drawn and what it was drawn from.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from . import bonehub, fine_skin
from .common import Body, Structure, normals_of

# width x length, mm (skin_features_hair_maps.md C3: fingers' widths and the toes' sizes from the textbooks'
# ranges, fingers' lengths by the measured width / length ratios of men's nails)
SIZES = {"great toe": (18.0, 14.0), "second toe": (9.0, 7.0), "third toe": (9.0, 7.0), "fourth toe": (8.5, 6.5), "little toe": (6.0, 4.5),
         "thumb": (16.0, 15.4), "index finger": (12.0, 12.8), "middle finger": (12.5, 13.2), "ring finger": (11.5, 12.1), "little finger": (9.5, 10.2)}
WIDTH_SHARE = 0.72              # a nail is at most this much of its digit's width,
NEIGHBOUR = 0.8                 # and this much of its share of the way to the next digit's
INSET = 0.22                    # it ends this share of the digit's thickness short of the digit's end
ABOVE_MM = 0.15                 # the plate's upper face over the skin
SKIRT_MM = 0.6                  # its rim, turned down
FREE_MM = 0.9                   # the free edge: the plate's last stretch, off-white
ROWS, COLUMNS = 15, 13          # the plate's grid: along, across
SETTLE_MM = 6.0                 # a digit's bones may be moved so far as a whole, to lie in the digit
BED_TOE, BED_FINGER = (212, 186, 156), (201, 170, 162)      # the nail seen on its bed, against the skin's (210, 170, 150): a toe's is
                                                            # yellower and a dead man's fingers' are pale, greyer (C3), neither by much
FREE_EDGE, LUNULA = (226, 214, 196), (216, 196, 186)
FOLD = (1.0, 0.93, 0.92)        # the skin of the folds round a nail is a little redder: its colour times this
GLOSS = 235                     # the plate's gloss in the bake (128 = the material's own)


@dataclass
class Nail:
    """One nail's place: millimetres, the body's array order (z back, y up, x left)."""
    name: str                   # "left great toe"
    tip: np.ndarray             # the digit's end, on the skin
    along: np.ndarray           # unit: the way the digit points
    out: np.ndarray             # unit: out of the digit's back
    across: np.ndarray          # unit: along x out
    axis: np.ndarray            # a point of the digit's middle line, under the nail
    width: float                # the nail's
    length: float
    inset: float                # from the digit's end to the nail's end
    digit: tuple = (0.0, 0.0)   # the digit's width and thickness there
    info: dict = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return self.name.split(" ", 1)[1]

    def local(self, zyx_mm: np.ndarray):
        """Points -> (q, s, h): q 0 at the nail's far end to 1 at its root, s millimetres across from its middle,
        h millimetres out from the digit's middle line."""
        d = np.asarray(zyx_mm, np.float64) - self.axis
        a = (np.asarray(zyx_mm, np.float64) - self.tip) @ self.along
        return (-self.inset - a) / self.length, d @ self.across, d @ self.out


def half_width(q: np.ndarray) -> np.ndarray:
    """The nail's outline: its half width at q (0 far end .. 1 root) as a share of its half width. Rounded at
    the far end as the digit's end is, and at the root."""
    q = np.asarray(q, np.float64)
    g = np.ones(q.shape)
    far = q < 0.28
    g[far] = np.sqrt(np.clip(1.0 - 0.42 * ((0.28 - np.clip(q[far], 0, 0.28)) / 0.28) ** 2, 0.0, 1.0))
    root = q > 0.6
    g[root] = np.sqrt(np.clip(1.0 - 0.48 * ((q[root] - 0.6) / 0.4) ** 2, 0.0, 1.0))
    return g


def first_hits(origins: np.ndarray, directions: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Rays against triangles (k, 3, 3): the distance to each ray's first hit, inf where there is none."""
    origins, directions = np.atleast_2d(origins).astype(np.float64), np.atleast_2d(directions).astype(np.float64)
    out = np.full(len(origins), np.inf)
    if len(triangles) == 0:
        return out
    a, e1, e2 = triangles[:, 0], triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    for i in range(0, len(origins), 256):
        o, d = origins[i:i + 256, None, :], directions[i:i + 256, None, :]
        p = np.cross(d, e2[None])
        det = (e1[None] * p).sum(axis=2)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o - a[None]
        u = (s * p).sum(axis=2) * inv
        q = np.cross(s, e1[None])
        v = (d * q).sum(axis=2) * inv
        t = (e2[None] * q).sum(axis=2) * inv
        hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6)
        out[i:i + 256] = np.where(hit, t, np.inf).min(axis=1)
    return out


def settle(fine: fine_skin.FineOutline, zyx_mm: np.ndarray, most_mm: float = SETTLE_MM) -> np.ndarray:
    """The move (mm, any way, `most_mm` at most, in steps of 1.5) that leaves the fewest of a digit's bone
    vertices at the skin or outside it; the shortest of those that leave as few."""
    field_ = fine_skin.depth_near(fine, zyx_mm, 8.0 + most_mm)
    none = np.zeros(3)
    if field_ is None:
        return none

    def shallow(move):
        return int((fine_skin.depth_at(fine, field_, zyx_mm + move) < 1.0).sum())

    best = (shallow(none), 0.0, none)
    if best[0] == 0:
        return none
    steps = np.arange(-most_mm, most_mm + 0.1, 1.5)
    for dz in steps:
        for dy in steps:
            for dx in steps:
                far = float(np.sqrt(dz * dz + dy * dy + dx * dx))
                if 0 < far <= most_mm:
                    move = np.array([dz, dy, dx])
                    found = (shallow(move), far, move)
                    if found[:2] < best[:2]:
                        best = found
    return best[2]


def limb_back(bones: list, triangles: np.ndarray) -> np.ndarray | None:
    """The way a foot's or a hand's back looks (unit; mm axes): across the plane its long bones lie in (the least
    of their three spreads), to the side on which the skin lies nearer them (the back of a foot has a few
    millimetres over the bones, its sole fifteen)."""
    if not bones:
        return None
    points = np.concatenate(bones)
    centre = points.mean(axis=0)
    normal = np.linalg.svd(points - centre, full_matrices=False)[2][2]
    near = first_hits(np.stack([centre, centre]), np.stack([normal, -normal]), triangles)
    if not np.isfinite(near).any():
        return None
    return normal if near[0] <= near[1] else -normal


def frame(name: str, bone: np.ndarray, back: np.ndarray | None, others: list, skin_mm: np.ndarray, faces: np.ndarray) -> Nail | None:
    """One digit's nail from its bones (settled; mm), the way its limb's back looks, the other digits' bones, and
    the skin near it (vertices mm, faces). None when the digit's end is not found."""
    kind = name.split(" ", 1)[1]
    triangles = skin_mm[faces]
    centre = bone.mean(axis=0)
    main = np.linalg.svd(bone - centre, full_matrices=False)[2][0]
    t = (bone - centre) @ main
    edges = np.linspace(t.min(), t.max() + 1e-6, 9)
    line = np.array([bone[(t >= lo) & (t < hi)].mean(axis=0) for lo, hi in zip(edges[:-1], edges[1:]) if ((t >= lo) & (t < hi)).sum() >= 3])
    if len(line) < 5:
        return None
    # The digit's end: where the bones' middle line, carried on from within the digit, leaves the skin soonest
    # (from within: a bone's own end may stand out of a toe that was pressed flat).
    ends = []
    for end, start in ((line[0], line[2]), (line[-1], line[-3])):
        way = (end - start) / np.linalg.norm(end - start)
        hit = float(first_hits(start, way, triangles)[0])
        ends.append((hit - float(np.linalg.norm(end - start)), start + way * hit, way))
    beyond, tip, along = min(ends, key=lambda e: e[0])
    if not np.isfinite(beyond) or beyond > 30.0:
        return None
    width, length = SIZES[kind]
    # Its back.
    out = None
    if back is not None and kind != "thumb":
        out = back - (back @ along) * along
        out = out / np.linalg.norm(out) if np.linalg.norm(out) > 0.2 else None
    if out is None:
        # The thumb is turned against the fingers: its back is the side on which the skin lies nearest the bone
        # (a millimetre or two over the bone under a nail, eight under the pad), not towards a finger, nor
        # looking the other way from the hand's back.
        station = tip - along * (0.5 * length + 3.0)
        under = bone[np.argsort(np.linalg.norm(bone - station, axis=1))[:40]].mean(axis=0)
        e1 = np.cross(along, [1.0, 0.0, 0.0] if abs(along[0]) < 0.8 else [0.0, 1.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(along, e1)
        angles = np.radians(np.arange(0, 360, 5))
        ways = np.cos(angles)[:, None] * e1 + np.sin(angles)[:, None] * e2
        far = first_hits(np.tile(under, (len(ways), 1)), ways, triangles)
        far = ndimage.uniform_filter1d(np.where(np.isfinite(far), far, 40.0), 5, mode="wrap")
        allowed = np.ones(len(ways), bool) if back is None else ways @ back > -0.3
        for other in others:
            gap = other - under
            nearest = gap[np.argmin(np.linalg.norm(gap, axis=1))]
            side = nearest - (nearest @ along) * along
            if np.linalg.norm(nearest) < 32.0 and np.linalg.norm(side) > 1.0:
                allowed &= ways @ (side / np.linalg.norm(side)) < np.cos(np.radians(60.0))
        if not allowed.any():
            return None
        out = ways[np.flatnonzero(allowed)[np.argmin(far[allowed])]]
    across = np.cross(along, out)
    # The digit's thickness and width under the nail, from its middle line (the line through its end, the way it
    # points) to the skin either way. Across, a toe that lies pressed to its neighbour has no skin of its own to
    # meet: then the ray runs on into the neighbour, and the table's width stands (find narrows it by the
    # neighbours' distance).
    def through(point, way):
        both = first_hits(np.stack([point, point]), np.stack([way, -way]), triangles)
        return float(both.sum()) if np.isfinite(both).all() else float("inf")

    thick = through(tip - along * (0.5 * length + 3.0), out)
    if not np.isfinite(thick) or thick > 45.0:
        return None
    inset = INSET * thick
    middle = tip - along * (inset + length / 2)
    wide = through(middle, across)
    if not np.isfinite(wide) or wide > 2.2 * width:
        wide = width / WIDTH_SHARE
    mine = min(width, WIDTH_SHARE * wide)
    return Nail(name, tip, along, out, across, middle, mine, length * mine / width, inset, (wide, thick),
                {"drawn": "its outline is not read from him: a nail of the usual proportions, laid where his digit ends and as wide as the digit allows",
                 "digit_width_mm": round(wide, 1), "digit_thickness_mm": round(thick, 1)})


def find(body: Body, v: np.ndarray, f: np.ndarray, log=print, limbs: tuple = ("toe",)) -> list[Nail]:
    """The digits' nails, on the skin as built (v: glTF metres). Needs BoneHub's bones and the fine outline;
    without them, none.

    The toes' only, as it stands (`limbs`): the skin of the hands is still read by the rule that joins what lies
    together, his fingers lie together, and on fingers that are one piece of skin the nails come out across each
    other (tried: of the right hand's five, two are not found and two overlap). The fingers' nails wait for the
    hands' skin."""
    from . import feet
    fine = fine_skin.load(body)
    if fine is None or not bonehub.cache_path(body).exists():
        return []
    placed, _, _ = bonehub.load_or_build(body, None, log)
    bones = {name: np.asarray(bv, np.float64) for _, name, bv, _ in placed}
    digits = {name[len("phalanges of the "):]: bv for name, bv in bones.items() if name.startswith("phalanges of the ")}
    size = feet.size_of(body)
    skin_mm = feet.to_mm(size, v)
    f = np.asarray(f)
    centres = skin_mm[f].mean(axis=1)
    for name in digits:
        digits[name] = digits[name] + settle(fine, digits[name][::max(1, len(digits[name]) // 600)])
    backs = {}
    for side in ("left", "right"):
        for limb, long in (("toe", [f"{side} metatarsal {k}" for k in range(1, 6)]), ("finger", [f"{side} metacarpal {k}" for k in range(2, 6)])):
            have = [bones[name] for name in long if name in bones]
            if have:
                middle = np.concatenate(have).mean(axis=0)
                backs[(side, limb)] = limb_back(have, skin_mm[f[np.linalg.norm(centres - middle, axis=1) < 90.0]])
    found = []
    for name, bone in sorted(digits.items()):
        side, kind = name.split(" ", 1)
        if kind not in SIZES:
            continue
        limb = "toe" if "toe" in kind else "finger"
        if limb not in limbs:
            continue
        near = np.flatnonzero(np.linalg.norm(centres - bone.mean(axis=0), axis=1) < float(np.ptp(bone, axis=0).max()) * 0.5 + 35.0)
        used, inverse = np.unique(f[near], return_inverse=True)
        others = [o for other, o in digits.items() if other != name and other.split(" ", 1)[0] == side and (("toe" in other) == (limb == "toe"))]
        nail = frame(name, bone, backs.get((side, limb)), others, skin_mm[used], inverse.reshape(-1, 3)) if len(near) else None
        if nail is None:
            log(f"nails: the {name}'s end was not found: no nail drawn")
            continue
        found.append(nail)
    # No nail wider than its share of the way to the next digit's: of the distance between two digits' middles
    # each has the part that its own width is of the two widths together, and its nail NEIGHBOUR of that, twice.
    for nail in found:
        side, limb = nail.name.split(" ", 1)[0], "toe" in nail.name
        room = []
        for other in found:
            if other is not nail and other.name.split(" ", 1)[0] == side and ("toe" in other.name) == limb:
                gap = other.axis - nail.axis
                room.append(2.0 * NEIGHBOUR * float(np.linalg.norm(gap - (gap @ nail.along) * nail.along)) * nail.digit[0] / (nail.digit[0] + other.digit[0]))
        if room and min(room) < nail.width:
            narrow = min(room)
            nail.length, nail.width = nail.length * narrow / nail.width, narrow
            nail.info["narrowed"] = "by its neighbour's distance"
    if found:
        log("nails (width x length mm; the digit's width): " + "; ".join(f"{n.name} {n.width:.1f} x {n.length:.1f} ({n.digit[0]:.1f})" for n in found))
    return found


def on_skin(found: list[Nail], v: np.ndarray, normals: np.ndarray, size: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per skin vertex (v glTF metres, its normals): how much it lies under a nail (0..1), how much in the fold
    round one, and the nail bed's colour there (uint8 sRGB; anything where the first is 0)."""
    from . import feet
    mm = feet.to_mm(size, v)
    normal = np.stack([-normals[:, 2], normals[:, 1], normals[:, 0]], axis=1)
    plate, fold = np.zeros(len(mm)), np.zeros(len(mm))
    bed = np.zeros((len(mm), 3), np.uint8)
    for nail in found:
        near = np.flatnonzero(np.linalg.norm(mm - (nail.tip - nail.along * (nail.inset + nail.length / 2)), axis=1) < nail.length + 6.0)
        if len(near) == 0:
            continue
        q, s, h = nail.local(mm[near])
        back = (h > 0) & (normal[near] @ nail.out > 0.2)
        edge = np.minimum.reduce([(nail.width / 2) * half_width(np.clip(q, 0, 1)) - np.abs(s), q * nail.length, (1.0 - q) * nail.length])      # mm inside the outline
        inside = back * np.clip(edge / 0.5 + 0.5, 0, 1)
        round_it = back * np.clip((edge + 1.6) / 0.6, 0, 1) * (1.0 - np.clip(edge / 0.5 + 0.5, 0, 1)) * (q > 0.05)
        better = inside > plate[near]
        plate[near] = np.maximum(plate[near], inside)
        fold[near] = np.maximum(fold[near], round_it)
        bed[near[better]] = BED_TOE if "toe" in nail.name else BED_FINGER
    return plate, fold, bed


def plates(found: list[Nail], v: np.ndarray, f: np.ndarray, size: np.ndarray) -> list[Structure]:
    """The nails' plates: one structure each, layer "skin"."""
    from . import feet
    skin_mm = feet.to_mm(size, v)
    f = np.asarray(f)
    centres = skin_mm[f].mean(axis=1)
    out = []
    for nail in found:
        middle = nail.tip - nail.along * (nail.inset + nail.length / 2)
        triangles = skin_mm[f[np.linalg.norm(centres - middle, axis=1) < nail.length + 12.0]]
        got = plate(nail, triangles)
        if got is None:
            continue
        pv, pf, colour = got
        bake = np.zeros((len(pv), 4), np.uint8)
        bake[:, 0], bake[:, 1], bake[:, 2], bake[:, 3] = 255, 30, 0, GLOSS
        bed = BED_TOE if "toe" in nail.name else BED_FINGER
        out.append(Structure(f"nail of the {nail.name}", "skin", feet.to_gltf(size, pv), pf, tuple(c / 255.0 for c in bed), bake=bake, albedo=colour,
                             info={"class": "nail", "width_mm": round(nail.width, 1), "length_mm": round(nail.length, 1), **nail.info}))
    return out


def plate(nail: Nail, triangles: np.ndarray):
    """One nail's plate (vertices mm, faces wound to look out, colours uint8) on the skin's triangles near it;
    None when the skin is not found under it."""
    over = (FREE_MM * 0.5) / nail.length                                 # the free edge stands this far (as q) beyond the nail's bed
    q = np.linspace(-over, 1.0, ROWS)
    sigma = np.linspace(-1.0, 1.0, COLUMNS)
    place = nail.tip - nail.along * nail.inset + ((nail.axis - nail.tip) - ((nail.axis - nail.tip) @ nail.along) * nail.along)      # the far end's middle, on the axis
    grid = (place[None, None] - q[:, None, None] * nail.length * nail.along
            + (sigma[None, :] * (nail.width / 2) * half_width(np.clip(q, 0, 1))[:, None])[..., None] * nail.across)
    # The skin's height over the grid's plane, which lies in the digit's middle: outwards from each point of it (from
    # outside inwards, another digit that lies over this one would be met first).
    height = first_hits(grid.reshape(-1, 3), np.tile(nail.out, (ROWS * COLUMNS, 1)), triangles).reshape(ROWS, COLUMNS)
    height[height > nail.digit[1]] = np.inf
    known = np.isfinite(height)
    if known[ROWS // 2:].sum() < 0.8 * known[ROWS // 2:].size:
        return None
    for j in range(COLUMNS):                                             # a column's gaps take its neighbours' height
        col = height[:, j]
        ok = np.isfinite(col)
        if ok.any():
            col[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), col[ok])
        else:
            height[:, j] = np.nanmean(np.where(known, height, np.nan))
    # Towards the digit's end the skin turns down round the tip; a nail goes straight on.
    for i in range(ROWS - 3, -1, -1):
        straight = 2.0 * height[i + 1] - height[i + 2]
        height[i] = np.maximum(height[i], np.minimum(straight, height[i + 1]) - 0.05)
    top = grid + nail.out * (height + ABOVE_MM)[..., None]
    # The rim, turned down and a little in.
    index = np.arange(ROWS * COLUMNS).reshape(ROWS, COLUMNS)
    ring = np.concatenate([index[0, :-1], index[:-1, -1], index[-1, :0:-1], index[:0:-1, 0]])
    centre = top.reshape(-1, 3).mean(axis=0)
    rim = top.reshape(-1, 3)[ring]
    skirt = rim - nail.out * SKIRT_MM + (centre - rim) * 0.02
    vertices = np.concatenate([top.reshape(-1, 3), skirt])
    faces = []
    for i in range(ROWS - 1):
        for j in range(COLUMNS - 1):
            a, b, c, d = index[i, j], index[i, j + 1], index[i + 1, j + 1], index[i + 1, j]
            faces += [(a, b, c), (a, c, d)]
    n0 = ROWS * COLUMNS
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        c, d = n0 + (k + 1) % len(ring), n0 + k
        faces += [(a, c, b), (a, d, c)]
    faces = np.array(faces, np.uint32)
    # Wound to look out of the digit's back (the body's millimetres and glTF's metres are a turn apart, not a
    # mirror image: what is wound right here is wound right there).
    tri = vertices[faces[:(ROWS - 1) * (COLUMNS - 1) * 2]]
    if (np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]) @ nail.out).sum() < 0:
        faces = faces[:, ::-1].copy()
    bed = np.array(BED_TOE if "toe" in nail.name else BED_FINGER, np.float64)
    qq = np.repeat(q[:, None], COLUMNS, axis=1)
    ss = np.repeat(np.abs(sigma)[None, :], ROWS, axis=0)
    free = np.clip((FREE_MM / nail.length - qq) / (0.6 / nail.length), 0, 1)
    moon = np.clip((qq - (0.80 + 0.14 * ss ** 2)) / 0.05, 0, 1) * (0.9 if nail.kind in ("thumb", "great toe") else 0.5 if nail.kind in ("index finger", "middle finger") else 0.0)
    colour = bed + (np.array(LUNULA, np.float64) - bed) * moon[..., None]
    colour = colour + (np.array(FREE_EDGE, np.float64) - colour) * free[..., None]
    colour = colour.reshape(-1, 3)
    colour = np.concatenate([colour, colour[ring] * 0.9])
    return vertices, faces, np.round(np.clip(colour, 0, 255)).astype(np.uint8)
