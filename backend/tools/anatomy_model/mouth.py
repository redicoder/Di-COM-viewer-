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
jaw's hinge (through the two condyles) by its weight times the opening (LabLids.hlsl, LabJaw).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import ct_frame, fine_skin, head_layers
from .common import Body, Structure, decimate, level_set, normals_of, surface
from .zones import MM, Face

GUM_MM = 3.0                    # soft tissue over the upper jaw's bone (gum, palate)
LOWER_GUM_MM = 2.0
SPACE_MM = 3.0                  # the mouth's space under the sheet
TOOTH_HU = 1400                 # brighter than this inside the teeth's label: tooth
HALF_WIDTH = 27.0               # mm: half the mouth's width on the skin
OPEN_DEGREES = 18.0             # the jaw's full turn about its hinge (about 35 mm more between the incisors)
FIRM_MM = 5.0                   # flesh this near the mandible goes with it wholly
CROWN_MM = 8.0                  # a crown's height: this far from the tooth row's edge the bones' own teeth are taken out
LIP_ROWS = (6.0, 12.0)          # mm in from the lips' edges: the rows of the strips that give the lips their depth
RIM_MM = 3.0                    # towards the sheet's rim its two sides come to move alike, over this distance
MUCOSA = (186, 106, 104)
GUM = (204, 138, 132)
PALATE = (208, 150, 140)
TONGUE = (176, 104, 100)
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
    axis: np.ndarray | None = None                 # glTF: the axis' direction (to his left)
    weight_grid: Grid | None = None                # the jaw's weights (jaw_weights): their grid,
    weights: np.ndarray = None                     # as solved; `above` as seen from the upper side of the sheet, `below` from the lower
    above: np.ndarray = None
    below: np.ndarray = None
    rim: np.ndarray = None                         # (nz, nx) 0..1: how far the sheet's two sides part there (nothing at its rim and at the mouth's corners)
    rim_only: np.ndarray = None                    # (nz, nx) 0..1: the rim's share of that alone
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
    hi = np.array([s[0] + 106.0, s[1] + 38.0, s[2] + 56.0])
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
    return Mouth(grid, face, w_of, sheet, domain, space, teeth_upper, teeth_lower, tongue, upper, lower, lips=lips, skin_front=skin_front, u_of_x=u_of_x,
                 stomion_mm=s, depth=depth.astype(np.float32), tooth_fields={"upper teeth": field_upper, "lower teeth": field_lower}, ct=ct,
                 rgba_grid=head_grid, rgba=rgba, info=info)


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


def turned(m: Mouth, v: np.ndarray, w: np.ndarray, amount: float = 1.0) -> np.ndarray:
    """Vertices (glTF metres) as they lie with the jaw open by `amount` of its full turn: what Unity's shader does."""
    angle = np.radians(OPEN_DEGREES) * amount * np.asarray(w, np.float64)
    x = np.asarray(v, np.float64) - m.hinge
    c, sn = np.cos(angle)[:, None], np.sin(angle)[:, None]
    return x * c + np.cross(m.axis, x) * sn + m.axis * (x @ m.axis)[:, None] * (1.0 - c) + m.hinge


def with_the_tongue(m: Mouth, zyx_mm: np.ndarray, w: np.ndarray) -> np.ndarray:
    """The jaw weights of points of the tongue (or of the lining on it). The tongue hangs on the mandible and the
    hyoid, not on what lies round it: its front two thirds go with the jaw wholly, its root as the throat's tissue
    does (the weight given), with a smooth step between."""
    zs = m.grid.axis(0)[m.tongue.any(axis=(1, 2))]
    if len(zs) == 0:
        return w
    t = np.clip(((zyx_mm[:, 0] - zs.min()) / max(1.0, zs.max() - zs.min()) - 0.6) / 0.35, 0.0, 1.0)
    return np.maximum(w, 1.0 - t * t * (3.0 - 2.0 * t)).astype(np.float32)


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
    front = ndimage.binary_dilation(m.lips, iterations=3)[iz, ix] & (np.abs(m.u_of_x[ix]) < HALF_WIDTH - 2.0)
    if front.all() or not front.any():
        return None
    first = int(np.nonzero(front & ~np.roll(front, -1))[0][0]) + 1            # the run that is not in front, taken once round
    order = (first + np.arange(len(front))) % len(front)
    order = order[~front[order]]
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


def lining(body: Body, m: Mouth, log=print) -> Structure | None:
    """The mouth's lining: the roof and the floor of the space and what stands wholly on one of them (the gums, the
    lips' inner sides), open where a tooth is the wall and at the lips; and the cheeks' and the throat's wall between
    them (cheek_wall). Over the tongue it is the tongue's own surface, in the tongue's colour (the tongue's mesh is
    under it and shows with the skin layer off): left open there, it let the fat and muscle beside the tongue be seen."""
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
    wall = ~roof & ~floor
    in_slit = wall & (v_mm[:, 1] < height + 0.6) & (v_mm[:, 1] > height - SPACE_MM - 0.6)
    side = np.where(roof, 1.0, np.where(floor, -1.0, np.where(v_mm[:, 1] > height - SPACE_MM / 2, 1.0, -1.0)))
    keep = ~(gone[f].sum(axis=1) >= 2) & ~(in_slit[f].sum(axis=1) >= 2)
    opened = len(f) - int(keep.sum())
    f = f[keep][:, ::-1]                                                      # seen from inside the mouth
    w = weight(body, m, v, side) if m.weight_grid is not None else np.zeros(len(v), np.float32)
    if w.any():
        on_tongue = tongue_wall & (side < 0)
        w[on_tongue] = with_the_tongue(m, v_mm[on_tongue], w[on_tongue])        # the lining on the tongue goes as the tongue goes
        # Whatever is still drawn out when the jaw is open (to more than two and a half times its longest edge) goes too.
        there = turned(m, v, w)

        def longest(p):
            return np.max([np.linalg.norm(p[f[:, a]] - p[f[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)

        drawn = longest(there) > 2.5 * np.maximum(longest(np.asarray(v, np.float64)), 2e-4)
        f = f[~drawn]
        log(f"mouth: lining: {int(drawn.sum())} triangles that would be drawn out across the open mouth taken out")
    used = np.unique(f)
    remap = np.full(len(v), -1, np.int64)
    remap[used] = np.arange(len(used))
    v, v_mm, n, w, f = (v - n * 0.0003)[used], v_mm[used], n[used], w[used], remap[f]
    # Its colour: gum by the teeth, the palate paler, the rest the cheeks' and the floor's red; lighter and darker as the photographs are.
    by_tooth = np.clip(1.0 - g.sample(to_tooth, v_mm) / 6.0, 0.0, 1.0)
    above = g.sample(m.upper.astype(np.float32), v_mm + _zyx(n) * 1.5) > 0.5
    colour = np.tile(np.array(MUCOSA, np.float64), (len(v), 1))
    colour[above] = PALATE
    colour += (np.array(GUM, np.float64) - colour) * by_tooth[:, None]
    colour[tongue_wall[used]] = TONGUE
    colour *= photo_tone(m, v_mm, n)[:, None]
    front = float(np.nanmin(m.skin_front))

    def light(mm):                                                           # the light fails towards the throat
        return 1.0 - 0.6 * np.clip((mm[:, 0] - front) / 80.0, 0.0, 1.0)

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
        v, w = np.concatenate([v, bv]), np.concatenate([w, bw])
        colour, bake = np.concatenate([colour, band_colour]), np.concatenate([bake, band_bake])
    log(f"mouth: lining {len(f)} triangles ({opened} left open at the teeth, the lips and across the slit)"
        + ("" if band is None else f"; the cheeks' and throat's wall {len(band[2])} triangles"))
    out = Structure("lining of the mouth", "skin", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in MUCOSA), bake=bake,
                    albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8), info={"class": "skin", "source": "the mouth's space (mouth.py)"})
    if w.any():
        out.data3 = np.stack([w, np.zeros_like(w)], axis=1).astype(np.float32)
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
        hard = ndimage.gaussian_filter((m.teeth_upper | m.teeth_lower | m.ct["skull"] | m.ct["mandible"]).astype(np.float32), [1.3 / sp for sp in m.grid.spacing])
        crowded = m.grid.sample(hard, at + _zyx(n) * 1.4)
        ys = at[:, 1]
        edge = np.percentile(ys, 2) if name.startswith("upper") else np.percentile(ys, 98)
        root = np.clip((np.abs(ys - edge) - 8.0) / 3.0, 0.0, 1.0)
        albedo = np.array(TOOTH, np.float64)[None, :] + (np.array(ROOT, np.float64) - np.array(TOOTH, np.float64))[None, :] * root[:, None]
        bake = np.tile(np.array([255, 255, 82, 185], np.uint8), (len(v), 1))
        bake[:, 0] = np.round(255 * np.clip(1.2 - 1.7 * crowded, 0.22, 1.0))
        out.append(Structure(name, "skeleton", v, f, tuple(c / 255 for c in TOOTH), bake=bake, albedo=np.round(albedo).astype(np.uint8),
                             info={"class": "bone", "source": "the frozen CT's bright voxels in TotalSegmentator's teeth labels"}))
    return out


def without_crowns(body: Body, m: Mouth, bone: Structure, upper: bool, log=print) -> Structure:
    """A jaw bone without the teeth's crowns. BoneHub's skull and mandible have the teeth in them, as one blurred
    row that does not lie quite where his teeth are; the mouth has every tooth by itself. Where the bone's surface
    is a crown's (within a crown's height of the tooth row's edge, in the row's columns or within 2 mm of a tooth;
    the roots' bone stays) its triangles are taken out, and the teeth stand in their sockets."""
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
    edge = nearest_fill(edge, has)
    q = v_mm[inside]
    at = np.stack([(q[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (q[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    row_edge = ndimage.map_coordinates(edge, at, order=1, mode="nearest")
    row = ndimage.map_coordinates(near(has, (g.spacing[0], g.spacing[2]), 6.0).astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    crown = np.zeros(len(v_mm), bool)
    crown[inside] = ((g.sample(to_tooth, q) < 2.0) | row) & ((q[:, 1] < row_edge + CROWN_MM) if upper else (q[:, 1] > row_edge - CROWN_MM))
    f = np.asarray(bone.f)
    gone = crown[f].sum(axis=1) >= 2
    if gone.any():
        bone.f = f[~gone]
        log(f"mouth: {bone.name}: {int(gone.sum())} triangles of its teeth's crowns taken out (the teeth are their own meshes)")
    return bone


def tongue(body: Body, m: Mouth, log=print) -> Structure | None:
    got = _mesh(body, m.grid, m.tongue, 0.9)
    if got is None:
        return None
    v, v_mm, f, n = got
    colour = np.tile(np.array(TONGUE, np.float64), (len(v), 1)) * photo_tone(m, v_mm, -n)[:, None]
    back = np.clip((v_mm[:, 0] - float(np.nanmin(m.skin_front))) / 80.0, 0.0, 1.0)
    bake = np.tile(np.array([255, 255, 82, 215], np.uint8), (len(v), 1))
    bake[:, 0] = np.round(255 * (1.0 - 0.5 * back))
    return Structure("tongue", "organs", v.astype(np.float32), f.astype(np.uint32), tuple(c / 255 for c in TONGUE), bake=bake,
                     albedo=np.round(np.clip(colour, 0, 255)).astype(np.uint8),
                     info={"class": "organ", "cm3": m.info.get("tongue_cm3"), "source": "TotalSegmentator's tongue label on the frozen CT, grown up to the palate"})


# ---- how the jaw opens -----------------------------------------------------------------------------------------------
def find_hinge(body: Body, m: Mouth):
    """The jaw's axis: through the heads of the two condyles (the mandible's hindmost tops), 3 mm under their crowns.
    Returns a point on it and its direction (towards his left), in glTF metres, or None."""
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
    return right, axis / np.linalg.norm(axis)


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
    # What sits on a bone goes with it: the flesh within 5 mm of the mandible (gum, the chin's pad, the muscles'
    # attachments) is held at 1, within 3 mm of the skull at 0; where the two meet (the joint) each keeps the nearer.
    to_jaw = ndimage.distance_transform_edt(~mandible, sampling=grid.spacing)
    to_skull = ndimage.distance_transform_edt(~skull, sampling=grid.spacing)
    one = (to_jaw <= FIRM_MM) & (to_jaw <= to_skull) & (side != 1) & inside | mandible
    # The skull, the spine and the shoulder girdle hold still; the hyoid hangs between and goes as the tissue takes it.
    zero = ((to_skull <= 3.0) & (to_skull < to_jaw) & (side != -1) & inside) | skull | (bone & (to_jaw > FIRM_MM + 2.0) & ~near(hyoid, grid.spacing, 3.0))
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
    wide = near(m.space, g.spacing, 1.6).astype(np.float32)
    space = g.sample(wide, flat, order=1, cval=0.0).reshape(block.shape) > 0.3
    tongue = g.sample(m.tongue.astype(np.float32), flat, order=1, cval=0.0).reshape(block.shape) > 0.5
    view = lab[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    hit = (space & np.isin(view, loose)) | (tongue & np.isin(view, muscle))
    # Between the lips the space thins to nothing at the skin, but what the labels have there must be parted too.
    height, _ = sheet_at(m, flat)
    at = np.stack([(flat[:, 0] - g.origin[0]) / g.spacing[0] - 0.5, (flat[:, 2] - g.origin[2]) / g.spacing[2] - 0.5], axis=0)
    in_lips = ndimage.map_coordinates(m.lips.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    slit = (in_lips & (np.abs(flat[:, 1] - (height - 1.0)) < 2.4)).reshape(block.shape)
    hit |= slit & np.isin(view, loose)
    # The labels' fat is "what is fat-coloured in the photographs", on voxels of 1.3 x 2 mm: round the tongue and
    # under the palate it marks mucosa, glands and the tongue's own pale edge, and in the opened mouth it stood there
    # as yellow slabs. Within the arch of the teeth and the cheeks' wall, from the palate down to the mouth's
    # floor, there is no fat layer (the lips, in front, keep theirs).
    fat = [o["index"] for o in body.objects if o["layer"] == "fat"]
    inner = (m.rim_only > 0.5) & ~ndimage.binary_dilation(m.lips, iterations=2)
    within = ndimage.map_coordinates(inner.astype(np.float32), at, order=0, mode="constant", cval=0.0) > 0.5
    oral = (within & (flat[:, 1] < height + 14.0) & (flat[:, 1] > height - 34.0)).reshape(block.shape)
    hit |= oral & np.isin(view, fat)
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
    clear_labels(body, m, log)
    grab = to_gltf(body, m.stomion_mm) - face.ey * 0.006                    # on the lower lip
    reach = float(np.linalg.norm(np.cross(grab - m.hinge, m.axis)))
    m.info["unity"] = {"hinge": [float(x) for x in m.hinge], "axis": [float(x) for x in m.axis], "degrees": OPEN_DEGREES,
                       "grab": [float(x) for x in grab], "travel_m": reach * float(np.radians(OPEN_DEGREES))}
    log(f"mouth: hinge at {np.round(m.hinge * 1000, 1)} mm, axis {np.round(m.axis, 3)}; the lower lip lies {reach * 1000:.0f} mm from it "
        f"and travels {reach * np.radians(OPEN_DEGREES) * 1000:.0f} mm")
    return m


# ---- the lips' cut ---------------------------------------------------------------------------------------------------
def cut(v: np.ndarray, f: np.ndarray, body: Body, m: Mouth, log=print):
    """Parts the skin along the lip line, as lids.cut parts the lids. Returns the new vertices and faces, `source`
    (for each new vertex the old vertex whose colour and bake it takes), `side` (+1 on the upper lip, -1 on the
    lower, NaN away from the mouth), a mask of the strips that give the lips' edges their depth, and `anchor` (for
    a strip's inner vertex the edge vertex it hangs from, else -1: it goes as its edge goes)."""
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
        return v.astype(np.float32), f.astype(np.uint32), source, side, np.zeros(k0, bool), np.full(k0, -1, np.int64)
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
    taper = 1.0 - np.clip((np.abs(u) - (span - 7.0)) / 7.0, 0.0, 1.0)        # no depth at the corners
    # The strip's two inner rows: 6 and 12 mm in from the lip's edge (the lip's whole thickness, to where the lining
    # begins), at the sheet's height there (the lower lip's on the space's floor), smoothed along the lip so each
    # row is a curve and not the sheet's every step.
    order = seam_ids[np.argsort(u[seam_ids])]
    rows, new_f = {}, []
    for depth in LIP_ROWS:
        reach = depth * taper[order]
        inward = v[order] - face.ez[None, :] * (reach * MM)[:, None]
        mm = to_mm(body, inward)
        height, there = sheet_at(m, mm)
        height = np.where(there, height, mm[:, 1])
        drop = np.minimum(SPACE_MM, SPACE_MM * reach / 5.0)
        for top in (True, False):
            y = ndimage.gaussian_filter1d(height - (0.0 if top else drop), 2.5, mode="nearest")
            for j, i in enumerate(order):
                rows[(int(i), top, depth)] = k0 + len(new_v)
                new_v.append(inward[j] + np.array([0.0, (y[j] - mm[j, 1]) * MM, 0.0]))
                new_side.append(1.0 if top else -1.0)
                new_src.append(int(i))
                new_margin.append(True)
                new_anchor.append(int(i) if top else int(copy_of[i]))
    grown = np.array(new_v)

    def at(index):
        return v[index] if index < k0 else grown[index - k0]

    for a, b in edges:
        for top in (True, False):
            a0, b0 = (a, b) if top else (int(copy_of[a]), int(copy_of[b]))
            for depth in LIP_ROWS:
                a1, b1 = rows[(a, top, depth)], rows[(b, top, depth)]
                # One face each, looking into the opening: the upper lip's strip down, the lower lip's up.
                normal = np.cross(at(b0) - at(a0), at(b1) - at(a0))
                if (normal @ face.ey) * (-1.0 if top else 1.0) >= 0:
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
    log(f"mouth: lips cut along {len(seam_ids)} vertices, {len(edges)} edges")
    return v.astype(np.float32), f.astype(np.uint32), source, side, margin, anchor


def skin_weights(body: Body, m: Mouth, v: np.ndarray, side: np.ndarray, anchor: np.ndarray) -> np.ndarray:
    """The cut skin's jaw weights (n, 2 for Structure.data3)."""
    w = weight(body, m, v, side)
    hung = anchor >= 0
    w[hung] = w[anchor[hung]]
    return np.stack([w, np.zeros_like(w)], axis=1).astype(np.float32)


# ---- every structure's share in the jaw's turn -----------------------------------------------------------------------
WITH_THE_JAW = ("mandible", "lower teeth")
HELD = ("cranium and maxilla", "upper teeth")
MASSES = ("muscles", "subcutaneous fat", "visceral fat")                                               # meshed through the closed mouth: parted where it parts
AS_ONE = ("hyoid bone", "thyroid cartilage", "cricoid cartilage", "bone (not named)", "eyeball")       # stiff: one weight for the whole of each


def assign(structures: list[Structure], body: Body, m: Mouth, log=print) -> int:
    """Gives every structure near the mouth its jaw weights (Structure.data3: x = the weight; hair: a TEXCOORD_3
    stream, a strand going as its root goes). Triangles that reach across the sheet (a mesh drawn through the
    closed mouth) are taken out: they would be drawn out into sheets when it opens. Returns how many structures move."""
    moved = 0
    for s in structures:
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
        w = weight(body, m, v, np.full(len(v), -1.0) if s.name == "tongue" else None)
        if w.max() < 0.004:
            continue
        if s.name == "subcutaneous fat" and s.streams is None:
            # The fat's outer face lies a millimetre or two under the skin, and where the weights change quickly (the
            # folds under the chin) that is enough for it to move otherwise than the skin and show through it. Its
            # weights are read where the skin over it is, 1.5 mm out along its own normal (not where that reads
            # something else altogether: across the mouth's slit).
            outer = weight(body, m, v + normals_of(np.asarray(s.v, np.float32), np.asarray(s.f)) * 0.0015)
            _, at_mouth = sheet_at(m, to_mm(body, v))
            w = np.where((np.abs(outer - w) < 0.25) & ~at_mouth, outer, w).astype(np.float32)
        if s.name == "tongue":
            w = with_the_tongue(m, to_mm(body, v), w)
        if any(s.name.startswith(k) or s.name.endswith(k) for k in AS_ONE):
            w[:] = float(w.mean())
        if s.streams:
            start = np.asarray(s.streams["TEXCOORD_0"])[:, 1] == 0.0          # a strand's first ring
            strand = np.maximum(np.cumsum(start) - 1, 0) // 2
            first = np.nonzero(start)[0][::2]
            w = w[first][np.minimum(strand, len(first) - 1)]
            s.streams = dict(s.streams, TEXCOORD_3=np.stack([w, np.zeros_like(w)], axis=1).astype(np.float32))
        else:
            # A triangle that the open jaw draws out to more than 1.7 times its length (and to more than 4 mm) joins what
            # the mouth parts: a mesh made through the closed mouth. Left in, it hangs across the open mouth as a sheet.
            f = np.asarray(s.f, np.int64)
            there = turned(m, v, w)

            def longest(p):
                return np.max([np.linalg.norm(p[f[:, a]] - p[f[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))], axis=0)

            after = longest(there)
            across = (after > 1.7 * np.maximum(longest(v), 2e-4)) & (after > 0.004)
            if across.any() and s.name in MASSES:
                s.f = np.asarray(s.f)[~across]
                log(f"mouth: {s.name}: {int(across.sum())} triangles reaching across the closed mouth taken out")
            s.data3 = np.stack([w, np.zeros_like(w)], axis=1).astype(np.float32)
        moved += 1
    return moved
