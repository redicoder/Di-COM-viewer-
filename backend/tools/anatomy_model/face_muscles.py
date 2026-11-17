"""The muscles of expression, drawn on his own skull and under his own skin.

No open data set has these muscles as shapes (docs/research/head_anatomy_data.md, 4.1 and 5.5), and in his frozen
head they are a millimetre or two thick: the labels show them as scraps. So they are GENERATED: each muscle is a
band from where it arises to where it ends, as the textbooks give them (the table in 5.5: origin, insertion,
length x width x thickness), placed on HIS head: its bony end on his skull's surface, its other end at its depth
under his skin, between them through his own soft tissue. They are a drawing of where these muscles lie in a face
of his shape, not a reading of his muscles; every one carries info["generated"].

How a band is laid. From a point in the middle of the head (behind the nose, between the ears) every direction
meets his skull's outer surface and then his skin: two maps of radius by direction, made once from the two
meshes. A muscle is a strip of directions from its origin's to its insertion's (a straight run on the sphere, or
an ellipse for the ring muscles), so wide; along it the band's outer face goes from lying on the bone to its
depth under the skin, never deeper than the bone nor nearer the skin than 1.2 mm, and its inner face a thickness
below. Points are given in the face's own frame (u to his left, w up, millimetres from between the eyes; zones.Face),
measured off what the model already knows: the eyes, the nose, the lip line.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from . import head_layers, mouth
from .common import Body, Structure, load_structures
from .zones import MM, Face

MUSCLE = (0.50, 0.23, 0.21)
TENDON = (0.74, 0.62, 0.52)
STEP_DEGREES = 0.35                       # the maps' cell: 0.6 mm at 100 mm from the centre
GRID_MM = 1.4                             # the bands' own mesh
SKIN_MM = 2.4                             # no muscle nearer the skin than this (the fat layer's face lies 1.5 to 2.5 mm under it)
DEEP_MM = 22.0                            # bone further under the skin than this is not a face muscle's bed


@dataclass
class Maps:
    """His skin and skull seen from the head's middle: radius (mm) by direction."""
    centre: np.ndarray                    # glTF metres
    axes: np.ndarray                      # rows: the face's ex (to his left), ey (up), ez (forward)
    skin: np.ndarray                      # (latitudes, longitudes) mm; 0 where no skin was met
    bone: np.ndarray                      # the skull's outermost surface; 0 where the direction meets no bone
    face: np.ndarray = None               # the skin without what stands out of the face narrowly (the nose): for muscles that pass beside it
    lon0: float = -125.0
    lat0: float = -80.0

    def cell(self, directions: np.ndarray):
        d = directions @ self.axes.T                                         # across, up, forward
        lon = np.degrees(np.arctan2(d[:, 0], d[:, 2]))
        lat = np.degrees(np.arcsin(np.clip(d[:, 1], -1.0, 1.0)))
        return np.stack([(lat - self.lat0) / STEP_DEGREES, (lon - self.lon0) / STEP_DEGREES], axis=0)

    def radius(self, which: np.ndarray, directions: np.ndarray) -> np.ndarray:
        return ndimage.map_coordinates(which, self.cell(directions), order=1, mode="nearest")

    def direction(self, points: np.ndarray) -> np.ndarray:
        d = np.asarray(points, np.float64) - self.centre
        return d / np.linalg.norm(d, axis=-1, keepdims=True)


def _splat(maps_shape, cells: np.ndarray, radius: np.ndarray, least: bool) -> np.ndarray:
    """The greatest radius met in each cell, or the least; 0 where none was met. Cells that no point fell into,
    between ones that have a radius, take their neighbours' (greatest or least alike)."""
    i = np.round(cells[0]).astype(int)
    j = np.round(cells[1]).astype(int)
    ok = (i >= 0) & (i < maps_shape[0]) & (j >= 0) & (j < maps_shape[1])
    if least:
        out = np.full(maps_shape, np.inf, np.float32)
        np.minimum.at(out, (i[ok], j[ok]), radius[ok].astype(np.float32))
        for _ in range(2):
            out = np.where(np.isfinite(out), out, ndimage.minimum_filter(out, 3))
        return np.where(np.isfinite(out), out, 0.0).astype(np.float32)
    out = np.zeros(maps_shape, np.float32)
    np.maximum.at(out, (i[ok], j[ok]), radius[ok].astype(np.float32))
    for _ in range(2):
        out = np.where(out > 0, out, ndimage.maximum_filter(out, 3))
    return out


def _dense(v: np.ndarray, f: np.ndarray, step_m: float) -> np.ndarray:
    """Points on a mesh no further apart than `step_m`: its vertices and, on its bigger triangles, points between."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    longest = np.max([np.linalg.norm(a - b, axis=1), np.linalg.norm(b - c, axis=1), np.linalg.norm(c - a, axis=1)], axis=0)
    out = [v]
    for parts in range(2, 9):
        mine = (longest > step_m * (parts - 1)) & ((longest <= step_m * parts) | (parts == 8))
        if not mine.any():
            continue
        for i in range(parts + 1):
            for j in range(parts + 1 - i):
                k = parts - i - j
                out.append((a[mine] * i + b[mine] * j + c[mine] * k) / parts)
    return np.concatenate(out)


def make_maps(face: Face, skin_v: np.ndarray, skin_f: np.ndarray, bone_v: np.ndarray, bone_f: np.ndarray) -> Maps:
    centre = face.origin - face.ez * 0.085 - face.ey * 0.045
    axes = np.stack([face.ex, face.ey, face.ez])
    shape = (int(160.0 / STEP_DEGREES), int(250.0 / STEP_DEGREES))
    maps = Maps(centre, axes, np.zeros(shape, np.float32), np.zeros(shape, np.float32))
    for name, v, f in (("skin", skin_v, skin_f), ("bone", bone_v, bone_f)):
        v = np.asarray(v, np.float64)
        near = np.linalg.norm(v - centre, axis=1) < 0.19
        keep = near[f].all(axis=1)
        points = _dense(v, np.asarray(f)[keep], 0.0005)
        offset = points - centre
        r = np.linalg.norm(offset, axis=1)
        # The skin: the first skin a direction meets (where the nose's wing or a fold stands before more skin, a
        # muscle must stay under the nearer); never more than what was met, so nothing laid under it comes out
        # of it. The bone: its outermost surface.
        grid = _splat(shape, maps.cell(offset / r[:, None]), r * 1000.0, least=name == "skin")
        blurred = ndimage.gaussian_filter(grid, 1.0)
        weight = ndimage.gaussian_filter((grid > 0).astype(np.float32), 1.0)
        smooth = np.where(grid > 0, blurred / np.maximum(weight, 1e-6), 0.0)
        setattr(maps, name, (np.minimum(smooth, grid) if name == "skin" else smooth).astype(np.float32))
    # The face without its nose: what is narrower than 40 mm and stands out is taken down to what lies round it.
    index = ndimage.distance_transform_edt(maps.skin <= 0, return_distances=False, return_indices=True)
    filled = maps.skin[tuple(index)]
    cells = int(40.0 / (100.0 * np.radians(STEP_DEGREES))) | 1
    maps.face = np.minimum(ndimage.gaussian_filter(ndimage.grey_opening(filled, size=(cells, cells)), 3.0), filled).astype(np.float32)
    return maps


class Layout:
    """Points of the face by name and by (u, w): on the skin, or on the bone under it."""

    def __init__(self, face: Face, maps: Maps, lip_w):
        self.face, self.maps, self.lip_w = face, maps, lip_w
        # The face from in front: how far forward the skin and the bone reach at each (u, w), from the maps.
        u, w = np.meshgrid(np.arange(-80.0, 80.5, 0.5), np.arange(-150.0, 95.5, 0.5))
        self.u0, self.w0 = -80.0, -150.0
        self.front = {}
        for name in ("skin", "bone"):
            self.front[name] = np.full(u.shape, np.nan, np.float32)
        lat = (np.arange(maps.skin.shape[0]) * STEP_DEGREES + maps.lat0)[:, None]
        lon = (np.arange(maps.skin.shape[1]) * STEP_DEGREES + maps.lon0)[None, :]
        local = np.stack([np.cos(np.radians(lat)) * np.sin(np.radians(lon)), np.sin(np.radians(lat)) * np.ones_like(lon), np.cos(np.radians(lat)) * np.cos(np.radians(lon))], axis=-1)
        offset = (maps.centre - face.origin) / MM
        c = np.array([offset @ face.ex, offset @ face.ey, offset @ face.ez])
        for name in ("skin", "bone"):
            r = getattr(maps, name)
            p = local * r[..., None] + c                                     # each cell's point in the face's millimetres
            ok = (r > 0) & (local[..., 2] > 0.15)
            i = np.round((p[..., 1][ok] - self.w0) / 0.5).astype(int)
            j = np.round((p[..., 0][ok] - self.u0) / 0.5).astype(int)
            inside = (i >= 0) & (i < u.shape[0]) & (j >= 0) & (j < u.shape[1])
            grid = np.full(u.shape, -1e9, np.float32)
            np.maximum.at(grid, (i[inside], j[inside]), p[..., 2][ok][inside].astype(np.float32))
            for _ in range(3):
                grid = np.where(grid > -1e8, grid, ndimage.maximum_filter(grid, 3))
            self.front[name] = np.where(grid > -1e8, grid, np.nan)

    def forward(self, name: str, u: float, w: float) -> float:
        grid = self.front[name]
        i = int(np.clip(round((w - self.w0) / 0.5), 0, grid.shape[0] - 1))
        j = int(np.clip(round((u - self.u0) / 0.5), 0, grid.shape[1] - 1))
        return float(grid[i, j])

    def on_skin(self, u: float, w: float) -> np.ndarray:
        d = self.forward("skin", u, w)
        return self.face.origin + (self.face.ex * u + self.face.ey * w + self.face.ez * d) * MM

    def on_bone(self, u: float, w: float, search_mm: float = 5.0) -> np.ndarray:
        """The bone under (u, w); where that is a hollow (an orbit, the nose's opening), the foremost bone within
        `search_mm`, which is the hollow's rim."""
        grid = self.front["bone"]
        i = int(np.clip(round((w - self.w0) / 0.5), 0, grid.shape[0] - 1))
        j = int(np.clip(round((u - self.u0) / 0.5), 0, grid.shape[1] - 1))
        k = int(search_mm / 0.5)
        block = grid[max(0, i - k):i + k + 1, max(0, j - k):j + k + 1]
        if np.isnan(block).all():
            return self.on_skin(u, w) - self.face.ez * 0.008
        best = np.unravel_index(int(np.nanargmax(block)), block.shape)
        bi, bj = max(0, i - k) + best[0], max(0, j - k) + best[1]
        if not np.isnan(grid[i, j]) and grid[i, j] > grid[bi, bj] - 2.5:    # the bone right here is no hollow: it is the point
            bi, bj = i, j
        return self.face.origin + (self.face.ex * (self.u0 + bj * 0.5) + self.face.ey * (self.w0 + bi * 0.5) + self.face.ez * float(grid[bi, bj])) * MM


def _slerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    angle = np.arccos(np.clip(a @ b, -1.0, 1.0))
    if angle < 1e-6:
        return np.tile(a, (len(t), 1))
    return (np.sin((1 - t) * angle)[:, None] * a + np.sin(t * angle)[:, None] * b) / np.sin(angle)


def strip(maps: Maps, line: np.ndarray, half_width: np.ndarray, thick: np.ndarray, under_skin: np.ndarray, on_bone: np.ndarray, closed: bool = False,
          beside_nose: bool = False, radius: np.ndarray | None = None):
    """A band along `line` (unit directions from the head's middle, n of them): at each of them `half_width` (mm)
    to either side, `thick` (mm) deep, its outer face `under_skin` (mm) below the skin, or lying on the bone where
    `on_bone` (0..1) says so. `beside_nose`: under the face's skin as it would be without the nose (a band that
    passes the nose's side would else climb it). `radius`: its outer face at these distances from the head's middle
    instead (mm, one per row: a deep muscle that follows neither skin nor bone).
    Returns vertices (glTF metres), faces, and per vertex how far along (0..1) and across (-1..1)."""
    n = len(line)
    skin_map = maps.face if beside_nose else maps.skin
    r_mid = np.maximum(maps.radius(skin_map, line), 30.0)
    tangent = np.gradient(line, axis=0)
    if closed:
        tangent[0] = line[1] - line[-1]
        tangent[-1] = line[0] - line[-2]
    tangent -= line * np.einsum("ij,ij->i", tangent, line)[:, None]
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    side = np.cross(line, tangent)
    across = max(3, int(np.ceil(2 * float(np.max(half_width)) / GRID_MM)) | 1)       # an odd count: a middle row
    s = np.linspace(-1.0, 1.0, across)
    directions = line[:, None, :] + side[:, None, :] * (s[None, :, None] * (half_width / r_mid)[:, None, None])
    directions /= np.linalg.norm(directions, axis=2, keepdims=True)
    flat = directions.reshape(-1, 3)
    skin = maps.radius(skin_map, flat).reshape(n, across)
    bone = maps.radius(maps.bone, flat).reshape(n, across)
    lens = np.sqrt(np.clip(1.0 - s ** 2, 0.0, 1.0))[None, :] * 0.85 + 0.15                # thinner towards its edges
    depth = thick[:, None] * lens
    outer = skin - under_skin[:, None]
    has_bone = (bone > 20.0) & (skin - bone < DEEP_MM)                                   # bone far under the skin (through an orbit, the nose) is not this muscle's bed
    seated = bone + depth + 0.3                                                         # lying on the bone
    outer = np.where(has_bone, outer + (seated - outer) * on_bone[:, None], outer)
    outer = np.minimum(outer, skin - SKIN_MM)
    inner = outer - depth
    low = has_bone & (inner < bone + 0.2)                                               # not into the bone: lifted, and thinned if the skin is near
    inner = np.where(low, bone + 0.2, inner)
    outer = np.minimum(np.maximum(outer, inner + 0.35), skin - 1.5)
    if radius is not None:
        outer = np.minimum(np.broadcast_to(radius[:, None], outer.shape), skin - SKIN_MM)
        inner = outer - depth
    top = maps.centre + directions * (outer[..., None] * MM)
    bottom = maps.centre + directions * (inner[..., None] * MM)
    v = np.concatenate([top.reshape(-1, 3), bottom.reshape(-1, 3)])
    faces = []
    count = n * across
    rows = n if closed else n - 1
    for i in range(rows):
        i2 = (i + 1) % n
        for j in range(across - 1):
            # (along x across = outward: so a triangle a, the next along, the next across looks out)
            a, b, c, d = i * across + j, i * across + j + 1, i2 * across + j + 1, i2 * across + j
            faces += [(a, c, b), (a, d, c), (count + a, count + b, count + c), (count + a, count + c, count + d)]
        for j in (0, across - 1):                                                       # the two long edges closed
            a, d = i * across + j, i2 * across + j
            quad = (a, count + a, count + d, d) if j == 0 else (a, d, count + d, count + a)
            faces += [(quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])]
    if not closed:                                                                      # and the two ends
        for i, last in ((0, False), (n - 1, True)):
            for j in range(across - 1):
                a, b = i * across + j, i * across + j + 1
                quad = (a, b, count + b, count + a) if not last else (a, count + a, count + b, b)
                faces += [(quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])]
    along = np.repeat(np.linspace(0.0, 1.0, n), across)
    return v.astype(np.float32), np.array(faces, np.int64), np.tile(along, 2), np.tile(np.tile(s, n), 2)


def band(maps: Maps, points: list, widths: tuple, thick, depth: tuple, seated: float = 0.35, beside_nose: bool = False, radii: tuple | None = None):
    """A muscle from points[0] (its origin) through any middle points to points[-1] (its insertion), all glTF
    metres. `widths`: half its width at the origin and at the insertion, mm. `depth`: its outer face's depth under
    the skin at the two ends, mm; a first value of None = it arises from the bone, and lies on it for the first
    `seated` of its length. `radii`: its outer face runs from this distance from the head's middle to that (mm) instead."""
    dirs = [maps.direction(p) for p in points]
    legs = [np.arccos(np.clip(a @ b, -1, 1)) for a, b in zip(dirs[:-1], dirs[1:])]
    r = float(np.mean([np.linalg.norm(p - maps.centre) for p in points])) * 1000.0
    total = sum(legs) * r
    n = max(4, int(np.ceil(total / GRID_MM)) + 1)
    t = np.linspace(0.0, 1.0, n)
    edges = np.concatenate([[0.0], np.cumsum(legs)]) / max(sum(legs), 1e-9)
    line = np.zeros((n, 3))
    for k in range(len(legs)):
        mine = (t >= edges[k] - 1e-12) & (t <= edges[k + 1] + 1e-12)
        local = (t[mine] - edges[k]) / max(edges[k + 1] - edges[k], 1e-9)
        line[mine] = _slerp(dirs[k], dirs[k + 1], local)
    ease = t * t * (3 - 2 * t)
    half = widths[0] + (widths[1] - widths[0]) * ease
    first_thick, last_thick = thick if np.ndim(thick) else (thick, thick)
    thickness = first_thick + (last_thick - first_thick) * t
    ends = np.minimum(1.0, np.minimum(t, 1 - t) * total / 3.0) * 0.6 + 0.4                 # thinner at its two ends
    first = depth[1] if depth[0] is None else depth[0]
    under = first + (depth[1] - first) * ease
    on_bone = np.clip(1.0 - (t - seated) / 0.3, 0.0, 1.0) if depth[0] is None else np.zeros(n)
    radius = None if radii is None else radii[0] + (radii[1] - radii[0]) * t
    return strip(maps, line, half, thickness * ends, under, on_bone, beside_nose=beside_nose, radius=radius)


def ring(maps: Maps, layout: Layout, centre: tuple, radii: tuple, half_width: float, thick: float, under_skin: float, arc=(0.0, 360.0)):
    """A ring muscle: round the ellipse of `radii` (mm, across and up) about (u, w) `centre` on the skin, or the arc
    of it between two angles (degrees, anticlockwise from his left as seen from in front)."""
    whole = arc[1] - arc[0] >= 359.9
    length = np.radians(arc[1] - arc[0]) * float(np.mean(radii))
    n = max(8, int(np.ceil(length / GRID_MM)))
    angles = np.radians(np.linspace(arc[0], arc[1], n, endpoint=not whole))
    points = np.array([layout.on_skin(centre[0] + radii[0] * np.cos(a), centre[1] + radii[1] * np.sin(a)) for a in angles])
    line = maps.direction(points)
    for _ in range(2):                                                                   # the skin's small relief out of the line
        line = (np.roll(line, 1, axis=0) + 2 * line + np.roll(line, -1, axis=0)) / 4 if whole else np.concatenate([line[:1], (line[:-2] + 2 * line[1:-1] + line[2:]) / 4, line[-1:]])
        line /= np.linalg.norm(line, axis=1, keepdims=True)
    ones = np.ones(len(line))
    return strip(maps, line, ones * half_width, ones * thick, ones * under_skin, np.zeros(len(line)), closed=whole)


def _muscle(name: str, built, note: str, from_bone: bool = False) -> Structure:
    v, f, along, across = built
    # Its fibres run along it: lighter and darker lines across its width; pale, as a tendon is, at its bony end.
    fibre = 0.87 + 0.13 * np.sin(across * 15.0 + 1.5 * np.sin(along * 6.0))
    colour = np.array(MUSCLE)[None, :] * 255.0 * fibre[:, None]
    if from_bone:
        pale = np.clip(1.0 - along / 0.09, 0.0, 1.0)[:, None]
        colour = colour + (np.array(TENDON)[None, :] * 255.0 - colour) * pale * 0.8
    bake = np.tile(np.array([235, 14, 82, 128], np.uint8), (len(v), 1))
    return Structure(name, "muscles", v, f.astype(np.uint32), MUSCLE, bake=bake, albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8),
                     info={"class": "muscle", "generated": True, "source": "drawn from its origin and insertion on his skull and skin (docs/research/head_anatomy_data.md 5.5)", "note": note})


def prepare(body: Body, log=print):
    """The face's frame and the two maps, once per run (kept on the body); None where the skin, the skull or the
    eyes are not at hand."""
    if getattr(body, "face_maps", None) is not None:
        return body.face_maps
    from . import bonehub, skin as skin_layer
    surface_path = body.export / "model" / "skin_surface.npz"
    if not surface_path.exists() or not bonehub.cache_path(body).exists() or len(getattr(body, "eyes_measured", None) or []) != 2:
        return None
    surface = load_structures(surface_path)[0]
    face = Face(skin_layer.landmarks(body), surface.v)
    placed, _, _ = bonehub.load_or_build(body, None, log)
    bones = [(v, f) for _, name, v, f in placed if name in ("cranium and maxilla", "mandible")]
    if not bones:
        return None
    bone_v = np.concatenate([body.to_gltf(v, f)[0] for v, f in bones])
    bone_f = np.concatenate([f + k for (v, f), k in zip(bones, np.cumsum([0] + [len(v) for v, _ in bones[:-1]]))])
    body.face_maps = (face, make_maps(face, surface.v, surface.f, bone_v, bone_f))
    return body.face_maps


LID_REACH_MM = 9.0              # a muscle's point belongs to the skin's nearest vertex within this


def lid_skin(body: Body):
    """The skin's vertices that move when a lid is opened (glTF metres) and all the skin's vertices near the eyes with
    whether they move: (vertices, moves), from the skin as last built; None before there is one."""
    path = body.export / "model" / "skin.npz"
    if not path.exists():
        return None
    skin = next((s for s in load_structures(path) if s.name == "skin"), None)
    if skin is None or skin.data2 is None:
        return None
    moves = np.abs(np.asarray(skin.data2)[:, 0]) > 0.02               # the lid's weight (lids.py): the lids and the fold over the upper one
    if not moves.any():
        return None
    v = np.asarray(skin.v, np.float64)
    lo, hi = v[moves].min(axis=0) - 0.03, v[moves].max(axis=0) + 0.03
    near = ((v > lo) & (v < hi)).all(axis=1)
    return v[near], moves[near]


def _big_pieces(n_vertices: int, f: np.ndarray, min_share: float) -> np.ndarray:
    """The triangles of the mesh's connected pieces that are at least `min_share` of the biggest (by triangles)."""
    from .common import components
    piece = components(f, n_vertices)[f[:, 0]]
    counts = np.bincount(piece)
    return f[(counts >= min_share * counts.max())[piece]]


def without_moving_skin(s: Structure, skin_v: np.ndarray, moves: np.ndarray, log=print) -> Structure:
    """A structure without the triangles that lie under skin which moves with a lid (each vertex judged by the skin's
    nearest vertex, within LID_REACH_MM)."""
    from scipy.spatial import cKDTree
    distance, index = cKDTree(skin_v).query(np.asarray(s.v, np.float64))
    under = moves[index] & (distance < LID_REACH_MM * MM)
    f = np.asarray(s.f)
    gone = under[f].any(axis=1)
    if gone.any() and not gone.all():
        kept = f[~gone]
        # (and the scraps the cut leaves, slivers that hang on by nothing: only what is at least a fifth of the biggest piece stays)
        kept = _big_pieces(len(s.v), kept, 0.2)
        s.f = kept
        log(f"face muscles: {s.name}: {len(f) - len(kept)} triangles under the lids' moving skin taken out")
    return s


def clear_scraps(body: Body, log=print) -> int:
    """Takes the labels' unnamed muscle off the face: what lies within 30 mm of the skin in front (in the cheeks,
    round the eyes, in the nose's opening) is, on the labels' voxels, scraps of the very muscles that are drawn
    here whole, and of mucosa of their colour. Returns how many voxels were cleared."""
    got = prepare(body, log)
    if got is None:
        return 0
    face, maps = got
    lab = body.labels
    index = next((o["index"] for o in body.objects if o["name"] == "muscles"), None)
    if index is None:
        return 0
    spacing = np.array(body.spacing)
    size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]])
    c = np.array([-maps.centre[2], maps.centre[1], maps.centre[0]]) * 1000.0 + size / 2      # the head's middle, body mm (z, y, x)
    lo = np.maximum(np.floor((c - 190.0) / spacing).astype(int), 0)
    hi = np.minimum(np.ceil((c + 190.0) / spacing).astype(int), np.array(lab.shape))
    view = lab[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    at = np.argwhere(view == index)
    if len(at) == 0:
        return 0
    mm = (at + lo + 0.5) * spacing - size / 2
    offset = np.stack([mm[:, 2], mm[:, 1], -mm[:, 0]], axis=1) / 1000.0 - maps.centre
    r = np.linalg.norm(offset, axis=1)
    direction = offset / np.maximum(r[:, None], 1e-9)
    d = direction @ maps.axes.T
    lon = np.degrees(np.arctan2(d[:, 0], d[:, 2]))
    lat = np.degrees(np.arcsin(np.clip(d[:, 1], -1.0, 1.0)))
    skin = maps.radius(maps.skin, direction)
    skin = maps.radius(maps.face, direction)                                # (the face without its nose: the nose's inside counts as near)
    front = (np.abs(lon) < 62.0) & (lat > -36.0) & (lat < 58.0) & (skin > 0) & (r * 1000.0 > skin - 34.0)
    hit = at[front]
    view[hit[:, 0], hit[:, 1], hit[:, 2]] = 0
    counts = np.bincount(lab.ravel(), minlength=256)
    for o in body.objects:
        o["voxels"] = int(counts[o["index"]])
    log(f"face muscles: {len(hit)} voxels of unnamed muscle taken off the face (its muscles are drawn whole)")
    return int(len(hit))


DEEP = ("levator anguli oris", "buccinator", "corrugator supercilii", "depressor labii inferioris")      # these lie under other muscles and under fat


def expose(body: Body, log=print) -> int:
    """Takes the labels' fat off the muscles of expression that lie right under the skin. They lie IN the face's
    thin fat, a millimetre or two from where the fat layer's own surface runs, and the two meshes went through
    each other in rags; a face with the skin off shows these muscles in its fat. Whatever fat lies over one of
    them (nearer the skin, in its directions from the head's middle) is cleared, so each shows whole in a window
    of the fat layer, as in a prepared face. The deep ones (DEEP) keep their fat. Returns the voxels cleared."""
    got = prepare(body, log)
    muscles = build(body, log)
    if got is None or not muscles:
        return 0
    _, maps = got
    least = np.full(maps.skin.shape, np.inf, np.float32)                     # per direction: the least radius of a superficial muscle's outer face
    for s in muscles:
        if any(s.name.endswith(k) for k in DEEP):
            continue
        offset = np.asarray(s.v, np.float64) - maps.centre
        r = np.linalg.norm(offset, axis=1)
        cells = np.round(maps.cell(offset / r[:, None])).astype(int)
        ok = (cells[0] >= 0) & (cells[0] < least.shape[0]) & (cells[1] >= 0) & (cells[1] < least.shape[1])
        np.minimum.at(least, (cells[0][ok], cells[1][ok]), (r[ok] * 1000.0).astype(np.float32))
    for _ in range(3):                                                        # the bands' meshes are coarser than the cells: the gaps between their vertices closed
        least = np.minimum(least, ndimage.minimum_filter(least, 3))
    cover = np.where(np.isfinite(least), least, 0.0)                         # 0 = no such muscle in that direction
    lab = body.labels
    fat = [o["index"] for o in body.objects if o["layer"] == "fat"]
    spacing = np.array(body.spacing)
    size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]])
    c = np.array([-maps.centre[2], maps.centre[1], maps.centre[0]]) * 1000.0 + size / 2
    lo = np.maximum(np.floor((c - 190.0) / spacing).astype(int), 0)
    hi = np.minimum(np.ceil((c + 190.0) / spacing).astype(int), np.array(lab.shape))
    view = lab[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    at = np.argwhere(np.isin(view, fat))
    if len(at) == 0:
        return 0
    mm = (at + lo + 0.5) * spacing - size / 2
    offset = np.stack([mm[:, 2], mm[:, 1], -mm[:, 0]], axis=1) / 1000.0 - maps.centre
    r = np.linalg.norm(offset, axis=1)
    under = ndimage.map_coordinates(cover, maps.cell(offset / np.maximum(r[:, None], 1e-9)), order=0, mode="constant", cval=0.0)
    hit = at[(under > 0) & (r * 1000.0 > under - 2.5)]                        # over the muscle, and what of the fat it lies in
    view[hit[:, 0], hit[:, 1], hit[:, 2]] = 0
    counts = np.bincount(lab.ravel(), minlength=256)
    for o in body.objects:
        o["voxels"] = int(counts[o["index"]])
    log(f"face muscles: {len(hit)} voxels of fat taken off the muscles that lie under the skin")
    return int(len(hit))


def build(body: Body, log=print) -> list[Structure]:
    """The muscles of expression of both sides (made once per run); [] where the skin, the skull or the eyes are not at hand."""
    if getattr(body, "face_muscles", None) is not None:
        return body.face_muscles
    got = prepare(body, log)
    if got is None:
        return []
    face, maps = got
    m = getattr(body, "mouth", None)
    lip_w = m.lip_w if m is not None else (lambda u: face.stomion_w + 0.0 * np.asarray(u))
    lay = Layout(face, maps, lip_w)
    lip = float(lip_w(0.0))
    sub = face.subnasale_w
    half = face.half_ipd
    out = []

    def add(name, built, note="", from_bone=True):
        out.append(_muscle(name, built, note, from_bone))

    for side, sg in (("right", -1.0), ("left", 1.0)):
        ew = face.eye_w[side]
        eu = sg * half
        modiolus = lay.on_skin(sg * 35.0, lip - 1.0)
        # Round the eye and on the forehead.
        add(f"{side} frontalis", band(maps, [lay.on_skin(sg * 31.0, ew + 15.0), lay.on_skin(sg * 29.0, ew + 46.0), lay.on_skin(sg * 26.0, ew + 76.0)], (27.0, 24.0), 1.5, (3.6, 3.6)),
            "the frontal belly of occipitofrontalis; it has no bony origin (it comes from the galea)", from_bone=False)
        add(f"{side} orbicularis oculi", ring(maps, lay, (eu, ew - 2.0), (25.0, 19.5), 8.5, 1.0, 2.8), "the orbital part, a ring round the orbit; the part in the lids is not drawn", from_bone=False)
        add(f"{side} corrugator supercilii", band(maps, [lay.on_bone(sg * 7.0, ew + 11.0), lay.on_skin(sg * 34.0, ew + 19.0)], (4.0, 4.5), 2.0, (None, 5.5), seated=0.6))
        # Beside the nose and to the upper lip.
        add(f"{side} nasalis", band(maps, [lay.on_skin(sg * 15.5, sub + 9.0), lay.on_skin(sg * 10.0, sub + 20.0), lay.on_skin(sg * 3.0, sub + 26.0)], (4.5, 3.0), 1.0, (2.4, 2.4)),
            "its transverse part, over the nose's cartilage (which the skeleton does not have)", from_bone=False)
        add(f"{side} levator labii superioris alaeque nasi",
            band(maps, [lay.on_bone(sg * (half - 20.0), ew - 8.0), lay.on_skin(sg * 19.0, sub + 6.0), lay.on_skin(sg * 15.0, lip + 8.0)], (2.5, 3.5), 1.5, (None, 3.6), seated=0.25, beside_nose=True))
        add(f"{side} levator labii superioris", band(maps, [lay.on_bone(eu - sg * 2.0, ew - 20.0), lay.on_skin(sg * 18.0, lip + 8.0)], (11.0, 7.0), 1.8, (None, 3.8), seated=0.25))
        add(f"{side} zygomaticus minor", band(maps, [lay.on_bone(sg * 47.0, ew - 24.0), lay.on_skin(sg * 23.0, lip + 7.0)], (2.5, 2.5), 1.0, (None, 3.6), seated=0.2))
        add(f"{side} zygomaticus major", band(maps, [lay.on_bone(sg * 56.0, ew - 25.0), modiolus], (4.0, 4.0), 2.0, (None, 4.2), seated=0.2))
        add(f"{side} levator anguli oris", band(maps, [lay.on_bone(sg * 27.0, ew - 34.0), lay.on_skin(sg * 33.0, lip + 3.0)], (7.0, 5.0), 1.7, (None, 7.0), seated=0.5))
        if m is not None:
            # The buccinator, deep in the cheek: from behind the last molars forward to the mouth's corner, against the
            # cheek's inner wall, between the upper jaw's gum and the lower's.
            g = m.grid
            mine = (m.teeth_upper | m.teeth_lower) & ((g.axis(2)[None, None, :] > m.stomion_mm[2]) == (sg > 0))
            if mine.any():
                zi, yi, xi = np.nonzero(mine)
                rear = zi > zi.max() - int(6.0 / g.spacing[0])
                behind = np.array([g.axis(0)[zi.max()] + 6.0, np.median(g.axis(1)[yi[rear]]), np.median(g.axis(2)[xi[rear]]) + sg * 5.0])
                back = mouth.to_gltf(body, behind)
                front = lay.on_skin(sg * 33.0, lip)
                r_front = float(np.linalg.norm(front - maps.centre)) * 1000.0 - 8.0
                r_back = float(np.linalg.norm(back - maps.centre)) * 1000.0
                add(f"{side} buccinator", band(maps, [back, front], (17.0, 13.0), 2.5, (6.0, 6.0), radii=(r_back, r_front)), "against the cheek's inner wall", from_bone=False)
        add(f"{side} risorius", band(maps, [lay.on_skin(sg * 62.0, lip + 5.0), modiolus], (6.0, 3.0), 1.0, (3.4, 3.4)), "from the fascia over the parotid; often absent in a real face", from_bone=False)
        # Below the mouth.
        add(f"{side} depressor anguli oris", band(maps, [lay.on_bone(sg * 31.0, lip - 33.0), lay.on_skin(sg * 34.0, lip - 4.0)], (15.0, 4.0), 1.5, (None, 3.4), seated=0.2))
        add(f"{side} depressor labii inferioris", band(maps, [lay.on_bone(sg * 21.0, lip - 28.0), lay.on_skin(sg * 11.0, lip - 8.0)], (8.0, 8.0), 2.2, (None, 4.2), seated=0.3))
        add(f"{side} mentalis", band(maps, [lay.on_bone(sg * 6.0, lip - 14.0), lay.on_skin(sg * 8.0, lip - 30.0)], (4.5, 5.5), (2.0, 3.5), (None, 3.2), seated=0.3))
    add("procerus", band(maps, [lay.on_bone(0.0, face.eye_w["right"] - 17.0), lay.on_skin(0.0, face.eye_w["right"] + 12.0)], (5.0, 7.0), 1.0, (None, 3.2), seated=0.3))
    # Round the mouth: the upper lip's half and the lower lip's, parted along the lip line (the mouth opens between them).
    for name, arc, lip_side in (("orbicularis oris, upper lip", (4.0, 176.0), 1.0), ("orbicularis oris, lower lip", (184.0, 356.0), -1.0)):
        add(name, ring(maps, lay, (0.0, lip), (29.0, 12.5), 9.0, 3.5, 3.0, arc), "the ring round the mouth, drawn as the two lips' halves", from_bone=False)
        if m is not None and m.weight_grid is not None:
            # Each half keeps to its own side of the sheet between the jaws (which rises behind the lips), and goes with its own lip.
            ring_s = out[-1]
            mm = mouth.to_mm(body, ring_s.v)
            height, there = mouth.sheet_at(m, mm)
            # (clear of the lips' inner sides in the skin mesh: the upper lip's lies 1 mm over the sheet, the lower's 4 mm under it)
            mm[:, 1] = np.where(there, np.maximum(mm[:, 1], height + 2.0) if lip_side > 0 else np.minimum(mm[:, 1], height - mouth.SPACE_MM - 2.0), mm[:, 1])
            ring_s.v = mouth.to_gltf(body, mm).astype(np.float32)
            w = mouth.weight(body, m, ring_s.v, np.full(len(mm), lip_side))
            pull = mouth.lip_pull(body, m, ring_s.v, np.full(len(mm), lip_side)) if m.lip is not None else np.zeros_like(w)
            ring_s.data3 = np.stack([w, pull], axis=1).astype(np.float32)
    if m is not None and m.weight_grid is not None:                          # none of them on a gum (mouth.gum_ridges): moved off it, into the lip
        mouth.clear_of_the_gums(body, m, out, log)
    head_layers.tuck_under_skin(body, out, least_mm=1.6, log=log)           # measured against the fine skin itself: nothing at or outside it
    # Round the eyes, nothing of them under the skin that moves when a lid is opened (the lid turns up into the orbit and
    # the skin over it lifts: the ring under them stayed, and stood over the opened eye as a red band).
    moving = lid_skin(body)
    if moving is not None:
        for k, s in enumerate(out):
            if s.name.endswith("orbicularis oculi"):
                out[k] = without_moving_skin(s, *moving, log=log)
    log(f"face muscles: {len(out)} drawn on his skull and skin (generated), {sum(s.triangles for s in out)} triangles")
    body.face_muscles = out
    return out
