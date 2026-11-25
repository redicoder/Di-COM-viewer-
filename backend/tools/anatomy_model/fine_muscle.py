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

(The photographs also come in runs that are shifted sideways against each other, 2 to 4.6 mm, six times between
the hips and the head: found here, because on a muscle contoured at 0.66 mm each was a ledge right round the body.
That is put right where the photographs are read: tools/register_photos.py, prepare_photo_volume.read_photo.)

    fine = extract(body, photos_dir)      # about six minutes; cached as <export>/model/muscle_fine.npy + .json
    fine = load(body)                     # fine_skin.FineOutline or None (memory-mapped)

Colour alone cannot say WHICH dark red thing a voxel is (lung, liver and marrow are dark red too). That stays
the labels' part: `surfaces` gives every muscle object of the labels the muscle-coloured voxels at and within
BAND_MM of its own coarse voxels (the nearest object's, where two meet), never where the labels have bone or an
organ, never where a named structure was taken out of the mass (the head's and the legs' named muscles, the
mouth), and never outside the fine skin. So each object keeps its place and its name and gets its own true
surface: the grooves between the muscles where the fat lies in them, the thin sheets, the tendons' pale ends
left out.

Three things the colour cannot be left to decide (2026-11-25, when the layers under the skin were brought up to
the skin's standard; docs/research/under_layers.md):

- HOW NEAR THE SKIN a muscle's surface may begin. It was cut 1.3 mm under the skin's outline, and what came
  nearer the skin than the layers' rule allows (head_layers.under_skin_everywhere: under the fat's surface too
  since the fat is the skin's outline moved in) was pressed in afterwards, vertex by vertex. Where a muscle lies
  shallow over a whole stretch (the arms' outer sides, where the photographs cut the arm and there is next to no
  fat) every vertex was pressed by its own lack, 12 271 of the mass's: a relief of small pits. Now the coverage
  itself ends UNDER_MM under the outline, measured in space (under_limit), and the surface comes out there as
  one smooth level, as the fat's does; the rule afterwards finds little to move (2663, most of them in the
  feet). (The arms' "lace" was something else: each arm's muscle in the model twice. layers.build.)
- THIN SHEETS. A sheet of muscle a voxel or two thick (the muscles over the ribs, the flat muscles of the
  belly's side) blurs to less than half and is not contoured: the chest's side was in rags, with the ribs
  showing. Where an object's own labels are thin (thin_parts), every voxel of them that holds tissue counts as
  the object, whatever its colour.
- APONEUROSES. The rectus sheath is a labelled object of the muscles' layer and is pale by nature: read by
  colour, three quarters of it were left out, and the belly's wall stood open along the midline and across the
  rectus. The objects named in SHEETS are taken as their labels have them, whole, and coloured as tendon.
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
BAND_MM = 4.0                   # an object's fine outline may lie this far outside its coarse voxels (three of them)
WHOLE = "muscles"               # the unnamed mass; the labels' other unnamed masses are meshed with it as one surface:
MASSES = ("muscles of the left arm", "muscles of the right arm")      # they are one flesh, and meshed apart each was closed where the
                                # labels' blocks end, which stood round the arm and the shoulder as ledges
MUSCLE_LIGHT = 52.0             # the export's lightness of muscle (its colours' mean): stands in where a surface has no voxel under it
SKIN_MM = 1.3                   # and never in the outermost of the fine skin: in the feet and the head (their own rules see to the rest)
UNDER_MM = 3.6                  # ... and between them not nearer the skin's outline than this: under the fat's surface (1.8 mm under
                                # the outline, contoured at 2.5) and the least the layers' rule asks there (head_layers.COARSE_MM + UNDER_FAT_MM)
UNDER_FROM_MM, UNDER_TO_MM = 190.0, 1640.0      # (fine_skin.TOES_MM, fine_skin.BODY_MM)
RAMP_MM = 1.0                   # the coverage falls to nothing over this, round UNDER_MM
SHEETS = ("rectus sheath",)     # aponeuroses: pale by nature, taken as the labels have them
THIN_PIECE = 12                 # thin parts of an object's labels smaller than this many voxels are corners of its thick parts
SHEET_PIECE = 60                # scraps of an aponeurosis's labels smaller than this many voxels (a square centimetre and a half of sheet) are left out
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
    missing = []
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
            continue
        light = rgb.astype(np.float32).mean(axis=-1)
        light = np.maximum(light, 1.0) * tissue                  # 0: no tissue
        counts = tissue.reshape(fz, FACTOR, fx, FACTOR).sum(axis=(1, 3))
        mean = light.reshape(fz, FACTOR, fx, FACTOR).sum(axis=(1, 3)) / np.maximum(counts, 1)
        mean[counts < FACTOR * FACTOR // 2] = 0.0                # less than half tissue: none
        cover[:, k, :] = np.round(mean).astype(np.uint8)
        if k % 100 == 0:
            log(f"fine muscle outline: photograph {number} ({k + 1}/{n_slices})")
    cover.flush()
    spacing = (ppv.PIXEL_MM * FACTOR, ppv.SLICE_MM, ppv.PIXEL_MM * FACTOR)
    origin = (0.0, (every - ppv.SLICE_MM) / 2.0, 0.0)            # as the fine skin's (fine_skin.extract)
    (folder / (CACHE + ".json")).write_text(json.dumps({"spacing_mm": spacing, "origin_mm": origin, "fallback": missing, "slices": [top, bottom], "factor": FACTOR}))
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
    return fine_skin.FineOutline(cover, tuple(info["spacing_mm"]), tuple(info["origin_mm"]), fallback)


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


def _slab(fine: fine_skin.FineOutline, a: int, b: int, with_tissue: bool = False):
    """Slices a..b-1 as muscle coverage, float32 0..1: from each voxel's lightness between its photograph's own
    muscle and fat (calibrate; MUSCLE_L and FAT_L without it). A blank photograph, or one that is not whole, takes
    the nearest good one's. `with_tissue`: also where there is tissue at all (bool), as a second array."""
    lower, upper = getattr(fine, "lower", None), getattr(fine, "upper", None)
    good = np.nonzero(~fine.fallback)[0]
    block = np.empty((fine.cover.shape[0], b - a, fine.cover.shape[2]), np.float32)
    tissue = np.zeros(block.shape, bool) if with_tissue else None
    for k in range(a, b):
        source = k
        if fine.fallback[k] and len(good):
            source = int(good[np.argmin(np.abs(good - k))])
        light = np.asarray(fine.cover[:, source, :], np.float32)
        lo, hi = (MUSCLE_L, FAT_L) if lower is None else (float(lower[source]), float(upper[source]))
        block[:, k - a, :] = np.clip((hi - light) / (hi - lo), 0.0, 1.0) * (light > 0)
        if with_tissue:
            tissue[:, k - a, :] = light > 0
    return (block, tissue) if with_tissue else block


def under_limit(inside: np.ndarray, spacing, under_mm, ramp_mm: float = RAMP_MM) -> np.ndarray:
    """How much of each voxel of a block (z, y, x) may be muscle, by its depth under the skin's outline (`inside`:
    bool, what the outline encloses): 0 nearer the outline than `under_mm` (a number, or one for every slice y),
    1 deeper, falling over `ramp_mm` round it. The depth is measured in space, on blocks of 2 x 2 x 2 voxels (a
    block counts as inside when all of it is; the block's faces are taken for the body going on: only the outline
    inside the block counts), good to a third of a millimetre."""
    inside = np.asarray(inside, bool)
    sp = np.asarray(spacing, np.float64)
    nz, ny, nx = (n // 2 for n in inside.shape)
    blocks = inside[:2 * nz, :2 * ny, :2 * nx].reshape(nz, 2, ny, 2, nx, 2).all(axis=(1, 3, 5))
    if blocks.all():
        return np.ones(inside.shape, np.float32) * inside
    # From a block's middle to the middle of the nearest block that is not wholly inside: the outline runs somewhere
    # through that block, through its middle on the average.
    depth = ndimage.distance_transform_edt(blocks, sampling=2.0 * sp)
    depth = ndimage.zoom(depth.astype(np.float32), 2, order=1, grid_mode=True, mode="nearest")
    depth = np.pad(depth, [(0, max(0, n - m)) for n, m in zip(inside.shape, depth.shape)], mode="edge")[:inside.shape[0], :inside.shape[1], :inside.shape[2]]
    least = np.broadcast_to(np.asarray(under_mm, np.float32), (inside.shape[1],))[None, :, None]
    return np.clip((depth - (least - ramp_mm / 2.0)) / ramp_mm, 0.0, 1.0).astype(np.float32) * inside


def thin_parts(mask: np.ndarray, least: int = THIN_PIECE) -> np.ndarray:
    """The thin parts of an object's voxels (bool, z, y, x): where no cube of three voxels fits into it (sheets one
    or two voxels thick; three or four where they run aslant), without the specks that are only the sharp
    ridges of its thick parts (connected pieces smaller than `least` voxels)."""
    mask = np.asarray(mask, bool)
    thin = mask & ~ndimage.binary_opening(mask, structure=np.ones((3, 3, 3), bool))
    if not thin.any():
        return thin
    parts, count = ndimage.label(thin, structure=np.ones((3, 3, 3), bool))
    sizes = ndimage.sum(thin, parts, range(1, count + 1))
    return np.isin(parts, 1 + np.flatnonzero(np.asarray(sizes) >= least))


def tidy_sheet(mask: np.ndarray, least: int = SHEET_PIECE) -> np.ndarray:
    """An aponeurosis's voxels as the labels have them (bool, z, y, x), a little tidier: gaps of a voxel closed,
    and scraps smaller than `least` voxels left out (a sheet a voxel thick is labelled in rags at its edges, and
    every scrap of it was a white fleck on the belly)."""
    mask = np.asarray(mask, bool)
    if not mask.any():
        return mask
    box = np.ones((3, 3, 3), bool)
    closed = ndimage.binary_closing(np.pad(mask, 1), structure=box)[1:-1, 1:-1, 1:-1] | mask
    parts, count = ndimage.label(closed, structure=box)
    sizes = np.asarray(ndimage.sum(closed, parts, range(1, count + 1)))
    return np.isin(parts, 1 + np.flatnonzero(sizes >= least))


def counted(cover: np.ndarray, tissue: np.ndarray, mine: np.ndarray, thin: np.ndarray, own: np.ndarray | None = None) -> np.ndarray:
    """What of a block counts as one object's (float32 0..1), before it is blurred and contoured: the muscle-red
    coverage where the object may be (`mine`: at and near its labels), and every voxel of tissue where its own
    labels are thin. `own` (its own labels' voxels) given: an aponeurosis, taken whole as the labels have it."""
    if own is not None:
        return (tissue * own).astype(np.float32)
    return np.maximum(cover * mine, tissue * thin).astype(np.float32)


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
    heights = fine.origin_mm[1] + (np.arange(ny) + 0.5) * spacing[1]
    under_mm = np.where((heights >= UNDER_FROM_MM) & (heights < UNDER_TO_MM), UNDER_MM, SKIN_MM).astype(np.float32)
    sheets = {int(o["index"]) for o in objs if o["name"] in SHEETS}
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
        labelled = np.where(np.isin(coarse, ids), coarse, 0)              # the objects' own voxels, without the band round them
        if merged:
            own[np.isin(own, merged)] = whole
            labelled[np.isin(labelled, merged)] = whole

        def to_fine(block):                                               # the export's voxels of this slab on the fine grid
            block = np.repeat(np.repeat(np.repeat(block, step, axis=0), step_y, axis=1), step, axis=2)
            block = block[:, a - ca * step_y:b - ca * step_y, :]
            return np.pad(block, ((0, max(0, fz - block.shape[0])), (0, 0), (0, max(0, fx - block.shape[2]))))[:fz, :, :fx]

        own = to_fine(own)
        cover, tissue = _slab(fine, a, b, with_tissue=True)
        tissue = tissue.astype(np.float32)
        if skin is not None:                                              # not in the skin, nor nearer it than a muscle may lie
            limit = under_limit(np.asarray(skin.cover[:, a:b, :]) > 127, spacing, under_mm[a:b])
            cover *= limit
            tissue *= limit
        for i in np.unique(own):
            if i == 0:
                continue
            mine = own == i
            zs, xs = np.nonzero(mine.any(axis=1))
            z0, z1, x0, x1 = max(0, zs.min() - 6), min(fz, zs.max() + 7), max(0, xs.min() - 6), min(fx, xs.max() + 7)
            box = (slice(z0, z1), slice(None), slice(x0, x1))
            if i in sheets:
                mass = counted(cover[box], tissue[box], mine[box], None, to_fine(tidy_sheet(labelled == i))[box])
            else:
                mass = counted(cover[box], tissue[box], mine[box], to_fine(thin_parts(labelled == i))[box])
            field = ndimage.gaussian_filter(mass, sigma)[:, y0 - a:y1 + 1 - a, :]
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
