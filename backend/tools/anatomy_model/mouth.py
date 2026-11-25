"""The mouth as a mouth: the gap between the jaws, what lines it, the teeth and the tongue, and how the jaw opens.

The body was frozen with its lips closed, its jaw a centimetre open and the tongue filling the mouth up to the
palate. For the mouth to be opened (pinched open like the lids) the model needs what the scan does not show as
shapes: where the upper jaw's parts end and the lower jaw's begin, something to see inside, and for every vertex
of every layer how far it goes with the jaw.

The gap. Everything is worked out on one grid round the mouth (the head's photographs' own voxels, 0.66 x 1 x
0.66 mm). The CT's labels (TotalSegmentator on his frozen CT, head_layers.py) give the skull, the mandible, the
teeth and the tongue there. The underside of the upper jaw (the upper teeth as they are, the bone with 3 mm of
gum and palate over it) is read column by column as a height: the `sheet`. It is carried on to the lip line on
the skin in front and a little way over the soft palate behind. All that lies under it goes with the lower jaw.
The space of the mouth is 3 mm under the sheet (taken from the tongue's top, which lay against the palate), and
the pockets of gelatin the photographs show beside the teeth.

What is seen inside. The `lining` is that space's roof and floor (palate, gums, the lips' inner sides; over the
tongue it is the tongue's own surface), left open where a tooth is the wall, with one band for the cheeks' inner
sides and the throat that is drawn out evenly as the mouth opens (`cheek_wall`). The teeth are meshed from the
CT's own bright voxels, each with its root (the bones' own blurred teeth give way to them, `without_crowns`); the
tongue is the label grown up to the space. The labels' unnamed muscle and fat are cleared from the space, and the
fat from the whole inside of the mouth (`clear_labels`).

The jaw's weights. One number per vertex, 0 with the skull, 1 with the mandible: the solution of Laplace's
equation in the head's and neck's soft tissue between the two (the skull, the spine and the neck's base held at
0, the mandible at 1), with no flow across the sheet. So the lower lip, the chin and the tongue go with the jaw,
the cheeks stretch between, the neck under the chin gives way gradually. Unity turns every vertex about the
jaw's axis (under the two condyles: find_hinge) by its weight times the opening (LabLids.hlsl, LabJaw).

Behind the hard palate the mouth passes into the throat (throat.py): the tongue's back, the soft palate that lay
on it, and the throat as drawn.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import ct_frame, fine_skin, head_layers, throat
from .common import FAT_LOWER_LIP, FAT_SURFACE, FAT_UPPER_LIP, Body, Structure, decimate, level_set, load_structures, normals_of, surface
from .zones import MM, Face

GUM_MM = 3.0                    # soft tissue over the upper jaw's bone (gum, palate)
LOWER_GUM_MM = 2.0
SPACE_MM = 3.0                  # the mouth's space under the sheet
TOOTH_HU = 1400                 # brighter than this inside the teeth's label: tooth
HALF_WIDTH = 27.0               # mm: half the mouth's width on the skin
OPEN_DEGREES = 18.0             # the jaw's full turn about its axis (the lower incisors' edges go about 23 mm down and 11 mm back)
AXIS_BELOW_MM = 30.0            # the axis lies this far under the condyles' heads: a jaw that opens wide turns AND its condyles slide forward
FIRM_MM = 5.0                   # flesh this near the mandible goes with it wholly
CROWN_MM = 8.0                  # a crown's height: this far from the tooth row's edge the bones' own teeth are taken out
FOLD_MM = 10.0                  # from the teeth's edges towards their roots: where a lip's lining turns onto the gum
LIP_PULL_MM = 10.0              # how far the lower lip is drawn down off the teeth when the mouth is fully open
LIP_LIFT_MM = 6.0               # how far the upper lip is lifted off the upper teeth (by itself: it does not go with the jaw)
GUM_FROM_MM = 7.0               # the gum's edge: this far from a row's biting edge (a little more at the front teeth, whose crowns are longer)
GUM_DEEP_MM = 15.0              # and how far the gum is drawn from there towards the roots' tips
RIM_MM = 3.0                    # towards the sheet's rim its two sides come to move alike, over this distance
MUCOSA = (186, 106, 104)
GUM = (204, 138, 132)
PALATE = (208, 150, 140)
TONGUE = (176, 104, 100)
TONGUE_COAT = (198, 156, 148)   # the pale coat on the middle and back of a tongue's upper side
TONGUE_EDGE = (168, 88, 90)     # its redder tip and edges
TOOTH = (212, 204, 180)
ROOT = (206, 186, 140)


@dataclass
class Grid:
    """A block of voxels in the body's millimetres (array order z, y, x: back, up, to his left)."""
    origin: np.ndarray           # the first voxel's corner
    spacing: np.ndarray
    shape: tuple

    def axis(self, k: int) -> np.ndarray:
        return self.origin[k] + (np.arange(self.shape[k]) + 0.5) * self.spacing[k]

    def points(self) -> np.ndarray:
        """Every voxel's centre, (nz, ny, nx, 3) float32."""
        z, y, x = np.meshgrid(self.axis(0), self.axis(1), self.axis(2), indexing="ij")
        return np.stack([z, y, x], axis=-1).astype(np.float32)

    def index(self, zyx_mm: np.ndarray) -> np.ndarray:
        """Millimetres (n, 3) -> (3, n) for scipy.ndimage.map_coordinates."""
        return ((np.asarray(zyx_mm, np.float64) - self.origin) / self.spacing - 0.5).T

    def sample(self, array: np.ndarray, zyx_mm: np.ndarray, order: int = 1, cval: float | None = None) -> np.ndarray:
        if cval is None:
            return ndimage.map_coordinates(array, self.index(zyx_mm), order=order, mode="nearest")
        return ndimage.map_coordinates(array, self.index(zyx_mm), order=order, mode="constant", cval=cval)


def to_mm(body: Body, v_gltf: np.ndarray) -> np.ndarray:
    """glTF metres -> the body's millimetres in array order z, y, x."""
    p = np.asarray(v_gltf, np.float64) * 1000.0
    return np.stack([-p[..., 2] + body.size_mm[2] / 2, p[..., 1] + body.size_mm[1] / 2, p[..., 0] + body.size_mm[0] / 2], axis=-1)


def to_gltf(body: Body, zyx_mm: np.ndarray) -> np.ndarray:
    p = np.asarray(zyx_mm, np.float64)
    return np.stack([p[..., 2] - body.size_mm[0] / 2, p[..., 1] - body.size_mm[1] / 2, -(p[..., 0] - body.size_mm[2] / 2)], axis=-1) / 1000.0


def head_export(body: Body):
    """The head's finer export as (Grid, rgba (z, y, x, 4)), or None."""
    entry = next((r for r in body.meta.get("regions", []) if r.get("name") == "head"), None)
    if entry is None:
        return None
    folder = body.export.parent / entry["folder"]
    if not (folder / "body.raw").exists():
        return None
    meta = json.loads((folder / "body.json").read_text())
    dx, dy, dz = meta["dims"]
    rgba = np.fromfile(folder / "body.raw", np.uint8).reshape(dz, dy, dx, 4)
    centre, size = np.array(entry["centre_m"], np.float64) * 1000.0, np.array(entry["size_m"], np.float64) * 1000.0
    corner = centre - size / 2 + np.array(body.size_mm) / 2                    # x, y, z
    return Grid(corner[::-1].copy(), (size / np.array([dx, dy, dz]))[::-1].copy(), (dz, dy, dx)), rgba


def under_skin(body: Body, grid: Grid, zyx_mm: np.ndarray) -> np.ndarray:
    """Which points lie inside the body: by the fine skin outline where there is one (the export's own outline is
    wider, most in the hollows of the face), else by the export's depth map."""
    fine = fine_skin.load(body)
    if fine is None:
        return body.sample(body.depth_mm(), to_gltf(body, zyx_mm)) > 0.5
    whole = Grid(np.array(fine.origin_mm, np.float64), np.array(fine.spacing, np.float64), fine.cover.shape)
    lo = np.maximum(np.floor((grid.origin - whole.origin) / whole.spacing).astype(int) - 2, 0)
    hi = np.minimum(lo + np.ceil(np.array(grid.shape) * grid.spacing / whole.spacing).astype(int) + 5, np.array(whole.shape))
    block = np.asarray(fine.cover[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]], np.float32)
    part = Grid(whole.origin + lo * whole.spacing, whole.spacing, block.shape)
    return part.sample(block, zyx_mm, order=1, cval=0.0) > 127.0


def near(mask: np.ndarray, spacing, mm: float) -> np.ndarray:
    """The mask grown by `mm` (a ball, in millimetres)."""
    if not mask.any():
        return mask.copy()
    return ndimage.distance_transform_edt(~mask, sampling=spacing) <= mm


def fill_columns(values: np.ndarray, known: np.ndarray, domain: np.ndarray, rounds: int = 1500) -> np.ndarray:
    """A height per column where it is known, carried smoothly over the rest of the domain (Laplace, by relaxation)."""
    h = np.where(known, values, 0.0).astype(np.float64)
    if not known.any():
        return h
    # Start from the nearest known value, then relax.
    idx = ndimage.distance_transform_edt(~known, return_distances=False, return_indices=True)
    h = h[tuple(idx)]
    free = domain & ~known
    for _ in range(rounds):
        total = np.zeros_like(h)
        count = np.zeros_like(h)
        for axis in (0, 1):
            for step in (1, -1):
                moved = np.roll(h, step, axis=axis)
                ok = np.roll(domain | known, step, axis=axis)
                edge = [slice(None), slice(None)]
                edge[axis] = 0 if step == 1 else -1
                ok[tuple(edge)] = False
                total += np.where(ok, moved, 0.0)
                count += ok
        h = np.where(free & (count > 0), total / np.maximum(count, 1), h)
    return h


def lip_line(face: Face, v: np.ndarray):
    """The line where the lips meet, read from the skin's relief: w (mm above the eyes) as a function of u, and
    how far forward the skin lies along it. Falls back on the profile's lip line with the corners turned down."""
    u, w, d = face.local(v)
    w0 = face.stomion_w
    us, found = [], []
    for ui in np.arange(-22.0, 22.1, 2.0):
        strip = (np.abs(u - ui) < 1.5) & (w > w0 - 7.0) & (w < w0 + 7.0) & (d > 20.0)
        if strip.sum() < 60:
            continue
        ws = np.arange(w0 - 7.0, w0 + 7.0, 0.4)
        rows = np.clip(((w[strip] - ws[0]) / 0.4).astype(int), 0, len(ws) - 1)
        depth = np.full(len(ws), np.nan)
        for k in np.unique(rows):
            depth[k] = np.median(d[strip][rows == k])
        good = ~np.isnan(depth)
        if good.sum() < len(ws) * 0.7:
            continue
        depth = np.interp(ws, ws[good], depth[good])
        dip = ndimage.gaussian_filter1d(depth, 1.0) - ndimage.gaussian_filter1d(depth, 8.0)
        inside = (ws > w0 - 4.5) & (ws < w0 + 4.5)
        k = int(np.argmin(np.where(inside, dip, 1e9)))
        if dip[k] < -0.05:
            us.append(ui)
            found.append(ws[k])
    if len(us) >= 8:
        coef = np.polyfit(us, found, 2)
        rest = np.abs(np.polyval(coef, us) - np.array(found))
        keep = rest < max(1.0, 2.0 * np.median(rest))
        coef = np.polyfit(np.array(us)[keep], np.array(found)[keep], 2)
        coef[0] = float(np.clip(coef[0], -0.006, 0.003))                    # a mouth's line bends little
    else:
        coef = np.array([-1.2 / (HALF_WIDTH - 1.0) ** 2, 0.0, w0])

    def w_of(uu):
        return np.polyval(coef, np.clip(uu, -HALF_WIDTH, HALF_WIDTH))

    return w_of, {"read_at": len(us), "coefficients": [float(c) for c in coef]}


@dataclass
class Mouth:
    grid: Grid
    face: Face
    lip_w: object                                  # the lip line: w of u
    sheet: np.ndarray                              # (nz, nx) the sheet's height, body mm (y)
    domain: np.ndarray                             # (nz, nx) where the sheet is
    space: np.ndarray                              # (nz, ny, nx) the mouth's space
    teeth_upper: np.ndarray
    teeth_lower: np.ndarray
    tongue: np.ndarray
    upper: np.ndarray                              # the upper jaw's hard parts with their gum
    lower: np.ndarray
    lips: np.ndarray = None                        # (nz, nx) the columns between the lips, from the skin to the teeth
    skin_front: np.ndarray = None                  # (nx,) how far forward the lips' skin lies (z, mm)
    u_of_x: np.ndarray = None                      # (nx,) the face's u (mm to his left of its middle) of each column
    stomion_mm: np.ndarray = None                  # where the lips meet in the midline, body mm (z, y, x)
    depth: np.ndarray = None                       # (nz, ny, nx) mm under the skin
    tooth_fields: dict = None                      # name -> the CT's values in that row of teeth (contoured for the teeth's meshes)
    ct: dict = None                                # ct_on_grid's result
    rgba_grid: Grid = None                         # the head's export: its grid and its colours (the photographs)
    rgba: np.ndarray = None
    hinge: np.ndarray | None = None                # glTF metres: a point on the jaw's axis
    condyles: tuple | None = None                  # glTF metres: the heads of the mandible's two condyles (right, left), 3 mm under their crowns
    axis: np.ndarray | None = None                 # glTF: the axis' direction (to his left)
    weight_grid: Grid | None = None                # the jaw's weights (jaw_weights): their grid,
    weights: np.ndarray = None                     # as solved; `above` as seen from the upper side of the sheet, `below` from the lower
    above: np.ndarray = None
    below: np.ndarray = None
    rim: np.ndarray = None                         # (nz, nx) 0..1: how far the sheet's two sides part there (nothing at its rim and at the mouth's corners)
    rim_only: np.ndarray = None                    # (nz, nx) 0..1: the rim's share of that alone
    lip: np.ndarray = None                         # (nz, ny, nx) -1..1: how far a point goes with the lower lip when it is drawn down (lip_field); negative: with the upper lip when it is lifted
    lip_whole: np.ndarray = None                   # the same for points known to be the lower lip's (not asked which lip they are of)
    lip_whole_up: np.ndarray = None                # and for points known to be the upper lip's: how far they go with it when it is lifted (0..1)
    lip_up: np.ndarray | None = None               # glTF: the way the upper lip is lifted (up the face and a little forward)
    lip_down: np.ndarray | None = None             # glTF: the way the lower lip is drawn (down the face and a little forward)
    throat: object = None                          # throat.Throat: what lies behind the hard palate (the tongue's back, the soft palate, the throat as drawn)
    drawn_lower: np.ndarray = None                 # (nz, ny, nx) the voxels the DRAWN mandible's surface passes through (BoneHub's bone as placed), and
    drawn_upper: np.ndarray = None                 # the drawn skull's: they lie a millimetre or two off the CT's own bone, which the gums are made from
    vestibule_up: np.ndarray = None                # (nz, ny, nx) 0..1: between the upper lip and the upper jaw's teeth and gum
    info: dict = field(default_factory=dict)


def ct_on_grid(body: Body, grid: Grid, ct_dir: Path | None = None, log=print):
    """The CT's values and labels at the grid's voxels: hu (float32; from the CT's own pixels where its folder or
    the window kept from it is at hand, else from the common grid) and bool masks by label name."""
    cache = body.export / "model" / "ct_head.npz"
    if not cache.exists() or not head_layers.folder(body).exists():
        return None
    vol = ct_frame.volume(None, head_layers.FIRST, head_layers.LAST, cache, log)
    to_body = ct_frame.CtToBody(body, vol)
    index = to_body.inverse(grid.points()).astype(np.float32)
    out = {"hu": ndimage.map_coordinates(vol.hu.astype(np.float32), index, order=1, mode="nearest")}
    number, y, x = to_body.scanner(index)
    fine = ct_frame.native(ct_dir, int(np.floor(number.min())) - 1, int(np.ceil(number.max())) + 1, (float(x.min()) - 2, float(x.max()) + 2),
                           (float(y.min()) - 2, float(y.max()) + 2), body.export / "model" / "ct_mouth.npz", log)
    out["fine"] = fine is not None
    out["raw"] = {}
    if fine is not None:
        at = np.stack([number - fine["first"] - 0.5, (y - fine["y0"]) / fine["px"] - 0.5, (x - fine["x0"]) / fine["px"] - 0.5], axis=0)
        sharp = ndimage.map_coordinates(fine["hu"].astype(np.float32), at, order=1, mode="nearest")
        out["hu"] = np.where(at[0] <= len(fine["hu"]) - 1, sharp, out["hu"])    # below the window's last slice: the common grid's
    for task, wanted in (("craniofacial_structures", ("mandible", "skull", "teeth_upper", "teeth_lower")), ("head_muscles", ("tongue",))):
        got = head_layers.read_labels(body, task)
        if got is None:
            return None
        data, names = got
        out["raw"][task] = got
        at = ndimage.map_coordinates(data, index, order=0, mode="constant", cval=0)
        for value, name in names.items():
            if name in wanted:
                out[name] = at == value
    got = head_layers.read_labels(body, "headneck_bones_vessels")
    if got is not None:
        out["raw"]["headneck_bones_vessels"] = got
    out["to_body"], out["vol"] = to_body, vol
    return out


def drawn_bones(body: Body, grid: Grid):
    """The jaws' bones as the skeleton layer draws them (BoneHub's mandible and skull as placed on him), on a grid:
    the voxels their surfaces pass through, as (lower, upper). The gums and the lips' inner sides are made from the
    CT's own bone; BoneHub's bone is another reading of the same jaw and lies a millimetre or two off it in places,
    where it came through the gum's face. Empty where the bones have not been placed."""
    from . import bonehub
    from .face_muscles import _dense
    out = [np.zeros(grid.shape, bool), np.zeros(grid.shape, bool)]
    if not bonehub.cache_path(body).exists():
        return out
    placed, _, _ = bonehub.load_or_build(body, None)
    lo, hi = grid.origin, grid.origin + np.array(grid.shape) * grid.spacing
    for _, name, v, f in placed:
        k = 0 if name == "mandible" else 1 if name == "cranium and maxilla" else None
        if k is None:
            continue
        v = np.asarray(v, np.float64)
        near_box = ((v > lo - 3.0) & (v < hi + 3.0)).all(axis=1)
        tri = np.asarray(f, np.int64)
        tri = tri[near_box[tri].any(axis=1)]
        if len(tri) == 0:
            continue
        index = np.floor((_dense(v, tri, 0.3) - grid.origin) / grid.spacing).astype(np.int64)
        index = index[((index >= 0) & (index < np.array(grid.shape))).all(axis=1)]
        out[k][index[:, 0], index[:, 1], index[:, 2]] = True
    return out


def tooth_field(hu: np.ndarray, label: np.ndarray, spacing) -> np.ndarray:
    """The CT's values where the teeth's label is (and a little round it: the label is drawn on a coarser grid),
    falling away outside, so a level in it is the teeth's own smooth surface and not the bone's beside them."""
    away = ndimage.distance_transform_edt(~label, sampling=spacing).astype(np.float32)
    return hu - np.clip(away - 1.0, 0.0, None) * 900.0


def measure(body: Body, face: Face, skin_v: np.ndarray, ct_dir: Path | None = None, log=print) -> Mouth | None:
    """Reads the mouth from the CT's labels and the head's photographs; None where either is missing."""
    head = head_export(body)
    if head is None:
        return None
    head_grid, rgba = head
    # The grid: round the lips' meeting point, on the head export's own voxels.
    k = int(np.argmin(np.abs(face.profile_w - face.stomion_w)))
    stomion = face.origin + face.ey * (face.stomion_w * MM) + face.ez * (float(face.profile_d[k]) * MM)
    s = to_mm(body, stomion)
    lo = np.array([s[0] - 8.0, s[1] - 66.0, s[2] - 56.0])
    hi = np.array([s[0] + 112.0, s[1] + 38.0, s[2] + 56.0])                  # (back to the spine's front: the throat's back wall)
    first = np.floor((lo - head_grid.origin) / head_grid.spacing).astype(int)
    shape = tuple(int(n) for n in np.ceil((hi - lo) / head_grid.spacing))
    grid = Grid(head_grid.origin + first * head_grid.spacing, head_grid.spacing.copy(), shape)
    ct = ct_on_grid(body, grid, ct_dir, log)
    if ct is None or "mandible" not in ct or "teeth_upper" not in ct:
        return None
    sz, sy, sx = grid.spacing
    points = grid.points()
    flat = points.reshape(-1, 3)
    alpha = head_grid.sample(rgba[..., 3], flat, order=0, cval=255).reshape(shape)
    inside = under_skin(body, grid, flat).reshape(shape)
    depth = ndimage.distance_transform_edt(np.pad(inside, 1, constant_values=True), sampling=grid.spacing)[1:-1, 1:-1, 1:-1]      # mm under the skin
    gelatin = (alpha < 100) & (depth > 2.5)

    # The teeth: the CT's bright voxels in and round the labels.
    hu = ct["hu"]
    field_upper = tooth_field(hu, ct["teeth_upper"], grid.spacing)
    field_lower = tooth_field(hu, ct["teeth_lower"], grid.spacing)
    field_upper, field_lower = np.where(field_lower > field_upper, -1000.0, field_upper), np.where(field_upper >= field_lower, -1000.0, field_lower)
    teeth_upper, teeth_lower = field_upper > TOOTH_HU, field_lower > TOOTH_HU
    skull = ct["skull"] & ~teeth_upper & ~teeth_lower
    mandible = ct["mandible"] & ~teeth_upper & ~teeth_lower
    upper = teeth_upper | near(skull, grid.spacing, GUM_MM)
    lower = teeth_lower | near(mandible, grid.spacing, LOWER_GUM_MM)

    ys = grid.axis(1)
    tips = teeth_upper.any(axis=(0, 2))
    if not tips.any():
        return None
    y_tip = float(ys[np.argmax(tips)])                                       # the upper teeth's lowest edge
    # The sheet: per column (z, x), the underside of the upper jaw near the mouth.
    band = (ys > y_tip - 4.0) & (ys < y_tip + 27.0)
    up = upper & band[None, :, None]
    has_up = up.any(axis=1)
    bottom = np.argmax(up, axis=1)                                           # the lowest upper voxel's index
    sheet = grid.origin[1] + bottom * sy                                     # its lower face
    lower_band = (ys > y_tip - 34.0) & (ys < y_tip + 12.0)
    low = lower & lower_band[None, :, None]
    has_low = low.any(axis=1)
    top = shape[1] - 1 - np.argmax(low[:, ::-1, :], axis=1)
    low_top = grid.origin[1] + (top + 1) * sy

    # Where the mouth is, seen from above: within the arch of the teeth and a little outside it (the vestibule),
    # on behind the last teeth over the tongue's back, and forward between the lips to the skin.
    from skimage.morphology import convex_hull_image
    teeth_cols = (teeth_upper | teeth_lower).any(axis=1)
    arch = convex_hull_image(teeth_cols)
    palate = convex_hull_image(teeth_upper.any(axis=1))                      # under the upper jaw itself
    plan = (sz, sx)
    inside_arch = arch.copy()
    for step in range(1, int(14.0 / sz)):                                    # 14 mm further back
        inside_arch[step:] |= arch[:-step]
    domain = near(inside_arch, plan, 4.0)
    xs, zs = grid.axis(2), grid.axis(0)
    skin_front = np.full(shape[2], np.nan)                                   # the lips' front per x, at the lip line's height
    w_of, lip_info = lip_line(face, skin_v)
    uu = np.linspace(-HALF_WIDTH - 6.0, HALF_WIDTH + 6.0, 140)
    u_all, w_all, d_all = face.local(skin_v)
    lip_known = np.zeros(domain.shape, bool)
    lip_value = np.zeros(domain.shape)
    for ui in uu:
        wl = float(w_of(ui))
        strip = (np.abs(u_all - ui) < 1.0) & (np.abs(w_all - wl) < 1.5) & (d_all > 0)
        if not strip.any():
            continue
        p = to_mm(body, face.origin + face.ex * (ui * MM) + face.ey * (wl * MM) + face.ez * (float(d_all[strip].max()) * MM))
        ix = int((p[2] - grid.origin[2]) / sx)
        iz = int((p[0] - grid.origin[0]) / sz)
        if not (0 <= ix < shape[2]) or not (0 <= iz < shape[0]):
            continue
        skin_front[ix] = p[0] if np.isnan(skin_front[ix]) else min(skin_front[ix], p[0])
        if abs(ui) <= HALF_WIDTH:
            lip_known[max(0, iz - 6):iz + 3, ix] = True                      # from in front of the skin to a little inside it
            lip_value[max(0, iz - 6):iz + 3, ix] = p[1]
    good = ~np.isnan(skin_front)
    if good.sum() < 10:
        return None
    skin_front = np.interp(np.arange(shape[2]), np.nonzero(good)[0], skin_front[good])
    u_of_x = (to_gltf(body, np.stack([np.full(shape[2], s[0]), np.full(shape[2], s[1]), xs], axis=1)) - face.origin) @ face.ex / MM
    arch_front = np.where(domain.any(axis=0), zs[np.argmax(domain, axis=0)], np.nan)
    lips = np.zeros(domain.shape, bool)
    for ix in range(shape[2]):
        if abs(u_of_x[ix]) > HALF_WIDTH or np.isnan(arch_front[ix]):
            continue
        lips[(zs > skin_front[ix] - 4.0) & (zs <= arch_front[ix] + sz), ix] = True
    domain |= lips
    pocket_cols = (gelatin & band[None, :, None]).any(axis=1) & near(domain, plan, 7.0)
    domain |= pocket_cols

    known = has_up & palate & ~lips
    # Not the skull's base behind the palate, nor a stray voxel: a known height lies near its neighbours' median.
    med = ndimage.median_filter(np.where(known, sheet, y_tip + 8.0), size=(9, 9))
    known &= np.abs(sheet - med) < 9.0
    values = np.where(lip_known, lip_value, sheet)
    sheet = fill_columns(values, known | lip_known, domain | lip_known)
    sheet = np.where(has_low & domain, np.maximum(sheet, np.minimum(low_top + 0.3, sheet + 6.0)), sheet)
    smooth = ndimage.gaussian_filter(sheet, 0.8)
    sheet = np.where(known, np.minimum(sheet, smooth + 0.5), smooth)        # the teeth's edges kept, the rest smoothed

    # The space: 3 mm under the sheet (none at the skin itself, where the lips touch), and the gelatin's pockets.
    behind = np.clip((zs[:, None] - skin_front[None, :]) / 5.0, 0.0, 1.0)   # 0 at the lips' front, 1 from 5 mm inside
    thick = np.where(lips, SPACE_MM * behind, SPACE_MM)
    y3 = ys[None, :, None]
    under = (y3 < sheet[:, None, :] + 1.2) & (y3 >= sheet[:, None, :] - thick[:, None, :]) & domain[:, None, :]
    pockets = gelatin & near(domain, plan, 7.0)[:, None, :] & (np.abs(y3 - sheet[:, None, :]) < 12.0)
    bone = near(ct["skull"] | ct["mandible"], grid.spacing, 0.7)
    space = (under & ~upper & ~lower) | (pockets & ~teeth_upper & ~teeth_lower & ~bone)
    space &= inside
    parts, count = ndimage.label(space)
    if count > 1:
        sizes = ndimage.sum(space, parts, range(1, count + 1))
        space = parts == 1 + int(np.argmax(sizes))

    # The tongue: the label, grown up to the space over it (the label stops short of the palate and of the tip).
    tongue_cols = near(ct["tongue"].any(axis=1), plan, 4.0) | arch
    label_top = np.where(ct["tongue"].any(axis=1), grid.origin[1] + (shape[1] - np.argmax(ct["tongue"][:, ::-1, :], axis=1)) * sy, -1e9)
    floor = np.where(label_top > -1e8, label_top - 3.0, sheet - SPACE_MM - 11.0)
    grow = tongue_cols[:, None, :] & ~lips[:, None, :] & (y3 < sheet[:, None, :] - thick[:, None, :]) & (y3 >= floor[:, None, :])
    tongue = (ct["tongue"] | grow) & ~space & ~lower & ~upper & inside & ~gelatin
    tongue = ndimage.binary_opening(ndimage.binary_closing(tongue, iterations=2), iterations=2)
    parts, count = ndimage.label(tongue)
    if count > 1:
        sizes = ndimage.sum(tongue, parts, range(1, count + 1))
        tongue = parts == 1 + int(np.argmax(sizes))

    voxel = float(np.prod(grid.spacing)) / 1000.0
    info = {"lip_line": lip_info, "upper_teeth_edge_y_mm": y_tip, "space_cm3": round(float(space.sum()) * voxel, 1),
            "tongue_cm3": round(float(tongue.sum()) * voxel, 1), "tongue_label_cm3": round(float(ct["tongue"].sum()) * voxel, 1),
            "teeth_upper_cm3": round(float(teeth_upper.sum()) * voxel, 1), "teeth_lower_cm3": round(float(teeth_lower.sum()) * voxel, 1)}
    log("mouth: " + json.dumps(info))
    m = Mouth(grid, face, w_of, sheet, domain, space, teeth_upper, teeth_lower, tongue, upper, lower, lips=lips, skin_front=skin_front, u_of_x=u_of_x,
              stomion_mm=s, depth=depth.astype(np.float32), tooth_fields={"upper teeth": field_upper, "lower teeth": field_lower}, ct=ct,
              rgba_grid=head_grid, rgba=rgba, info=info)
    # Behind the hard palate the tongue is not grown up to a roof (what lies on it there is the soft palate), and the
    # mouth's space ends: the throat takes over (throat.py).
    m.throat = throat.measure(body, m, log)
    m.drawn_lower, m.drawn_upper = drawn_bones(body, grid)
    return m


# ---- what is seen inside ---------------------------------------------------------------------------------------------
def _mesh(body: Body, grid: Grid, mask: np.ndarray, sigma_mm: float):
    """A mask's smoothed surface: vertices in glTF metres and in the body's millimetres, faces wound outward, normals."""
    got = surface(mask, tuple(grid.spacing), sigma_mm)
    if got is None or len(got[1]) < 8:
        return None
    v_mm = got[0] + grid.origin
    v, f = body.to_gltf(v_mm, got[1])
    return v, v_mm, f, normals_of(v, f)


def _zyx(n_gltf: np.ndarray) -> np.ndarray:
    """A glTF direction in the body's array order."""
    return np.stack([-n_gltf[:, 2], n_gltf[:, 1], n_gltf[:, 0]], axis=1)


def photo_tone(m: Mouth, v_mm: np.ndarray, n: np.ndarray, depths=(0.8, 1.6, 2.4)) -> np.ndarray:
    """How light the photographs are just behind a surface, against the middle of all of it (0.6..1.3 per vertex)."""
    total, weight = np.zeros(len(v_mm)), np.zeros(len(v_mm))
    grey = m.rgba[..., :3].astype(np.float32).mean(axis=-1)
    for depth in depths:
        q = v_mm + _zyx(n) * depth
        a = m.rgba_grid.sample(m.rgba[..., 3], q, order=0, cval=0)
        total += m.rgba_grid.sample(grey, q, order=1) * (a > 100)
        weight += a > 100
    light = total / np.maximum(weight, 1)
    known = weight > 0
    if known.sum() < 10:
        return np.ones(len(v_mm))
    return np.where(known, np.clip(light / np.median(light[known]), 0.6, 1.3), 1.0)


def turned(m: Mouth, v: np.ndarray, w: np.ndarray, amount: float = 1.0, pull: np.ndarray | None = None, lift: float | None = None) -> np.ndarray:
    """Vertices (glTF metres) as they lie with the jaw open by `amount` of its full turn: what Unity's shader does
    (LabLids.hlsl, LabJaw). `pull`: how far each goes with the lower lip, which is drawn down first; negative: with
    the upper lip, lifted by `lift` of its whole way (as far as the jaw is open, where not said)."""
    angle = np.radians(OPEN_DEGREES) * amount * np.asarray(w, np.float64)
    v = np.asarray(v, np.float64)
    if pull is not None and m.lip_down is not None:
        pull = np.asarray(pull, np.float64)
        v = v + m.lip_down * (np.clip(pull, 0.0, None) * (amount * LIP_PULL_MM * MM))[:, None]
        up = getattr(m, "lip_up", None)
        if up is not None:
            v = v + up * (np.clip(-pull, 0.0, None) * ((amount if lift is None else lift) * LIP_LIFT_MM * MM))[:, None]
    x = v - m.hinge
    c, sn = np.cos(angle)[:, None], np.sin(angle)[:, None]
    return x * c + np.cross(m.axis, x) * sn + m.axis * (x @ m.axis)[:, None] * (1.0 - c) + m.hinge


def with_the_tongue(m: Mouth, zyx_mm: np.ndarray, w: np.ndarray) -> np.ndarray:
    """The jaw weights of points of the tongue (or of the mouth's floor under it). The tongue hangs on the mandible
    and the hyoid, not on what lies round it: its front two thirds go with the jaw wholly, its root as the throat's
    tissue does (the weight given), with a smooth step between. With the throat drawn behind it, the root is held
    to a fifth of the turn at most: turned further it would go back into the throat's wall (a living jaw slides
    forward as it opens; this one only turns)."""
    zs = m.grid.axis(0)[m.tongue.any(axis=(1, 2))]
    if len(zs) == 0:
        return w
    t = np.clip(((zyx_mm[:, 0] - zs.min()) / max(1.0, zs.max() - zs.min()) - 0.6) / 0.35, 0.0, 1.0)
    step = 1.0 - t * t * (3.0 - 2.0 * t)
    if m.throat is not None:
        return np.maximum(np.minimum(w, 0.2 + 0.8 * step), step).astype(np.float32)
    return np.maximum(w, step).astype(np.float32)


def cheek_wall(body: Body, m: Mouth):
    """The mouth's side and back wall: the cheeks' inner sides and the throat, as one band from the mouth's one
    corner round its back to the other, from the cheek's upper fold to its lower. In the frozen mouth its middle is
    4 mm high (roof and floor lie together); that middle's upper edge goes with the roof and its lower with the
    floor, so it is drawn out evenly as the mouth opens (the scan's own side walls are scraps of every height,
    which stretch into rags). Returns vertices (glTF), their millimetres,
    faces (seen from inside), weights; or None."""
    from skimage import measure
    g = m.grid
    whole = np.pad((m.rim_only > 0.98).astype(np.float32), 1)
    loops = measure.find_contours(whole, 0.5)
    if not loops:
        return None
    loop = max(loops, key=len) - 1.0                                          # (row = z index, column = x index)
    z_mm = g.origin[0] + (loop[:, 0] + 0.5) * g.spacing[0]
    x_mm = g.origin[2] + (loop[:, 1] + 0.5) * g.spacing[2]
    # Every 2 mm along it, smoothed.
    step = np.hypot(np.diff(z_mm), np.diff(x_mm))
    along = np.concatenate([[0.0], np.cumsum(step)])
    at = np.arange(0.0, along[-1], 2.0)
    z_mm, x_mm = np.interp(at, along, z_mm), np.interp(at, along, x_mm)
    for _ in range(3):
        z_mm = (np.roll(z_mm, 1) + 2 * z_mm + np.roll(z_mm, -1)) / 4
        x_mm = (np.roll(x_mm, 1) + 2 * x_mm + np.roll(x_mm, -1)) / 4
    # Not across the mouth's opening: the part in front, between the lips, is left out.
    iz = np.clip(((z_mm - g.origin[0]) / g.spacing[0]).astype(int), 0, g.shape[0] - 1)
    ix = np.clip(((x_mm - g.origin[2]) / g.spacing[2]).astype(int), 0, g.shape[2] - 1)
    front = ndimage.binary_dilation(m.lips, iterations=3)[iz, ix] & (np.abs(m.u_of_x[ix]) < HALF_WIDTH - 9.0)      # (it reaches in behind the lips' ends: their own inner sides thin out there)
    if front.all() or not front.any():
        return None
    # Nor behind the hard palate: there the throat's own lining is the wall (throat.lining: the folds from the cheeks
    # to the throat's side walls are the walls the tongue's sides lay against).
    behind = z_mm > (m.throat.z_end + 1.5) if m.throat is not None else np.zeros(len(z_mm), bool)
    first = int(np.nonzero(front & ~np.roll(front, -1))[0][0]) + 1            # the run that is not in front, taken once round
    order = (first + np.arange(len(front))) % len(front)
    order = order[~front[order] & ~behind[order]]
    z_mm, x_mm = z_mm[order], x_mm[order]
    y0 = np.zeros(len(z_mm))
    height, _ = sheet_at(m, np.stack([z_mm, y0, x_mm], axis=1))
    height = ndimage.gaussian_filter1d(height, 2.0, mode="nearest")
    # Four rows: the upper fold of the cheek, the slit's upper and lower edge, the lower fold. The two outer rows
    # stand in the cheek beside the gums (what lies behind them, fat and muscle, is not to be seen from inside the
    # mouth); they are drawn in where the skin is near (at the mouth's corners).
    offsets = np.array([11.0, 0.6, -SPACE_MM - 0.6, -SPACE_MM - 11.0])
    reach = np.ones(len(z_mm))
    for k in range(len(z_mm)):
        for share in (1.0, 0.6, 0.3, 0.0):
            ends = np.array([[z_mm[k], height[k] + offsets[0] * share, x_mm[k]], [z_mm[k], height[k] + (offsets[3] + SPACE_MM) * share - SPACE_MM, x_mm[k]]])
            if g.sample(m.depth, ends).min() >= 3.0 or share == 0.0:
                reach[k] = share
                break
    reach = ndimage.minimum_filter1d(reach, 3, mode="nearest")
    rows = [np.stack([z_mm, height + 0.6 + (offsets[0] - 0.6) * reach, x_mm], axis=1), np.stack([z_mm, height + offsets[1], x_mm], axis=1),
            np.stack([z_mm, height + offsets[2], x_mm], axis=1), np.stack([z_mm, height + offsets[2] + (offsets[3] - offsets[2]) * reach, x_mm], axis=1)]
    v_mm = np.concatenate(rows)
    k = len(z_mm)
    v = to_gltf(body, v_mm)
    faces = []
    gap = np.hypot(np.diff(z_mm), np.diff(x_mm))
    for i in range(k - 1):
        if gap[i] > 6.0:                                                      # the band is not carried across where it was left out
            continue
        for r in range(3):
            a, b = r * k + i, (r + 1) * k + i
            faces += [(a, a + 1, b + 1), (a, b + 1, b)]
    f = np.array(faces, np.int64)
    # Seen from inside: the faces look at the mouth's middle.
    centre = v.mean(axis=0)
    normal = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    away = np.einsum("ij,ij->i", normal, centre - v[f].mean(axis=1)) < 0
    f[away] = f[away][:, ::-1]
    w = weight(body, m, v, np.concatenate([np.ones(2 * k), -np.ones(2 * k)]))
    return v, v_mm, f, w


def lower_arch(m: Mouth, behind_mm: float = 26.0):
    """Seen from above: the inside of the lower row of teeth and what lies behind it for `behind_mm` (bool, (nz, nx)),
    and each column's level of the lower row's biting edge (mm; its own tooth's, or the nearest tooth's)."""
    from skimage.morphology import convex_hull_image
    g = m.grid
    row = m.teeth_lower
    has = row.any(axis=1)
    hull = convex_hull_image(has)
    behind = hull.copy()
    for step in range(1, int(behind_mm / g.spacing[0])):                     # and on behind the last teeth, over the tongue's root
        behind[step:] |= hull[:-step]
    edge = g.origin[1] + (biting_edge(row, g.spacing, False)[2] + 1.0) * g.spacing[1]
    return behind, has, edge


def mouth_floor(body: Body, m: Mouth, step: int = 2):
    """The floor of the mouth: a surface within the lower row of teeth and behind it, a little under the gum's edge,
    out of which the tongue stands. Returns vertices (glTF), their millimetres, faces (looking up), jaw weights; or None."""
    if not m.teeth_lower.any():
        return None
    g = m.grid
    from skimage.morphology import convex_hull_image
    inside, has, edge = lower_arch(m)
    region = ndimage.binary_dilation(inside, iterations=int(round(2.5 / g.spacing[0])))
    level = ndimage.gaussian_filter(edge - (GUM_FROM_MM + 3.0), 5.0)
    # Within the lower jaw AT THE FLOOR'S OWN LEVEL, and 2 mm inside its outer face. The front teeth lean forward: their
    # crowns stand further forward than the gum over their roots, and a floor drawn as far as the crowns reach came out
    # through the gum's front face as a ledge all along the lower front teeth.
    jaw = (m.lower & (np.abs(g.axis(1)[None, :, None] - level[:, None, :]) < 2.0)).any(axis=1)
    if jaw.any():
        region &= ndimage.binary_erosion(convex_hull_image(jaw), iterations=int(round(2.0 / g.spacing[0])))
    iz, ix = np.nonzero(region[::step, ::step])
    number = np.full(region[::step, ::step].shape, -1, np.int64)
    number[iz, ix] = np.arange(len(iz))
    z_mm, x_mm = g.axis(0)[::step][iz], g.axis(2)[::step][ix]
    v_mm = np.stack([z_mm, level[::step, ::step][iz, ix], x_mm], axis=1)
    a, b, c, d = number[:-1, :-1], number[1:, :-1], number[1:, 1:], number[:-1, 1:]
    whole = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
    quads = np.stack([a[whole], b[whole], c[whole], d[whole]], axis=1)
    f = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    v = to_gltf(body, v_mm)
    normal = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    f[normal[:, 1] < 0] = f[normal[:, 1] < 0][:, ::-1]
    w = with_the_tongue(m, v_mm, weight(body, m, v, np.full(len(v), -1.0)))
    return v, v_mm, f, w


def lining(body: Body, m: Mouth, log=print) -> Structure | None:
    """The mouth's lining: the roof and the floor of the space and what stands wholly on one of them (the gums, the
    lips' inner sides), open where a tooth is the wall and at the lips; and the cheeks' and the throat's wall between
    them (cheek_wall). Over the tongue it is sunk a millimetre and a half INTO the tongue: the tongue's own mesh is
    what is seen there, and the lining under it closes whatever lies beside and behind the tongue (left open there,
    it let the fat and muscle beside the tongue be seen)."""
    got = _mesh(body, m.grid, m.space, 0.7)
    if got is None:
        return None
    v, v_mm, f, n = got
    g = m.grid
    beyond = v_mm + _zyx(n) * 1.2                                            # in the wall
    teeth = m.teeth_upper | m.teeth_lower
    to_tooth = ndimage.distance_transform_edt(~teeth, sampling=g.spacing).astype(np.float32)
    tooth_wall = g.sample(to_tooth, beyond) < 0.9
    tongue_wall = g.sample(m.tongue.astype(np.float32), v_mm + _zyx(n) * 1.6) > 0.5      # here the lining is the tongue's own surface
    at_skin = g.sample(m.depth, v_mm) < 1.8
    gone = tooth_wall | at_skin
    # The roof has the space under it, the floor over it (a normal does not tell: the roof has bumps that look
    # down). What stands beside the space is a wall: kept where it is wholly above the frozen mouth's slit (the
    # upper gum, the upper lip's inner side) or wholly below it; a wall across the slit itself joins roof and floor
    # and would hang in the open mouth as a rag.
    height, _ = sheet_at(m, v_mm)
    room = m.space.astype(np.float32)
    step = np.array([0.0, 1.3, 0.0])
    over, under = g.sample(room, v_mm + step) > 0.5, g.sample(room, v_mm - step) > 0.5
    roof, floor = under & ~over, over & ~under
    wall = ~roof & ~floor
    in_slit = wall & (v_mm[:, 1] < height + 0.6) & (v_mm[:, 1] > height - SPACE_MM - 0.6)
    # (Where the space is thinner than the test's step, neither holds: there the wall's own facing tells, up or down.)
    faces_up, faces_down = wall & (n[:, 1] > 0.5), wall & (n[:, 1] < -0.5)
    roof, floor = roof | faces_up, floor | faces_down
    # (And what has the upper jaw's gum and bone behind it is the roof however steep it stands: the slope from the
    # palate down to the upper teeth's necks. Taken for a wall at the slit, it was left out, and a dark band ran
    # along the inner side of the upper teeth.)
    roof |= (g.sample((m.upper & ~m.teeth_upper).astype(np.float32), beyond) > 0.5) & ~floor
    wall = ~roof & ~floor
    in_slit = wall & (v_mm[:, 1] < height + 0.6) & (v_mm[:, 1] > height - SPACE_MM - 0.6)
    if m.lip_whole_up is not None:
        # Between the upper lip and the upper teeth and gum nothing of the lining is kept: the lip's own inner side
        # is the skin's (mouth.cut), which is lifted with the lip, and the gum's face is the gum's own mesh. The
        # lining there stayed behind as a rag before the upper teeth, or went part of the lip's way over the gum.
        # (At every height: up in the fold where the lip's lining turns onto the gum, what was kept of it lay on the
        # gum's face as rags.)
        field = m.vestibule_up if m.vestibule_up is not None else m.lip_whole_up
        gone |= np.maximum(g.sample(field, v_mm + _zyx(n) * 1.0, order=1, cval=0.0), g.sample(field, v_mm - _zyx(n) * 0.7, order=1, cval=0.0)) > 0.08
    if m.teeth_upper.any():
        # Nor in the upper row of teeth itself at its crowns' heights (between two teeth, where the gum rises: what was
        # kept of the lining there stood out between the teeth as small rags).
        has, to_row, edge = biting_edge(m.teeth_upper, g.spacing, True)
        at = np.stack([(v_mm[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (v_mm[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
        crown_top = g.origin[1] + (ndimage.map_coordinates(edge, at, order=1, mode="nearest") + 0.5) * g.spacing[1] + GUM_FROM_MM + 1.5
        gone |= (ndimage.map_coordinates(to_row.astype(np.float32), at, order=1, mode="nearest") < 1.5) & (v_mm[:, 1] < crown_top)
    side = np.where(roof, 1.0, np.where(floor, -1.0, np.where(v_mm[:, 1] > height - SPACE_MM / 2, 1.0, -1.0)))
    keep = ~(gone[f].sum(axis=1) >= 2) & ~(in_slit[f].sum(axis=1) >= 2)
    # Of the space's wall only the ROOF is kept (the palate, the upper gum's inner side, the upper lip's): it does not
    # move. Its floor lay on the tongue, the lower gum and the lower lip, which each have a surface of their own now
    # (tongue, gums, the lips' inner sides in the skin, mouth_floor); kept, it tore where they part.
    keep &= (side[f] > 0).all(axis=1)
    opened = len(f) - int(keep.sum())
    f = f[keep][:, ::-1]                                                      # seen from inside the mouth
    w = weight(body, m, v, side) if m.weight_grid is not None else np.zeros(len(v), np.float32)
    pull = lip_pull(body, m, v, side) if m.lip is not None else np.zeros(len(v), np.float32)
    if w.any():
        on_tongue = tongue_wall & (side < 0)
        w[on_tongue] = with_the_tongue(m, v_mm[on_tongue], w[on_tongue])        # the lining on the tongue goes as the tongue goes
        # Whatever is still drawn out when the jaw is open and the lip drawn down (to more than two and a half times
        # its longest edge) goes too: between the lip's lining, which comes down, and the gum's, which stays.
        there = turned(m, v, w, 1.0, pull)

        def longest(p):
            return np.max([np.linalg.norm(p[f[:, a]] - p[f[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)

        drawn = longest(there) > 2.5 * np.maximum(longest(np.asarray(v, np.float64)), 2e-4)
        f = f[~drawn]
        log(f"mouth: lining: {int(drawn.sum())} triangles that would be drawn out across the open mouth taken out")
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int64)
    remap[used] = np.arange(len(used))
    # (n looks out of the space, into the wall.) The lining stands a hair into the space, clear of the flesh behind
    # it; on the tongue it is sunk into the tongue instead, so the tongue's own mesh is what is seen.
    shift = np.where(tongue_wall & (side < 0), 0.0016, -0.0003)
    v, v_mm, n, w, pull, f = (v + n * shift[:, None])[used], v_mm[used], n[used], w[used], pull[used], remap[f]
    # Its colour: gum by the teeth, the palate paler, the rest the cheeks' and the floor's red; lighter and darker as the photographs are.
    by_tooth = np.clip(1.0 - g.sample(to_tooth, v_mm) / 6.0, 0.0, 1.0)
    above = g.sample(m.upper.astype(np.float32), v_mm + _zyx(n) * 1.5) > 0.5
    if m.teeth_upper.any():
        # The palate's ridges: a few cross ridges behind the upper front teeth, each side's running back a little as it
        # goes outwards. The scan's voxels do not hold them; they are drawn in, half a millimetre high.
        front = float(g.axis(0)[np.argmax(m.teeth_upper.any(axis=(1, 2)))])
        behind = v_mm[:, 0] - front
        across = np.abs(v_mm[:, 2] - m.stomion_mm[2])
        window = np.clip((behind - 7.0) / 3.0, 0.0, 1.0) * np.clip((26.0 - behind) / 5.0, 0.0, 1.0) * np.clip((across - 1.5) / 2.0, 0.0, 1.0) * np.clip((15.0 - across) / 4.0, 0.0, 1.0)
        ridge = 0.0005 * np.clip(np.sin(2.0 * np.pi * (behind - 0.3 * across) / 3.9), 0.0, 1.0) ** 1.5 * window * (above & (n[:, 1] > 0.6))
        v = v - n * ridge[:, None]                                          # (n looks up into the palate: the ridges stand down into the mouth)
    colour = np.tile(np.array(MUCOSA, np.float64), (len(v), 1))
    colour[above] = PALATE
    colour += (np.array(GUM, np.float64) - colour) * by_tooth[:, None]
    colour *= photo_tone(m, v_mm, n)[:, None]
    front = float(np.nanmin(m.skin_front))

    def light(mm):                                                           # the light fails towards the throat
        return 1.0 - DIM_BACK * np.clip((mm[:, 0] - front) / 80.0, 0.0, 1.0)

    bake = np.tile(np.array([255, 255, 82, 225], np.uint8), (len(v), 1))
    bake[:, 0] = np.round(255 * light(v_mm))
    band = cheek_wall(body, m) if w.any() else None
    if band is not None:
        bv, bv_mm, bf, bw = band
        shade = light(bv_mm)
        band_colour = np.array(MUCOSA, np.float64)[None, :] * (0.55 + 0.45 * shade)[:, None]
        band_bake = np.tile(np.array([255, 255, 82, 215], np.uint8), (len(bv), 1))
        band_bake[:, 0] = np.round(255 * shade * 0.85)
        f = np.concatenate([f, bf + len(v)])
        v, w, pull = np.concatenate([v, bv]), np.concatenate([w, bw]), np.concatenate([pull, np.zeros(len(bv), np.float32)])
        colour, bake = np.concatenate([colour, band_colour]), np.concatenate([bake, band_bake])
    under = mouth_floor(body, m) if w.any() else None
    if under is not None:
        uv, uv_mm, uf, uw = under
        shade = light(uv_mm) * 0.75
        f = np.concatenate([f, uf + len(v)])
        v, w, pull = np.concatenate([v, uv]), np.concatenate([w, uw]), np.concatenate([pull, np.zeros(len(uv), np.float32)])
        colour = np.concatenate([colour, np.array(MUCOSA, np.float64)[None, :] * (0.5 + 0.5 * shade)[:, None]])
        floor_bake = np.tile(np.array([255, 255, 82, 220], np.uint8), (len(uv), 1))
        floor_bake[:, 0] = np.round(255 * shade * 0.8)
        bake = np.concatenate([bake, floor_bake])
    log(f"mouth: lining {len(f)} triangles ({opened} left open at the teeth, the lips and across the slit)"
        + ("" if band is None else f"; the cheeks' and throat's wall {len(band[2])} triangles"))
    out = Structure("lining of the mouth", "skin", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in MUCOSA), bake=bake,
                    albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8), info={"class": "skin", "source": "the mouth's space (mouth.py)"})
    if w.any():
        out.data3 = np.stack([w, pull], axis=1).astype(np.float32)
    return out


DIM_BACK = 0.35                 # how much darker the mouth's surfaces are baked 8 cm behind the lips (the light fails towards the throat, but it is there to be looked into)
BAG_MM = 2.5                    # the bag lies this far outside the mouth's and the throat's lining
BAG_SHADE = 0.9                 # and is this much darker than the lining (little: where the lining has a gap, the bag is what is seen for it)


def bag(body: Body, m: Mouth, log=print) -> Structure | None:
    """The mouth's bag: one closed wall round the whole of the mouth and the throat, BAG_MM outside everything that
    lines them, seen from inside only. The lining, the gums, the teeth and the throat are many meshes that part and
    are drawn out as the mouth opens; wherever a gap is left between them (behind the last back teeth, between two
    teeth, at a fold's foot) the eye would go through to the layers behind or to nothing. With the bag it meets a
    shaded wall of the lining's colour, as it does in a mouth. It goes as the flesh it lies in goes: its upper half
    stays with the skull, its lower goes with the jaw, between them (the cheeks' inner sides) it is drawn out; round
    the throat it stays. It is open at the lips."""
    g = m.grid
    t = m.throat
    # (The teeth are taken into it: the bag goes round the rows of teeth on the cheeks' side, not through the crowns,
    # where its upper and lower halves were joined tooth to tooth and hung between the rows as the mouth opened.)
    room = m.space | m.tongue | m.teeth_upper | m.teeth_lower
    # (Each row of teeth with its gaps closed along the row, up to 14 mm: where a tooth stands alone the bag went in
    # round it on three sides, and that collar, going less far than the tooth, hung before it in the opened mouth.)
    flat = (g.spacing[0], 1e3, g.spacing[2])                                 # distances within a level only
    for row in (m.teeth_upper, m.teeth_lower):
        if row.any():
            room = room | ~near(~near(row, flat, 7.0), flat, 7.0)
    if t is not None:
        room = room | t.hollow | t.uvula | t.tonsils
    xs = g.axis(2)
    solid = near(room, g.spacing, BAG_MM) & (m.depth > 3.0)
    got = _mesh(body, g, solid, 1.2)
    if got is None:
        return None
    v, v_mm, f, n = got
    # Open at the lips: nothing of it between them, nor within the lips' own thickness behind their skin.
    at = np.stack([(v_mm[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (v_mm[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    wide = ndimage.binary_dilation(m.lips, iterations=int(round(4.0 / g.spacing[0])))
    in_lips = ndimage.map_coordinates(wide.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    front = v_mm[:, 0] - np.interp(v_mm[:, 2], xs, m.skin_front)
    gone = (in_lips & (front < 15.0)) | (g.sample(m.depth, v_mm) < 4.0)
    f = f[~gone[f].any(axis=1)][:, ::-1]                                     # seen from inside
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int64)
    remap[used] = np.arange(len(used))
    v, v_mm, f = v[used], v_mm[used], remap[f]
    # Its weights: by height alone. It is the upper jaw's above the level where the jaws meet (the sheet), the
    # lower jaw's 11 mm under it, and drawn out evenly between (the cheeks' inner sides, the folds from the cheeks to
    # the throat, a gap where teeth are missing); less and less of that towards the throat, and nothing near what is
    # held with the skull (the soft palate, the throat's wall). It goes round the rows of teeth on the cheeks' side,
    # so a part of it that goes less far than a tooth does not come before the tooth. (Weights read from the teeth
    # and gums it lies against stepped where a tooth stands alone, and drew single triangles out into spikes across
    # the opened mouth.) What is still drawn out to more than four times its length is taken out.
    w = np.zeros(len(v), np.float32)
    if m.weight_grid is not None:
        height, _ = sheet_at(m, v_mm)
        share = np.clip((height + 3.0 - v_mm[:, 1]) / 14.0, 0.0, 1.0)
        w = share * share * (3.0 - 2.0 * share)
        if t is not None:
            back = np.clip((v_mm[:, 0] - (t.z_end + 2.0)) / max(4.0, t.sink_from[1] - 8.0 - t.z_end), 0.0, 1.0)
            off = np.clip((g.sample(ndimage.distance_transform_edt(~t.held, sampling=g.spacing).astype(np.float32), v_mm) - 1.5) / 4.5, 0.0, 1.0)
            w = w * (1.0 - back * back * (3.0 - 2.0 * back)) * (off * off * (3.0 - 2.0 * off))
        w = w.astype(np.float32)
        there = turned(m, v, w, 1.0)

        def longest(q):
            return np.max([np.linalg.norm(q[f[:, i]] - q[f[:, j]], axis=1) for i, j in ((0, 1), (1, 2), (2, 0))], axis=0)

        after = longest(there)
        before = np.maximum(longest(np.asarray(v, np.float64)), 2e-4)
        threads = (after > 4.0 * before) & (after > 0.004)
        # (and what is drawn out into a sliver: a wall drawn out evenly keeps a tenth of its longest edge's square as
        # its area even at four times its length; a thread across the mouth has next to none)
        area = 0.5 * np.linalg.norm(np.cross(there[f[:, 1]] - there[f[:, 0]], there[f[:, 2]] - there[f[:, 0]]), axis=1)
        threads |= (after > 2.0 * before) & (after > 0.003) & (area < 0.05 * after * after)
        f = f[~threads]
        log(f"mouth: bag: {int(threads.sum())} triangles that would be drawn out into threads taken out")
    front_mm = float(np.nanmin(m.skin_front))
    light = 1.0 - DIM_BACK * np.clip((v_mm[:, 0] - front_mm) / 80.0, 0.0, 1.0)
    colour = np.tile(np.array(MUCOSA, np.float64) * BAG_SHADE, (len(v), 1))
    bake = np.tile(np.array([230, 255, 82, 215], np.uint8), (len(v), 1))
    bake[:, 0] = np.round(230 * light)
    log(f"mouth: bag {len(f)} triangles")
    out = Structure("wall of the mouth", "skin", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 * BAG_SHADE for c in MUCOSA), bake=bake,
                    albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8),
                    info={"class": "skin", "generated": "a closed dark wall behind the mouth's and the throat's lining, so that no gap between their parts shows what lies outside",
                          "source": "the mouth's space, the tongue's place and the throat, 2.5 mm outwards (mouth.py)"})
    if m.weight_grid is not None:
        out.data3 = np.stack([w, np.zeros(len(v), np.float32)], axis=1).astype(np.float32)
    return out


GUM_CLEAR_MM = 3.0              # a drawn muscle keeps this far off a jaw's tooth-bearing ridge, where the gum covers it


def gum_ridges(m: Mouth) -> np.ndarray:
    """Each jaw's tooth-bearing ridge where the gum covers it and the lips uncover it (bool, the mouth's grid): its
    teeth, its bone as the CT has it and as it is drawn, from the row's biting edge to where the gum is drawn to,
    within 9 mm of the row, behind the lips (the mouth's width and 3 mm: the cheeks' muscle does lie on the ridge
    beside the back teeth, and is not uncovered)."""
    g = m.grid
    out = np.zeros(g.shape, bool)
    for upper, row, hard, drawn in ((True, m.teeth_upper, m.upper, m.drawn_upper), (False, m.teeth_lower, m.lower, m.drawn_lower)):
        if not row.any():
            continue
        _, distance, edge = biting_edge(row, g.spacing, upper)
        rows = np.arange(row.shape[1])[None, :, None]
        away = ((rows - edge[:, None, :]) if upper else (edge[:, None, :] - rows)) * g.spacing[1]        # mm from the biting edge towards the roots
        solid = hard | row
        if drawn is not None and drawn.any():
            solid = solid | near(drawn, g.spacing, 1.8)
        out |= solid & (away >= 0.0) & (away <= GUM_FROM_MM + GUM_DEEP_MM) & (distance[:, None, :] <= 9.0)
    if m.u_of_x is not None:
        out &= (np.abs(m.u_of_x) < HALF_WIDTH + 3.0)[None, None, :]
    return out


def clear_of_the_gums(body: Body, m: Mouth, structures: list[Structure], log=print) -> int:
    """Moves drawn structures off the gums: every vertex nearer a gum-covered ridge (gum_ridges) than GUM_CLEAR_MM
    is moved straight out to that distance, into the lip before it. A muscle does not arise from the ridge the gum
    covers; one drawn there (the chin's, seated on the bone under the lower front teeth) stood between the gum and
    the lip's inner side, and before the gum's face when the lip was drawn down. (Moved, not cut: cut, the chin's
    muscles ended in rags on the muscles' own layer.) Returns how many structures were touched."""
    ridges = gum_ridges(m)
    if not ridges.any():
        return 0
    touched = throat._move_out(structures, body, m, ridges, GUM_CLEAR_MM, lambda s: True)
    if touched:
        log("mouth: moved off the gums (vertices): " + "; ".join(touched))
    return len(touched)


def biting_edge(row: np.ndarray, spacing, upper: bool):
    """Seen along the teeth: which columns hold a tooth of the row, how far every column lies from one (mm), and the
    level (a row index, float) of the row's biting edge there. The edge is each tooth's tip, carried over the tooth's
    whole footprint and 3 mm round it (a tooth that leans has its root under other columns than its tip), smoothed."""
    has = row.any(axis=1)
    index = (np.argmax(row, axis=1) if upper else row.shape[1] - 1 - np.argmax(row[:, ::-1, :], axis=1)).astype(np.float32)
    size = (int(round(7.0 / spacing[0])) | 1, int(round(7.0 / spacing[2])) | 1)
    tip = ndimage.minimum_filter(np.where(has, index, np.inf), size=size) if upper else ndimage.maximum_filter(np.where(has, index, -np.inf), size=size)
    known = np.isfinite(tip)
    distance = ndimage.distance_transform_edt(~has, sampling=(spacing[0], spacing[2]))
    nearest = ndimage.distance_transform_edt(~known, return_distances=False, return_indices=True)
    tip = ndimage.gaussian_filter(tip[tuple(nearest)], 3.0 / spacing[0])
    return has, distance, tip


def gums(body: Body, m: Mouth, log=print) -> list[Structure]:
    """The gums: the soft cover of each jaw's tooth-bearing ridge, from the edge it has on the teeth (GUM_FROM_MM
    from the row's biting edge) towards the roots' tips, round the teeth and over the bone within 4 mm of the row.
    Without them, a lip drawn off the teeth shows the roots standing in bare bone. The lower gum goes with the jaw."""
    g = m.grid
    sz, sy, sx = g.spacing
    out = []
    for upper, row, hard in ((True, m.teeth_upper, m.upper), (False, m.teeth_lower, m.lower)):
        if not row.any():
            continue
        has, distance, edge = biting_edge(row, g.spacing, upper)
        rows = np.arange(row.shape[1])[None, :, None]
        away = ((rows - edge[:, None, :]) if upper else (edge[:, None, :] - rows)) * sy       # mm from the biting edge towards the roots
        start = GUM_FROM_MM + 0.7 * np.clip(1.0 - np.abs(m.u_of_x) / 14.0, 0.0, 1.0)[None, None, :]
        # (Within 4 mm of the row on its inner side, 7 mm on the lips' and cheeks' side: there the bone under the roots
        # swells forward, and below a gum cut off at 4 mm it showed white between the gum and the lip's inner side.)
        from skimage.morphology import convex_hull_image
        reach = np.where(convex_hull_image(has), 4.0, 7.0)
        # The gum covers the jaw's bone AS IT IS DRAWN too (BoneHub's, a millimetre or two off the CT's in places: it
        # came through the gum's face as white wedges), by 1.8 mm.
        drawn = m.drawn_upper if upper else m.drawn_lower
        if drawn is not None and drawn.any():
            hard = hard | near(drawn, g.spacing, 1.8)
        # (The upper gum is drawn 8 mm further towards the nose: with the upper lip lifted, one looks up between the lip
        # and the gum, and past a gum that ended at the roots' tips saw the bare bone.)
        deep = GUM_DEEP_MM + (8.0 if upper else 0.0)
        solid = (hard | near(row, g.spacing, 1.8)) & (distance[:, None, :] <= reach[:, None, :]) & (away >= start) & (away <= start + deep) & (m.depth > 1.0)
        # Between two teeth the gum rises to where their crowns touch (its points between the teeth): the gaps between
        # neighbouring teeth, up to 3 mm wide, are closed for 3.5 mm above the gum's edge.
        span = 2 * int(round(1.6 / sz)) + 1
        between = ndimage.binary_closing(row, structure=np.ones((span, 1, span), bool)) & ~row
        solid |= between & (away >= start - 3.5) & (away <= start + 1.0) & (m.depth > 1.0)
        got = _mesh(body, g, solid, 0.8)
        if got is None:
            continue
        v, v_mm, f, n = got
        # Its cut ends (towards the roots' tips, and 4 mm from the row) lie inside the flesh and are left open.
        deep = g.sample(away.astype(np.float32), v_mm) > (g.sample(np.broadcast_to(start, away.shape).astype(np.float32), v_mm) + deep - 1.2)
        aside = ndimage.map_coordinates((distance - reach).astype(np.float32), np.stack([(v_mm[:, 0] - g.origin[0]) / sz - 0.5, (v_mm[:, 2] - g.origin[2]) / sx - 0.5]), order=1, mode="nearest") > -0.6
        f = f[~(deep | aside)[f].all(axis=1)]
        used = np.unique(f)
        remap = np.full(len(v), -1, np.int64)
        remap[used] = np.arange(len(used))
        v, v_mm, n, f = (v + n * 0.00035)[used], v_mm[used], n[used], remap[f]      # a hair proud of the lining, which lies on the same flesh
        depth = np.clip((g.sample(away.astype(np.float32), v_mm) - GUM_FROM_MM - 4.0) / 7.0, 0.0, 1.0)
        colour = np.array(GUM, np.float64)[None, :] + (np.array(MUCOSA, np.float64) - np.array(GUM, np.float64))[None, :] * depth[:, None]
        bake = np.tile(np.array([240, 255, 82, 215], np.uint8), (len(v), 1))
        piece = Structure("upper gum" if upper else "lower gum", "skin", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in GUM), bake=bake,
                          albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8), info={"class": "skin", "source": "the tooth-bearing ridge's soft cover, from the CT's bone and teeth (mouth.py)"})
        if m.weight_grid is not None:                                       # the lower gum goes with the jaw wholly, the upper not at all
            piece.data3 = np.stack([np.full(len(v), 0.0 if upper else 1.0, np.float32), np.zeros(len(v), np.float32)], axis=1)
        out.append(piece)
    log("mouth: gums: " + ", ".join(f"{s.name} {s.triangles} triangles" for s in out))
    return out


def teeth(body: Body, m: Mouth, log=print) -> list[Structure]:
    out = []
    for name, field in m.tooth_fields.items():
        # The CT's own values contoured (a hard mask would show its voxels as steps), a little smoothed.
        smooth = ndimage.gaussian_filter(np.clip(field, -200.0, 3000.0), [0.35 / s for s in m.grid.spacing])
        if smooth.max() <= TOOTH_HU:
            continue
        v_mm, f = level_set(smooth, TOOTH_HU, tuple(m.grid.spacing))
        v, f = body.to_gltf(v_mm + m.grid.origin, f)
        v, f = decimate(v, f, 70000)
        # What makes a row of teeth readable: the dark between them and at the gum. How much tooth and bone lies just
        # outside each vertex darkens it; the roots (more than 9 mm from the row's edge) are dentine's yellow.
        n = normals_of(v, f)
        at = to_mm(body, v)
        # (Its own row and its own jaw only: with the other row counted too, the faces the back teeth bite with were
        # baked black, and stayed black in the opened mouth.)
        own = (m.teeth_upper | m.ct["skull"]) if name.startswith("upper") else (m.teeth_lower | m.ct["mandible"])
        hard = ndimage.gaussian_filter(own.astype(np.float32), [1.3 / sp for sp in m.grid.spacing])
        crowded = m.grid.sample(hard, at + _zyx(n) * 1.4)
        ys = at[:, 1]
        edge = np.percentile(ys, 2) if name.startswith("upper") else np.percentile(ys, 98)
        root = np.clip((np.abs(ys - edge) - 9.5) / 3.0, 0.0, 1.0)
        albedo = np.array(TOOTH, np.float64)[None, :] + (np.array(ROOT, np.float64) - np.array(TOOTH, np.float64))[None, :] * root[:, None]
        bake = np.tile(np.array([255, 255, 82, 185], np.uint8), (len(v), 1))
        bake[:, 0] = np.round(255 * np.clip(1.2 - 1.7 * crowded, 0.3, 1.0))
        # (the lower row goes with the jaw wholly: its weights are set here, so they stay with its teeth when the row is split into them)
        whole = np.stack([np.ones(len(v), np.float32), np.zeros(len(v), np.float32)], axis=1) if name.startswith("lower") and m.weight_grid is not None else None
        out.append(Structure(name, "skeleton", v, f, tuple(c / 255 for c in TOOTH), bake=bake, albedo=np.round(albedo).astype(np.uint8), data3=whole,
                             info={"class": "bone", "source": "the frozen CT's bright voxels in TotalSegmentator's teeth labels"}))
    return out


def without_crowns(body: Body, m: Mouth, bone: Structure, upper: bool, log=print) -> Structure:
    """A jaw bone without the teeth's crowns. BoneHub's skull and mandible have the teeth in them, as one blurred
    row that does not lie quite where his teeth are; the mouth has every tooth by itself. Where the bone's surface
    is a crown's (within a crown's height of the tooth row's edge, in the row's columns or within 2 mm of a tooth;
    the roots' bone stays) it is pressed flat onto the level a crown's height from the row's edge: the ridge the
    teeth stand in, closed, with the teeth's own meshes coming out of it. (Cut out instead, the crowns left the bone
    open along a ragged edge, with single triangles standing over it.)"""
    g = m.grid
    teeth_mask = m.teeth_upper if upper else m.teeth_lower
    if not teeth_mask.any():
        return bone
    v_mm = to_mm(body, bone.v)
    index = g.index(v_mm)
    inside = ((index > 0) & (index < np.array(g.shape)[:, None] - 1)).all(axis=0)
    if not inside.any():
        return bone
    to_tooth = ndimage.distance_transform_edt(~teeth_mask, sampling=g.spacing).astype(np.float32)
    has = teeth_mask.any(axis=1)
    ys = g.axis(1)
    if upper:
        edge = np.where(has, ys[np.argmax(teeth_mask, axis=1)], 0.0)                              # each column's lowest tooth voxel
    else:
        edge = np.where(has, ys[g.shape[1] - 1 - np.argmax(teeth_mask[:, ::-1, :], axis=1)], 0.0)  # its highest
    # (each tooth's tip carried over its footprint and smoothed: a level ridge along the row, not a step at every tooth)
    size = (int(round(7.0 / g.spacing[0])) | 1, int(round(7.0 / g.spacing[2])) | 1)
    edge = ndimage.minimum_filter(np.where(has, edge, np.inf), size=size) if upper else ndimage.maximum_filter(np.where(has, edge, -np.inf), size=size)
    edge = ndimage.gaussian_filter(nearest_fill(np.where(np.isfinite(edge), edge, 0.0), np.isfinite(edge)), 3.0 / g.spacing[0])
    q = v_mm[inside]
    at = np.stack([(q[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (q[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    row_edge = ndimage.map_coordinates(edge, at, order=1, mode="nearest")
    row = ndimage.map_coordinates(near(has, (g.spacing[0], g.spacing[2]), 6.0).astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    level = row_edge + CROWN_MM if upper else row_edge - CROWN_MM
    crown = ((g.sample(to_tooth, q) < 2.0) | row) & ((q[:, 1] < level) if upper else (q[:, 1] > level))
    if crown.any():
        q[crown, 1] = level[crown]
        # And drawn in under his own teeth where they pass that level (their necks): BoneHub's crowns stand a millimetre
        # or two further forward than the gum does, and pressed flat only they lay as a ledge before the gum's edge.
        level_map = edge + CROWN_MM if upper else edge - CROWN_MM              # (nz, nx) mm: the level, column by column
        row_map = np.clip(np.round((level_map - g.origin[1]) / g.spacing[1] - 0.5).astype(int), 1, g.shape[1] - 2)
        neck = np.zeros(has.shape, bool)
        for dy in (-1, 0, 1):
            neck |= np.take_along_axis(teeth_mask, (row_map + dy)[:, None, :], axis=1)[:, 0, :]
        neck = ndimage.binary_erosion(neck, iterations=1)
        if neck.any():
            away, nearest = ndimage.distance_transform_edt(~neck, sampling=(g.spacing[0], g.spacing[2]), return_indices=True)
            iz = np.clip(np.round(at[0]).astype(int), 0, g.shape[0] - 1)
            ix = np.clip(np.round(at[1]).astype(int), 0, g.shape[2] - 1)
            pull = crown & (away[iz, ix] > 0.0) & (away[iz, ix] < 6.0)
            q[pull, 0] = g.axis(0)[nearest[0][iz[pull], ix[pull]]]
            q[pull, 2] = g.axis(2)[nearest[1][iz[pull], ix[pull]]]
            # (where none of his teeth is near, 3 mm further towards the roots: under the gum, whose edge lies at 7 mm)
            lone = crown & (away[iz, ix] >= 6.0)
            q[lone, 1] += 3.0 if upper else -3.0
        v_mm[inside] = q
        bone.v = to_gltf(body, v_mm).astype(np.float32)
        log(f"mouth: {bone.name}: {int(crown.sum())} vertices of its own teeth's crowns pressed flat onto the ridge (the teeth are their own meshes)")
    return bone


def tongue(body: Body, m: Mouth, log=print) -> Structure | None:
    """The tongue as it lay: filling the mouth, its upper side against the palate, its tip between the front teeth.
    Its middle groove is drawn in (the scan's voxels do not hold it), and its colours: the pale coat on the middle and
    back of its upper side, the redder tip and edges, lighter and darker as the photographs are."""
    g = m.grid
    mask = m.tongue
    if m.teeth_lower.any():
        # As it lay, its tip reached over the lower front teeth to the lips. A tongue at rest in an opened mouth lies
        # within the lower row of teeth: what of it lay over the row or before it is left off (a little of its tip).
        inside, has, _ = lower_arch(m, 44.0)                                 # (to the tongue's root, whole)
        clear = inside & ~ndimage.binary_dilation(has, iterations=int(round(1.4 / g.spacing[0])))
        mask = ndimage.binary_opening(mask & clear[:, None, :], iterations=1)
    got = _mesh(body, g, mask, 1.1)
    if got is None:
        return None
    v, v_mm, f, n = got
    # Its own middle line (the head is a little turned: the face's is not it) and its length.
    zi, _, xi = np.nonzero(mask)
    zs = np.unique(zi)
    middle_x = ndimage.gaussian_filter1d(np.array([g.axis(2)[xi[zi == k]].mean() for k in zs]), 6.0, mode="nearest")
    z_mm = g.axis(0)[zs]
    aside = v_mm[:, 2] - np.interp(v_mm[:, 0], z_mm, middle_x)              # mm to his left of the tongue's middle
    along = np.clip((v_mm[:, 0] - z_mm[0]) / max(1.0, z_mm[-1] - z_mm[0]), 0.0, 1.0)      # 0 at its tip, 1 at its root
    top = np.clip((n[:, 1] - 0.25) / 0.5, 0.0, 1.0)                         # its upper side
    groove = 0.0009 * np.exp(-(aside / 1.7) ** 2) * top * np.clip(along / 0.12, 0.0, 1.0) * np.clip((0.72 - along) / 0.2, 0.0, 1.0)
    v = v - n * groove[:, None]
    coat = top * np.clip((along - 0.12) / 0.3, 0.0, 1.0) * np.exp(-(aside / 15.0) ** 2) * 0.75
    edge = np.clip(1.0 - top * 1.2, 0.0, 1.0) * 0.6 + np.clip(1.0 - along / 0.15, 0.0, 1.0) * 0.5
    colour = np.array(TONGUE, np.float64)[None, :] + (np.array(TONGUE_COAT, np.float64) - np.array(TONGUE, np.float64))[None, :] * coat[:, None]
    colour += (np.array(TONGUE_EDGE, np.float64)[None, :] - colour) * np.clip(edge, 0.0, 1.0)[:, None] * (1.0 - coat)[:, None]
    colour *= (1.0 - 0.22 * np.exp(-(aside / 1.1) ** 2) * top * (groove > 0))[:, None]      # the groove's shadow
    colour *= photo_tone(m, v_mm, -n)[:, None] ** 0.5
    back = np.clip((v_mm[:, 0] - float(np.nanmin(m.skin_front))) / 80.0, 0.0, 1.0)
    bake = np.tile(np.array([255, 255, 82, 225], np.uint8), (len(v), 1))
    bake[:, 0] = np.round(255 * (1.0 - DIM_BACK * back))
    return Structure("tongue", "organs", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in TONGUE), bake=bake,
                     albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8),
                     info={"class": "organ", "cm3": m.info.get("tongue_cm3"), "source": "TotalSegmentator's tongue label on the frozen CT, grown up to the palate"})


# ---- how the jaw opens -----------------------------------------------------------------------------------------------
def find_hinge(body: Body, m: Mouth):
    """The jaw's axis. A jaw that opens wide does two things: it turns in its joints, and the condyles' heads slide
    forward out of their sockets onto the bone before them (about a centimetre). The two together are one turn about
    an axis UNDER the joints, near the middle of the jaw's upright part (where the nerve enters it): AXIS_BELOW_MM
    under the heads of the two condyles (the mandible's hindmost tops, 3 mm under their crowns: m.condyles).
    Turned about the joints themselves, everything under them (the back teeth, the tongue's root) swung backwards
    into the throat. Returns a point on the axis and its direction (towards his left), in glTF metres, or None."""
    data, names = m.ct["raw"]["craniofacial_structures"]
    value = next((k for k, n in names.items() if n == "mandible"), None)
    if value is None:
        return None
    k, r, c = np.nonzero(data == value)                                       # slices (down), rows (back), columns (to his left)
    if len(k) < 1000:
        return None
    middle = np.median(c)
    heads = []
    for side in (c < middle, c >= middle):
        if side.sum() < 300:
            return None
        back = side & (r > r[side].max() - 13.0)                              # the ramus' hind edge: the condyle, not the coronoid in front
        top = back & (k < k[back].min() + 5)
        heads.append(np.array([k[top].min() + 3.5, r[top].mean() + 0.5, c[top].mean() + 0.5]))
    p = to_gltf(body, m.ct["to_body"].grid_points(np.array(heads)))
    right, left = (p[0], p[1]) if p[0][0] < p[1][0] else (p[1], p[0])
    axis = left - right
    m.condyles = (right, left)
    axis = axis / np.linalg.norm(axis)
    down = np.array([0.0, -1.0, 0.0]) - axis * (-axis[1])                     # straight down the body, square to the axis
    return right + down / np.linalg.norm(down) * (AXIS_BELOW_MM * MM), axis


def solve_weights(node: np.ndarray, zero: np.ndarray, one: np.ndarray, side: np.ndarray, log=print) -> np.ndarray:
    """Laplace's equation on a block of voxels: `node` the tissue, `zero` and `one` held at 0 and 1, no flow between
    neighbours that lie on opposite sides of the sheet (`side` +1 above it, -1 below, 0 where there is none).
    Returns the value per voxel (0 outside the tissue)."""
    from scipy import sparse
    from scipy.sparse.linalg import cg
    free = node & ~zero & ~one
    n = int(free.sum())
    ids = np.full(node.shape, -1, np.int64)
    ids[free] = np.arange(n)
    fixed = zero | one
    diag = np.full(n, 1e-6)
    rhs = np.zeros(n)
    rows, cols = [], []
    for axis in range(3):
        a = [slice(None)] * 3
        b = [slice(None)] * 3
        a[axis], b[axis] = slice(0, -1), slice(1, None)
        a, b = tuple(a), tuple(b)
        joined = (node | fixed)[a] & (node | fixed)[b] & ((side[a].astype(np.int16) * side[b]) != -1)
        for here, there in ((a, b), (b, a)):
            mine = joined & free[here]
            i = ids[here][mine]
            np.add.at(diag, i, 1.0)
            other_free = free[there][mine]
            rows.append(i[other_free])
            cols.append(ids[there][mine][other_free])
            np.add.at(rhs, i[~other_free], one[there][mine][~other_free].astype(np.float64))
    rows, cols = np.concatenate(rows), np.concatenate(cols)
    matrix = sparse.coo_matrix((np.concatenate([-np.ones(len(rows)), diag]), (np.concatenate([rows, np.arange(n)]), np.concatenate([cols, np.arange(n)]))), shape=(n, n)).tocsr()
    precondition = sparse.diags(1.0 / diag)
    x, flag = cg(matrix, rhs, x0=np.full(n, 0.3), M=precondition, rtol=1e-5, maxiter=6000)
    out = np.zeros(node.shape, np.float32)
    out[free] = np.clip(x, 0.0, 1.0)
    out[one] = 1.0
    log(f"mouth: jaw weights solved on {n} voxels" + ("" if flag == 0 else f" (stopped at {flag} iterations)"))
    return out


def stiffen(w: np.ndarray) -> np.ndarray:
    """Laplace's solution falls away from a thin bone faster than flesh that hangs on it does: the chin's skin comes
    out a little under 1. What is mostly with one jaw is given to it wholly (above 0.92 and below 0.08), with a
    smooth step between."""
    t = np.clip((w - 0.5) / 0.84 + 0.5, 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def nearest_fill(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """The values with every voxel outside `valid` given its nearest valid voxel's."""
    if valid.all() or not valid.any():
        return values
    index = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    return values[tuple(index)]


def sheet_at(m: Mouth, zyx_mm: np.ndarray, rim: bool = False):
    """The sheet's height at points' columns, and whether the sheet is there (and, asked for, how far inside its rim, mm)."""
    g = m.grid
    at = np.stack([(zyx_mm[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (zyx_mm[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    height = ndimage.map_coordinates(m.sheet, at, order=1, mode="nearest")
    there = ndimage.map_coordinates(m.domain.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    if rim:
        return height, there, ndimage.map_coordinates(m.rim_only if rim == "only" else m.rim, at, order=1, mode="constant", cval=0.0)        # 0..1
    return height, there


def jaw_weights(body: Body, m: Mouth, voxel_mm: float = 2.0, log=print) -> None:
    """Works the jaw's weights out on a block round the head's lower half and the neck, and keeps them on the Mouth
    (m.weight_grid; m.weights = as solved, above = as seen from above the sheet, below = from below it)."""
    s = m.stomion_mm
    lo = np.array([s[0] - 14.0, s[1] - 150.0, s[2] - 90.0])
    shape = (95, 128, 90)
    grid = Grid(lo, np.full(3, voxel_mm), shape)
    points = grid.points()
    flat = points.reshape(-1, 3)
    inside = under_skin(body, grid, flat).reshape(shape)
    index = m.ct["to_body"].inverse(points).astype(np.float32)

    def label(task, *wanted):
        data, names = m.ct["raw"][task]
        values = [k for k, n in names.items() if n in wanted]
        return np.isin(ndimage.map_coordinates(data, index, order=0, mode="constant", cval=0), values)

    mandible = label("craniofacial_structures", "mandible", "teeth_lower")
    skull = label("craniofacial_structures", "skull", "teeth_upper")
    hyoid = label("headneck_bones_vessels", "hyoid") if "headneck_bones_vessels" in m.ct["raw"] else np.zeros(shape, bool)
    bones = [o["index"] for o in body.objects if o["layer"] == "bone"]
    bone = body.sample(np.isin(body.labels, bones).astype(np.float32), to_gltf(body, flat), order=1).reshape(shape) > 0.5
    height, there = sheet_at(m, np.stack([np.repeat(grid.axis(0), shape[2]), np.zeros(shape[0] * shape[2]), np.tile(grid.axis(2), shape[0])], axis=1))
    height, there = height.reshape(shape[0], shape[2]), there.reshape(shape[0], shape[2])
    side = np.where(there[:, None, :], np.where(grid.axis(1)[None, :, None] > height[:, None, :], 1, -1), 0).astype(np.int8)
    held = np.zeros(shape, bool)
    if m.throat is not None:
        # Behind the hard palate there is no sheet: the tongue is the lower side, what lies on and behind it (the soft
        # palate, the throat's wall) the upper, held with the skull.
        held = throat.on_grid(m, grid, m.throat.held) & inside
        tongue = throat.on_grid(m, grid, m.tongue)
        side = np.where((grid.axis(0) > m.throat.z_end)[:, None, None], 0, side).astype(np.int8)
        side[tongue & (grid.axis(0) > m.throat.z_end - 6.0)[:, None, None]] = -1
        side[held] = 1
    # What sits on a bone goes with it: the flesh within 5 mm of the mandible (gum, the chin's pad, the muscles'
    # attachments) is held at 1, within 3 mm of the skull at 0; where the two meet (the joint) each keeps the nearer.
    to_jaw = ndimage.distance_transform_edt(~mandible, sampling=grid.spacing)
    to_skull = ndimage.distance_transform_edt(~skull, sampling=grid.spacing)
    one = (to_jaw <= FIRM_MM) & (to_jaw <= to_skull) & (side != 1) & inside | mandible
    # The skull, the spine and the shoulder girdle hold still; the hyoid hangs between and goes as the tissue takes it.
    zero = ((to_skull <= 3.0) & (to_skull < to_jaw) & (side != -1) & inside) | skull | (bone & (to_jaw > FIRM_MM + 2.0) & ~near(hyoid, grid.spacing, 3.0))
    zero |= held
    zero &= ~mandible
    zero[:, :2, :] = True                                                     # the neck's base
    zero[-2:, :, :] = True                                                    # the nape
    zero[:, -2:, :] = True
    one &= ~zero
    node = inside | zero | one
    solved = stiffen(solve_weights(node, zero, one, side, log))
    # Under the jaw and down the neck the skin lies in folds (the chin's against the neck's) a few millimetres apart,
    # and under it the fat and the muscles are other meshes: a weight that changes within millimetres there moves
    # them differently and one shows through the other. Away from the jaw's bone and below the mouth the weights
    # are smoothed over 6 mm, so neighbours move together.
    filled = nearest_fill(solved, node)
    soft = ndimage.gaussian_filter(filled, 6.0 / voxel_mm)
    loose = np.clip((to_jaw - 8.0) / 10.0, 0.0, 1.0) * np.clip((s[1] - 22.0 - grid.axis(1)[None, :, None]) / 12.0, 0.0, 1.0)
    solved = np.where(node, filled + (soft - filled) * loose, 0.0).astype(np.float32)
    solved[one] = 1.0
    m.weight_grid = grid
    # Outside the tissue each voxel takes its nearest tissue's value; seen from above the sheet, the voxels under it
    # take the nearest value of the upper side's tissue (and the other way round), so a point at the sheet itself
    # is read wholly from its own side.
    m.weights = nearest_fill(solved, node)
    m.above = nearest_fill(solved, node & (side != -1))
    m.below = nearest_fill(solved, node & (side != 1))
    # How far the two sides part at each column: wholly inside the mouth; along the lips less and less towards the
    # corners, where the lips are one (a mouth opens as a lens, not as a slot); nothing at the sheet's rim.
    plan = (m.grid.spacing[0], m.grid.spacing[2])
    rim = np.clip(ndimage.distance_transform_edt(m.domain, sampling=plan) / RIM_MM, 0.0, 1.0)
    along = np.clip(np.abs(m.u_of_x) / (HALF_WIDTH - 1.0), 0.0, 1.0)
    lens = (1.0 - along ** 3) ** 0.7
    part = np.where(m.lips, lens[None, :], 1.0)
    part = ndimage.gaussian_filter(part, [1.5 / plan[0], 1.5 / plan[1]])
    m.rim = (np.minimum(part, 1.0) * rim).astype(np.float32)
    m.rim_only = rim.astype(np.float32)


def weight(body: Body, m: Mouth, v_gltf: np.ndarray, side: np.ndarray | None = None) -> np.ndarray:
    """How far points go with the jaw, 0..1. `side` says, where it is known, on which side of the sheet a point
    belongs (+1 the upper jaw's, -1 the lower's, between them a share of each; NaN = not known: by its height)."""
    p = to_mm(body, v_gltf)
    g = m.weight_grid
    out = np.zeros(len(p), np.float32)
    index = g.index(p)
    inside = ((index > -0.5) & (index < np.array(g.shape)[:, None] - 0.5)).all(axis=0)
    if not inside.any():
        return out
    q = p[inside]
    height, there, rim = sheet_at(m, q, rim=True)
    share = (q[:, 1] > height).astype(np.float64)                            # of the upper side
    if side is not None:
        given = np.asarray(side, np.float64)[inside]
        share = np.where(np.isnan(given), share, (given + 1.0) / 2.0)
    share = 0.5 + (share - 0.5) * rim                                        # at the sheet's rim and the mouth's corners both sides alike
    plain = g.sample(m.weights, q)
    split = g.sample(m.below, q) * (1.0 - share) + g.sample(m.above, q) * share
    out[inside] = np.where(there, split, plain)
    return out


def lip_field(body: Body, m: Mouth):
    """How far each voxel of the mouth's grid goes with a lip taken in the fingers and drawn off the teeth.
    With the jaw only turned, the lower lip stays before the lower teeth as it lay (their edges are 3 to 5 mm
    under the lip line) and nothing of them is seen. A lip drawn towards the chin comes off the teeth: so all the
    flesh of the lower lip that lies in front of the lower jaw's hard parts (teeth, gum, bone) goes down with it:
    wholly from the lip's edge to 12 mm under the lip line, less and less to nothing at 32 mm (the chin), and less
    towards the mouth's corners, where the lips are one. The upper lip the same way, lifted towards the nose: the
    flesh in front of the upper jaw's hard parts, wholly to 6 mm over the lip line, nothing at 16 mm (the nose's foot).
    Returns the field with a sign (0..1 the lower lip's, 0..-1 the upper lip's) and the two lips' own (0..1)."""
    g, face = m.grid, m.face
    zs, ys = g.axis(0), g.axis(1)
    lip_y = np.array([to_mm(body, face.origin + face.ex * (u * MM) + face.ey * (float(m.lip_w(u)) * MM))[1] for u in m.u_of_x])
    lens = np.clip(1.0 - (np.abs(m.u_of_x) / (HALF_WIDTH - 1.0)) ** 3, 0.0, 1.0)
    under = lip_y[None, None, :] - ys[None, :, None]                         # mm under the lip line
    down = np.clip(1.0 - (under - 12.0) / 20.0, 0.0, 1.0)
    up = np.clip(1.0 - (-under - 6.0) / 10.0, 0.0, 1.0)
    lower_side = np.where(m.domain[:, None, :], ys[None, :, None] < m.sheet[:, None, :] - 0.2, under > 0.0)
    lip_thick = (zs[:, None, None] - m.skin_front[None, None, :]) < 16.0

    def before(hard):                                                        # per (y, x): in front of the first hard voxel from the front
        first = np.where(hard.any(axis=0), np.argmax(hard, axis=0), hard.shape[0])
        return np.arange(hard.shape[0])[:, None, None] < first[None, :, :]

    # (`lower`, `upper`: without the question of which lip a point is of, for points that are known to be that lip's:
    # read across the line between the lips, the answer stepped with the voxels' rows and notched the lip's edge.)
    lower = (lens[None, None, :] * down * before(m.lower | m.teeth_lower) * lip_thick).astype(np.float32)
    before_upper = lens[None, None, :] * before(m.upper | m.teeth_upper) * lip_thick
    upper = (before_upper * up).astype(np.float32)
    m.vestibule_up = (before_upper * ~lower_side).astype(np.float32)        # between the upper lip and the upper jaw, at every height
    return np.where(lower_side, lower, -upper).astype(np.float32), lower, upper


def lip_pull(body: Body, m: Mouth, v_gltf: np.ndarray, side: np.ndarray | None = None) -> np.ndarray:
    """How far points go with the lower lip when it is drawn down (0..1), or with the upper lip when it is lifted
    (0..-1). `side`, where it is known: +1 = of the upper jaw's side (the upper lip, the roof), -1 = of the lower:
    each read from its own lip's field, clear of the line between the lips."""
    p = to_mm(body, v_gltf)
    if side is None:
        return m.grid.sample(m.lip, p, order=1, cval=0.0).astype(np.float32)
    given = np.asarray(side, np.float64)
    out = np.where(given < 0, m.grid.sample(m.lip_whole, p, order=1, cval=0.0), m.grid.sample(m.lip, p, order=1, cval=0.0))
    if m.lip_whole_up is None:
        return np.where(given > 0, 0.0, out).astype(np.float32)
    return np.where(given > 0, -m.grid.sample(m.lip_whole_up, p, order=1, cval=0.0), out).astype(np.float32)


def clear_labels(body: Body, m: Mouth, log=print) -> int:
    """Takes the mouth's space (a little more than it, the labels' voxels being coarser) and the tongue's place out of
    the body's unnamed muscle and fat, so their meshes are parted where the mouth is and do not fill it."""
    lab = body.labels
    g = m.grid
    loose = [o["index"] for o in body.objects if o["name"] in ("muscles", "subcutaneous fat") or o["layer"] == "skin"]
    muscle = [o["index"] for o in body.objects if o["name"] == "muscles"]
    spacing = np.array(body.spacing)
    lo = np.maximum(np.floor(g.origin / spacing).astype(int), 0)
    hi = np.minimum(np.ceil((g.origin + np.array(g.shape) * g.spacing) / spacing).astype(int), np.array(lab.shape))
    block = Grid(lo * spacing, spacing, tuple(int(x) for x in hi - lo))
    flat = block.points().reshape(-1, 3)
    room = m.space if m.throat is None else m.space | m.throat.hollow | m.throat.uvula | m.throat.tonsils
    wide = near(room, g.spacing, 1.6 if m.throat is None else BAG_MM + 0.7).astype(np.float32)      # (to behind the mouth's bag)
    space = g.sample(wide, flat, order=1, cval=0.0).reshape(block.shape) > 0.3
    tongue = g.sample(m.tongue.astype(np.float32), flat, order=1, cval=0.0).reshape(block.shape) > 0.5
    if m.throat is not None:
        # The soft palate lies ON the tongue: its unnamed muscle must end clear of the lining drawn between them.
        back = near(m.tongue & (g.axis(0) > m.throat.z_end - 2.0)[:, None, None], g.spacing, BAG_MM + 0.7).astype(np.float32)
        space |= g.sample(back, flat, order=1, cval=0.0).reshape(block.shape) > 0.3
    view = lab[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    hit = (space & np.isin(view, loose)) | (tongue & np.isin(view, muscle))
    # Between the lips the space thins to nothing at the skin, but what the labels have there must be parted too.
    height, _ = sheet_at(m, flat)
    at = np.stack([(flat[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (flat[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    in_lips = ndimage.map_coordinates(m.lips.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    slit = (in_lips & (np.abs(flat[:, 1] - (height - 1.0)) < 2.4)).reshape(block.shape)
    hit |= slit & np.isin(view, loose)
    # And a little more of them round it, in the lips and 9 mm beyond the mouth's corners: from 3.5 mm over the line to
    # 3.5 mm under the lower lip's inner side. What the labels have there stood up over the lips' inner sides at the
    # opened mouth's corners (the red of the lips has no fat, and its muscle is drawn: face_muscles).
    wide = ndimage.binary_dilation(m.lips, iterations=int(round(9.0 / g.spacing[0])))
    in_wide = ndimage.map_coordinates(wide.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    band = (in_wide & (flat[:, 1] < height + 3.5) & (flat[:, 1] > height - SPACE_MM - 4.5)).reshape(block.shape)
    hit |= band & np.isin(view, loose)
    # The labels' fat is "what is fat-coloured in the photographs", on voxels of 1.3 x 2 mm: round the tongue and
    # under the palate it marks mucosa, glands and the tongue's own pale edge, and in the opened mouth it stood there
    # as yellow slabs. Within the arch of the teeth and the cheeks' wall, from the palate down to the mouth's
    # floor, there is no fat layer (the lips, in front, keep theirs).
    fat = [o["index"] for o in body.objects if o["layer"] == "fat"]
    inner = (m.rim_only > 0.5) & ~ndimage.binary_dilation(m.lips, iterations=2)
    within = ndimage.map_coordinates(inner.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    oral = (within & (flat[:, 1] < height + 14.0) & (flat[:, 1] > height - 34.0)).reshape(block.shape)
    hit |= oral & np.isin(view, fat)
    # And in the lips and the mouth's corners, the half of them towards the teeth (more than 5 mm in from their
    # skin): the labels' fat and unnamed muscle there stood behind the lips' inner sides and showed in the opened
    # mouth, drawn out where the lower lip comes down. The lips keep what lies under their skin.
    near_lips = ndimage.binary_dilation(m.lips, iterations=int(round(9.0 / g.spacing[0])))       # (and 9 mm beyond the mouth's corners)
    in_lips = ndimage.map_coordinates(near_lips.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    behind_skin = flat[:, 0] - np.interp(flat[:, 2], g.axis(2), m.skin_front)
    inner_lip = (in_lips & (behind_skin > 5.0) & (np.abs(flat[:, 1] - height) < 17.0)).reshape(block.shape)
    hit |= inner_lip & np.isin(view, fat + muscle)
    view[hit] = 0
    counts = np.bincount(lab.ravel(), minlength=256)
    for o in body.objects:
        o["voxels"] = int(counts[o["index"]])
    log(f"mouth: {int(hit.sum())} voxels of unnamed muscle and fat cleared for the mouth and the tongue")
    return int(hit.sum())


def prepare(body: Body, face: Face, skin_v: np.ndarray, ct_dir: Path | None = None, log=print) -> Mouth | None:
    """Everything about the mouth, once per run (kept on the body as body.mouth); None where the data is missing."""
    m = measure(body, face, skin_v, ct_dir, log)
    body.mouth = m
    if m is None:
        log("mouth: not built (needs the head's export and the head CT's labels)")
        return None
    hinge = find_hinge(body, m)
    if hinge is None:
        body.mouth = None
        return None
    m.hinge, m.axis = hinge
    jaw_weights(body, m, log=log)
    m.lip, m.lip_whole, m.lip_whole_up = lip_field(body, m)
    m.lip_down = -face.ey * 0.94 + face.ez * 0.34                           # down the face and a little forward: the lip turns out as it comes down
    m.lip_down = m.lip_down / np.linalg.norm(m.lip_down)
    m.lip_up = face.ey * 0.90 + face.ez * 0.44                              # up the face and forward: the upper lip turns out as it is lifted
    m.lip_up = m.lip_up / np.linalg.norm(m.lip_up)
    clear_labels(body, m, log)
    grab = to_gltf(body, m.stomion_mm) - face.ey * 0.006                    # on the lower lip
    reach = float(np.linalg.norm(np.cross(grab - m.hinge, m.axis)))
    m.info["unity"] = {"hinge": [float(x) for x in m.hinge], "axis": [float(x) for x in m.axis], "degrees": OPEN_DEGREES,
                       "grab": [float(x) for x in grab], "travel_m": reach * float(np.radians(OPEN_DEGREES)),
                       "lip_down": [float(x) for x in m.lip_down], "lip_pull_m": LIP_PULL_MM * MM,
                       "lip_up": [float(x) for x in m.lip_up], "lip_lift_m": LIP_LIFT_MM * MM,
                       "grab_upper": [float(x) for x in to_gltf(body, m.stomion_mm) + face.ey * 0.007]}
    log(f"mouth: hinge at {np.round(m.hinge * 1000, 1)} mm, axis {np.round(m.axis, 3)}; the lower lip lies {reach * 1000:.0f} mm from it "
        f"and travels {reach * np.radians(OPEN_DEGREES) * 1000:.0f} mm")
    return m


# ---- the lips' cut ---------------------------------------------------------------------------------------------------
def cut(v: np.ndarray, f: np.ndarray, body: Body, m: Mouth, log=print):
    """Parts the skin along the lip line, as lids.cut parts the lids. Returns the new vertices and faces, `source`
    (for each new vertex the old vertex whose colour and bake it takes), `side` (+1 on the upper lip, -1 on the
    lower, NaN away from the mouth), a mask of the strips that are the lips' inner sides, `anchor` (for a strip's
    vertex the edge vertex it hangs from, else -1: it goes as its edge goes) and `held` (n, 2: for the strips' last
    row, at the gum, its jaw weight and lip pull as they are to be; NaN elsewhere)."""
    face = m.face
    v = np.asarray(v, np.float64).copy()
    f = np.asarray(f, np.int64).copy()
    k0 = len(v)
    u, w, d = face.local(v)
    g = w - m.lip_w(u)                                                       # mm above the lip line
    span = HALF_WIDTH - 1.0
    close = (np.abs(u) < HALF_WIDTH + 8.0) & (np.abs(g) < 16.0) & (d > 15.0)
    tri_close = close[f].all(axis=1)
    tri_u, tri_g = u[f].mean(axis=1), g[f].mean(axis=1)
    in_slit = tri_close & (np.abs(tri_u) < span)
    up, down = in_slit & (tri_g > 0), in_slit & (tri_g <= 0)
    on_up = np.zeros(k0, bool)
    on_up[f[up].ravel()] = True
    on_down = np.zeros(k0, bool)
    on_down[f[down].ravel()] = True
    seam = on_up & on_down & (np.abs(u) < span)
    side = np.where(close & (np.abs(u) < HALF_WIDTH + 2.0), np.sign(g), np.nan)
    source = np.arange(k0)
    if seam.sum() < 8:
        log(f"mouth: no cut between the lips ({int(seam.sum())} vertices on the line)")
        return v.astype(np.float32), f.astype(np.uint32), source, side, np.zeros(k0, bool), np.full(k0, -1, np.int64), np.full((k0, 2), np.nan)
    v[seam] -= face.ey * (g[seam] * MM)[:, None]                             # onto the line itself
    # A vertex belongs to the lip whose triangles it is part of (a vertex a hair under the line can be the upper lip's).
    side[on_up] = 1.0
    side[on_down & ~on_up] = -1.0
    seam_ids = np.nonzero(seam)[0]
    copy_of = np.full(k0, -1, np.int64)
    copy_of[seam_ids] = k0 + np.arange(len(seam_ids))
    new_v = [v[i].copy() for i in seam_ids]
    new_side = [-1.0] * len(seam_ids)
    new_src = [int(i) for i in seam_ids]
    new_margin = [False] * len(seam_ids)
    new_anchor = [-1] * len(seam_ids)
    lower_faces = f[down]
    swap = copy_of[lower_faces]
    f[down] = np.where(swap >= 0, swap, lower_faces)
    # The lips' depth: from each cut edge a strip inwards along the sheet, the upper lip's on the sheet and the lower
    # lip's on the space's floor under it.
    edges = set()
    for tri in f[up]:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            if seam[a] and seam[b]:
                edges.add((int(a), int(b)))
    # Each lip's inner side, as rows of points behind its edge: half way in to the teeth and at the teeth (both at the
    # sheet's height there; the lower lip's on the space's floor), smoothed along the lip; then the fold where the lip's
    # lining turns onto the gum, FOLD_MM towards the roots, against the gum's face there. The rows at the lip go as
    # the lip's edge goes; the fold is the gum's (the upper jaw's, or the lower's wholly, and never drawn down with
    # the lip): between them the lining is drawn out as the lip comes off the teeth.
    order = seam_ids[np.argsort(u[seam_ids])]
    g = m.grid
    edge_mm = to_mm(body, v[order])
    back = np.arange(0.0, 20.5, 0.5)

    def to_teeth(hard, y_mm):
        """mm from each edge point back to the first of `hard` at the heights y_mm (20 where there is none)."""
        probe = np.stack([edge_mm[:, None, 0] + back[None, :], np.broadcast_to(y_mm[:, None], (len(order), len(back))),
                          np.broadcast_to(edge_mm[:, None, 2], (len(order), len(back)))], axis=-1).reshape(-1, 3)
        met = g.sample(hard.astype(np.float32), probe, order=0, cval=0.0).reshape(len(order), len(back)) > 0.5
        return np.where(met.any(axis=1), back[np.argmax(met, axis=1)], 20.0)

    height, there = sheet_at(m, edge_mm + np.array([4.0, 0.0, 0.0]))
    height = np.where(there, height, edge_mm[:, 1])
    rows, new_f = {}, []
    fixed = {}
    for top in (True, False):
        hard = (m.upper | m.teeth_upper) if top else (m.lower | m.teeth_lower)
        drawn = m.drawn_upper if top else m.drawn_lower
        if drawn is not None and drawn.any():
            hard = hard | near(drawn, m.grid.spacing, 1.2)                   # (and the gum over the bone as it is drawn: gums())
        level = height + 1.0 if top else height - SPACE_MM - 1.0
        # (At the mouth's corners the lips' inner sides keep their whole depth: there they are the cheek's inner side
        # behind the corner, and close it. Thinned out to nothing there, they let the lips' muscle and fat be seen.)
        deep = ndimage.gaussian_filter1d(np.clip(to_teeth(hard, level) - 0.8, 3.0, 14.0), 2.5, mode="nearest")
        fold_y = level + (FOLD_MM if top else -FOLD_MM)
        fold_deep = ndimage.gaussian_filter1d(np.clip(to_teeth(hard, fold_y) - 0.8, 2.0, 16.0), 2.5, mode="nearest")
        drop = np.minimum(SPACE_MM, SPACE_MM * deep / 5.0)
        y = height - (0.0 if top else drop)
        for name, depth, y_row in (("half", deep * 0.5, y), ("teeth", deep, y), ("fold", fold_deep, fold_y)):
            # Each row a smooth curve along the lip (the lip's edge is the skin mesh's own vertices, which zigzag
            # in depth: carried into the rows they shaded the lip's inner side in streaks).
            z_row = ndimage.gaussian_filter1d(edge_mm[:, 0] + depth, 3.0, mode="nearest")
            y_smooth = ndimage.gaussian_filter1d(y_row, 3.0, mode="nearest")
            for k, i in enumerate(order):
                p_mm = np.array([z_row[k], y_smooth[k], edge_mm[k, 2]])
                rows[(int(i), top, name)] = k0 + len(new_v)
                new_v.append(to_gltf(body, p_mm))
                new_side.append(1.0 if top else -1.0)
                new_src.append(int(i))
                new_margin.append(True)
                if name == "fold":
                    new_anchor.append(-1)
                    # (the lower lip's fold is the gum's and stays; the upper lip's comes 0.6 of the lip's way with it:
                    # lying against the gum's face, the lifted lip's lining cut through the swellings over the roots)
                    fixed[k0 + len(new_v) - 1] = (0.0, -0.6) if top else (1.0, 0.0)
                else:
                    new_anchor.append(int(i) if top else int(copy_of[i]))
    grown = np.array(new_v)

    def at(index):
        return v[index] if index < k0 else grown[index - k0]

    for i in (int(order[0]), int(order[-1])):                                # the two ends, behind the corners: closed (seen from either side)
        ring = [rows[(i, True, "fold")], rows[(i, True, "teeth")], rows[(i, True, "half")], rows[(i, False, "half")], rows[(i, False, "teeth")], rows[(i, False, "fold")]]
        for tri in ((ring[0], ring[1], ring[4]), (ring[0], ring[4], ring[5]), (ring[1], ring[2], ring[3]), (ring[1], ring[3], ring[4])):
            new_f += [tri, tri[::-1]]
    for a, b in edges:
        for top in (True, False):
            a0, b0 = (a, b) if top else (int(copy_of[a]), int(copy_of[b]))
            # Each face looks into the mouth: the upper lip's down and back, the lower lip's up and back.
            inward = (-face.ey if top else face.ey) - face.ez
            for name in ("half", "teeth", "fold"):
                a1, b1 = rows[(a, top, name)], rows[(b, top, name)]
                normal = np.cross(at(b0) - at(a0), at(b1) - at(a0))
                if normal @ inward >= 0:
                    new_f += [(a0, b0, b1), (a0, b1, a1)]
                else:
                    new_f += [(b0, a0, a1), (b0, a1, b1)]
                a0, b0 = a1, b1
    v = np.concatenate([v, np.array(new_v)])
    f = np.concatenate([f, np.array(new_f, np.int64)])
    side = np.concatenate([side, new_side])
    source = np.concatenate([source, np.array(new_src, np.int64)])
    margin = np.concatenate([np.zeros(k0, bool), np.array(new_margin, bool)])
    anchor = np.concatenate([np.full(k0, -1, np.int64), np.array(new_anchor, np.int64)])
    held = np.full((len(v), 2), np.nan)
    for index, values in fixed.items():
        held[index] = values
    log(f"mouth: lips cut along {len(seam_ids)} vertices, {len(edges)} edges")
    return v.astype(np.float32), f.astype(np.uint32), source, side, margin, anchor, held


def skin_weights(body: Body, m: Mouth, v: np.ndarray, side: np.ndarray, anchor: np.ndarray, held: np.ndarray | None = None) -> np.ndarray:
    """The cut skin's jaw weights and how far it goes with the lower lip drawn down (n, 2 for Structure.data3)."""
    w = weight(body, m, v, side)
    pull = lip_pull(body, m, v, side)
    hung = anchor >= 0
    w[hung] = w[anchor[hung]]
    pull[hung] = pull[anchor[hung]]
    out = np.stack([w, pull], axis=1).astype(np.float32)
    if held is not None:
        given = ~np.isnan(held[:, 0])
        out[given] = held[given]
    return out


def lip_sides(v: np.ndarray, m: Mouth, least_d: float = 15.0) -> np.ndarray:
    """Which lip each vertex of a surface before the mouth is of: +1 the upper, -1 the lower, NaN away from the
    mouth (as cut says it of the skin's, by the side of the lip line it lies on). `least_d`: only what lies
    further forward than this is the lips' (mm before the eyes, in the face's frame; the skin's own: 15)."""
    u, w, d = m.face.local(np.asarray(v, np.float64))
    g = w - m.lip_w(u)
    close = (np.abs(u) < HALF_WIDTH + 8.0) & (np.abs(g) < 16.0) & (d > least_d)
    return np.where(close & (np.abs(u) < HALF_WIDTH + 2.0), np.sign(g), np.nan)


def nearest_in_triangles(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """For points p and triangles a, b, c (all (..., 3)): the shares of a, b and c in each triangle's point nearest
    its p, (..., 3), summing to 1 (Ericson, Real-Time Collision Detection, 5.1.5)."""
    ab, ac = b - a, c - a
    ap, bp, cp = p - a, p - b, p - c
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2

    def over(x, y):
        return x / np.where(np.abs(y) > 1e-30, y, 1.0)

    inside = np.stack([va, vb, vc], axis=-1) / np.where(np.abs(va + vb + vc) > 1e-30, va + vb + vc, 1.0)[..., None]
    zero, one = np.zeros_like(d1), np.ones_like(d1)
    t_ab, t_ac, t_bc = over(d1, d1 - d3), over(d2, d2 - d6), over(d4 - d3, (d4 - d3) + (d5 - d6))
    cases = [((d1 <= 0) & (d2 <= 0), np.stack([one, zero, zero], axis=-1)),                 # nearest a
             ((d3 >= 0) & (d4 <= d3), np.stack([zero, one, zero], axis=-1)),                # nearest b
             ((vc <= 0) & (d1 >= 0) & (d3 <= 0), np.stack([1 - t_ab, t_ab, zero], axis=-1)),          # on the edge a b
             ((d6 >= 0) & (d5 <= d6), np.stack([zero, zero, one], axis=-1)),                # nearest c
             ((vb <= 0) & (d2 >= 0) & (d6 <= 0), np.stack([1 - t_ac, zero, t_ac], axis=-1)),          # on the edge a c
             ((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), np.stack([zero, 1 - t_bc, t_bc], axis=-1))]    # on the edge b c
    out = inside
    for when, shares in reversed(cases):
        out = np.where(when[..., None], shares, out)
    return out


def on_the_skin(v: np.ndarray, n: np.ndarray, skin_v: np.ndarray, skin_f: np.ndarray, reach_mm: float = 8.0, k: int = 16):
    """For points under the skin (glTF metres) and their own normals: the skin's triangle over each. Returns its
    corners (n, 3; the skin's vertex numbers), their shares in the skin's point nearest the point (n, 3), and
    whether there is one.

    Of the `k` skin triangles whose middles lie nearest (within `reach_mm`), the one whose nearest point is
    nearest, among those that look the way the point's own surface does: in a fold (under the chin) the nearest
    skin of all can be the fold's other side, which goes otherwise with the jaw.

    What is under the skin goes with the jaw as the skin over it does only if it takes the skin's own movement
    there, and the skin moves as its triangles do: straight between their corners. Read at a point of its own
    (even one on the skin), a vertex under a triangle in which the weights bend took another way than the
    triangle did, by millimetres where the jaw travels 30."""
    from scipy.spatial import cKDTree
    v, n = np.asarray(v, np.float64), np.asarray(n, np.float64)
    skin_v, skin_f = np.asarray(skin_v, np.float64), np.asarray(skin_f, np.int64)
    corners, shares = np.zeros((len(v), 3), np.int64), np.zeros((len(v), 3))
    if len(v) == 0 or len(skin_f) == 0:
        return corners, shares, np.zeros(len(v), bool)
    a, b, c = skin_v[skin_f[:, 0]], skin_v[skin_f[:, 1]], skin_v[skin_f[:, 2]]
    looks = np.cross(b - a, c - a)
    looks /= np.maximum(np.linalg.norm(looks, axis=1, keepdims=True), 1e-20)
    k = min(k, len(skin_f))
    far, index = cKDTree((a + b + c) / 3.0).query(v, k=k, distance_upper_bound=reach_mm / 1000.0)
    far, index = far.reshape(len(v), k), np.minimum(index.reshape(len(v), k), len(skin_f) - 1)
    part = nearest_in_triangles(v[:, None, :], a[index], b[index], c[index])
    point = part[..., 0:1] * a[index] + part[..., 1:2] * b[index] + part[..., 2:3] * c[index]
    away = np.linalg.norm(point - v[:, None, :], axis=-1)
    same = np.isfinite(far) & (np.einsum("nkc,nc->nk", looks[index], n) > 0.3)
    away = np.where(same, away, np.inf)
    best = np.argmin(away, axis=1)
    rows = np.arange(len(v))
    found = np.isfinite(away[rows, best]) & (away[rows, best] < reach_mm / 1000.0)
    return skin_f[index[rows, best]], part[rows, best], found


# ---- every structure's share in the jaw's turn -----------------------------------------------------------------------
WITH_THE_JAW = ("mandible", "lower teeth")
HELD = ("cranium and maxilla", "upper teeth")
MASSES = ("muscles", "subcutaneous fat", "visceral fat")                                               # meshed through the closed mouth: parted where it parts
AS_ONE = ("hyoid bone", "thyroid cartilage", "cricoid cartilage", "bone (not named)", "eyeball")       # stiff: one weight for the whole of each


def assign(structures: list[Structure], body: Body, m: Mouth, log=print) -> int:
    """Gives every structure near the mouth its jaw weights (Structure.data3: x = the weight, y = how far it goes
    with the lower lip when that is drawn down; hair: a TEXCOORD_3 stream, a strand going as its root goes). Triangles that reach across the sheet (a mesh drawn through the
    closed mouth) are taken out: they would be drawn out into sheets when it opens. Returns how many structures move.

    The fat's outer surface is the skin's outline moved in (fat_shell), and it carries marks (Structure.extra:
    common.FAT_SURFACE, FAT_LOWER_LIP, FAT_UPPER_LIP). It goes as the skin over it goes: each of its vertices
    takes the movement of the skin's triangle over it (on_the_skin, on the skin's surface as last built: the
    triangle's corners read, at the lips on the vertex's own lip's side of the sheet, and weighed by where the
    vertex lies under the triangle), and none of its triangles is taken out. (Read at its own place, a
    millimetre or two under the skin, it moved otherwise than the skin where the weights change quickly, and
    with the mouth open it showed through the skin of the upper lip and the jaw.) The marks are taken off
    here: they are the build's."""
    moved = 0
    whole_skin = None
    for s in structures:
        side, spared = None, None
        if s.name == "subcutaneous fat" and s.extra is not None and not s.streams:
            mark = np.asarray(s.extra, np.uint8)
            side = np.where((mark & FAT_UPPER_LIP) > 0, 1.0, np.where((mark & FAT_LOWER_LIP) > 0, -1.0, np.nan))
            spared = (mark & FAT_SURFACE) > 0
            s.extra = None
            path = getattr(body, "export", None)
            if path is not None and (path / "model" / "skin_surface.npz").exists():
                whole_skin = load_structures(path / "model" / "skin_surface.npz")[0]
        if s.data3 is not None or (s.streams and "TEXCOORD_3" in s.streams):
            moved += 1
            continue
        if s.name in HELD or s.layer == "skeleton" and not any(s.name.startswith(k) for k in WITH_THE_JAW + AS_ONE):
            continue
        v = np.asarray(s.v, np.float64)
        if s.name in WITH_THE_JAW:
            s.data3 = np.stack([np.ones(len(v), np.float32), np.zeros(len(v), np.float32)], axis=1)
            moved += 1
            continue
        w = weight(body, m, v, np.full(len(v), -1.0) if s.name == "tongue" else side)
        over = None                                                         # the fat's surface: the skin's points over it
        if w.max() < 0.004:
            continue
        if s.name == "subcutaneous fat" and s.streams is None:
            # The fat's outer face lies a millimetre or two under the skin, and where the weights change quickly (the
            # folds under the chin) that is enough for it to move otherwise than the skin and show through it. Its
            # weights are read where the skin over it is, 1.5 mm out along its own normal (not where that reads
            # something else altogether: across the mouth's slit).
            own = normals_of(np.asarray(s.v, np.float32), np.asarray(s.f))
            outer = weight(body, m, v + own * 0.0015, side)
            _, at_mouth = sheet_at(m, to_mm(body, v))
            w = np.where((np.abs(outer - w) < 0.25) & ~at_mouth, outer, w).astype(np.float32)
            if spared is not None and whole_skin is not None and spared.any():
                corners, shares, found = on_the_skin(v[spared], own[spared], whole_skin.v, whole_skin.f)
                mine = np.flatnonzero(spared)[found]
                at = np.asarray(whole_skin.v, np.float64)[corners[found]].reshape(-1, 3)         # the triangles' corners, three for each vertex
                over = (mine, at, shares[found], np.repeat(side[mine], 3))
                w[mine] = (weight(body, m, at, over[3]).reshape(-1, 3) * over[2]).sum(axis=1)
        if s.name == "tongue":
            w = with_the_tongue(m, to_mm(body, v), w)
        if any(s.name.startswith(k) or s.name.endswith(k) for k in AS_ONE):
            w[:] = float(w.mean())
        if s.streams:
            start = np.asarray(s.streams["TEXCOORD_0"])[:, 1] == 0.0          # a strand's first ring
            strand = np.maximum(np.cumsum(start) - 1, 0) // 2
            first = np.nonzero(start)[0][::2]
            w = w[first][np.minimum(strand, len(first) - 1)]
            pull = lip_pull(body, m, v)[first][np.minimum(strand, len(first) - 1)]
            s.streams = dict(s.streams, TEXCOORD_3=np.stack([w, pull], axis=1).astype(np.float32))
        else:
            # A triangle that the open jaw draws out to more than 1.7 times its length (and to more than 4 mm) joins what
            # the mouth parts: a mesh made through the closed mouth. Left in, it hangs across the open mouth as a sheet.
            f = np.asarray(s.f, np.int64)
            hard = s.layer == "skeleton" or s.name == "tongue"             # bone, cartilage and the tongue are not the lip's flesh
            pull = np.zeros_like(w) if hard else lip_pull(body, m, v, side)
            if over is not None:
                pull[over[0]] = (lip_pull(body, m, over[1], over[3]).reshape(-1, 3) * over[2]).sum(axis=1)
            if s.name == "tongue" and m.throat is not None:
                pull = throat.sink(body, m, v)                              # it lies down as the mouth opens (else it hides the throat)
            there = turned(m, v, w, 1.0, pull)

            def longest(p):
                return np.max([np.linalg.norm(p[f[:, a]] - p[f[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)

            after = longest(there)
            across = (after > 1.7 * np.maximum(longest(v), 2e-4)) & (after > 0.004)
            if spared is not None:
                across &= ~spared[f].all(axis=1)                            # (the fat's own surface stays whole)
            if across.any() and s.name in MASSES:
                s.f = np.asarray(s.f)[~across]
                log(f"mouth: {s.name}: {int(across.sum())} triangles reaching across the closed mouth taken out")
            s.data3 = np.stack([w, pull], axis=1).astype(np.float32)
        moved += 1
    return moved
