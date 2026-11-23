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

THE BODY BELOW THE HEAD, from above the feet to BODY_MM (the neck), is read by the tissue alone as well
(body_outline; its text says why: the rule above takes whatever lies inside the mask for body, and the mask has the
frost round him and has what lies together as one). What that needs beyond the feet's rule: what he encloses on
a photograph and is gelatin is a gap between his parts or a cavity in him, told apart along the body
(fill_closed); a film of gelatin between parts pressed together is closed, but in the hands it is a cleft between
fingers (hand_boxes); a photograph that is not whole counts as blank (not_whole), and blank photographs are passed
over from the one below to the one above (bridge). THE HEAD keeps the rule of the first paragraph: its eyes, lids,
mouth and face muscles were fitted to that skin.

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
BODY_MM = 1640.0                # above the feet and up to here (the neck, under the chin) the body's rule reads the
                                # photographs (body_outline); above it the head keeps the rule it was fitted to
BODY_BLEND = 60                 # the last of those photographs pass over to the head's rule (2 mm apart)
SEAMS_MM = 776.0                # seams between photographs are looked for up to here (the legs: above them his own parts
                                # come and go from one photograph to the next)
FROST = (4, 8, 2)               # (body) frost on skin: green more than this above red, and red above blue by less than
                                # the second + the third x (green - red)
VEIN_PX = 8                     # (body) a notch in the outline no wider than twice this many pixels is closed, if not gelatin
VEIN_SPOT_PX = 1500             # (body) a black spot of up to this many pixels (1.6 cm2) is a vein cut across
NOT_WHOLE = 0.025               # (body) a photograph on which he is this much larger or smaller than the photographs before
                                # and after give between them is not whole (frost over a cut face where two blocks meet)
FILM_PX = 3                     # (body) gelatin between two parts of him no wider than twice this many pixels (2 mm) is
                                # closed: what lies pressed together is one (but in the hands: there such a film is a cleft)
HAND_MM = 25.0                  # the hands, for that: the box round each hand's bones and this much more
OPEN_VOXELS = 4                 # (body) an enclosed space is a gap between his parts if it lies on open space of the
                                # photograph below or above by this many voxels
HAND_BONES = ("capitate", "hamate", "lunate", "pisiform", "scaphoid", "trapezium", "trapezoid", "triquetrum", "metacarpal", "phalanges of the")
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


def body_outline(rgb: np.ndarray, guide: np.ndarray, wide: np.ndarray | None = None, hands: np.ndarray | None = None):
    """A photograph through him below the head and the export's mask there (bool, the photograph's pixels; `wide`:
    the mask with its neighbouring slices', for a part's last millimetre) -> (what is him, the pixels taken off
    him to widen thin clefts in the hands).

    The head's rule takes for body whatever lies BAND inside the mask, whatever its colour. The mask has the frost
    round him as body, 3 to 4 mm of it on the legs, so that core reaches past his skin: measured on every 25th
    photograph from the ankles to the belly, the outline stood 1.8 to 2.3 mm outside the skin all round, with the
    frost's lumps and the tube on the left shin as warts; and it has what lies together as one, so the fingers
    were one piece of skin. Here only the tissue counts, as in the feet:

    - redder than blue, and not frost: frost on skin is pale and greenish, greener than red while only weakly redder
      than blue (FROST). The feet's plain 'greener than red' will not do above them: the fat under the skin is pale
      and on many photographs a little greener than red too, and where it lies at the surface (the calf's inner
      side, 50 photographs running) the outline wandered about inside it, a patch of scratches on the shin. That
      fat is well redder than blue (33 against the frost's 18, at the median);
    - or black without being blue: a vein cut across is black, and one that lies at the surface (the long vein of
      the leg's inner side, with the hollow it lies in) otherwise leaves a notch;
    - in pieces of some size that touch the mask (a scrap out in the gelatin does not);
    - what such pieces enclose is him if it is not gelatin. What is gelatin stays open HERE: it may be a gap
      between his parts (an arm and the trunk, the fingers and the belly) or a cavity in him (the bowel, the
      windpipe: the cut cavities were filled with the same blue), and one photograph cannot tell; fill_closed
      does, with the photographs below and above;
    - a notch no wider than 2 x VEIN_PX that is not gelatin is closed (what is left of a vein's notch);
    - gelatin no wider than 2 x FILM_PX between two parts of him is closed too: what lies pressed together (the
      thighs, an arm against the chest) is one piece, as it was; a slit a millimetre wide and a hand deep cannot
      be meshed at the body's 3 mm. But not in the hands (`hands`: where they are): there the films between the
      fingers are clefts, found and widened as the toes' are (_with_clefts)."""
    structure = ndimage.generate_binary_structure(2, 1)
    wide = guide if wide is None else wide
    allowed = ndimage.binary_dilation(wide, structure, iterations=BAND * FACTOR)
    r, g, b = (rgb[..., c].astype(np.int16) for c in range(3))
    blue = b > r - 8
    frost = (g > r + FROST[0]) & (r - b < FROST[1] + FROST[2] * (g - r))
    blood = (r <= 45) & (b <= r + 8) & (g <= r + 8)            # black, and not the gelatin's dark blue: a vein, cut across;
    parts, count = ndimage.label(blood)                         # in spots, not in sheets: the photograph's own frame is
    if count:                                                   # black too, and where an arm reaches it the frame stood on
        sizes = ndimage.sum(blood, parts, range(1, count + 1))  # the arm's side as a plate. (Its size is taken on the
        blood = np.isin(parts, 1 + np.flatnonzero(sizes <= VEIN_SPOT_PX))      # whole photograph: cut to what the mask
    body = (((r > b + 8) & (r > 45) & ~frost) | blood) & allowed                # allows, the frame falls into spots.)
    body = ndimage.binary_opening(body, iterations=2)          # threads, a pixel or two wide
    parts, count = ndimage.label(body)
    if count:
        sizes = ndimage.sum(body, parts, range(1, count + 1))
        good = (sizes >= PIECE_PX) & np.isin(np.arange(1, count + 1), np.unique(parts[wide]))
        body = np.isin(parts, 1 + np.flatnonzero(good))
    body |= ndimage.binary_fill_holes(body) & ~blue
    body |= ndimage.binary_closing(body, structure=_disc(VEIN_PX)) & ~blue & allowed
    carved = np.zeros(body.shape, bool)
    film = ndimage.binary_closing(body, structure=_disc(FILM_PX)) & allowed
    if hands is None or not hands.any():
        return body | film, carved
    body |= film & ~hands
    gelatin = blue | frost
    for box in ndimage.find_objects(ndimage.label(hands)[0]):
        body[box], carved[box] = _with_clefts(body[box], gelatin[box])
    return body, carved


def fill_closed(cover: np.ndarray, first: int, last: int, log=print) -> int:
    """Among the slices first..last: what the outline encloses on a photograph and has left open (gelatin) is
    filled where it is a cavity in him, and stays open where it is a gap between his parts. Returns the voxels
    filled.

    A gap opens to the outside on some photograph near; a cavity does not (his mouth and nose are above these
    slices, and the outline there has no holes). So: open is what the outline does not enclose; an enclosed piece
    is open if it lies on open space of the photograph below or above, by OPEN_VOXELS at least; that is told
    from photograph to photograph, upwards and downwards, until nothing changes. What is then not open is him."""
    first, last = max(first, 0), min(last, cover.shape[1] - 1)
    count = last - first + 1
    if count <= 0:
        return 0

    def outside(k):                                             # of a slice beyond these: what its outline does not enclose
        if k < 0 or k >= cover.shape[1]:
            return np.ones((cover.shape[0], cover.shape[2]), bool)
        return ~ndimage.binary_fill_holes(np.asarray(cover[:, k, :]) > 127)

    opened, pieces, flags = [], [], []
    for k in range(first, last + 1):
        body = np.asarray(cover[:, k, :]) > 127
        whole = ndimage.binary_fill_holes(body)
        lab, n = ndimage.label(whole & ~body)
        opened.append(~whole)
        pieces.append(lab if n else None)
        flags.append(np.zeros(n + 1, bool))
    below, above = outside(first - 1), outside(last + 1)
    changed, rounds = True, 0
    while changed and rounds < 20:
        changed, rounds = False, rounds + 1
        for order in (range(count), range(count - 1, -1, -1)):
            for i in order:
                lab = pieces[i]
                if lab is None:
                    continue
                for other in (opened[i - 1] if i > 0 else below, opened[i + 1] if i < count - 1 else above):
                    touched = np.bincount(lab[other & (lab > 0)], minlength=len(flags[i])) >= OPEN_VOXELS
                    touched[0] = False
                    new = touched & ~flags[i]
                    if new.any():
                        flags[i] |= new
                        opened[i] |= np.isin(lab, np.flatnonzero(new))
                        changed = True
    filled = 0
    for i, lab in enumerate(pieces):
        if lab is None:
            continue
        closed = (lab > 0) & ~opened[i]
        if closed.any():
            block = np.asarray(cover[:, first + i, :]).copy()
            block[closed] = 255
            cover[:, first + i, :] = block
            filled += int(closed.sum())
    log(f"fine skin outline: {filled} voxels enclosed by him and not open to the outside filled (cavities), in {rounds} rounds")
    return filled


def not_whole(areas: np.ndarray, least: float = 3000.0) -> np.ndarray:
    """Which photographs are not whole, from his area on each (any unit): off by more than NOT_WHOLE from the
    middle of the medians of the four before and the four after (a part of him that really begins or ends, a
    shoulder, a finger, does so over many photographs). As fine_muscle.partial, which finds the same photographs
    by his muscles."""
    t = np.asarray(areas, np.float64)
    out = np.zeros(len(t), bool)
    for k in range(len(t)):
        n = min(4, k, len(t) - 1 - k)
        if n < 2 or t[k] < least:
            continue
        expected = 0.5 * (np.median(t[k - n:k]) + np.median(t[k + 1:k + 1 + n]))
        out[k] = abs(t[k] - expected) > NOT_WHOLE * max(expected, 1.0)
    return out


def hand_boxes(body: Body) -> list:
    """Where his hands are: for each, the box round its bones (BoneHub's; mm, the body's array order: z0, z1, y0,
    y1, x0, x1) and HAND_MM more. None without the bones."""
    from . import bonehub
    if not bonehub.cache_path(body).exists():
        return []
    placed, _, _ = bonehub.load_or_build(body, None, lambda *_: None)
    out = []
    for side in ("left", "right"):
        mine = [np.asarray(v) for _, name, v, _ in placed
                if side in name and any(key in name for key in HAND_BONES) and "toe" not in name and "metatarsal" not in name]
        if mine:
            points = np.concatenate(mine)
            lo, hi = points.min(axis=0) - HAND_MM, points.max(axis=0) + HAND_MM
            out.append((float(lo[0]), float(hi[0]), float(lo[1]), float(hi[1]), float(lo[2]), float(hi[2])))
    return out


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
    if last < first:
        return []
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
    n_toes, n_clefts, n_body, n_seams = (int(round(mm / ppv.SLICE_MM)) for mm in (TOES_MM, CLEFTS_MM, BODY_MM, SEAMS_MM))
    structure = ndimage.generate_binary_structure(2, 1)
    boxes = hand_boxes(body)
    for k in range(first, last + 1):
        cover[:, k, :], fallback[k] = 0, False
        number = bottom - k
        kc = min(ny - 1, k // every)
        g = ndimage.binary_fill_holes(guide[:, kc, :])
        if every > 1 and k % every and kc + 1 < ny:            # a photograph the export skipped: between two coarse slices
            g |= ndimage.binary_fill_holes(guide[:, kc + 1, :])
        wide = g
        if k < n_body:                                          # a part's last millimetre (the toes' tips, a fingertip): the guide of
            wide = g.copy()                                     # the slices next to it too (the very last photograph has toes in it
            for j in (kc - 1, kc + 1):                          # and the export's mask has none there). Not for the head's rule: it
                if 0 <= j < ny:                                 # fills the guide's core, and read a third of a millimetre wider with it.
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
        # Which rules read this photograph: the toes' (to above the ankles), the body's (to the neck), the head's;
        # where two of them do, the one passes over to the other.
        blank = t is None or (t & g).sum() < 0.6 * g.sum()
        read = {}                                               # rule -> (what is him, each pixel's share)

        def shares(outline, off=None):
            share = a.copy()
            share[outline] = 1.0                                # solid where the tissue is, the measured share in the one ring
            share[~ndimage.binary_dilation(outline, structure) if off is None else ~ndimage.binary_dilation(outline, structure) | off] = 0.0
            return outline, share                               # of pixels round it, nothing beyond

        if t is not None and k < n_toes:                        # the toes: the tissue itself, with its clefts
            foot, carved = toes_outline(rgb, ndimage.binary_dilation(wide, structure, iterations=BAND * FACTOR), clefts=k < n_clefts)
            read["toes"] = shares(foot, carved)
        if not blank and n_toes - TOES_BLEND <= k < n_body:
            hands = None
            height = (every - ppv.SLICE_MM) / 2.0 + (k + 0.5) * ppv.SLICE_MM
            for z0, z1, y0, y1, x0, x1 in boxes:
                if y0 <= height <= y1:
                    hands = np.zeros(g.shape, bool) if hands is None else hands
                    hands[max(0, int(z0 / ppv.PIXEL_MM)):int(z1 / ppv.PIXEL_MM) + 1, max(0, int(x0 / ppv.PIXEL_MM)):int(x1 / ppv.PIXEL_MM) + 1] = True
            read["body"] = shares(*body_outline(rgb, g, wide, hands))
        if not blank and k >= n_body - BODY_BLEND:
            allowed = ndimage.binary_dilation(g, structure, iterations=BAND * FACTOR)
            core = ndimage.binary_erosion(g, structure, iterations=BAND * FACTOR)
            m = ndimage.binary_fill_holes((t & allowed) | core)
            m = ndimage.binary_opening(m, structure, iterations=2)  # frost and threads of gelatin colour, a pixel or two wide
            parts, n = ndimage.label(m)
            if n > 1:
                seeds = core if core.any() else g
                keep = np.unique(parts[seeds & m])
                m = np.isin(parts, keep[keep > 0])
            read["head"] = shares(m)
        if not read:                                            # a blank or missing photograph
            cover[:, k, :], fallback[k] = g[::FACTOR, ::FACTOR].astype(np.uint8) * 255, True
            continue
        # The last photographs of a rule pass over to the next little by little (the rules read his edge up to 2 mm
        # apart: changed from one photograph to the next, that is a line right round him).
        share = next(iter(read.values()))[1]
        for one, other, last_of, over in (("toes", "body", n_toes, TOES_BLEND), ("body", "head", n_body, BODY_BLEND)):
            if one in read and other in read and read[one][0].any() and read[other][0].any():
                share = passed_over(read[one][0], read[other][0], read[one][1], read[other][1], (k - (last_of - over) + 1.0) / (over + 1.0))
        cover[:, k, :] = np.round(share.reshape(fz, FACTOR, fx, FACTOR).mean(axis=(1, 3)) * 255.0).astype(np.uint8)
        if k % 100 == 0:
            log(f"fine skin outline: photograph {number} ({k + 1}/{n_slices})")
    # Photographs that are not whole (frost over the cut face where two of the specimen's blocks meet: the rule
    # for the head fills what is missing from the mask, the body's rule believes the photograph) count as blank.
    if first < n_body:
        areas = np.array([np.count_nonzero(np.asarray(cover[:, k, :]) > 127) for k in range(n_toes, n_body)])
        broken = n_toes + np.flatnonzero(not_whole(areas))
        if len(broken):
            fallback[broken] = True
            log(f"fine skin outline: photographs that are not whole (mm up), counted as blank: {broken.tolist()}")
    # Blank photographs took the coarse outline, which stands round him as a collar: the outline passes over them
    # from the photograph below to the photograph above (two runs of them with one or two good photographs between
    # are one run).
    blanks = np.flatnonzero(fallback)
    for a, b in zip(blanks[:-1], blanks[1:]):
        if 1 < b - a <= 3:
            fallback[a:b] = True
    blanks = np.flatnonzero(fallback)
    for run in np.split(blanks, np.flatnonzero(np.diff(blanks) > 1) + 1):
        if len(run) and run[0] > 0 and run[-1] < n_slices - 1 and run[-1] >= first and run[0] <= last:
            bridge(cover, int(run[0]) - 1, int(run[-1]) + 1)
            log(f"fine skin outline: the blank photographs {int(run[0])} to {int(run[-1])} mm up, bridged")
    if first < n_body:
        fill_closed(cover, n_toes - TOES_BLEND, n_body - 1, log)      # (all of the body's slices: what is open is told along them)
        steady(cover, first, min(last, n_body - 1))
        if first < n_toes:
            clean_toes(cover, n_toes + 8, log)
        # Above the toes (where they join the foot the edge moves far from one photograph to the next of itself).
        for a, b in seams(cover, max(first, n_clefts + 8), min(last, n_seams - 1), ppv.PIXEL_MM * FACTOR):
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


def export_slice(body: Body, fine: FineOutline, j: int) -> np.ndarray:
    """Slice `j` of the export's grid: its voxels that lie at least half inside the fine outline (bool; z, x)."""
    nz, _, nx = body.dims
    step_y = int(round(body.spacing[1] / fine.spacing[1]))
    step = int(round(body.spacing[0] / fine.spacing[0]))
    block = np.asarray(fine.cover[:nz * step, j * step_y:(j + 1) * step_y, :nx * step], np.float32)
    return block.reshape(nz, step, step_y, nx, step).mean(axis=(1, 2, 4)) / 255.0 > 0.5


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
    fz, fy, fx = fine.cover.shape
    out = np.zeros(body.dims, bool)
    whole = np.zeros(body.dims, bool)
    rounds = max(1, int(round(skin_mm / body.spacing[0])))
    structure = ndimage.generate_binary_structure(2, 1)
    for j in range(min(ny, fy // step_y)):
        whole[:, j, :] = export_slice(body, fine, j)
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
