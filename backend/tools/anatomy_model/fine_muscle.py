"""The muscles' outline at twice the export's detail, straight from the photographs.

The export's labels say where muscle is on voxels of 1.32 x 2 x 1.32 mm: enough to know WHAT lies where, coarse
for a surface a student looks at. Meshed from them, the trunk's and the arms' muscles were lumps with steps, and
patched (a voxel is muscle or it is not; a thin sheet of muscle is neither). The photographs hold the muscles
themselves: dark red against the cream of the fat, the fascia and the tendons, 0.33 mm a pixel, a millimetre a
slice. This module reads every photograph again and keeps, for voxels of 0.66 x 1 x 0.66 mm (the fine skin's own
grid: fine_skin.py), how LIGHT the tissue in each is (the mean of its pixels' r, g, b; 0 where there is none). How
much of a voxel is muscle is read from that when a slab is meshed: a COVERAGE 0..1, from where its lightness lies
between the muscle's and the fat's.

The photographs are not all alike. They were taken in runs: from one run to the next the fat is 5 to 10 %
darker or lighter while the muscle stays as it was, and the fat of the shoulders is darker than the arms' anyway
(measured: muscle 50..57 everywhere, fat 165 at the upper arm's middle, 135 at the shoulder). Read with one pair of
lightnesses for all of them, the fat of the darker runs counted as a fifth muscle, and those photographs' muscles
came out a millimetre or two fatter all round: ledges round the arm and the chest wherever a run began. So each
photograph is read against ITS OWN muscle and fat (`calibrate`): the median lightness of the voxels the labels are
sure are muscle, and of those they are sure are fat, in that photograph. A photograph with a part of the picture
missing (three of them at the chest) is found by its tissue's area against its neighbours' and takes the nearest
whole one's place.

And they do not lie on one another. NOTHING IN THIS PROJECT REGISTERS THE PHOTOGRAPHS TO EACH OTHER, and they come
in runs that are shifted sideways against each other by whole pixels: six times between the hips and the head the
picture jumps by 6 to 14 pixels (2 to 4.6 mm) from one photograph to the next (measured by phase correlation,
`shift_between`; at fine slices 1149, 1462, 1488, 1518, 1626 and 1648). The export, the labels and the skin have
those steps in them too, softened by their coarseness and their smoothing; on a muscle contoured at 0.66 mm each
was a ledge right round the arm and the chest. Registering the stack would move everything built on it. Here the
steps are only SPREAD: every photograph's muscle is slid sideways by the difference between where its run lies
and where the runs lie on average over the 25 photographs either way (`run_offsets`, `spread`), so a step becomes
a slope over five centimetres and, away from a step, nothing moves. (To do properly, once: register the
photographs in prepare_photo_volume.py and build everything on that.)

    fine = extract(body, photos_dir)      # about six minutes; cached as <export>/model/muscle_fine.npy + .json
    fine = load(body)                     # fine_skin.FineOutline or None (memory-mapped)

Colour alone cannot say WHICH dark red thing a voxel is (lung, liver and marrow are dark red too). That stays
the labels' part: `surfaces` gives every muscle object of the labels the muscle-coloured voxels at and within
BAND_MM of its own coarse voxels (the nearest object's, where two meet), never where the labels have bone or an
organ, never where a named structure was taken out of the mass (the head's and the legs' named muscles, the
mouth), and never outside the fine skin. So each object keeps its place and its name and gets its own true
surface: the grooves between the muscles where the fat lies in them, the thin sheets, the tendons' pale ends
left out.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import fine_skin
from .common import Body, keep_big_pieces

CACHE = "muscle_fine.npy"
FACTOR = fine_skin.FACTOR
MUSCLE_L, FAT_L = 70.0, 150.0   # a voxel's lightness (mean of r, g, b): wholly muscle at or under the first, wholly not at or over the
                                # second; used only where a photograph cannot be read against its own muscle and fat (calibrate)
RAMP = (0.17, 0.83)             # between a photograph's own muscle and fat lightness: wholly muscle up to the first share of the way
                                # from the one to the other, wholly not from the second (muscle 49, fat 172: 70 and 151)
SURE = 2                        # coarse voxels inside its class's labels a voxel must lie to count as surely muscle, or surely fat
PARTIAL = 0.025                 # a photograph whose tissue area is off its neighbours' by more than this share is not whole
JUMP_PX, QUIET_PX, PEAK = 5.0, 2.5, 0.1     # a run begins where a photograph lies at least the first off the one before it, its neighbours
                                # no more than the second off theirs (a part that slants through the stack, a foot, the skull's top, drifts
                                # by a pixel or two from every photograph to the next), and the correlation's peak is at least the third
SPREAD = 10.0                   # photographs: a run's step is spread over a Gaussian of this width (a slope over about 5 cm; at the
                                # shoulder three runs of 26 and 30 photographs lie one on another: narrower, they stayed as ripples)
BAND_MM = 4.0                   # an object's fine outline may lie this far outside its coarse voxels (three of them)
WHOLE = "muscles"               # the unnamed mass; the labels' other unnamed masses are meshed with it as one surface:
MASSES = ("muscles of the left arm", "muscles of the right arm")      # they are one flesh, and meshed apart each was closed where the
                                # labels' blocks end, which stood round the arm and the shoulder as ledges
MUSCLE_LIGHT = 52.0             # the export's lightness of muscle (its colours' mean): stands in where a surface has no voxel under it
SKIN_MM = 1.3                   # and never in the outermost of the fine skin
SLAB = 96                       # fine slices meshed at a time
SMOOTH_MM = 0.8                 # blur of the coverage before contouring, within a photograph
ALONG_MM = 2.5                  # and from photograph to photograph: a muscle streaked with fat (the deltoid) reads a little fuller or
                                # leaner from one run of photographs to the next whatever they are read against; blurred over five
                                # photographs, what was a ledge round the shoulder is a slope nobody sees (muscles run along the body)
MIN_PIECE = 0.004               # connected pieces smaller than this share of an object's biggest are dropped (specks of marrow and blood)
TENDON = (0.80, 0.74, 0.62)     # where the photographs are pale under a muscle's surface: tendon and fascia


def extract(body: Body, photos_dir: Path, log=print) -> fine_skin.FineOutline:
    ppv = fine_skin._photo_tools()
    photo = json.loads((body.export / "photo.json").read_text())
    every = int(round(photo["spacing_mm"][2] / ppv.SLICE_MM))
    rows = slice(*photo["crop_photo_px"]["rows"])
    cols = slice(*photo["crop_photo_px"]["cols"])
    top, bottom = photo["slices"]
    files = ppv.index_slices(Path(photos_dir))
    fz, fx = (rows.stop - rows.start) // FACTOR, (cols.stop - cols.start) // FACTOR
    n_slices = bottom - top + 1
    folder = body.export / "model"
    folder.mkdir(parents=True, exist_ok=True)
    cover = np.lib.format.open_memmap(folder / CACHE, mode="w+", dtype=np.uint8, shape=(fz, n_slices, fx))
    missing, shifts, last = [], [], None
    for k in range(n_slices):
        number = bottom - k
        path = files.get(number)
        rgb = None if path is None else ppv.read_photo(path)[rows, cols][:fz * FACTOR, :fx * FACTOR]
        if rgb is not None:
            r, b = rgb[..., 0].astype(np.int16), rgb[..., 2].astype(np.int16)
            tissue = (r > b + 8) & (r > 25)                      # redder than blue (the gelatin), and not the black frame
        if rgb is None or tissue.sum() < 2000:                   # a blank or missing photograph (a joint between the specimen's blocks)
            cover[:, k, :] = 0
            missing.append(k)
            shifts.append([0.0, 0.0, -1.0])
            continue
        light = rgb.astype(np.float32).mean(axis=-1)
        light = np.maximum(light, 1.0) * tissue                  # 0: no tissue
        # How the picture lies against the last one (the grey bar and the number card at its top are not him).
        h, w = (light.shape[0] // 2) * 2, (light.shape[1] // 2) * 2
        small = light[:h, :w].copy()
        small[:80] = 0.0
        small = small.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))        # at half the photographs' size
        shifts.append([0.0, 0.0, -1.0] if last is None else [float(x) for x in shift_between(last, small, 2.0)])
        last = small
        counts = tissue.reshape(fz, FACTOR, fx, FACTOR).sum(axis=(1, 3))
        mean = light.reshape(fz, FACTOR, fx, FACTOR).sum(axis=(1, 3)) / np.maximum(counts, 1)
        mean[counts < FACTOR * FACTOR // 2] = 0.0                # less than half tissue: none
        cover[:, k, :] = np.round(mean).astype(np.uint8)
        if k % 100 == 0:
            log(f"fine muscle outline: photograph {number} ({k + 1}/{n_slices})")
    cover.flush()
    spacing = (ppv.PIXEL_MM * FACTOR, ppv.SLICE_MM, ppv.PIXEL_MM * FACTOR)
    origin = (0.0, (every - ppv.SLICE_MM) / 2.0, 0.0)            # as the fine skin's (fine_skin.extract)
    (folder / (CACHE + ".json")).write_text(json.dumps({"spacing_mm": spacing, "origin_mm": origin, "fallback": missing, "slices": [top, bottom], "factor": FACTOR,
                                                         "shift_px": shifts}))
    log(f"fine muscle outline: {cover.shape} voxels at {spacing} mm, {len(missing)} photographs blank or missing")
    del cover
    return load(body)


def load(body: Body) -> fine_skin.FineOutline | None:
    path = body.export / "model" / CACHE
    meta = path.with_name(CACHE + ".json")
    if not path.exists() or not meta.exists():
        return None
    info = json.loads(meta.read_text())
    cover = np.load(path, mmap_mode="r")
    fallback = np.zeros(cover.shape[1], bool)
    fallback[info["fallback"]] = True
    fine = fine_skin.FineOutline(cover, tuple(info["spacing_mm"]), tuple(info["origin_mm"]), fallback)
    if info.get("shift_px"):
        fine.offsets = run_offsets(np.array(info["shift_px"], np.float64))
        fine.slide = spread(fine.offsets)
    return fine


def shift_between(before: np.ndarray, after: np.ndarray, px: float = 1.0):
    """How far the second picture's content lies from the first's, by phase correlation: (rows, columns) in pixels
    times `px` (the pictures' own pixel in photograph pixels), and the correlation's peak (0..1: 1 the same picture
    moved, near 0 no likeness)."""
    from scipy import fft
    shape = [fft.next_fast_len(int(n), real=True) for n in before.shape]     # (501 x 873 has the primes 167 and 97 in it: forty times slower)
    fa, fb = fft.rfft2(before - before.mean(), s=shape), fft.rfft2(after - after.mean(), s=shape)
    cross = fb * np.conj(fa)
    corr = fft.irfft2(cross / np.maximum(np.abs(cross), 1e-9), s=shape)
    i = np.unravel_index(int(np.argmax(corr)), corr.shape)
    rows, cols = [float(x if x < n // 2 else x - n) * px for x, n in zip(i, shape)]
    return rows, cols, float(corr[i])


def run_offsets(shifts: np.ndarray) -> np.ndarray:
    """Where every photograph's picture lies (rows, columns in photograph pixels, against the first run's): the sum
    of the jumps up to it. `shifts`: per photograph its shift against the one before and the correlation's peak
    (shift_between; peak < 0: blank). A jump is a shift of JUMP_PX or more that stands alone: the photographs on
    either side of it lie within QUIET_PX of their own neighbours."""
    shifts = np.asarray(shifts, np.float64)
    size = np.hypot(shifts[:, 0], shifts[:, 1])
    known = shifts[:, 2] >= 0
    out = np.zeros((len(shifts), 2))
    at = np.zeros(2)
    for k in range(len(shifts)):
        quiet = all(not known[j] or size[j] <= QUIET_PX for j in (k - 2, k - 1, k + 1, k + 2) if 0 <= j < len(shifts))
        if known[k] and size[k] >= JUMP_PX and shifts[k, 2] >= PEAK and quiet:
            at = at + shifts[k, :2]
        out[k] = at
    return out


def spread(offsets: np.ndarray, width: float = SPREAD) -> np.ndarray:
    """How far every photograph's content is slid (rows, columns, photograph pixels) so that the runs' steps become
    slopes: to the offsets' Gaussian mean over its neighbours, from where its own run lies."""
    offsets = np.asarray(offsets, np.float64)
    return ndimage.gaussian_filter1d(offsets, width, axis=0, mode="nearest") - offsets


def running_median(x: np.ndarray, window: int) -> np.ndarray:
    half = window // 2
    padded = np.pad(np.asarray(x, np.float64), half, mode="edge")
    return np.array([np.median(padded[i:i + window]) for i in range(len(x))])


def anchors(muscle: np.ndarray, fat: np.ndarray):
    """Per photograph, the lightness at and under which a voxel is wholly muscle and that at and over which it is
    wholly not, from the photograph's own muscle and fat lightness (NaN where it has too little of one: taken from
    its neighbours; a median of five steadies a single photograph's value and keeps the step where a run begins)."""
    out = []
    for values, default in ((muscle, 49.0), (fat, 172.0)):
        values = np.asarray(values, np.float64)
        known = ~np.isnan(values)
        if known.sum() < 2:
            out.append(np.full(len(values), default))
            continue
        out.append(running_median(np.interp(np.arange(len(values)), np.flatnonzero(known), values[known]), 5))
    m, f = out
    f = np.maximum(f, m + 40.0)                                             # (never nearer than this: the ramp has to have a width)
    return m + RAMP[0] * (f - m), m + RAMP[1] * (f - m)


def partial(tissue: np.ndarray, least: float = 3000.0) -> np.ndarray:
    """Which photographs are not whole: their tissue's area (any unit) is off by more than PARTIAL from what the four
    photographs before and the four after give between them (the middle of their two medians: a part that really
    grows or ends, a shoulder, a fingertip, does so over many photographs)."""
    t = np.asarray(tissue, np.float64)
    out = np.zeros(len(t), bool)
    for k in range(len(t)):
        n = min(4, k, len(t) - 1 - k)                                       # as many on either side (else a slope reads as a step)
        if n < 2 or t[k] < least:
            continue
        before, after = t[k - n:k], t[k + 1:k + 1 + n]
        expected = 0.5 * (np.median(before) + np.median(after))
        out[k] = abs(t[k] - expected) > PARTIAL * max(expected, 1.0)
    return out


def calibrate(body: Body, fine: fine_skin.FineOutline, labels: np.ndarray | None = None, log=print) -> None:
    """Reads every photograph's own muscle and fat lightness from the voxels the labels are sure of, and finds the
    photographs that are not whole; kept on `fine` (lower, upper: per photograph; fallback)."""
    lab = body.labels if labels is None else labels
    kind = np.zeros(256, np.uint8)
    for o in body.objects:
        kind[o["index"]] = {"muscle": 1, "fat": 2}.get(o["layer"], 0)
    kinds = kind[lab]
    sure = [ndimage.binary_erosion(kinds == c, iterations=SURE) for c in (1, 2)]
    fz, ny, fx = fine.cover.shape
    step = int(round(body.spacing[0] / fine.spacing[0]))
    step_y = int(round(body.spacing[1] / fine.spacing[1]))
    nz, nx = min(lab.shape[0], fz // step), min(lab.shape[2], fx // step)
    muscle, fat, tissue = np.full(ny, np.nan), np.full(ny, np.nan), np.zeros(ny)
    for k in range(ny):
        kc = min(lab.shape[1] - 1, k // step_y)
        light = np.asarray(fine.cover[:nz * step:step, k, :nx * step:step])     # one fine voxel of each coarse one
        there = light > 0
        tissue[k] = float(there.sum())
        for values, mask in ((muscle, sure[0]), (fat, sure[1])):
            mine = light[mask[:nz, kc, :nx] & there]
            if len(mine) >= 150:
                values[k] = float(np.median(mine))
    fine.lower, fine.upper = anchors(muscle, fat)
    broken = partial(tissue) & ~fine.fallback
    fine.fallback = fine.fallback | broken
    log(f"fine muscles: every photograph read against its own muscle and fat (muscle {np.nanmin(muscle):.0f}..{np.nanmax(muscle):.0f}, "
        f"fat {np.nanmin(fat):.0f}..{np.nanmax(fat):.0f}); {int(broken.sum())} photographs not whole: {np.flatnonzero(broken).tolist()[:40]}")


def owners(labels: np.ndarray, ids, soft, taken: np.ndarray | None, spacing, band_mm: float = BAND_MM) -> np.ndarray:
    """For every coarse voxel the muscle object whose fine outline may pass through it (0: none): the object the
    voxel is labelled as; else the nearest of them within `band_mm`, where the labels have nothing, fat or skin
    (`soft`); never where they have anything else (bone, an organ), nor where `taken` says a named structure was
    taken out of the mass."""
    mine = np.isin(labels, ids)
    if not mine.any():
        return np.zeros(labels.shape, labels.dtype)
    away, nearest = ndimage.distance_transform_edt(~mine, sampling=spacing, return_indices=True)
    out = np.where(away <= band_mm, labels[tuple(nearest)], 0).astype(labels.dtype)
    blocked = (labels != 0) & ~mine & ~np.isin(labels, soft)
    if taken is not None:
        blocked |= taken
    out[blocked] = 0
    return out


def _slab(fine: fine_skin.FineOutline, a: int, b: int) -> np.ndarray:
    """Slices a..b-1 as muscle coverage, float32 0..1: from each voxel's lightness between its photograph's own
    muscle and fat (calibrate; MUSCLE_L and FAT_L without it). A blank photograph, or one that is not whole, takes
    the nearest good one's."""
    lower, upper = getattr(fine, "lower", None), getattr(fine, "upper", None)
    slide = getattr(fine, "slide", None)
    good = np.nonzero(~fine.fallback)[0]
    block = np.empty((fine.cover.shape[0], b - a, fine.cover.shape[2]), np.float32)
    for k in range(a, b):
        source = k
        if fine.fallback[k] and len(good):
            source = int(good[np.argmin(np.abs(good - k))])
        light = np.asarray(fine.cover[:, source, :], np.float32)
        lo, hi = (MUSCLE_L, FAT_L) if lower is None else (float(lower[source]), float(upper[source]))
        share = np.clip((hi - light) / (hi - lo), 0.0, 1.0) * (light > 0)
        if slide is not None and np.abs(slide[source]).max() > 0.05:        # a run's step, spread: this photograph's share of the slope
            share = ndimage.shift(share, slide[source] / FACTOR, order=1, mode="constant", cval=0.0)
        block[:, k - a, :] = share
    return block


def surfaces(body: Body, fine: fine_skin.FineOutline, objs: list[dict], original: np.ndarray | None = None, sigma_mm: float = SMOOTH_MM, log=print,
             only: tuple | None = None):
    """[(object, vertices in the body's millimetres (z, y, x), faces)] for the muscle objects `objs` of the labels:
    each object's fine surface (see the module's text). `original`: the labels as the export has them, before
    anything was taken out of them (what was muscle there and is nothing now is not given back). `only`: the fine
    slices (first, last) to do, for a look at a part of him."""
    from skimage import measure
    from .skin import weld, WELD_MM
    lab = body.labels
    if getattr(fine, "lower", None) is None:
        calibrate(body, fine, original, log)
    ids = [int(o["index"]) for o in objs]
    by_id = {int(o["index"]): o for o in objs}
    soft = [int(o["index"]) for o in body.objects if o["layer"] in ("fat", "skin")]
    spacing = np.array(fine.spacing)
    fz, ny, fx = fine.cover.shape
    step = int(round(body.spacing[0] / spacing[0]))
    step_y = int(round(body.spacing[1] / spacing[1]))
    sigma = [sigma_mm / spacing[0], ALONG_MM / spacing[1], sigma_mm / spacing[2]]
    pad = int(np.ceil(4 * sigma[1])) + 1
    skin = fine_skin.load(body)
    rounds = max(1, int(round(SKIN_MM / spacing[0])))
    cross = ndimage.generate_binary_structure(2, 1)
    whole = next((int(o["index"]) for o in objs if o["name"] == WHOLE), None)
    merged = [int(o["index"]) for o in objs if o["name"] in MASSES] if whole is not None else []
    verts, faces, offsets = {i: [] for i in ids}, {i: [] for i in ids}, {i: 0 for i in ids}
    first, last = (0, ny - 1) if only is None else (max(0, int(only[0])), min(ny - 1, int(only[1])))
    for y0 in range(first, last, SLAB):
        y1 = min(last, y0 + SLAB)                                         # cells between fine slices y0 .. y1
        a, b = max(0, y0 - pad), min(ny, y1 + 1 + pad)
        # The owners on the coarse grid (with two coarse slices to spare either way), brought to the fine slab.
        ca, cb = max(0, a // step_y - 2), min(lab.shape[1], (b - 1) // step_y + 3)
        coarse = lab[:, ca:cb, :]
        if not np.isin(coarse, ids).any():
            continue
        taken = None if original is None else np.isin(original[:, ca:cb, :], ids) & (coarse != original[:, ca:cb, :])
        own = owners(coarse, ids, soft, taken, body.spacing)
        if merged:
            own[np.isin(own, merged)] = whole
        own = np.repeat(np.repeat(np.repeat(own, step, axis=0), step_y, axis=1), step, axis=2)
        own = own[:, a - ca * step_y:b - ca * step_y, :]
        own = np.pad(own, ((0, max(0, fz - own.shape[0])), (0, 0), (0, max(0, fx - own.shape[2]))))[:fz, :, :fx]
        cover = _slab(fine, a, b)
        if skin is not None:                                              # not in the skin, nor outside it
            under = np.asarray(skin.cover[:, a:b, :]) > 127
            for k in range(under.shape[1]):
                under[:, k, :] = ndimage.binary_erosion(under[:, k, :], cross, iterations=rounds)
            cover *= under
        for i in np.unique(own):
            if i == 0:
                continue
            mine = own == i
            zs, xs = np.nonzero(mine.any(axis=1))
            z0, z1, x0, x1 = max(0, zs.min() - 6), min(fz, zs.max() + 7), max(0, xs.min() - 6), min(fx, xs.max() + 7)
            field = ndimage.gaussian_filter(cover[z0:z1, :, x0:x1] * mine[z0:z1, :, x0:x1], sigma)[:, y0 - a:y1 + 1 - a, :]
            if field.max() <= 0.5:
                continue
            field = np.pad(field, ((1, 1), (1 if y0 == 0 else 0, 1 if y1 == ny - 1 else 0), (1, 1)))
            v, f, _, _ = measure.marching_cubes(field, 0.5)
            v[:, 0] += z0 - 1
            v[:, 2] += x0 - 1
            v[:, 1] += y0 - (1 if y0 == 0 else 0)
            verts[i].append(v)
            faces[i].append(f + offsets[i])
            offsets[i] += len(v)
        log(f"fine muscles: slices {y0}..{y1}: " + ", ".join(f"{by_id[i]['name']} {sum(len(f) for f in faces[i])}" for i in ids if faces[i])[:300])
    out = []
    for i in ids:
        if not faces[i]:
            continue
        v, f = weld(np.concatenate(verts[i]), np.concatenate(faces[i]), WELD_MM)
        v, f = keep_big_pieces(v, f, MIN_PIECE)
        if len(f) >= 8:
            out.append((by_id[i], (np.array(fine.origin_mm) + (v + 0.5) * spacing).astype(np.float32), f))
    return out


def tone(body: Body, v_mm: np.ndarray, n_zyx: np.ndarray, base: tuple, f: np.ndarray | None = None, depth_mm: float = 2.5) -> np.ndarray:
    """Per-vertex colour (uint8) of a muscle's surface from the export's own colours a little under it: the
    structure's colour, lighter and darker as the photographs are there, and towards the tendon's where they are
    pale (a tendon's end, a sheet of fascia over the muscle). v_mm: vertices in the body's millimetres (z, y, x);
    n_zyx: their outward normals in the same order; f: the faces (given, the lightness is evened out over each
    vertex's neighbourhood: read voxel by voxel, 1.3 x 2 mm, it speckled, and banded where a run of photographs begins)."""
    dz, dy, dx = body.dims
    rgba = np.memmap(body.export / "body.raw", np.uint8, "r", shape=(dz, dy, dx, 4))
    inside = (np.asarray(v_mm, np.float64) - np.asarray(n_zyx, np.float64) * depth_mm) / np.array(body.spacing) - 0.5
    index = np.clip(np.round(inside).astype(np.int64), 0, np.array(body.dims) - 1)
    c = np.asarray(rgba[index[:, 0], index[:, 1], index[:, 2]], np.float32)
    seen = c[:, 3] > 0
    light = np.where(seen, c[:, :3].mean(axis=1), MUSCLE_LIGHT)
    if f is not None and len(f):
        from scipy import sparse
        f = np.asarray(f, np.int64)
        edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        joined = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(light), len(light))).tocsr()
        joined = joined + joined.T + sparse.identity(len(light), format="csr")
        degree = np.asarray(joined.sum(axis=1)).ravel()
        for _ in range(6):
            light = (joined @ light) / degree
    # Against the structure's own middle lightness (2.5 mm under a surface the export's coarse voxels are part fat: read
    # against the muscle's own lightness, the whole surface came out a shade too light beside the legs' muscles).
    middle = float(np.clip(np.median(light[seen]) if seen.any() else MUSCLE_LIGHT, 45.0, 95.0))
    shade = np.clip(light / middle, 0.75, 1.25)
    pale = np.clip((light - 2.1 * middle) / (1.2 * middle), 0.0, 1.0)      # more than twice as light: tendon, fascia
    colour = np.array(base, np.float64)[None, :] * shade[:, None]
    colour += (np.array(TENDON, np.float64)[None, :] - colour) * (0.7 * pale)[:, None]
    return np.round(np.clip(colour, 0.0, 1.0) * 255.0).astype(np.uint8)
