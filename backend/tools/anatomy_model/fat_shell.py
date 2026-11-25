"""The fat's outer surface, all over him: the skin's own outline, moved in.

The fat layer is what shows when the skin is taken off. Meshed from the labels (voxels of 1.3 x 2 x 1.3 mm cut back
1.4 mm from the skin, in triangles of 4 to 5 mm) it was a faceted head with a lump for an ear, and wherever the
fat is thinner than a voxel or two it had ragged holes with the muscle showing red in them: down both shins, at
the knees, on the forearms. A body with the skin off has no such holes: over a shin there is little fat, but
there is the fat's sheet all the same. In the feet and the hands this was already cured (feet.sock, hands.glove):
there the fat's surface is the level a millimetre and a half under the skin's fine outline. This module does the
same for the rest of him:

- the HEAD at the outline's own 0.66 mm, in triangles of 1.4 mm (surface_of_head);
- the NECK, the TRUNK and the LIMBS at the export's grid (the fine outline averaged down), in triangles of 3 mm
  (surface_of_body), a little deeper (the surface lies within half a millimetre of where it is meant there);
- and nowhere nearer the skin's MESH than UNDER_MESH_MM (under_the_mesh). The outline is not the skin as drawn:
  where photographs were passed over the skin's mesh may move 2.25 mm when it is relaxed (skin.tolerance), and
  the fat showed through it there in rings. Sunk by a fixed 1.5 mm more in those stretches (tried first), the
  fat had three grooves round him instead; following the skin's own mesh it has none.

What the labels have of fat nearer the skin than KEEP_MM gives way to this surface; their deeper faces (the fat's
inner side, against the muscles) stay, so the layer keeps its thickness for what is cut into it later.

Two kinds of opening are cut into it: over each EYE (Body.eye_pits: the globe and the lids' thickness are left to
the eyeball and the skin), and over the RED OF THE LIPS, which has no fat under it (lips). An opening's rim is
drawn smooth along the mesh (smooth_rims), not left as the triangles' saw teeth.

THE FACE HAS NO WINDOWS ANY MORE. While the fat was the labels', the muscles of expression, which lie in the
face's thin fat, went through its surface in rags, and the fat over each was cleared so that it showed whole in a
window (face_muscles.expose, removed). With this surface the windows ran together into one hole from the brow to
the chin, with bone between the muscles' ribbons and scraps of the labels' fat at its edge. A face with the skin
off is covered by its fat as the rest of him is; its muscles are the muscles layer's to show, and they are kept
under this surface as everything else is (head_layers.under_skin_everywhere).

    fat_shell.fat(body, structures, baker, occupancy, gloss)     # the fat layer: its surface put in place of the labels'
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import fine_skin, mouth
from .common import FAT_LOWER_LIP, FAT_SURFACE, FAT_UPPER_LIP, Body, Structure, decimate_regions, outward, taubin

FAT = "subcutaneous fat"
LEVEL_MM = 1.5                  # the fat's surface under the skin's outline: in the head
BODY_LEVEL_MM = 1.8             # ... and below it, where the outline is read coarsely
UNDER_MESH_MM = 1.2             # ... and at the least this far under the skin's mesh
HEAD_MM = 1640.0                # the head's surface from here up (fine_skin.BODY_MM)
LAP_MM = 8.0                    # ... and this far below it, sinking under the body's, which ends just above
SINK_MM = 1.0
EDGE_HEAD_MM, EDGE_BODY_MM = 1.4, 3.0
KEEP_MM = 4.0                   # the labels' fat nearer the skin than this gives way to the surface
BLUR_MM = (1.3, 1.5, 1.3)       # the depth blurred by this before it is contoured (as feet.BLUR; z, y, x)
SLAB = 120                      # the export's slices contoured at a time, below the head
HALO = 8
LIPS_FROM_MM = 10.0             # the lips' fat: what lies further forward than this in the face's frame (the skin's own: 15)
LIPS_UP_MM, LIPS_DOWN_MM = 6.0, 7.5     # the red of the lips over and under the lip line, in the middle (zones.LIP_UP, LIP_DOWN)
LIPS_EDGE_MM = (1.5, 4.0)       # ... and at the least this far from the line (up, down), to the mouth's corners
LIPS_BEYOND_MM = 4.0            # ... and this far past them


def under_the_mesh(v: np.ndarray, skin_v: np.ndarray, skin_n: np.ndarray, own_n: np.ndarray | None = None, least_mm: float = UNDER_MESH_MM, reach_mm: float = 8.0,
                   most_mm: float = 3.0) -> np.ndarray:
    """Vertices (glTF metres) -> the same, those that lie nearer the skin's mesh than `least_mm` (or outside it)
    moved in, against the skin's normal there, by `most_mm` at the most. The skin is taken as flat at its nearest
    vertex (its triangles are 3 mm at the most and it is smooth where this matters); a vertex further than
    `reach_mm` from any of the skin's is left.

    `own_n`: the vertices' own normals. Where two parts of him lie together (an arm on the trunk) the nearest
    skin may be the OTHER part's, which looks the other way: a vertex is measured only against skin that looks
    the way it does."""
    from scipy.spatial import cKDTree
    v = np.asarray(v, np.float64).copy()
    if len(v) == 0 or len(skin_v) == 0:
        return v.astype(np.float32)
    far, index = cKDTree(np.asarray(skin_v, np.float64)).query(v, distance_upper_bound=reach_mm / 1000.0)
    near = np.flatnonzero(far < reach_mm / 1000.0)
    normal = np.asarray(skin_n, np.float64)[index[near]]
    if own_n is not None:
        same = np.einsum("ij,ij->i", normal, np.asarray(own_n, np.float64)[near]) > 0.3
        near, normal = near[same], normal[same]
    under = -np.einsum("ij,ij->i", v[near] - np.asarray(skin_v, np.float64)[index[near]], normal) * 1000.0     # mm under the skin's plane there
    lacks = np.clip(least_mm - under, 0.0, most_mm)
    v[near] -= normal * (lacks / 1000.0)[:, None]
    return v.astype(np.float32)


def _mesh(v_mm: np.ndarray, f: np.ndarray, size: np.ndarray, edge_mm: float):
    """Contoured vertices (mm, the body's axes) and faces -> the mesh in glTF metres, wound to look out,
    decimated to `edge_mm` and smoothed with its rim left where it is."""
    if len(f) == 0:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint32)
    used, inverse = np.unique(f, return_inverse=True)
    q = v_mm[used] - size / 2
    v = (np.stack([q[:, 2], q[:, 1], -q[:, 0]], axis=1) / 1000.0).astype(np.float32)
    f = outward(v, inverse.reshape(-1, 3))
    v, f = decimate_regions(v, f.astype(np.uint32), np.zeros(len(v), np.int8), [edge_mm])
    return taubin(v, f, 8, weight=1.0 - rim_of(f, len(v)).astype(np.float64)).astype(np.float32), f


def rim_of(f: np.ndarray, n: int) -> np.ndarray:
    """Which vertices lie on the mesh's rim (on an edge that belongs to one triangle only): bool (n,)."""
    edges, counts = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]).astype(np.int64), axis=1), axis=0, return_counts=True)
    out = np.zeros(n, bool)
    out[np.unique(edges[counts == 1])] = True
    return out


def surface_of_head(fine: fine_skin.FineOutline, size: np.ndarray):
    """The fat's surface in the head (glTF metres; faces): the level LEVEL_MM under the fine outline from
    HEAD_MM - LAP_MM up, its lowest LAP_MM sinking by SINK_MM (under the body's surface, which ends there)."""
    from skimage import measure
    spacing, origin = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64)
    j0 = max(0, int((HEAD_MM - LAP_MM - 14.0 - origin[1]) / spacing[1]))
    solid = np.asarray(fine.cover[:, j0:, :]) > 127
    if not solid.any():
        return _mesh(np.zeros((0, 3)), np.zeros((0, 3), np.int64), size, EDGE_HEAD_MM)
    z, x = np.flatnonzero(solid.any(axis=(1, 2))), np.flatnonzero(solid.any(axis=(0, 1)))
    lo = np.array([max(z[0] - 3, 0), j0, max(x[0] - 3, 0)])
    block = solid[lo[0]:z[-1] + 4, :, lo[2]:x[-1] + 4]
    block = np.pad(block, ((1, 1), (0, 1), (1, 1)), constant_values=False)      # not him: round the box and over his head;
    block = np.pad(block, ((0, 0), (1, 0), (0, 0)), mode="edge")                # below it the neck goes on
    depth = ndimage.gaussian_filter(ndimage.distance_transform_edt(block, sampling=spacing).astype(np.float32), [b / s for b, s in zip(BLUR_MM, spacing)])
    height = origin[1] + (np.arange(depth.shape[1]) - 1 + lo[1] + 0.5) * spacing[1]
    # (the distance is to a voxel's centre: the outline itself lies some 0.4 mm nearer, as in feet.sock)
    level = LEVEL_MM + 0.4 + np.interp(height, (HEAD_MM - LAP_MM, HEAD_MM), (SINK_MM, 0.0))
    depth -= level.astype(np.float32)[None, :, None]
    pv, pf, _, _ = measure.marching_cubes(depth, 0.0)
    mm = origin + (pv - 1.0 + lo + 0.5) * spacing
    pf = pf[(mm[:, 1] > HEAD_MM - LAP_MM)[pf].all(axis=1)]
    return _mesh(mm, pf, size, EDGE_HEAD_MM)


def surface_of_body(body: Body, fine: fine_skin.FineOutline, size: np.ndarray, occupancy: np.ndarray | None = None):
    """The fat's surface below the head (glTF metres; faces): the level BODY_LEVEL_MM under the outline as the
    export's grid has it (fine_skin.occupancy), up to just over HEAD_MM. Contoured SLAB slices at a time, each
    with HALO slices of its neighbours for the depth, and welded."""
    from skimage import measure
    spacing = np.array(body.spacing, np.float64)
    solid = (fine_skin.occupancy(body, fine) if occupancy is None else occupancy) > 127
    nz, ny, nx = solid.shape
    top = min(ny - 1, int(np.ceil((HEAD_MM + 2.0) / spacing[1])))
    sigma = [b / s for b, s in zip(BLUR_MM, spacing)]
    verts, faces, count = [], [], 0
    for y0 in range(0, top, SLAB):
        y1 = min(top, y0 + SLAB)                                          # the cells between slices y0 .. y1
        a, b = max(0, y0 - HALO), min(ny, y1 + 1 + HALO)
        block = np.pad(solid[:, a:b, :], ((1, 1), (0, 0), (1, 1)), constant_values=False)
        if a == 0:
            block = np.pad(block, ((0, 0), (1, 0), (0, 0)), constant_values=False)      # under his feet: nothing of him
        if not block.any():
            continue
        depth = ndimage.gaussian_filter(ndimage.distance_transform_edt(block, sampling=spacing).astype(np.float32), sigma)
        first = y0 - a + (1 if a == 0 else 0)
        depth = depth[:, first:first + (y1 - y0) + 1, :]
        depth = depth - np.float32(BODY_LEVEL_MM + 0.7)                  # (counted to a voxel's centre: half a voxel more than to the outline)
        if depth.max() <= 0 or depth.min() >= 0:
            continue
        pv, pf, _, _ = measure.marching_cubes(depth, 0.0)
        mm = (pv + np.array([-1.0, y0, -1.0]) + 0.5) * spacing
        verts.append(mm)
        faces.append(pf.astype(np.int64) + count)
        count += len(mm)
    if not verts:
        return _mesh(np.zeros((0, 3)), np.zeros((0, 3), np.int64), size, EDGE_BODY_MM)
    mm, f = np.concatenate(verts), np.concatenate(faces)
    key = np.round(mm * 1000.0).astype(np.int64)                           # the slabs' shared slices: the same points twice
    _, keep, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    mm, f = mm[keep], inverse.reshape(-1)[f]
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    f = f[(mm[:, 1] < HEAD_MM + 2.0)[f].all(axis=1)]
    return _mesh(mm, f, size, EDGE_BODY_MM)


def in_eye_pits(body: Body, size: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Which vertices (glTF metres) lie in the space left to an eye and its lids (Body.eye_pits), or within a
    voxel of it: bool."""
    out = np.zeros(len(v), bool)
    p = np.asarray(v, np.float64) * 1000.0
    mm = np.stack([-p[:, 2], p[:, 1], p[:, 0]], axis=1) + size / 2
    index = np.floor(mm / np.array(body.spacing)).astype(int)
    for (z0, y0, x0), pit in getattr(body, "eye_pits", None) or []:
        wide = ndimage.binary_dilation(np.pad(pit, 1), iterations=1)
        local = index - np.array([z0 - 1, y0 - 1, x0 - 1])
        ok = ((local >= 0) & (local < np.array(wide.shape))).all(axis=1)
        out[ok] |= wide[local[ok, 0], local[ok, 1], local[ok, 2]]
    return out


def smooth_rims(v: np.ndarray, f: np.ndarray, which: np.ndarray, rounds: int = 12) -> np.ndarray:
    """The rim vertices marked in `which` moved towards the middle of their two neighbours along the rim, `rounds`
    times: a rim cut along the triangles' edges is a saw, and an opening's edge in a sheet of fat is not."""
    v = np.asarray(v, np.float64).copy()
    edges, counts = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]).astype(np.int64), axis=1), axis=0, return_counts=True)
    rim = edges[counts == 1]
    rim = rim[which[rim].all(axis=1)]
    if len(rim) == 0:
        return v.astype(np.float32)
    n = len(v)
    total = np.zeros((n, 3))
    degree = np.zeros(n)
    for _ in range(rounds):
        total[:] = 0.0
        degree[:] = 0.0
        np.add.at(total, rim[:, 0], v[rim[:, 1]])
        np.add.at(total, rim[:, 1], v[rim[:, 0]])
        np.add.at(degree, rim[:, 0], 1.0)
        np.add.at(degree, rim[:, 1], 1.0)
        mine = degree == 2                                                 # (a vertex where rims meet stays)
        v[mine] = 0.5 * v[mine] + 0.5 * total[mine] / 2.0
    return v.astype(np.float32)


def with_openings(body: Body, size: np.ndarray, v: np.ndarray, f: np.ndarray, log=print):
    """The head's surface with its openings cut, over the eyes, and their rims drawn smooth. Returns (vertices,
    faces). (The lips' is cut last of all: lips.)"""
    v, f, _, cut = opened(v, f, in_eye_pits(body, size, v))
    if cut:
        log(f"fat: {cut} triangles of the head's surface opened over the eyes")
    return v, f


def fat(body: Body, structures: list[Structure], baker, occupancy: np.ndarray, gloss: int, log=print) -> int:
    """Puts the surface in place of the labels' fat near the skin (the structure FAT of `structures`). Needs the
    fine outline; without it nothing changes. Returns the surface's triangles."""
    s = next((x for x in structures if x.name == FAT), None)
    fine = fine_skin.load(body)
    if s is None or fine is None:
        return 0
    size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]], np.float64)
    hv, hf = surface_of_head(fine, size)
    hv, hf = with_openings(body, size, hv, hf, log)
    bv, bf = surface_of_body(body, fine, size)
    if len(hf) + len(bf) == 0:
        return 0
    # Under the skin as it is drawn, not only under its outline.
    skin_path = body.export / "model" / "skin_surface.npz"
    if skin_path.exists():
        from .common import load_structures, normals_of
        skin = load_structures(skin_path)[0]
        skin_n = normals_of(skin.v, skin.f)
        before = [hv.copy(), bv.copy()]
        hv, bv = under_the_mesh(hv, skin.v, skin_n, normals_of(hv, hf)), under_the_mesh(bv, skin.v, skin_n, normals_of(bv, bf))
        moved = [np.linalg.norm(np.asarray(a, np.float64) - b, axis=1) * 1000.0 for a, b in zip((hv, bv), before)]
        log(f"fat: kept {UNDER_MESH_MM} mm under the skin's mesh: {int((moved[0] > 0.05).sum())} vertices of the head's surface and {int((moved[1] > 0.05).sum())} below it moved in "
            f"(by up to {max(float(m.max()) if len(m) else 0.0 for m in moved):.1f} mm)")
    # The labels' fat near the skin gives way (their depth is counted from the labels' own edge, which lies 1.4 mm
    # under the outline: fine_skin.inside_export).
    deep = body.sample(baker.depth(body.labels > 0), np.asarray(s.v, np.float64), step=baker.STEP) > KEEP_MM - 1.4
    f = np.asarray(s.f)
    keep = deep[f].all(axis=1)                                             # (wholly: these triangles are 10 to 25 mm long, and one with a single deep
                                                                           #  corner reached up to the skin, and through it when the jaw moved)
    used, inverse = np.unique(f[keep], return_inverse=True)
    parts_v = [np.asarray(s.v, np.float32)[used], hv, bv]
    parts_f = [inverse.reshape(-1, 3).astype(np.int64), hf.astype(np.int64) + len(used), bf.astype(np.int64) + len(used) + len(hv)]
    s.v, s.f = np.concatenate(parts_v).astype(np.float32), np.concatenate(parts_f).astype(np.uint32)
    s.extra = np.concatenate([np.zeros(len(used), np.uint8), np.full(len(hv) + len(bv), FAT_SURFACE, np.uint8)])       # (the marks: common.FAT_SURFACE)
    s.bake = baker.colours(s.v, s.f, occupancy, gloss=gloss)
    s.info["surface"] = (f"its outer surface is the level {LEVEL_MM} mm (head) and {BODY_LEVEL_MM} mm (below it) under the skin's outline (fat_shell.py), "
                         f"not the labels' fat; the labels' fat deeper than {KEEP_MM} mm is kept as its inner side")
    log(f"fat: its surface is the skin's outline moved in: {len(hf)} triangles in the head, {len(bf)} below it, in place of {int((~keep).sum())} from the labels "
        f"({int(keep.sum())} of the labels' kept as its inner side)")
    return int(len(hf) + len(bf))


def opened(v: np.ndarray, f: np.ndarray, gone: np.ndarray, fine: np.ndarray | None = None):
    """A surface with the triangles that touch the vertices `gone` taken out and the rims that leaves drawn
    smooth. Returns (vertices, faces, which of the old vertices are kept, how many triangles went).

    `fine`: the vertices whose rims may be drawn smooth (the surface's own, in triangles of a millimetre or
    two). The labels' fat that is kept as the inner side is in triangles of 10 to 25 mm: a rim vertex of
    those, drawn towards the middle of its neighbours, went 20 mm and stood out of the skin under the nose as
    a sliver."""
    f = np.asarray(f, np.int64)
    cut = gone[f].any(axis=1)
    if not cut.any():
        return np.asarray(v, np.float32), f.astype(np.uint32), np.arange(len(v)), 0
    kept = f[~cut]
    along = np.zeros(len(v), bool)
    along[f[cut].ravel()] = True                                           # the vertices the cut ran along are on its rims
    which = along & rim_of(kept, len(v))
    v = smooth_rims(v, kept, which if fine is None else which & fine)
    used, inverse = np.unique(kept, return_inverse=True)
    return v[used], inverse.reshape(-1, 3).astype(np.uint32), used, int(cut.sum())


def red_of_the_lips(m, v: np.ndarray) -> np.ndarray:
    """Which vertices (glTF metres) lie under the red of the lips: a lens along the lip line, LIPS_UP_MM high
    over its middle and LIPS_DOWN_MM under it (as the skin's red is laid out: zones.LIP_UP, LIP_DOWN); to the
    mouth's corners and LIPS_BEYOND_MM past them at the least LIPS_EDGE_MM (up, down) from the line."""
    u, w, d = m.face.local(np.asarray(v, np.float64))
    g = w - m.lip_w(u)
    span = mouth.HALF_WIDTH - 1.0
    lens = np.sqrt(np.clip(1.0 - (u / span) ** 2, 0.0, 1.0)) ** 0.8
    return ((np.abs(u) < span + LIPS_BEYOND_MM) & (d > LIPS_FROM_MM) & (g < np.maximum(LIPS_UP_MM * lens, LIPS_EDGE_MM[0]))
            & (g > -np.maximum(LIPS_DOWN_MM * lens, LIPS_EDGE_MM[1])))


def lips(body: Body, structures: list[Structure], log=print) -> int:
    """Opens the fat over the red of the lips and marks which lip each vertex round the mouth is of (for
    mouth.assign). The last thing done to the fat: nothing after it renumbers its vertices. Returns the
    triangles taken out.

    The red of the lips has no fat under it: the lips' muscle lies under their skin. And the surface, made over
    the closed lips as the outline has them, cannot stay there: everything is given its share in the jaw's
    turn afterwards (mouth.assign), which takes out what the open mouth would draw into sheets: 677 triangles of
    it, along their edges (with the skin off the teeth showed in a ragged slit and scraps of the lips' muscles at
    both corners). Parted along the lip line instead and left whole, its edge lay where the lips' inner sides
    are, and with the mouth open a yellow line ran round the lips. So it ends where the red begins, and at the
    corners far enough from the line to stay inside the lip (the lower lip's inner side sinks 3 mm behind its
    edge: mouth.cut), and a little past the corners, where the open mouth's edge is drawn furthest from where it
    lay and the fat behind it was seen."""
    s = next((x for x in structures if x.name == FAT), None)
    m = getattr(body, "mouth", None)
    if s is None or m is None or s.extra is None:
        return 0
    v, f, used, cut = opened(s.v, s.f, red_of_the_lips(m, s.v), (np.asarray(s.extra, np.uint8) & FAT_SURFACE) > 0)
    for key in ("bake", "albedo", "extra"):
        a = getattr(s, key)
        if a is not None:
            setattr(s, key, np.asarray(a)[used])
    side = mouth.lip_sides(v, m, least_d=LIPS_FROM_MM)
    mark = np.asarray(s.extra, np.uint8).copy()
    mark[side > 0] |= FAT_UPPER_LIP
    mark[side < 0] |= FAT_LOWER_LIP
    s.v, s.f, s.extra = v, f, mark
    log(f"fat: opened over the red of the lips: {cut} triangles; {int((side > 0).sum())} vertices marked the upper lip's, {int((side < 0).sum())} the lower lip's")
    return cut
