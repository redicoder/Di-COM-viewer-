"""The throat behind the mouth: what is seen past the tongue when the mouth is open.

He was frozen with the tongue filling the mouth, the soft palate lying on the tongue's back and the throat fallen
shut behind it (the photographs show the uvula between the tongue's root and the back wall, with a film of dark
fluid round it; the CT a few bubbles of air). Three things follow for the model.

The tongue's back. Under the hard palate the tongue reaches up to the mouth's space (mouth.measure grows the CT's
label up to it). Behind the hard palate's hind edge there is no such roof: what lies on the tongue there is the
soft palate, and the tongue is the label itself (it follows the tongue's pale rim in the photographs to about a
millimetre). Grown up to palate height there, the tongue had the soft palate in it and stood in the opened mouth as
a wall before the throat.

The soft palate. What lies on the tongue's back behind the hard palate, down to its free edge, is the soft palate's
own under side: it stays with the skull when the tongue goes down (`held`), and the lining drawn on it is the
tongue's own frozen surface seen from below (`lining`).

The throat itself is DRAWN, at the places the photographs show its parts: below the soft palate's free edge the
space between the tongue's root and the back wall is opened (`hollow`: as he lay there was no space, only the
film), the uvula hangs in it from the edge's middle, against the tongue's back where it lay, the two tonsils stand
in its side walls with a fold behind each, and the space goes up behind the soft palate as the nose's does. The
measures (how far under the hard palate the free edge lies, the uvula's length, the opening's width, the back
wall's place before the spine) are read from the photographs; the shapes are simple ones. The structure says so
(info["generated"]).

So that the throat can be seen at all, the tongue lies down as the mouth opens (`sink`): frozen, it stood up to the
palate, and turned with the jaw only it would hide everything behind it. Its upper side is drawn down towards the
level of the lower teeth's edges (lower still at its root), keeping a third of its own relief.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from .common import Body, Structure

FREE_EDGE_MM = 15.0             # the soft palate's free edge lies this far under the hard palate's hind edge (photographs)
UVULA_MM = 14.0                 # the uvula's length under the edge
UVULA_RADIUS_MM = 3.3
FAUCES_HALF_MM = 16.0           # half the throat's width between its side walls at the tongue's back
WALL_Z_MM = 101.5               # the back wall: this far behind the lips' meeting point in the middle (photographs: the dark film's hind edge)
WALL_BEFORE_SPINE_MM = 5.0      # ... and never nearer the vertebrae's front than this
CURTAIN_MM = 7.0                # the soft palate's thickness at its free edge: behind it the space goes up
BRIDGE_MM = 8.0                 # behind the hard palate's hind edge the roof comes down onto the tongue's back over this length
DEEP_MM = 45.0                  # the hollow is drawn this far down under the lips' meeting point
TONSIL = (5.5, 8.5, 4.8)        # a tonsil's half sizes: front to back, up and down, and across (3.5 mm of it stands out of the wall)
KEEP_RELIEF = 0.16              # of the tongue's own relief over the level it is drawn down to
SINK_ROOT_MM = 11.0             # the tongue's root is drawn this much lower than its middle
THROAT_RED = (150, 62, 60)      # the back wall
TONSIL_PINK = (204, 140, 132)
UVULA_PINK = (196, 112, 108)


@dataclass
class Throat:
    roofed: np.ndarray                      # (nz, nx) the columns under the hard palate
    z_end: float                            # the hard palate's hind edge near the middle (z, mm)
    x_mid: float                            # the tongue's own middle at its back (x, mm)
    edge_y: float                           # the soft palate's free edge in the middle (y, mm)
    hollow: np.ndarray                      # (nz, ny, nx) the throat's space as drawn, without the uvula and the tonsils; with the bridge under the soft palate's front
    uvula: np.ndarray                       # (nz, ny, nx)
    tonsils: np.ndarray
    held: np.ndarray                        # tissue on and behind the tongue that stays with the skull: soft palate, uvula, tonsils, back wall
    wall_z: np.ndarray                      # (ny, nx) the back wall (z, mm)
    sink_from: tuple = (0.0, 1.0)           # z (mm): from where to where the tongue's root is drawn lower
    info: dict = field(default_factory=dict)


def _smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def measure(body: Body, m, log=print) -> Throat | None:
    """Reads the throat's measures and corrects the mouth's tongue and space behind the hard palate (m.tongue,
    m.space). Returns None (and leaves the mouth as it was) where the tongue's label is missing."""
    from skimage.morphology import convex_hull_image
    from .mouth import near, nearest_fill
    g = m.grid
    sz, sy, sx = g.spacing
    zs, ys, xs = g.axis(0), g.axis(1), g.axis(2)
    label = m.ct.get("tongue")
    if label is None or not label.any() or not m.teeth_upper.any():
        return None
    s = m.stomion_mm
    # The hard palate: the CT's bone over the mouth, above the crowns and the streaks of their metal, between the two
    # sides of the upper row; its hind edge near the middle.
    y_tip = float(m.info["upper_teeth_edge_y_mm"])
    rows = (ys > y_tip + 12.0) & (ys < y_tip + 34.0)
    over = ((m.ct["hu"] > 300.0) & rows[None, :, None]).any(axis=1)
    hull = convex_hull_image(m.teeth_upper.any(axis=1))
    over &= hull.any(axis=0)[None, :]
    over = ndimage.binary_closing(over, iterations=3)
    parts, count = ndimage.label(over | hull)
    over = parts == parts[tuple(np.argwhere(hull)[len(np.argwhere(hull)) // 2])] if count else over
    zi, _, xi = np.nonzero(label)
    x_mid = float(xs[xi[zi > zi.max() - int(20.0 / sz)]].mean())             # the tongue's own middle at its back (the head is a little turned)
    ends = [zs[np.nonzero(over[:, i])[0].max()] for i in np.nonzero(np.abs(xs - x_mid) < 8.0)[0] if over[:, i].any()]
    if not ends:
        return None
    z_end = float(np.clip(np.median(ends), s[0] + 50.0, s[0] + 80.0))
    roofed = over & (zs <= z_end + 1.0)[:, None]
    behind = (zs > z_end)[:, None, None]

    # The tongue behind the hard palate: the label itself.
    old = m.tongue
    tongue = old & ~(behind & ~near(label, g.spacing, 1.0))
    tongue = ndimage.binary_opening(ndimage.binary_closing(tongue, iterations=2), iterations=2)
    parts, count = ndimage.label(tongue)
    if count > 1:
        tongue = parts == 1 + int(np.argmax(ndimage.sum(tongue, parts, range(1, count + 1))))
    space = m.space & ~behind

    # Its top per column and its hind face per row, carried on over where it is not (smoothed).
    nz = g.shape[0]
    has_top = tongue.any(axis=1)                                             # (nz, nx)
    top = np.where(has_top, g.origin[1] + (g.shape[1] - np.argmax(tongue[:, ::-1, :], axis=1)) * sy, np.nan)
    has_hind = tongue.any(axis=0)                                            # (ny, nx)
    hind = np.where(has_hind, zs[nz - 1 - np.argmax(tongue[::-1], axis=0)] + sz / 2, np.nan)
    hind_all = ndimage.gaussian_filter(nearest_fill(np.nan_to_num(hind), has_hind), [2.0 / sy, 2.0 / sx])
    hind_all = np.where(has_hind, np.maximum(hind, hind_all - 1.0), hind_all)
    top_all = ndimage.gaussian_filter(nearest_fill(np.nan_to_num(top), has_top), [2.0 / sz, 2.0 / sx])

    ix_mid = int(np.argmin(np.abs(xs - x_mid)))
    iz_end = int(np.argmin(np.abs(zs - z_end)))
    roof_y = float(m.sheet[iz_end, ix_mid])                                  # the mouth's roof at the hard palate's hind edge
    edge_y = roof_y - FREE_EDGE_MM
    dx = xs - x_mid
    e = np.abs(dx)
    # The free edge seen from the front: an arch on each side of the uvula, coming down into the side walls.
    arch = np.where(e < 6.0, 3.0 * np.sin(0.5 * np.pi * e / 6.0), 3.0 - 26.0 * ((e - 6.0) / (FAUCES_HALF_MM - 6.0)) ** 2)
    edge = edge_y + arch                                                     # (nx,)

    # The back wall: before the spine, a little hollow from side to side.
    spine = (m.ct["hu"] > 250.0) & (zs > s[0] + 92.0)[:, None, None]
    first = np.where(spine.any(axis=0), zs[np.argmax(spine, axis=0)], 1e9)   # (ny, nx)
    first = ndimage.minimum_filter(first, size=(9, 13))
    wall = np.minimum(s[0] + WALL_Z_MM - 0.012 * dx[None, :] ** 2, first - WALL_BEFORE_SPINE_MM)
    wall = np.minimum(wall, zs[-1] - 2.0)

    # The uvula: from the edge's middle down, lying against the tongue's back as it did.
    iy_tip = int(np.argmin(np.abs(ys - (edge_y - UVULA_MM))))
    iy_base = int(np.argmin(np.abs(ys - (edge_y + 2.0))))
    z_base = float(hind_all[iy_base, ix_mid]) + UVULA_RADIUS_MM + 0.6
    z_tip = float(hind_all[iy_tip, ix_mid]) + UVULA_RADIUS_MM + 0.8
    wall = np.maximum(wall, max(z_base, z_tip) + UVULA_RADIUS_MM + 4.5 - 0.012 * dx[None, :] ** 2)      # room behind it
    wall = np.minimum(np.minimum(wall, first - 3.0), zs[-1] - 1.5)                                       # (but not into the spine)
    Z, Y, X = zs[:, None, None], ys[None, :, None], xs[None, None, :]
    a = np.array([z_base, edge_y + 4.0, x_mid])
    b = np.array([z_tip, edge_y - UVULA_MM + UVULA_RADIUS_MM, x_mid])
    ab = b - a
    t = np.clip(((Z - a[0]) * ab[0] + (Y - a[1]) * ab[1] + (X - a[2]) * ab[2]) / float(ab @ ab), 0.0, 1.0)
    away = np.sqrt((Z - a[0] - t * ab[0]) ** 2 + (Y - a[1] - t * ab[1]) ** 2 + (X - a[2] - t * ab[2]) ** 2)
    radius = UVULA_RADIUS_MM * (1.25 - 0.45 * t + 0.20 * t * t * t * 2.0)     # broad at its base, a little bulb at its tip
    uvula = away < radius

    # The hollow: below the free edge, between the tongue's back and the wall, between the side walls; behind the
    # soft palate's edge (a curtain of CURTAIN_MM) it goes up.
    front = hind_all[None, :, :]
    roof = edge[None, None, :] + np.clip(Z - front - CURTAIN_MM, 0.0, None) * 0.9
    half = FAUCES_HALF_MM - 6.0 * _smoothstep((edge_y - 12.0 - Y) / 30.0)     # narrower downwards
    inside = np.abs(X - x_mid) < half
    # (the fold behind each tonsil: the side walls come in a little there)
    tonsil_y = edge_y - 13.0
    iy_t = int(np.argmin(np.abs(ys - tonsil_y)))
    tonsil_z = 0.5 * (hind_all[iy_t][None, None, :] + wall[iy_t][None, None, :]) - 1.0
    fold = 2.6 * np.exp(-((Z - tonsil_z - TONSIL[0] - 2.0) / 2.2) ** 2) * _smoothstep((edge_y + 2.0 - Y) / 6.0)
    inside = inside & (np.abs(X - x_mid) < half - fold)
    hollow = (Z > front) & (Z < wall[None, :, :]) & (Y < roof) & (Y > s[1] - DEEP_MM) & inside
    tonsils = np.zeros(g.shape, bool)
    for sign in (-1.0, 1.0):
        cx = x_mid + sign * (FAUCES_HALF_MM + TONSIL[2] - 3.5)
        cz = float(tonsil_z[0, 0, int(np.argmin(np.abs(xs - cx)))])
        tonsils |= ((Z - cz) / TONSIL[0]) ** 2 + ((Y - tonsil_y) / TONSIL[1]) ** 2 + ((X - cx) / TONSIL[2]) ** 2 < 1.0
    # The bridge: behind the hard palate's hind edge the roof comes down from the mouth's own to the tongue's back.
    along = _smoothstep((Z - (z_end - 0.5)) / BRIDGE_MM)
    line = (m.sheet[:, None, :] + 1.2) * (1.0 - along) + top_all[:, None, :] * along
    bridge = (Z > z_end - 0.5) & (Z < z_end + BRIDGE_MM) & (Y < line) & (Y >= top_all[:, None, :] - 0.5) & near(has_top, (sz, sx), 1.0)[:, None, :]
    bone = near(m.ct["skull"] | m.ct["mandible"], g.spacing, 0.7) | m.teeth_upper | m.teeth_lower
    under = m.depth > 3.0
    hollow = (hollow | bridge) & ~tongue & ~bone & under
    uvula &= hollow | near(hollow, g.spacing, 1.0)
    tonsils &= ~tongue & ~bone & under
    solid = uvula | tonsils
    hollow &= ~solid
    hollow = ndimage.binary_opening(hollow, iterations=1)
    parts, count = ndimage.label(hollow)
    if count > 1:
        hollow = parts == 1 + int(np.argmax(ndimage.sum(hollow, parts, range(1, count + 1))))

    # What stays with the skull: the tissue over and behind the tongue from the hard palate's hind edge on (the soft
    # palate, the uvula, the tonsils' beds, the back wall): not what lies beside the tongue, which is the cheeks'.
    over_tongue = has_top[:, None, :] & (Y > top_all[:, None, :] - 0.5)
    behind_tongue = has_hind[None, :, :] & (Z > hind_all[None, :, :] - 0.5)
    cavity = tongue | hollow | solid
    held = near(cavity, g.spacing, 7.0) & ~tongue & ~hollow & (over_tongue | behind_tongue | near(hollow | solid, g.spacing, 4.0)) & (Z > z_end - 2.0) & under
    held |= solid

    m.tongue, m.space = tongue, space
    voxel = float(np.prod(g.spacing)) / 1000.0
    zi = np.nonzero(tongue.any(axis=(1, 2)))[0]
    molar = float(zs[np.nonzero(m.teeth_lower.any(axis=(1, 2)))[0].max()]) if m.teeth_lower.any() else z_end - 8.0
    info = {"hard_palate_ends_mm": round(float(z_end - s[0]), 1), "tongue_middle_x_mm": round(float(x_mid - s[2]), 1), "free_edge_y_mm": round(float(edge_y - s[1]), 1),
            "uvula_tip_mm": [round(float(z_tip - s[0]), 1), round(float(edge_y - UVULA_MM - s[1]), 1)], "back_wall_mm": round(float(wall[iy_tip, ix_mid] - s[0]), 1),
            "tongue_cm3": round(float(tongue.sum()) * voxel, 1), "tongue_before_cm3": round(float(old.sum()) * voxel, 1),
            "hollow_cm3": round(float(hollow.sum()) * voxel, 1), "generated": "the throat's space, the uvula, the tonsils and the folds behind them are drawn at the places the photographs show them"}
    m.info["tongue_cm3"] = info["tongue_cm3"]
    log("throat: " + str(info))
    return Throat(roofed, z_end, x_mid, edge_y, hollow, uvula, tonsils, held, wall, sink_from=(molar - 4.0, float(zs[zi.max()]) - 3.0), info=info)


def on_grid(m, grid, mask: np.ndarray) -> np.ndarray:
    """A mask of the mouth's grid at another grid's voxels."""
    flat = grid.points().reshape(-1, 3)
    return m.grid.sample(mask.astype(np.float32), flat, order=1, cval=0.0).reshape(grid.shape) > 0.5


def sink(body: Body, m, v_gltf: np.ndarray) -> np.ndarray:
    """How far the tongue's points are drawn down as the mouth opens, in units of the lower lip's pull
    (mouth.LIP_PULL_MM; the shader moves a vertex along the same way by TEXCOORD_3.y). Everything above the level
    the tongue lies down to comes most of the way down to it."""
    from .mouth import LIP_PULL_MM, lower_arch, to_mm
    t = m.throat
    if t is None or not m.teeth_lower.any():
        return np.zeros(len(v_gltf), np.float32)
    g = m.grid
    p = to_mm(body, v_gltf)
    _, _, edge = lower_arch(m)
    edge = ndimage.gaussian_filter(edge, 4.0 / g.spacing[0])
    at = np.stack([(p[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (p[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    level = ndimage.map_coordinates(edge, at, order=1, mode="nearest") - 1.5
    level -= SINK_ROOT_MM * _smoothstep((p[:, 0] - t.sink_from[0]) / max(1.0, t.sink_from[1] - t.sink_from[0]))
    over = p[:, 1] - level
    soft = 0.5 * (over + np.sqrt(over * over + 4.0))                         # a smooth max(over, 0)
    down = float(abs(m.lip_down @ m.face.ey)) if m.lip_down is not None else 1.0
    return ((1.0 - KEEP_RELIEF) * soft / down / LIP_PULL_MM).astype(np.float32)


def _move_out(structures, body: Body, m, room: np.ndarray, margin: float, wanted) -> list[str]:
    """Moves every vertex of the wanted structures that lies nearer a space than `margin` (mm; or in it) straight out
    of it to that distance. Returns what was moved."""
    from . import mouth
    g = m.grid
    away = ndimage.distance_transform_edt(~room, sampling=g.spacing) - ndimage.distance_transform_edt(room, sampling=g.spacing)      # mm outside it (inside: negative)
    away = ndimage.gaussian_filter(away.astype(np.float32), 0.8)
    slope = np.gradient(away, *[float(x) for x in g.spacing])
    lo = g.origin + 1.0
    hi = g.origin + np.array(g.shape) * g.spacing - 1.0
    touched = []
    for s in structures:
        if s.streams or len(s.v) == 0 or not wanted(s):
            continue
        p = mouth.to_mm(body, s.v)
        ids = np.nonzero(((p > lo) & (p < hi)).all(axis=1))[0]
        if len(ids) == 0:
            continue
        ids = ids[g.sample(away, p[ids], order=1) < margin]
        if len(ids) == 0:
            continue
        q = p[ids]
        for _ in range(4):
            short = np.clip(margin - g.sample(away, q, order=1), 0.0, None)
            way = np.stack([g.sample(c, q, order=1) for c in slope], axis=1)
            q = np.clip(q + way / np.maximum(np.linalg.norm(way, axis=1, keepdims=True), 1e-6) * short[:, None], lo, hi)
        p[ids] = q
        s.v = mouth.to_gltf(body, p).astype(np.float32)
        touched.append(f"{s.name} {len(ids)}")
    return touched


def tuck(structures: list[Structure], body: Body, m, log=print) -> int:
    """Moves what reaches into the throat and the mouth out of them. The named structures of the layers under the
    skin lie where their own data put them (BoneHub's vertebrae and jaws, the CT's labels of the throat's muscles),
    a few millimetres off the walls drawn here: the vertebrae and the throat's muscles stood before the back wall,
    white and red in the opened mouth, and the jaws' bone showed at the gums' edges. In the throat every vertex
    nearer its space than the mouth's bag lies (and a little more) is moved out to that distance; in the mouth
    itself the bones only, to 1.2 mm from its space. (BoneHub's mandible still comes through the lower gum's face
    in three small places under the front teeth, where no space lies before it: drawing its surface in under the
    gum, along the CT's bone or along its own normals, stood single triangles out further, and was taken out again.)
    Returns how many structures were touched."""
    from . import mouth
    t = getattr(m, "throat", None)
    if t is None:
        return 0
    touched = []
    room = t.hollow | t.uvula | t.tonsils
    if room.any():
        touched += _move_out(structures, body, m, room, mouth.BAG_MM + 0.8, lambda s: s.layer != "skin" and s.name != "tongue" and "teeth" not in s.name)
    touched += _move_out(structures, body, m, m.space | m.tongue, 1.2, lambda s: s.layer == "skeleton" and s.info.get("class") == "bone" and not _is_tooth(s.name))
    if touched:
        log("throat: moved out of the throat's and the mouth's space (vertices): " + "; ".join(touched))
    return len(touched)


def _is_tooth(name: str) -> bool:
    return any(k in name for k in ("teeth", "incisor", "canine", "molar"))


def lining(body: Body, m, log=print) -> Structure | None:
    """The throat's lining: what the tongue lay against behind the hard palate (the soft palate's under side, the
    walls beside the tongue's back) and the drawn throat's walls, uvula and tonsils. It stays with the skull; the
    walls beside the tongue go as the cheeks' flesh goes."""
    from . import mouth
    t = m.throat
    if t is None:
        return None
    g = m.grid
    zs = g.axis(0)
    # From the hard palate's hind edge on; at the sides from the last back teeth on (behind them the tongue's sides
    # lay against the folds that run from the cheeks to the throat's side walls).
    last = [float(zs[np.nonzero(row.any(axis=(1, 2)))[0].max()]) for row in (m.teeth_upper, m.teeth_lower) if row.any()]
    start = min([t.z_end - 0.5] + [z - 4.0 for z in last])
    cavity = (m.tongue | t.hollow) & (zs >= start)[:, None, None]
    got = mouth._mesh(body, g, cavity, 0.8)
    if got is None:
        return None
    v, v_mm, f, n = got                                                      # n looks out of the cavity, into its wall
    _, _, edge = mouth.lower_arch(m)
    low_edge = float(np.median(edge[m.teeth_lower.any(axis=1)]))
    floor = low_edge - 22.0                                                  # under this the tongue's sides lie against the mouth's floor, which goes with it
    root = t.sink_from[1] - 8.0
    gone = (v_mm[:, 0] < start + 1.0) | ((v_mm[:, 1] < floor) & (v_mm[:, 0] < root))
    # Under the hard palate the roof is the mouth's own lining, and the teeth and their gums are the walls: only
    # what lies clear of them is the throat's.
    hard = m.teeth_upper | m.teeth_lower | m.upper | m.lower | m.space
    to_hard = ndimage.distance_transform_edt(~hard, sampling=g.spacing).astype(np.float32)
    gone |= (v_mm[:, 0] < t.z_end + 0.5) & (g.sample(to_hard, v_mm + mouth._zyx(n) * 0.8) < 1.6)
    f = f[~gone[f].any(axis=1)][:, ::-1]                                     # seen from inside
    inward = v_mm + mouth._zyx(n) * 2.2
    w = m.weight_grid.sample(m.above, inward).astype(np.float32) if m.weight_grid is not None else np.zeros(len(v), np.float32)
    if m.weight_grid is not None:
        # The walls beside the tongue before the throat (the folds from the cheeks to its side walls) hang between the
        # jaws: the upper jaw's at their top, the lower jaw's at their foot, drawn out evenly between as the mouth
        # opens. Further back, at the throat's own walls, nothing goes with the jaw.
        aside = _smoothstep((np.abs(v_mm[:, 2] - t.x_mid) - 10.0) / 6.0)
        before = 1.0 - _smoothstep((v_mm[:, 0] - (t.z_end + 4.0)) / 10.0)
        top = t.edge_y + FREE_EDGE_MM - 3.0
        down = _smoothstep((top - v_mm[:, 1]) / max(4.0, top - (low_edge - 9.0)))
        w = np.maximum(w * (1.0 - before), aside * before * down).astype(np.float32)
        there = mouth.turned(m, v, w, 1.0)

        def longest(q):
            return np.max([np.linalg.norm(q[f[:, a]] - q[f[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)

        f = f[~(longest(there) > 3.0 * np.maximum(longest(np.asarray(v, np.float64)), 2e-4))]
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int64)
    remap[used] = np.arange(len(used))
    v, v_mm, n, w, f = (v - n * 0.0003)[used], v_mm[used], n[used], w[used], remap[f]
    # Colours: the mouth's own lining on the soft palate, a deeper red on the walls, the uvula and the tonsils paler;
    # lighter and darker as the photographs are; the light fails towards the throat.
    inside = v_mm + mouth._zyx(n) * 1.2
    on_uvula = g.sample(ndimage.gaussian_filter(t.uvula.astype(np.float32), 1.0), inside)
    on_tonsil = g.sample(ndimage.gaussian_filter(t.tonsils.astype(np.float32), 1.0), inside)
    at = np.stack([(v_mm[:, 1] - g.origin[1]) / g.spacing[1] - 0.5, (v_mm[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    behind = np.clip((v_mm[:, 0] - ndimage.map_coordinates(t.wall_z, at, order=1, mode="nearest") + 9.0) / 7.0, 0.0, 1.0)      # towards the back wall
    colour = np.tile(np.array(mouth.MUCOSA, np.float64), (len(v), 1))
    colour += (np.array(THROAT_RED, np.float64) - colour) * (behind * (v_mm[:, 1] < t.edge_y + 6.0))[:, None]
    colour += (np.array(UVULA_PINK, np.float64) - colour) * np.clip(on_uvula * 2.0, 0.0, 1.0)[:, None]
    colour += (np.array(TONSIL_PINK, np.float64) - colour) * np.clip(on_tonsil * 2.0, 0.0, 1.0)[:, None]
    real = (on_uvula < 0.1) & (on_tonsil < 0.1) & (behind < 0.5)
    colour *= np.where(real, mouth.photo_tone(m, v_mm, n), 1.0)[:, None]
    # (the tonsils' pits: a few darker dots)
    pits = np.sin(v_mm[:, 0] * 1.9) * np.sin(v_mm[:, 1] * 1.6 + 1.0) * np.sin(v_mm[:, 2] * 2.1)
    colour *= (1.0 - 0.22 * np.clip(on_tonsil * 2.0, 0.0, 1.0) * np.clip(pits * 2.5 - 0.9, 0.0, 1.0))[:, None]
    front = float(np.nanmin(m.skin_front))
    light = 1.0 - mouth.DIM_BACK * np.clip((v_mm[:, 0] - front) / 80.0, 0.0, 1.0)
    light *= 1.0 - 0.35 * np.clip((t.edge_y - 14.0 - v_mm[:, 1]) / 22.0, 0.0, 1.0) * behind       # and down the throat
    bake = np.tile(np.array([255, 255, 82, 225], np.uint8), (len(v), 1))
    bake[:, 0] = np.round(255 * light)
    log(f"throat: lining {len(f)} triangles")
    out = Structure("lining of the throat", "skin", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in mouth.MUCOSA), bake=bake,
                    albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8),
                    info={"class": "skin", "generated": t.info["generated"],
                          "source": "the soft palate's under side as the tongue lay against it (CT label of the tongue); the throat behind it drawn (throat.py)"})
    if m.weight_grid is not None:
        out.data3 = np.stack([w, np.zeros(len(v), np.float32)], axis=1).astype(np.float32)
    return out
