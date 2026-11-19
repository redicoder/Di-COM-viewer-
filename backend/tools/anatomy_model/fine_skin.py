"""The body's outline at twice the export's detail, straight from the photographs, for the skin's surface.

The whole-body export averages 4 x 4 photo pixels and uses every second photograph (1.32 x 2 x 1.32 mm): enough
for what lies inside, coarse for the skin a student looks at (the face, the fingers, the toes). The photographs
hold 0.33 mm pixels a millimetre apart. This module reads every photograph again at 2 x 2 pixels (0.66 mm) and
keeps only what the skin needs: how much of each voxel is body. The export's own cleaned mask guides it (which
pieces are him and not the label card or the gelatin), so each photograph only refines the outline within a few
millimetres of the coarse one, and a blank photograph at a joint between the specimen's blocks falls back to the
coarse outline.

THE TOES are read otherwise (toes_outline). The export's mask has the five toes of a foot as one lump (its voxels
are 1.3 mm, the clefts between toes that lie side by side a third of that), and the lump was this outline's guide:
whatever lay more than 2.6 mm inside it was taken for body, the clefts with it, and where the toes' tips are (less
tissue than the lump has) the photograph was not believed at all. A foot has no hollows, so over the lowest
TOES_MM (the feet, to above the ankles) the outline is simply the tissue the photograph shows, and what is gelatin
between two parts of him is a cleft; and a single photograph's flaw is taken out by its neighbours (steady).
That also leaves out what is not him: a thin tube lies along the back of the left foot and up the shin, a few
millimetres off the skin, and the export's mask has it and the frost round it as body (the old outline stood over
it like a tent, 6 to 8 mm off the skin at the ankle). A cleft thinner than two voxels would be lost again when the
outline is blurred and contoured, so the thin ones are widened to a millimetre and a half (half a millimetre off
each toe's side). The last TOES_BLEND photographs hand over to the rule for the rest of him by moving the edge
from the one outline to the other (passed_over), and a seam between two photographs (the specimen's blocks meet
at the ankles) is bridged the same way (seams, bridge).

What is placed in him from another source (the bones, from the CT) is kept under this outline by drawn_under.

The result is a COVERAGE, not a yes/no mask. The export's own tissue test (red well above blue) says which pixels
are body; the ring of pixels just outside them is part skin and part blue gelatin, and how red against blue each
is says how much. A yes/no outline moves in whole pixels from one photograph to the next and the surface built
from it is terraced like a map's contour lines; the ring places the outline within a pixel. Only that one ring is
measured: the frost round the frozen body is pale blue too, and counted further out it grows into warts.

    fine = extract(body, photos_dir)      # about twelve minutes; cached as <export>/model/skin_fine.npy + .json
    fine = load(body)                     # FineOutline or None (memory-mapped: slabs are read as they are used)

FineOutline.cover is uint8 0..255 (rows front to back, slices bottom to top, columns to the patient's left): the
Body's array order z, y, x, with spacing (0.66, 1.0, 0.66) mm. Its voxel (z, y, x) has its centre at
origin_mm + (index + 0.5) * spacing in the body's millimetres (array order).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from .common import Body

FACTOR = 2                      # photo pixels per fine voxel, in the plane: the outline is found at the photographs'
                                # own 0.33 mm pixels and kept as each 0.66 mm voxel's share of body
BAND = 4                        # fine voxels (2.6 mm) the fine outline may differ from the coarse one, either way
GEL, TISSUE = -130.0, 60.0      # red minus blue of the gelatin and of the tissue at the surface: a ring pixel's
                                # share of tissue is where its own value lies between the two
TOES_MM = 190.0                 # the lowest millimetres of him: the feet to above the ankles, read by toes_outline
TOES_BLEND = 24                 # the last of those photographs pass over to the rule for the rest of him
CLEFTS_MM = 62.0                # the lowest of them have the toes in them: there the clefts between toes are looked for
PIECE_PX = 60                   # (toes) a piece of tissue smaller than this many photo pixels is not kept (6.5 mm2)
CLEFT_PX = 4                    # (toes) a channel of gelatin between two parts of him narrower than 2 x this + 1 pixels is a cleft
CLEFT_MIN_PX = 24               # ... if it has at least this many pixels (smaller: a speck, filled)
CLEFT_NARROW_PX, CLEFT_WIDEN_PX = 2, 2      # a cleft no wider than 2 x the first is widened by the second on either side
CACHE = "skin_fine.npy"


@dataclass
class FineOutline:
    cover: np.ndarray           # uint8 (z, y, x): how much of the voxel is body, 0..255
    spacing: tuple              # mm, array order z, y, x
    origin_mm: tuple            # array order z, y, x
    fallback: np.ndarray        # bool per y: the photograph was unusable there, the coarse outline stands in

    def slab(self, y0: int, y1: int) -> np.ndarray:
        """Slices y0..y1-1 as float32 0..1."""
        return np.asarray(self.cover[:, y0:y1, :], np.float32) * (1.0 / 255.0)


def _photo_tools():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import prepare_photo_volume as ppv
    return ppv


def ring_coverage(rgb: np.ndarray) -> np.ndarray:
    """How much of a pixel beside the tissue is tissue, 0..1, from how red against blue it is (the gelatin is blue)."""
    d = rgb[..., 0].astype(np.float32) - rgb[..., 2].astype(np.float32)
    return np.clip((d - GEL) / (TISSUE - GEL), 0.0, 1.0)


def _disc(radius: int) -> np.ndarray:
    y, x = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    return (x * x + y * y) <= radius * radius + 0.5


def toes_outline(rgb: np.ndarray, allowed: np.ndarray | None = None, clefts: bool = True):
    """A photograph through a foot -> (body, carved): what is him (bool, the photograph's pixels) and the pixels
    taken off him to widen the thin clefts between his toes. See the module's text.

    Tissue is redder than blue (the export's own test) and not greener than red: gelatin is blue-green, and so is
    the frost on him and whatever else lies against his skin (the tube on the left foot); a line of gelatin one
    pixel wide between two toes, mixed with the pale skin on either side, is still greener than red when it is no
    longer bluer than red. With `clefts` (the photographs through the toes) the holes in him that are gelatin
    stay open (a cleft between two toes that touch at both ends), thin channels of gelatin between parts of him
    are clefts, and the thinnest are widened; without, every hole is filled (above the toes a foot has none: what
    reads as gelatin inside it there is a blue-green stain on the cut face, which some photographs have)."""
    r, g, b = (rgb[..., c].astype(np.int16) for c in range(3))
    gelatin = (b > r - 8) | (g > r + 4)
    body = (r > b + 8) & (r > 45) & ~gelatin
    if allowed is not None:
        body &= allowed
    body = ndimage.binary_opening(body, iterations=2)          # frost and threads, a pixel or two wide
    parts, count = ndimage.label(body)
    if count:
        sizes = ndimage.sum(body, parts, range(1, count + 1))
        body = np.isin(parts, 1 + np.flatnonzero(sizes >= PIECE_PX))
    carved = np.zeros(body.shape, bool)
    if not clefts:
        return ndimage.binary_fill_holes(body), carved
    # Each foot by itself, in its own box of the picture (the work below is slow on a whole photograph).
    margin = 3 * CLEFT_PX + 6
    columns = np.flatnonzero(body.any(axis=0))
    if len(columns) == 0:
        return body, carved
    for run in np.split(columns, np.flatnonzero(np.diff(columns) > 2 * margin) + 1):
        c0, c1 = max(0, int(run[0]) - margin), min(body.shape[1], int(run[-1]) + margin + 1)
        rows = np.flatnonzero(body[:, c0:c1].any(axis=1))
        r0, r1 = max(0, int(rows[0]) - margin), min(body.shape[0], int(rows[-1]) + margin + 1)
        box = (slice(r0, r1), slice(c0, c1))
        body[box], carved[box] = _with_clefts(body[box], gelatin[box])
    return body, carved


def _with_clefts(body: np.ndarray, gelatin: np.ndarray):
    """toes_outline's second half on one foot's box: the holes that are not gelatin filled, the clefts found, the
    thin ones widened."""
    body = body | (ndimage.binary_fill_holes(body) & ~gelatin)
    carved = np.zeros(body.shape, bool)
    # The clefts: thin channels of gelatin between parts of him.
    outside = ~body
    thin = outside & ~ndimage.binary_opening(outside, structure=_disc(CLEFT_PX)) & gelatin & ndimage.binary_closing(body, structure=_disc(3 * CLEFT_PX))
    parts, count = ndimage.label(thin, structure=np.ones((3, 3), bool))
    cleft = np.zeros(body.shape, bool)
    if count:
        sizes = ndimage.sum(thin, parts, range(1, count + 1))
        cleft = np.isin(parts, 1 + np.flatnonzero(sizes >= CLEFT_MIN_PX))
    body |= thin & ~cleft & ndimage.binary_fill_holes(body)     # specks of gelatin colour inside him
    narrow = cleft & ~ndimage.binary_opening(~body, structure=_disc(CLEFT_NARROW_PX))
    if narrow.any():
        carved = ndimage.binary_dilation(narrow, structure=_disc(CLEFT_WIDEN_PX)) & body
        body = body & ~carved
    return body, carved


def passed_over(first: np.ndarray, second: np.ndarray, first_share: np.ndarray, second_share: np.ndarray, w: float) -> np.ndarray:
    """Between two outlines of one photograph (bool, its pixels; neither empty): the outline whose edge lies the
    share `w` of the way from the first's edge to the second's, as each pixel's share (float32, 0..1). Where the
    two outlines agree a pixel keeps its measured share (the two's, mixed).

    The edge is moved, not the shares mixed: mixed, a pixel that is in one outline and not in the other turns
    from out to in at w = 1/2 wherever it lies, so the whole way between the two edges was gone on one photograph
    (a step of a millimetre right round both legs, 178 mm up)."""
    def signed(mask):                                           # pixels from the edge: positive inside
        return ndimage.distance_transform_edt(mask) - ndimage.distance_transform_edt(~mask)

    out = ((1.0 - w) * signed(first) + w * signed(second) > 0).astype(np.float32)
    same = first == second
    out[same] = ((1.0 - w) * first_share + w * second_share)[same]
    return out


STEADY = 5                      # photographs: a slice takes the middle value of this many (itself and its neighbours along the body)


def steady(cover: np.ndarray, first: int, last: int) -> None:
    """Each of the slices first..last takes, voxel by voxel, the middle value of itself and its neighbours along the
    body (STEADY of them). A blue-green stain on a photograph's cut face that reaches his skin reads as a dent
    there, a millimetre thick, and the stains come on two or three photographs running: a slit across the front
    of the ankle like a cut. Nothing of him is two photographs thick."""
    half = STEADY // 2
    lo, hi = max(0, first - half), min(cover.shape[1], last + half + 1)
    block = np.asarray(cover[:, lo:hi, :]).copy()
    middle = ndimage.median_filter(block, size=(1, STEADY, 1), mode="nearest")
    cover[:, first:last + 1, :] = middle[:, first - lo:last + 1 - lo, :]


SEAM_MM = 0.7                   # (feet) the outline's edge moving this much further from one photograph to the next than it
                                # does in the photographs round it: a seam
SEAM_REACH = 4                  # photographs either side of a seam that pass over from the one side's outline to the other's


def edge_moves(cover: np.ndarray, first: int, last: int, voxel_mm: float) -> np.ndarray:
    """For each of the slices first..last: how far its outline's edge lies from the edge of the slice below, where
    it lies furthest (the 98th percentile over the edge's voxels), in millimetres."""
    out = np.zeros(last - first + 1)
    below = np.asarray(cover[:, first - 1, :]) > 127
    for k in range(first, last + 1):
        here = np.asarray(cover[:, k, :]) > 127
        edge = here & ~ndimage.binary_erosion(here)
        if edge.any() and below.any() and not below.all():
            away = np.where(below, ndimage.distance_transform_edt(below), ndimage.distance_transform_edt(~below))
            out[k - first] = np.percentile(away[edge], 98) * voxel_mm
        below = here
    return out


def seams(cover: np.ndarray, first: int, last: int, voxel_mm: float) -> list[tuple[int, int]]:
    """The seams among the slices first..last: (a, b), the slices a..b each of which stands SEAM_MM further from the
    one below it than slices do there (the median of eight either side).

    Between two of the photographs (101 and 103 mm up on him, where the gelatin round him changes its look: the
    specimen's blocks meet there, and what the saw took is missing) the front of both feet steps back by 1.7 mm:
    a line across the front of both ankles."""
    lo, hi = max(1, first - 8), min(cover.shape[1] - 1, last + 8)      # the slices beyond the ends too: what is usual there
    moves = edge_moves(cover, lo, hi, voxel_mm)
    usual = np.array([np.median(moves[max(0, j - 8):j + 9]) for j in range(len(moves))])
    found = lo + np.flatnonzero(moves > usual + SEAM_MM)
    found = found[(found >= first) & (found <= last)]
    return [(int(run[0]), int(run[-1])) for run in np.split(found, np.flatnonzero(np.diff(found) > 1) + 1) if len(run)]


def bridge(cover: np.ndarray, below: int, above: int) -> None:
    """The slices between `below` and `above` pass over from the one's outline to the other's, the edge moved an
    equal part of the way with each (passed_over): a step between two photographs becomes a slope."""
    a, b = np.asarray(cover[:, below, :]), np.asarray(cover[:, above, :])
    if not (a > 127).any() or not (b > 127).any():
        return
    for k in range(below + 1, above):
        w = (k - below) / float(above - below)
        cover[:, k, :] = np.round(passed_over(a > 127, b > 127, a / 255.0, b / 255.0, w) * 255.0).astype(np.uint8)


def clean_toes(cover: np.ndarray, slices: int, log=print) -> int:
    """Among the toes' photographs, what does not hang together with the rest of him is not him (a scrap of
    something beside the left foot, tissue-coloured, was drawn as a thorn at the big toe): of the pieces of the
    lowest `slices` slices (in three dimensions), only those that reach the top of them are kept. Returns how many
    voxels were dropped."""
    slices = min(slices, cover.shape[1])
    block = np.asarray(cover[:, :slices, :])
    solid = block > 127
    parts, count = ndimage.label(solid, structure=np.ones((3, 3, 3), bool))
    if count < 2:
        return 0
    keep = np.unique(parts[:, slices - 1, :])
    loose = solid & ~np.isin(parts, keep[keep > 0])
    if not loose.any():
        return 0
    # (with the ring of part-covered voxels round each dropped piece)
    loose = ndimage.binary_dilation(loose, structure=np.ones((3, 3, 3), bool)) & ~ndimage.binary_dilation(solid & ~loose, structure=np.ones((3, 3, 3), bool))
    block = block.copy()
    block[loose] = 0
    cover[:, :slices, :] = block
    log(f"fine skin outline: the toes: {int((solid & loose).sum())} voxels of pieces that do not hang together with him dropped")
    return int((solid & loose).sum())


def whole_body(body: Body) -> np.ndarray:
    """Where he is, on the export's grid (bool, z, y, x): every labelled voxel, AND the space round the eyes that the
    labels were cleared of for the layers under the skin (Body.eye_pits: the globes and what lies before them are
    left to the eyeballs and the lids). That space is open to the front; taken for a hole in him, the skin's
    outline ran into the orbits and the face had two pits for eyes (seen when the outline was read again after the
    pits had come into the labels: it had first been read before there were any)."""
    guide = body.labels > 0
    for (z0, y0, x0), pit in getattr(body, "eye_pits", None) or []:
        guide[z0:z0 + pit.shape[0], y0:y0 + pit.shape[1], x0:x0 + pit.shape[2]] |= pit
    return guide


def extract(body: Body, photos_dir: Path, log=print, only: tuple | None = None) -> FineOutline:
    """Reads the outline from the photographs and keeps it (see the module's text). `only`: the slices (first, last,
    counted from the feet) to read again into an outline that is already kept; the others stay as they are."""
    ppv = _photo_tools()
    photo = json.loads((body.export / "photo.json").read_text())
    coarse_factor = int(round(photo["spacing_mm"][0] / ppv.PIXEL_MM))
    every = int(round(photo["spacing_mm"][2] / ppv.SLICE_MM))
    rows = slice(*photo["crop_photo_px"]["rows"])
    cols = slice(*photo["crop_photo_px"]["cols"])
    top, bottom = photo["slices"]                               # slice numbers: the head's end, the feet's end
    files = ppv.index_slices(Path(photos_dir))
    # The coarse guide: the body's own voxels, holes filled slice by slice (the outer envelope).
    guide = whole_body(body)                                   # (z, y, x)
    nz, ny, nx = guide.shape
    fz, fx = (rows.stop - rows.start) // FACTOR, (cols.stop - cols.start) // FACTOR
    n_slices = bottom - top + 1
    folder = body.export / "model"
    folder.mkdir(parents=True, exist_ok=True)
    fallback = np.zeros(n_slices, bool)
    kept = folder / (CACHE + ".json")
    if only is not None and (folder / CACHE).exists() and kept.exists():
        cover = np.lib.format.open_memmap(folder / CACHE, mode="r+")
        fallback[json.loads(kept.read_text())["fallback"]] = True
        first, last = max(0, int(only[0])), min(n_slices - 1, int(only[1]))
    else:
        cover = np.lib.format.open_memmap(folder / CACHE, mode="w+", dtype=np.uint8, shape=(fz, n_slices, fx))
        first, last = 0, n_slices - 1
    n_toes, n_clefts = int(round(TOES_MM / ppv.SLICE_MM)), int(round(CLEFTS_MM / ppv.SLICE_MM))
    structure = ndimage.generate_binary_structure(2, 1)
    for k in range(first, last + 1):
        cover[:, k, :], fallback[k] = 0, False
        number = bottom - k
        kc = min(ny - 1, k // every)
        g = ndimage.binary_fill_holes(guide[:, kc, :])
        if every > 1 and k % every and kc + 1 < ny:            # a photograph the export skipped: between two coarse slices
            g |= ndimage.binary_fill_holes(guide[:, kc + 1, :])
        wide = g
        if k < n_toes:                                          # the toes' tips: the guide of the slices next to it too (the very
            wide = g.copy()                                     # last photograph has toes in it and the export's mask has none there).
            for j in (kc - 1, kc + 1):                          # For the toes' rule only: the rule for the rest of him fills the
                if 0 <= j < ny:                                 # guide's core, and read a third of a millimetre wider with it.
                    wide |= ndimage.binary_fill_holes(guide[:, j, :])
        if not wide.any():
            continue

        def at_pixels(mask):                                    # the guide at the photographs' own pixels
            mask = np.repeat(np.repeat(mask, coarse_factor, axis=0), coarse_factor, axis=1)
            return np.pad(mask, ((0, max(0, fz * FACTOR - mask.shape[0])), (0, max(0, fx * FACTOR - mask.shape[1]))), mode="edge")[:fz * FACTOR, :fx * FACTOR]

        wide, g = (at_pixels(wide), at_pixels(g)) if wide is not g else (at_pixels(g),) * 2
        path = files.get(number)
        a = t = None
        if path is not None:
            rgb = ppv.read_photo(path)[rows, cols][:fz * FACTOR, :fx * FACTOR]
            t, a = ppv.tissue_mask(rgb), ring_coverage(rgb)
        toes = foot = foot_share = None
        if t is not None and k < n_toes:                        # the toes: the tissue itself, with its clefts
            foot, carved = toes_outline(rgb, ndimage.binary_dilation(wide, structure, iterations=BAND * FACTOR), clefts=k < n_clefts)
            foot_share = a.copy()
            foot_share[foot] = 1.0
            foot_share[~ndimage.binary_dilation(foot, structure) | carved] = 0.0
            toes = foot_share.reshape(fz, FACTOR, fx, FACTOR).mean(axis=(1, 3))
            if k < n_toes - TOES_BLEND:
                cover[:, k, :] = np.round(toes * 255.0).astype(np.uint8)
                continue
        if t is None or (t & g).sum() < 0.6 * g.sum():
            if toes is not None:
                cover[:, k, :] = np.round(toes * 255.0).astype(np.uint8)
            else:
                cover[:, k, :], fallback[k] = g[::FACTOR, ::FACTOR].astype(np.uint8) * 255, True      # a blank or missing photograph
            continue
        allowed = ndimage.binary_dilation(g, structure, iterations=BAND * FACTOR)
        core = ndimage.binary_erosion(g, structure, iterations=BAND * FACTOR)
        m = ndimage.binary_fill_holes((t & allowed) | core)
        m = ndimage.binary_opening(m, structure, iterations=2)  # frost and threads of gelatin colour, a pixel or two wide
        parts, n = ndimage.label(m)
        if n > 1:
            seeds = core if core.any() else g
            keep = np.unique(parts[seeds & m])
            m = np.isin(parts, keep[keep > 0])
        # Solid where the tissue is, the measured share in the one ring of pixels round it, nothing beyond; then
        # each fine voxel's share is the mean of its photo pixels.
        a[m] = 1.0
        a[~ndimage.binary_dilation(m, structure)] = 0.0
        if toes is not None and foot.any() and m.any():
            # The last of the toes' photographs pass over to the rule for the rest of him little by little (the two
            # read the leg's edge a millimetre apart: changed from one photograph to the next, that was a line right
            # round the leg).
            a = passed_over(foot, m, foot_share, a, (k - (n_toes - TOES_BLEND) + 1.0) / (TOES_BLEND + 1.0))
        share = a.reshape(fz, FACTOR, fx, FACTOR).mean(axis=(1, 3))
        cover[:, k, :] = np.round(share * 255.0).astype(np.uint8)
        if k % 100 == 0:
            log(f"fine skin outline: photograph {number} ({k + 1}/{n_slices})")
    if first < n_toes:
        steady(cover, first, min(last, n_toes - 1))
        clean_toes(cover, n_toes + 8, log)
        # Above the toes (where they join the foot the edge moves far from one photograph to the next of itself).
        for a, b in seams(cover, n_clefts + 8, n_toes - 1, ppv.PIXEL_MM * FACTOR):
            bridge(cover, max(0, a - 1 - SEAM_REACH), min(n_slices - 1, b + SEAM_REACH))
            log(f"fine skin outline: a seam between the photographs {a - 1} and {b} mm up, bridged over {SEAM_REACH} photographs either side")
    cover.flush()
    spacing = (ppv.PIXEL_MM * FACTOR, ppv.SLICE_MM, ppv.PIXEL_MM * FACTOR)
    # The export shows photograph (bottom - every * j) at y = (j + 0.5) * every mm: photograph (bottom - k) sits at
    # y = k + every / 2 mm, so the fine grid starts (every - 1) / 2 mm up.
    origin = (0.0, (every - ppv.SLICE_MM) / 2.0, 0.0)
    (folder / (CACHE + ".json")).write_text(json.dumps({"spacing_mm": spacing, "origin_mm": origin, "fallback": np.nonzero(fallback)[0].tolist(),
                                                         "slices": [top, bottom], "factor": FACTOR}))
    log(f"fine skin outline: {cover.shape} voxels at {spacing} mm, {int(fallback.sum())} photographs replaced by the coarse outline")
    del cover
    return load(body)


def inside_export(body: Body, fine: FineOutline, skin_mm: float = 1.4) -> np.ndarray:
    """The export's voxels that lie under the fine skin (bool, the Body's grid): at least half inside the fine
    outline and not in its outermost `skin_mm`, sideways or along the body. The export's own outline is a voxel or
    so wider than the fine one, so fat and bone meshed from its labels alone would show through the skin in places.

    Along the body as well as sideways: where he ends flat across it (the toes' pads and the ball of the foot,
    pressed flat when he was frozen; the heel; a fingertip) his side is far off and only the slice beyond is not
    him. Cut back sideways alone, the fat reached the skin there and showed on the soles in yellow patches.
    (In the feet 39 of the fat's vertices were still at the skin's mesh after this: there the fat's surface is
    made from the skin's own, feet.py.)"""
    nz, ny, nx = body.dims
    step_y = int(round(body.spacing[1] / fine.spacing[1]))
    step = int(round(body.spacing[0] / fine.spacing[0]))
    fz, fy, fx = fine.cover.shape
    out = np.zeros(body.dims, bool)
    whole = np.zeros(body.dims, bool)
    rounds = max(1, int(round(skin_mm / body.spacing[0])))
    structure = ndimage.generate_binary_structure(2, 1)
    for j in range(min(ny, fy // step_y)):
        block = np.asarray(fine.cover[:nz * step, j * step_y:(j + 1) * step_y, :nx * step], np.float32)
        share = block.reshape(nz, step, step_y, nx, step).mean(axis=(1, 2, 4)) / 255.0
        whole[:, j, :] = share > 0.5
        out[:, j, :] = ndimage.binary_erosion(whole[:, j, :], structure, iterations=rounds)
    for r in range(1, max(1, int(round(skin_mm / body.spacing[1]))) + 1):
        out[:, r:, :] &= whole[:, :-r, :]                       # the slice below is him too,
        out[:, :-r, :] &= whole[:, r:, :]                       # and the slice above
        out[:, :r, :] = out[:, ny - r:, :] = False
    return out


def depth_near(fine: FineOutline, zyx_mm: np.ndarray, reach_mm: float = 8.0):
    """The depth under the skin (mm, float32; negative outside it) in the box round the points and `reach_mm`
    further each way: (depth, lo, step), depth[i] being that of the outline's voxel lo + i * step; or None when
    the box holds nothing but him, or nothing of him.

    At the outline's own fineness, or at half of it when the box is large (a long bone that lies shallow from end
    to end). Beyond the outline's ends there is nothing of him (his toes' tips lie at its lower end); beyond the
    box's other sides it is not known, and what is there is left out of the count either way."""
    spacing, origin, shape = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64), np.array(fine.cover.shape)
    index = (np.asarray(zyx_mm, np.float64) - origin) / spacing - 0.5
    reach = reach_mm / spacing
    lo = np.maximum(np.floor(index.min(axis=0) - reach).astype(int), 0)
    hi = np.minimum(np.ceil(index.max(axis=0) + reach).astype(int) + 1, shape)
    if (hi <= lo).any():
        return None
    step = 1 if np.prod((hi - lo).astype(np.float64)) <= 4e7 else 2
    block = np.asarray(fine.cover[tuple(slice(a, b, step) for a, b in zip(lo, hi))]) > 127
    him = block
    for axis in range(3):
        for end, at_end in ((0, lo[axis] == 0), (1, hi[axis] == shape[axis])):
            widths = [(0, 0)] * 3
            widths[axis] = (1, 0) if end == 0 else (0, 1)
            him = np.pad(him, widths, constant_values=not at_end)
    if him.all() or not block.any():
        return None
    sampling = spacing * step
    depth = ndimage.distance_transform_edt(him, sampling=sampling)[1:-1, 1:-1, 1:-1]
    depth -= ndimage.distance_transform_edt(np.pad(~block, 1, constant_values=True), sampling=sampling)[1:-1, 1:-1, 1:-1]
    return ndimage.gaussian_filter(depth.astype(np.float32), 0.7), lo, step


def depth_at(fine: FineOutline, field, zyx_mm: np.ndarray) -> np.ndarray:
    """The depth of each point in a field from depth_near."""
    depth, lo, step = field
    at = (((np.asarray(zyx_mm, np.float64) - np.array(fine.origin_mm)) / np.array(fine.spacing) - 0.5 - lo) / step).T
    return ndimage.map_coordinates(depth, at, order=1, mode="nearest")


def drawn_under(fine: FineOutline, zyx_mm: np.ndarray, least_mm=1.2, most_mm: float = 8.0) -> np.ndarray:
    """Points (mm; z, y, x as the outline's axes) -> the same points, those that lie less than `least_mm` (one
    number, or one for each point) under the skin, or outside it, moved in along the way the depth grows; none by
    more than `most_mm`.

    For what is placed from another source than the photographs and may be anywhere in him (the bones): the points
    are looked at coarsely first (most lie deep, and nothing more is done), then the depth is measured at the
    outline's own fineness in the box round the shallow ones (the clefts between the toes are a millimetre and a
    half wide). The depth is counted on outside the skin, so what stands out of it comes in as well."""
    mm = np.asarray(zyx_mm, np.float64).copy()
    if len(mm) == 0:
        return mm
    least = np.broadcast_to(np.asarray(least_mm, np.float64), (len(mm),))
    spacing, origin, shape = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64), np.array(fine.cover.shape)

    def voxel(points):                                           # the outline's (fractional) voxel index of each point's place
        return (points - origin) / spacing - 0.5

    # Coarsely (every second voxel): the points that are surely deep.
    coarse_step = 2
    index = voxel(mm) / coarse_step
    lo = np.maximum(np.floor(index.min(axis=0)).astype(int) - 3, 0)
    hi = np.minimum(np.ceil(index.max(axis=0)).astype(int) + 4, shape // coarse_step)
    if (hi <= lo).any():
        return mm
    block = np.asarray(fine.cover[tuple(slice(a * coarse_step, b * coarse_step, coarse_step) for a, b in zip(lo, hi))]) > 127
    rounds = int(np.ceil((float(least.max()) + 3.0) / (spacing.min() * coarse_step))) + 1
    deep = ndimage.binary_erosion(block, iterations=rounds, border_value=1)
    at = np.clip(np.rint(index).astype(int) - lo, 0, np.array(block.shape) - 1)
    todo = np.flatnonzero(~deep[at[:, 0], at[:, 1], at[:, 2]])
    if len(todo) == 0:
        return mm
    # Finely, in the box round the shallow points.
    field = depth_near(fine, mm[todo])
    if field is None:
        return mm
    depth, lo, step = field
    slope = np.gradient(depth, *(spacing * step))
    first = mm[todo].copy()
    for _ in range(6):
        at = ((voxel(mm[todo]) - lo) / step).T
        d = ndimage.map_coordinates(depth, at, order=1, mode="nearest")
        shallow = d < least[todo]
        if not shallow.any():
            break
        g = np.stack([ndimage.map_coordinates(c, at[:, shallow], order=1, mode="nearest") for c in slope], axis=1)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        mm[todo[shallow]] += g * (least[todo][shallow] - d[shallow] + 0.2)[:, None]
    move = mm[todo] - first
    far = np.linalg.norm(move, axis=1)
    mm[todo] = first + move * np.minimum(1.0, most_mm / np.maximum(far, 1e-6))[:, None]
    return mm


def load(body: Body) -> FineOutline | None:
    path = body.export / "model" / CACHE
    meta = path.with_name(CACHE + ".json")
    if not path.exists() or not meta.exists():
        return None
    info = json.loads(meta.read_text())
    cover = np.load(path, mmap_mode="r")
    fallback = np.zeros(cover.shape[1], bool)
    fallback[info["fallback"]] = True
    return FineOutline(cover, tuple(info["spacing_mm"]), tuple(info["origin_mm"]), fallback)
