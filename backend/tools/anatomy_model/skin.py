"""The skin (the whole body's outer surface) and the briefs over it.

The surface comes from the fine outline (fine_skin: 0.66 x 1 x 0.66 mm, read from every photograph) when it has
been extracted, else from the export's own voxels (1.32 x 2 x 1.32 mm). The fine outline is blurred a little
(the photographs' outlines sit a fraction of a millimetre off their neighbours'), contoured slab by slab along
the body, welded, smoothed without shrinking and decimated. The decimation keeps more triangles where a student
looks closely: the mesh is magnified round the face, the hands and the feet before it and shrunk back after, so
those parts keep about twice the detail of the trunk and no seam separates them.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage import measure

from . import fine_skin, hair, lids, mouth, zones
from .common import Baker, Body, Structure, decimate, decimate_regions, keep_big_pieces, load_structures, normals_of, outward, relax, save_structures, surface
from .palette import BRIEFS

SLAB = 96                       # fine slices meshed at a time
SMOOTH_MM = 0.65                # blur of the fine outline before contouring (the lid and lip lines are a millimetre high)
WELD_MM = 1e-3


# ---- landmarks the skin needs (glTF metres) ----------------------------------------------------------------------
def measured_eyes(body: Body) -> list[dict]:
    """The export's eyes with their globes measured again in the head's photographs, where those are at hand."""
    eyes = body.meta.get("eyes") or []
    measured = zones.measure_globes(body) if len(eyes) == 2 else None
    if not measured:
        return eyes
    return [dict(e, centre_m=m["centre_m"], radius_m=m["radius_m"]) for e, m in zip(eyes, measured)]


def landmarks(body: Body) -> dict:
    """Where the face, the hands and the feet are, from the export's own data."""
    lab = body.labels
    sz, sy, sx = body.spacing
    out = {}
    eyes = measured_eyes(body)
    if len(eyes) == 2:
        c = np.mean([e["centre_m"] for e in eyes], axis=0)                 # body metres: x left, y up, z back
        out["eyes"] = [np.array([e["centre_m"][0], e["centre_m"][1], -e["centre_m"][2]]) for e in eyes]
        out["face"] = np.array([c[0], c[1] - 0.035, -c[2] + 0.02])
        out["head"] = np.array([c[0], c[1] + 0.01, -c[2] - 0.07])

    def to_gltf(z, y, x):
        return np.array([(x + 0.5) * sx - body.size_mm[0] / 2, (y + 0.5) * sy - body.size_mm[1] / 2, -((z + 0.5) * sz - body.size_mm[2] / 2)]) / 1000.0

    # The hands: the far end of each arm (the arms lie along the trunk, the hands lowest).
    for side in ("left", "right"):
        ids = [o["index"] for o in body.objects if "arm" in o["name"] and side in o["name"]]
        if not ids:
            continue
        arm = np.isin(lab, ids)
        ys = np.nonzero(arm.any(axis=(0, 2)))[0]
        if len(ys) == 0:
            continue
        low = arm[:, ys[0]:ys[0] + int(round(110 / sy)), :]
        z, y, x = (float(a.mean()) for a in np.nonzero(low))
        out[f"hand_{side}"] = to_gltf(z, y + ys[0], x)
    # The feet: the body's lowest 13 cm, either side of the midline.
    foot = lab[:, :int(round(130 / sy)), :] > 0
    mid = lab.shape[2] // 2
    for side, part in (("right", foot[:, :, :mid]), ("left", foot[:, :, mid:])):
        if part.any():
            z, y, x = (float(a.mean()) for a in np.nonzero(part))
            out[f"foot_{side}"] = to_gltf(z, y, x + (mid if side == "left" else 0))
    return out


def detail_bubbles(marks: dict) -> list[tuple]:
    """(centre, radius m, magnification): where the skin keeps more triangles. The bubbles are applied in order,
    so the face's bubble, which lies inside the head's, is given where the head's bubble has already put it."""
    out = []
    if "head" in marks:
        out.append((marks["head"], 0.125, 1.5))
    if "face" in marks:
        centre, radius = marks["face"], 0.08
        if out:
            centre, radius = magnify(centre[None, :], out)[0], radius * out[0][2]
        out.append((centre, radius, 1.9))
    for key, radius, gain in (("hand_left", 0.11, 2.2), ("hand_right", 0.11, 2.2), ("foot_left", 0.12, 1.8), ("foot_right", 0.12, 1.8)):
        if key in marks:
            out.append((marks[key], radius, gain))
    return out


def detail_regions(v: np.ndarray, marks: dict, triangles: int) -> tuple[np.ndarray, list[float]]:
    """A region number per vertex (coarse to fine) and the edge length wanted in each, millimetres: 0 the body,
    1 the feet, 2 the hands, 3 the head and neck, 4 the face and ears. The body's edge length is what the
    triangle budget leaves."""
    v = np.asarray(v, np.float64)
    region = np.zeros(len(v), np.int8)

    def within(centre, radius):
        return np.linalg.norm(v - np.asarray(centre), axis=1) < radius

    for key in ("foot_left", "foot_right"):
        if key in marks:
            region[within(marks[key], 0.15)] = 1
    for key in ("hand_left", "hand_right"):
        if key in marks:
            region[within(marks[key], 0.105)] = 2
    if "head" in marks:
        region[within(marks["head"], 0.15)] = 3
    if "face" in marks:
        face = np.asarray(marks["face"], np.float64)
        region[within(face, 0.082)] = 4
        for side in (-1.0, 1.0):                                         # the ears, either side and behind the face
            region[within(face + np.array([side * 0.082, 0.02, -0.085]), 0.05)] = 4
    edges = [3.0, 1.8, 1.4, 1.8, 0.8]
    # The body's edge from what is left of the budget.
    fine_triangles = 0.0
    # Rough areas: the regions' share of the vertices times the whole surface (the vertices are evenly spread before decimation).
    share = np.bincount(region, minlength=5) / max(1, len(v))
    surface_mm2 = 2.13e6
    for r in range(1, 5):
        fine_triangles += share[r] * surface_mm2 / (0.433 * edges[r] ** 2)
    left = max(triangles - fine_triangles, 150_000)
    edges[0] = float(np.clip(np.sqrt(share[0] * surface_mm2 / (0.433 * left)), 2.0, 4.0))
    return region, edges


def magnify(v: np.ndarray, bubbles: list[tuple]) -> np.ndarray:
    """Each bubble scales what is inside it by its gain about its centre and pushes the rest outward by the same
    amount, so the map stays one-to-one and continuous."""
    v = np.asarray(v, np.float64).copy()
    for centre, radius, gain in bubbles:
        d = v - centre
        r = np.linalg.norm(d, axis=1)
        r2 = np.where(r < radius, r * gain, r + (gain - 1.0) * radius)
        v = centre + d * (r2 / np.maximum(r, 1e-12))[:, None]
    return v


def shrink(v: np.ndarray, bubbles: list[tuple]) -> np.ndarray:
    """The inverse of magnify."""
    v = np.asarray(v, np.float64).copy()
    for centre, radius, gain in reversed(bubbles):
        d = v - centre
        r2 = np.linalg.norm(d, axis=1)
        r = np.where(r2 < radius * gain, r2 / gain, r2 - (gain - 1.0) * radius)
        v = centre + d * (r / np.maximum(r2, 1e-12))[:, None]
    return v


# ---- the surface -----------------------------------------------------------------------------------------------
def fine_surface(fine: fine_skin.FineOutline, sigma_mm: float = SMOOTH_MM, log=print):
    """The blurred fine outline's 0.5 level: vertices in the body's millimetres (array order z, y, x) and faces."""
    spacing = np.array(fine.spacing)
    nz, ny, nx = fine.cover.shape
    sigma = [sigma_mm / s for s in spacing]
    pad = int(np.ceil(4 * sigma[1])) + 1
    verts, faces, offset = [], [], 0
    for y0 in range(0, ny - 1, SLAB):
        y1 = min(ny - 1, y0 + SLAB)                                       # cells between slices y0 .. y1
        a, b = max(0, y0 - pad), min(ny, y1 + 1 + pad)
        field = ndimage.gaussian_filter(fine.slab(a, b), sigma)[:, y0 - a:y1 + 1 - a, :]
        if field.max() <= 0.5:
            continue
        # Closed at the grid's sides always; at the ends of the stack only where the stack itself ends.
        field = np.pad(field, ((1, 1), (1 if y0 == 0 else 0, 1 if y1 == ny - 1 else 0), (1, 1)))
        v, f, _, _ = measure.marching_cubes(field, 0.5)
        v[:, 0] -= 1
        v[:, 2] -= 1
        v[:, 1] += y0 - (1 if y0 == 0 else 0)
        verts.append(v)
        faces.append(f + offset)
        offset += len(v)
        log(f"skin surface: slices {y0}..{y1}: {len(f)} triangles")
    v = np.concatenate(verts)
    f = np.concatenate(faces)
    v, f = weld(v, f, WELD_MM)
    return np.array(fine.origin_mm) + (v + 0.5) * spacing, f


def weld(v: np.ndarray, f: np.ndarray, tolerance: float):
    """Vertices at the same place (within `tolerance`) become one; triangles that collapse are dropped."""
    key = np.round(v / tolerance).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    f = inverse.reshape(-1)[f]
    good = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    return v[first], f[good].astype(np.uint32)


def fine_openness(fine: fine_skin.FineOutline, body: Body, v: np.ndarray, n: np.ndarray, sigma_mm: float = 2.2, out_mm: float = 1.6) -> np.ndarray:
    """Small-scale openness at the vertices (creases of the lids, the nostrils, between the fingers): the fine
    outline blurred by `sigma_mm`, read `out_mm` above the surface; 1 open, 0 closed in."""
    spacing = np.array(fine.spacing)
    p = np.asarray(v, np.float64) + n * (out_mm / 1000.0)
    mm = np.stack([-p[:, 2] * 1000.0 + body.size_mm[2] / 2, p[:, 1] * 1000.0 + body.size_mm[1] / 2, p[:, 0] * 1000.0 + body.size_mm[0] / 2], axis=1)
    idx = (mm - np.array(fine.origin_mm)) / spacing - 0.5                 # fine voxel coordinates (z, y, x)
    sigma = [sigma_mm / s for s in spacing]
    pad = int(np.ceil(4 * sigma[1])) + 2
    ny = fine.cover.shape[1]
    occ = np.zeros(len(v), np.float32)
    slab_of = np.clip(np.floor((idx[:, 1] + 0.5) / SLAB).astype(np.int64), 0, (ny - 1) // SLAB)
    for k in np.unique(slab_of):
        sel = np.nonzero(slab_of == k)[0]
        y0, y1 = int(k) * SLAB, min(ny, (int(k) + 1) * SLAB)
        a, b = max(0, y0 - pad), min(ny, y1 + pad)
        field = ndimage.gaussian_filter(fine.slab(a, b), sigma)
        q = idx[sel].T.copy()
        q[1] -= a
        occ[sel] = ndimage.map_coordinates(field, q, order=1, mode="nearest")
    # Over a flat surface the blurred outline reads Phi(-out / sigma); a crease reads more.
    from math import erf, sqrt
    flat = 0.5 * (1.0 + erf(-out_mm / sigma_mm / sqrt(2.0)))
    return np.clip(1.0 - (occ - flat) / (0.75 - flat), 0.0, 1.0)


def concavity_mm(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    """How far each vertex lies below the mean of its neighbours along its normal, millimetres (a furrow is
    positive, a ridge negative), smoothed once over the neighbours."""
    from scipy import sparse
    k = len(v)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    adj = sparse.coo_matrix((np.ones(len(i), np.float32), (i, j)), shape=(k, k)).tocsr()
    adj.data[:] = 1.0
    degree = np.maximum(np.asarray(adj.sum(axis=1)).ravel(), 1.0)
    p = np.asarray(v, np.float64)
    dip = np.einsum("ij,ij->i", (adj @ p) / degree[:, None] - p, normals_of(v, f)) * 1000.0
    return 0.5 * dip + 0.5 * (adj @ dip) / degree


def tolerance(body: Body, fine: fine_skin.FineOutline, v: np.ndarray) -> np.ndarray:
    """How far a skin vertex may move when the surface is relaxed (metres): under a pixel everywhere, and a couple
    of millimetres at the photographs that had to be replaced (the joints between the specimen's blocks, where the
    outline jumps)."""
    y_mm = np.asarray(v[:, 1], np.float64) * 1000.0 + body.size_mm[1] / 2
    index = np.clip(np.round((y_mm - fine.origin_mm[1]) / fine.spacing[1] - 0.5).astype(np.int64), 0, len(fine.fallback) - 1)
    joint = ndimage.gaussian_filter1d(ndimage.binary_dilation(fine.fallback, iterations=3).astype(np.float32), 2.0)
    return (0.00045 + 0.0018 * np.clip(joint[index] * 1.5, 0, 1)).astype(np.float32)   # the bake reads these two numbers back


def face_tolerance(base: np.ndarray, v: np.ndarray, marks: dict) -> np.ndarray:
    """On the face the relaxation is held tighter: its lines (lids, lips, nostrils) are under a millimetre deep."""
    if "face" not in marks:
        return base
    near = np.linalg.norm(np.asarray(v, np.float64) - np.asarray(marks["face"]), axis=1)
    weight = np.clip((0.11 - near) / 0.03, 0.0, 1.0)
    return (base - (base - 0.00032) * weight * (base < 0.0006)).astype(np.float32)


# ---- the briefs ------------------------------------------------------------------------------------------------
def briefs_solid(body: Body) -> np.ndarray | None:
    """The briefs as a solid (z, y, x) on the export's grid: the pelvis and the tops of the thighs wrapped in cloth
    that spans the hollows (it hangs between the thighs and hides the shape under it), 2.5 mm proud of the skin."""
    lab, (sz, sy, sx) = body.labels, body.spacing
    hips = [o["index"] for o in body.objects if o["name"] in ("left hip bone", "right hip bone")]
    low = [o["index"] for o in body.objects if o["name"] in ("scrotum", "testis", "penis")]
    if not hips or not low:
        return None
    ys = np.nonzero(np.isin(lab, hips).any(axis=(0, 2)))[0]
    yl = np.nonzero(np.isin(lab, low).any(axis=(0, 2)))[0]
    y0 = max(0, int(yl.min()) - int(round(45 / sy)))            # short legs, well below the crotch
    y1 = int(ys.min() + 0.52 * (ys.max() - ys.min()))           # below the iliac crests, as briefs sit
    arms = [o["index"] for o in body.objects if "arm" in o["name"]]
    block = (lab[:, y0:y1, :] > 0) & ~np.isin(lab[:, y0:y1, :], arms)
    block = ndimage.binary_opening(block, iterations=3)          # the hands lie against the thighs: cut the thin joins
    parts, n = ndimage.label(block)
    if n == 0:
        return None
    sizes = ndimage.sum(block, parts, range(1, n + 1))
    block = parts == (1 + int(np.argmax(sizes)))
    for k in range(block.shape[1]):
        block[:, k, :] = ndimage.binary_fill_holes(block[:, k, :])
    # Cloth under tension: a strong blur of the outline, cut where the blurred body is a third present, bridges the
    # hollow of the groin and rounds what stands out; nowhere may it sink below the skin itself.
    tent = ndimage.gaussian_filter(block.astype(np.float32), (9.0 / sz, 3.0 / sy, 9.0 / sx)) > 0.36
    outer = np.isin(lab[:, y0:y1, :], low)                             # what the opening took away of him, not the hands
    proud = ndimage.binary_dilation(block | outer, ndimage.generate_binary_structure(3, 1), iterations=3)
    cloth = tent | proud
    cloth[:, :1, :] = cloth[:, -1:, :] = False                  # hems, not open ends
    solid = np.zeros(lab.shape, bool)
    solid[:, y0:y1, :] = cloth
    return solid


# ---- the layer -------------------------------------------------------------------------------------------------
def build(body: Body, triangles: int, log=print, reuse_surface: bool = False) -> list[Structure]:
    """The skin layer: the skin, the briefs, the hair. `reuse_surface` takes the surface (shape and bake) from the
    last build and redoes only what is painted and grown on it: for working on the zones, the lids or the hair."""
    lab = body.labels
    baker = Baker(body)
    tissue = lab > 0
    field, depth = baker.field(tissue), baker.depth(tissue)
    marks = landmarks(body)
    bubbles = detail_bubbles(marks)
    fine = fine_skin.load(body)
    base_path = body.export / "model" / "skin_surface.npz"
    base = load_structures(base_path)[0] if reuse_surface and base_path.exists() else None
    if base is not None:
        v, f, bake = base.v, base.f, base.bake.copy()
        log(f"skin surface: {len(f)} triangles from the last build")
    elif fine is not None:
        v_mm, f = fine_surface(fine, log=log)
        v, f = body.to_gltf(v_mm, f)
        v, f = keep_big_pieces(v, f, 0.01)
        log(f"skin surface: {len(f)} triangles from the fine outline")
        v = relax(v, f, 40, face_tolerance(tolerance(body, fine, v), v, marks))
    else:
        v_mm, f = surface(tissue, body.spacing, 1.6)
        v, f = body.to_gltf(v_mm, f)
        log(f"skin surface: {len(f)} triangles from the export's voxels (no fine outline: run with --photos)")
    if base is not None:
        pass
    elif fine is not None:
        # Finer where a student looks closely: the face under a millimetre, the ears, hands and feet a little over.
        region, edges = detail_regions(v, marks, triangles)
        v, f = decimate_regions(v, f, region, edges, log)
    else:
        big = magnify(v, bubbles)
        big, f = decimate(big.astype(np.float32), f, int(triangles), agg=4.0)
        v = shrink(big, bubbles).astype(np.float32)
    if base is None:
        f = outward(v, f)
    if base is None and fine is not None:                                 # the steps the decimation kept as edges
        v = relax(v, f, 30, face_tolerance(tolerance(body, fine, v), v, marks))
    if base is None:
        bake = baker.colours(v, f, field, depth)
    if base is None and fine is not None:
        small = fine_openness(fine, body, v, normals_of(v, f))
        # At the joints between the specimen's blocks the outline steps; that step is not a crease of his skin.
        joint = np.clip((tolerance(body, fine, v) - 0.00045) / 0.0018, 0, 1)
        small = small + (1.0 - small) * joint
        bake[:, 0] = np.round(np.maximum(bake[:, 0], 255.0 * 0.85 * joint) * (0.35 + 0.65 * small))
        if "face" in marks:
            # The face's fine lines (where the lids meet, between the lips, the nostrils' rims) are a millimetre wide:
            # how far each vertex lies below its neighbours on the finished mesh draws them as the dark lines they
            # are (the outline's own blur at that scale would read its pixel steps as lines too).
            near = np.linalg.norm(np.asarray(v, np.float64) - np.asarray(marks["face"]), axis=1)
            weight = np.clip((0.105 - near) / 0.02, 0.0, 1.0)
            line = np.clip(1.0 - (concavity_mm(v, f) - 0.03) / 0.26, 0.0, 1.0)
            bake[:, 0] = np.round(bake[:, 0] * (1.0 - weight * 0.5 * (1.0 - line)))
    if base is None:
        save_structures(base_path, [Structure("skin surface", "skin", v, f, (1.0, 1.0, 1.0), bake=bake)])
    # The skin's own colour, gloss and hair by region; then the hair itself.
    normals = normals_of(v, f)
    albedo, hair_mask, gloss, reg, info = zones.paint(body, v, normals, bake, marks, f)
    bake[:, 3] = gloss
    if "face" in info:
        log(info["face"].describe())
    skin_colour = tuple(c / 255 for c in zones.SKIN_BASE)
    skin_info = {"landmarks": {k: [float(x) for x in np.ravel(p)] for k, p in marks.items()}}
    lid_y = None
    if "face" in info and len(body.meta.get("eyes") or []) == 2:
        eyes = sorted(measured_eyes(body), key=lambda e: e["centre_m"][0])
        log("eyes as measured in the photographs: " + "; ".join(f"centre {[round(x * 1000, 1) for x in e['centre_m']]} mm, radius {e['radius_m'] * 1000:.1f} mm" for e in eyes)
            + " | as the export had them: " + "; ".join(str([round(x * 1000, 1) for x in e["centre_m"]]) for e in sorted(body.meta["eyes"], key=lambda e: e["centre_m"][0])))
        face = info["face"]
        lid_y = {side: (e["lid_line_y_m"] - face.origin[1]) / zones.MM for side, e in zip(("right", "left"), eyes)}
        for side, found in (info.get("lid_w") or {}).items():                # the furrow in the skin itself, where it shows
            if found is not None:
                lid_y[side] = found
        log("lid lines, mm above the eyes: %s; read from the relief: %s; furrows below each globe's middle (mm, depth): %s"
            % ({k: round(x, 1) for k, x in lid_y.items()}, info.get("lid_w"), getattr(face, "furrows", None)))
        centres = {side: np.array([e["centre_m"][0], e["centre_m"][1], -e["centre_m"][2]]) for side, e in zip(("right", "left"), eyes)}
        skin_info["eyes"] = {"centres": {s: [float(x) for x in c] for s, c in centres.items()},
                             "radius": {side: float(e["radius_m"]) for side, e in zip(("right", "left"), eyes)},
                             "forward": [float(x) for x in face.ez], "up": [float(x) for x in face.ey],
                             "lid_w": {s: float(x) for s, x in lid_y.items()},
                             "upper_degrees": lids.UPPER_DEGREES, "lower_degrees": lids.LOWER_DEGREES}
    # The lids: the hair is grown on the uncut skin (its roots do not care), then the slits are cut.
    data2 = None
    v_hair, f_hair, n_hair = v, f, normals
    if lid_y is not None:
        v2, f2, source, data2, margin = lids.cut(v, f, info["face"], lid_y, centres, log)
        bake, albedo, hair_mask = bake[source], albedo[source], hair_mask[source]
        albedo[margin] = lids.MARGIN_COLOUR
        bake[margin, 3] = 215                                              # the margin is wet
        bake[margin, 0] = 150
        v, f = v2, f2
    # The mouth: measured on this surface, the lips parted along their line, every vertex given its share in the jaw's turn.
    data3, mouth_lining, mouth_gums = None, None, []
    if "face" in info:
        m = getattr(body, "mouth", None)
        if m is None or base is None:
            m = mouth.prepare(body, info["face"], v_hair, getattr(body, "head_ct_dir", None), log)
        if m is not None:
            v2, f2, source, side, margin, anchor, held = mouth.cut(v, f, body, m, log)
            bake, albedo, hair_mask = bake[source], albedo[source], hair_mask[source]
            if data2 is not None:
                data2 = data2[source]
            albedo[margin] = mouth.MUCOSA
            bake[margin] = (178, 255, 82, 220)                               # the lips' inner sides: one even, wet lining (not their edges' own shading, drawn out in streaks)
            hair_mask[margin] = 0                                            # and no beard's follicles on them
            v, f = v2, f2
            data3 = mouth.skin_weights(body, m, v, side, anchor, held)
            skin_info["mouth"] = m.info["unity"]
            mouth_lining = mouth.lining(body, m, log)
            mouth_gums = mouth.gums(body, m, log)
    out = [Structure("skin", "skin", v, f, skin_colour, bake=bake, albedo=albedo, extra=hair_mask, data2=data2, data3=data3, info=skin_info)]
    if mouth_lining is not None:
        out.append(mouth_lining)
    out += mouth_gums

    solid = briefs_solid(body)
    covered = None
    if solid is not None:                                                 # no hair grows through the cloth
        cloth = ndimage.gaussian_filter(solid[::2, ::2, ::2].astype(np.float32), 0.8)
        covered = zones.smooth(body.sample(cloth, v_hair, step=2), 0.3, 0.6)
    out += hair.build(v_hair, f_hair, n_hair, reg, info, covered=covered, lid_y=lid_y, log=log)
    if solid is not None:
        box = ndimage.find_objects(solid.astype(np.int32))[0]
        got = surface(solid[box], body.spacing, 2.2, [s.start for s in box])
        if got is not None:
            bv, bf = decimate(*got, 36000)
            bv, bf = body.to_gltf(bv, bf)
            out.insert(1, Structure("briefs", "skin", bv, bf, BRIEFS, bake=baker.colours(bv, bf, field, gloss=30)))
    log(f"skin: {len(out)} structures, {sum(s.triangles for s in out)} triangles")
    return out
