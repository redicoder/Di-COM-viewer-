"""Every tooth by its name, from his own CT and the row's own shape.

The mouth's teeth (mouth.py) are two meshes, the upper row and the lower, contoured from his CT's own pixels.
Here each row is parted into its teeth and each tooth named by its place in the row:

1. The row's line: seen from above, the crowns' footprint is an arch; its centre line is read from the footprint
   (the middle radius by direction from the arch's middle, smoothed).
2. Where one tooth ends and the next begins: along that line, how much tooth there is per millimetre dips where
   two crowns touch and falls to nothing where a tooth is missing. The dips that are deep enough are the cuts.
3. The names: from the midline outwards the teeth are counted off (central incisor, lateral incisor, canine, two
   premolars, three molars); a space without tooth counts as the teeth that would fill it (by the average crown
   widths, docs/research/head_anatomy_data.md 5.3), and a tooth 9 mm or more long in the row is a molar, so if
   its turn falls on a premolar's place the premolars before it are counted as lost.
4. The whole tooth: the crowns so named are grown down their own roots through the tooth's voxels, and each
   triangle of the row's mesh takes its tooth's name. The shapes stay the CT's own.

A row that does not read as a row of teeth this way is left whole and unnamed: his lower row, whose front teeth
stand in the chin's dense bone and are not parted from it or from one another by the CT.

The names are an ESTIMATE from position: where a tooth was lost long ago and its neighbours closed the space,
the teeth behind it are named one place too far forward. Each tooth says so (info["named"]).

(TotalSegmentator has a task that names teeth, "teeth". It is NOT used: it was trained on the ToothFairy3 data,
whose page shows CC BY-NC-SA, a non-commercial share-alike licence; see LICENSES.md.)
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .common import Body, Structure, normals_of

SLOTS = ["central incisor", "lateral incisor", "canine", "first premolar", "second premolar", "first molar", "second molar", "third molar"]
WIDTH = {"upper": [8.5, 6.5, 7.5, 7.0, 7.0, 10.0, 9.0, 8.5], "lower": [5.0, 5.5, 7.0, 7.0, 7.0, 11.0, 10.5, 10.0]}     # along the row, mm (Wheeler's averages)
CROWN_MM = 8.0                        # the crowns: this far from the row's biting edge
NECK_MM = (6.5, 10.5)                 # the teeth's necks: between these distances from it
FUSED = 1.45                          # a piece longer than this many times its place's tooth is several teeth the CT did not part
BIN_MM = 0.25                         # the profile's step along the row
DIP = 0.72                            # a cut: the profile there is under this share of the lower of the two crowns beside it
MOLAR_MM = 9.0                        # a tooth this long in the row is a molar
MIN_TOOTH_MM = 3.5                    # no tooth is shorter in the row than this
SPACE_MM = 3.0                        # less than this between two teeth's necks is no space
MIN_TRIANGLES = 120


def crown_zone(mask: np.ndarray, spacing, upper: bool, band=(0.0, CROWN_MM)) -> np.ndarray:
    """The row's crowns: its voxels within CROWN_MM of the biting edge above or below them (array order z, y, x; y
    up); or the voxels between two such distances (`band`, mm)."""
    has = mask.any(axis=1)
    if not has.any():
        return mask & False
    index = np.argmax(mask, axis=1) if upper else mask.shape[1] - 1 - np.argmax(mask[:, ::-1, :], axis=1)
    near = ndimage.distance_transform_edt(~has, sampling=(spacing[0], spacing[2]), return_distances=False, return_indices=True)
    edge = index[tuple(near)]                                               # each column's biting edge: its own, or the nearest tooth column's
    rows = np.arange(mask.shape[1])[None, :, None]
    near_edge, far = int(round(band[0] / spacing[1])), int(round(band[1] / spacing[1]))
    away = (rows - edge[:, None, :]) if upper else (edge[:, None, :] - rows)
    return mask & (away >= near_edge) & (away <= far)


def centre_line(z_mm: np.ndarray, x_mm: np.ndarray):
    """The arch's centre line through the crowns' footprint (points given by their z, back, and x, to his left):
    dense points (k, 2: z, x) from the row's end on his right round to its end on his left, and their distance
    along the line (mm)."""
    cz, cx = float(np.percentile(z_mm, 60)), float((x_mm.min() + x_mm.max()) / 2)        # the arch's middle: between its ends, behind its front
    angle = np.degrees(np.arctan2(x_mm - cx, cz - z_mm))                   # 0 = straight forward, positive to his left
    radius = np.hypot(x_mm - cx, cz - z_mm)
    bins = np.arange(-178.0, 180.0, 2.0)
    which = np.digitize(angle, bins)
    centres, mids = [], []
    for k in range(1, len(bins)):
        mine = which == k
        if mine.sum() >= 4:
            centres.append((bins[k - 1] + bins[k]) / 2)
            mids.append((np.percentile(radius[mine], 15) + np.percentile(radius[mine], 85)) / 2)
    centres, mids = np.array(centres), np.array(mids)
    # The arch is open at the back: its angles run from one end to the other without wrapping.
    fine = np.arange(centres.min(), centres.max() + 0.01, 0.25)
    r = ndimage.gaussian_filter1d(np.interp(fine, centres, mids), 14.0, mode="nearest")
    a = np.radians(fine)
    points = np.stack([cz - r * np.cos(a), cx + r * np.sin(a)], axis=1)
    along = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    return points, along


def cuts_of(profile: np.ndarray, step: float = BIN_MM):
    """Where the teeth part, from how much tooth there is along the row. Returns the teeth as (start, end) index
    pairs into the profile, in order; between two of them that do not touch lies a space without tooth."""
    d = ndimage.gaussian_filter1d(profile.astype(np.float64), 0.6 / step)
    if d.max() <= 0:
        return []
    level = 0.06 * np.percentile(d[d > 0], 90)
    solid = d > level
    runs, start = [], None
    for i, on in enumerate(np.append(solid, False)):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if (i - start) * step >= MIN_TOOTH_MM * 0.6:
                runs.append((start, i))
            start = None
    teeth = []
    for a, b in runs:
        seg = d[a:b]
        # The dips within this run of tooth, the shallowest dropped until every one left is a true cut.
        window = max(1, int(1.5 / step))
        dips = [i for i in range(window, len(seg) - window) if seg[i] == seg[i - window:i + window + 1].min() and seg[i] < seg.max()]
        dips = [i for k, i in enumerate(dips) if k == 0 or i - dips[k - 1] > 1]
        while dips:
            edges = [0] + dips + [len(seg)]
            score = []
            for k, i in enumerate(dips):
                left, right = seg[edges[k]:i + 1].max(), seg[i:edges[k + 2]].max()
                short = min(i - edges[k], edges[k + 2] - i) * step < MIN_TOOTH_MM
                score.append(np.inf if short else seg[i] / max(min(left, right), 1e-9))
            worst = int(np.argmax(score))
            if score[worst] <= DIP:
                break
            dips.pop(worst)
        edges = [0] + dips + [len(seg)]
        teeth += [(a + edges[k], a + edges[k + 1]) for k in range(len(edges) - 1)]
    return teeth


def name_side(items: list, jaw: str) -> list:
    """The names of one side's teeth. `items`: from the midline outwards, ("tooth", its length in the row, mm) or
    ("space", its length). Returns a name per tooth item: None for a piece that is several teeth the CT did not
    part (it is counted as the teeth whose widths best add up to its length) and where the count runs past the
    third molar."""
    widths = WIDTH[jaw]
    names, k = [], 0

    def places(length):                                                    # how many teeth from place k on best add up to this length
        sums = np.cumsum(widths[k:])
        return int(np.argmin(np.abs(sums - length))) + 1 if len(sums) else 1

    for kind, length in items:
        if k >= len(widths):
            if kind == "tooth":
                names.append(None)
            continue
        if kind == "space":
            if length >= 0.6 * widths[k]:
                k += places(length)
            continue
        if k in (3, 4) and MOLAR_MM <= length <= FUSED * widths[5] * 0.85:   # a molar where a premolar's turn would be: the premolars before it are lost
            k = 5
        if length > FUSED * widths[k]:
            names.append(None)
            k += max(2, places(length))
            continue
        names.append(SLOTS[k])
        k += 1
    return names


def label_row(m, mask: np.ndarray, upper: bool):
    """A tooth's number per voxel of the row's mask (0 = none) and the teeth: [{number, name, side, length_mm}]."""
    from skimage.segmentation import watershed
    g = m.grid
    crowns = crown_zone(mask, g.spacing, upper)
    zi, yi, xi = np.nonzero(crowns)
    if len(zi) < 200:
        return np.zeros(mask.shape, np.int16), []
    z_mm, x_mm = g.axis(0)[zi], g.axis(2)[xi]
    points, along = centre_line(z_mm, x_mm)
    _, nearest = cKDTree(points).query(np.stack([z_mm, x_mm], axis=1))
    s = along[nearest]
    count = int(np.ceil(along[-1] / BIN_MM)) + 1
    # How much tooth there is along the row, read at the teeth's NECKS: crowns are widest where they touch, so across
    # the crowns the dips between teeth are shallow; a little towards the roots a tooth stands by itself. (Not the
    # lower front teeth: their roots stand in the chin's dense bone, which the CT does not part from them. They come
    # out as one piece, too long for one tooth, and are left unnamed: name_side.)
    ni, _, nxi = np.nonzero(crown_zone(mask, g.spacing, upper, NECK_MM))
    _, at_neck = cKDTree(points).query(np.stack([g.axis(0)[ni], g.axis(2)[nxi]], axis=1))
    profile = np.bincount((along[at_neck] / BIN_MM).astype(int), minlength=count).astype(np.float64)
    found = cuts_of(profile)
    if not found:
        return np.zeros(mask.shape, np.int16), []
    # The midline: where the row's line crosses the face's middle; then the cut between two teeth nearest to it (within 4 mm).
    middle = along[int(np.argmin(np.abs(points[:, 1] - m.stomion_mm[2]) + 1e3 * (points[:, 0] > np.percentile(points[:, 0], 40))))]
    joints = [(found[k][1] + found[k + 1][0]) / 2 * BIN_MM for k in range(len(found) - 1)]      # between two teeth: the middle of what parts them
    if joints:
        best = min(joints, key=lambda j: abs(j - middle))
        if abs(best - middle) < 4.0:
            middle = best
    jaw = "upper" if upper else "lower"
    teeth = []
    for side, wanted in (("right", lambda a, b: (a + b) / 2 * BIN_MM < middle), ("left", lambda a, b: (a + b) / 2 * BIN_MM >= middle)):
        mine = [t for t in found if wanted(*t)]
        mine.sort(key=lambda t: abs((t[0] + t[1]) / 2 * BIN_MM - middle))
        items, last = [], middle
        for a, b in mine:
            near, far = (b, a) if side == "right" else (a, b)                # the tooth's end towards the midline, and its other end
            space = abs(near * BIN_MM - last)
            if space >= SPACE_MM:                                            # (at their necks teeth stand a millimetre or two apart)
                items.append(("space", space))
            items.append(("tooth", (b - a) * BIN_MM))
            last = far * BIN_MM
        named = name_side(items, jaw)
        # The row is believed only if it reads as a row of teeth: a tooth at the midline on each side, no piece that is
        # several teeth unparted, none past the third molar. Else it is left whole and unnamed (wrong names are worse than none).
        if not items or items[0][0] == "space" or None in named:
            return np.zeros(mask.shape, np.int16), []
        for (a, b), name in zip(mine, named):
            teeth.append({"number": len(teeth) + 1, "name": None if name is None else f"{jaw} {side} {name}", "side": side, "length_mm": round((b - a) * BIN_MM, 1), "span": (a, b)})
    # The crowns' voxels take their tooth's number; the numbers then run down the roots through the tooth's own voxels.
    bins = (s / BIN_MM).astype(int)
    number = np.zeros(count + 1, np.int32)
    for t in teeth:
        number[t["span"][0]:t["span"][1]] = t["number"]
    seeds = np.zeros(mask.shape, np.int32)
    seeds[zi, yi, xi] = number[bins]
    labels = watershed(np.zeros(mask.shape, np.uint8), seeds, mask=mask)
    return labels.astype(np.int16), teeth


def split(body: Body, m, rows: list[Structure], log=print) -> list[Structure]:
    """The rows of teeth as their teeth. `rows`: mouth.teeth's two structures (upper teeth, lower teeth)."""
    from .mouth import to_mm
    out, report = [], []
    for row in rows:
        upper = row.name.startswith("upper")
        mask = m.teeth_upper if upper else m.teeth_lower
        labels, teeth = label_row(m, mask, upper)
        if not teeth:
            row.info = dict(row.info, parted="no: the CT does not part these teeth from one another well enough to name them (teeth.py)")
            out.append(row)
            report.append(f"{row.name} (left whole)")
            continue
        # Each voxel near the row takes the number of the nearest numbered voxel (the mesh lies half a voxel outside the mask).
        index = ndimage.distance_transform_edt(labels == 0, sampling=m.grid.spacing, return_distances=False, return_indices=True)
        spread = labels[tuple(index)]
        v = np.asarray(row.v)
        f = np.asarray(row.f, np.int64)
        centres = v[f].mean(axis=1) - normals_of(v, f)[f].mean(axis=1) * 0.0004
        which = m.grid.sample(spread, to_mm(body, centres), order=0).astype(np.int64)
        names = {t["number"]: t for t in teeth}
        sizes = np.bincount(which, minlength=len(teeth) + 2)
        which[(sizes[which] < MIN_TRIANGLES) | ~np.isin(which, [t["number"] for t in teeth if t["name"]])] = 0
        metal = ndimage.maximum(m.ct["hu"], labels, index=[t["number"] for t in teeth])
        for value in np.unique(which):
            mine = f[which == value]
            used = np.unique(mine)
            remap = np.full(len(v), -1, np.int64)
            remap[used] = np.arange(len(used))
            info = dict(row.info)
            if value == 0:
                name = f"{row.name} (not named)"
            else:
                tooth = names[int(value)]
                name = tooth["name"]
                info.update({"named": "by its place in the row: an estimate (a space closed long ago shifts the names behind it)", "length_in_row_mm": tooth["length_mm"]})
                if metal[int(value) - 1] >= 3000:
                    info["metal"] = "a metal restoration (the CT is saturated in it)"
            piece = Structure(name, row.layer, v[used], remap[mine].astype(np.uint32), row.colour, bake=None if row.bake is None else row.bake[used],
                              albedo=None if row.albedo is None else row.albedo[used], info=info)
            if row.data3 is not None:
                piece.data3 = np.asarray(row.data3)[used]
            out.append(piece)
            report.append(f"{name}" + ("" if value == 0 else f" {names[int(value)]['length_mm']} mm" + (" (metal)" if "metal" in info else "")))
    log(f"teeth: {len(report)} pieces: " + "; ".join(report))
    return out
