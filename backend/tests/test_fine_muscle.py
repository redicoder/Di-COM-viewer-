"""The fine muscle outline's rules on made-up blocks: which labelled muscle a voxel's fine outline may belong to,
what stands in for a blank photograph, how near the skin a muscle may begin, and what counts as an object's
where the colour cannot say (thin sheets, aponeuroses). Needs scipy and scikit-image (backend/.venv-seg); skipped
without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import fine_muscle, fine_skin  # noqa: E402

SPACING = (1.32, 2.0, 1.32)
A, B, FAT, BONE = 1, 2, 3, 4


def block():
    """Along x: fat (0..5), muscle A (6..11), muscle B (12..17), nothing (18..23), bone (24..29)."""
    lab = np.zeros((6, 4, 30), np.uint8)
    lab[:, :, 0:6] = FAT
    lab[:, :, 6:12] = A
    lab[:, :, 12:18] = B
    lab[:, :, 24:30] = BONE
    return lab


def test_a_muscles_fine_outline_may_reach_into_fat_and_nothing_but_not_into_bone():
    own = fine_muscle.owners(block(), [A, B], [FAT], None, SPACING, band_mm=2.64)
    row = own[3, 2]
    assert (row[6:12] == A).all() and (row[12:18] == B).all()          # its own voxels
    assert (row[4:6] == A).all() and row[3] == 0                        # two voxels (2.64 mm) into the fat beside it, no further
    assert (row[18:20] == B).all() and row[20] == 0                     # and into nothing, on the other muscle's side that muscle's
    assert (row[24:] == 0).all()                                        # never bone


def test_bone_right_beside_a_muscle_is_not_given_to_it():
    lab = block()
    lab[:, :, 18:24] = BONE
    own = fine_muscle.owners(lab, [A, B], [FAT], None, SPACING)
    assert (own[3, 2, 18:] == 0).all()


def test_what_was_taken_out_of_the_mass_is_not_given_back():
    lab = block()
    taken = np.zeros(lab.shape, bool)
    taken[:, :, 18:20] = True                                           # (a named muscle's place, cleared from the labels)
    own = fine_muscle.owners(lab, [A, B], [FAT], taken, SPACING)
    assert (own[3, 2, 18:20] == 0).all() and (own[3, 2, 12:18] == B).all()


def test_no_muscle_at_all_gives_nothing():
    lab = np.full((4, 4, 4), FAT, np.uint8)
    assert not fine_muscle.owners(lab, [A, B], [FAT], None, SPACING).any()


def test_a_blank_photograph_takes_the_nearest_good_ones_coverage():
    light = np.zeros((3, 6, 3), np.uint8)                               # every voxel's lightness; 0: no tissue
    light[:, 1, :], light[:, 4, :] = 60, 118
    fallback = np.zeros(6, bool)
    fallback[[2, 3]] = True
    fine = fine_skin.FineOutline(light, (0.66, 1.0, 0.66), (0.0, 0.5, 0.0), fallback)
    got = fine_muscle._slab(fine, 0, 6)
    assert got[1, 1, 1] == pytest.approx(1.0)                           # as dark as muscle: wholly muscle
    assert got[1, 4, 1] == pytest.approx(0.4)                           # (150 - 118) / (150 - 70)
    assert got[1, 2, 1] == pytest.approx(1.0)                           # slice 2 is blank: slice 1 is the nearest good one
    assert got[1, 3, 1] == pytest.approx(0.4)                           # slice 3: slice 4
    assert got[1, 0, 1] == 0.0 and got[1, 5, 1] == 0.0                  # no tissue: no muscle


def test_each_photograph_is_read_against_its_own_muscle_and_fat():
    muscle = np.full(30, 50.0)
    fat = np.full(30, 165.0)
    fat[15:] = 135.0                                                    # a run of photographs whose fat is darker
    fat[5] = np.nan                                                     # one with too little fat to tell
    lower, upper = fine_muscle.anchors(muscle, fat)
    assert lower[5] == pytest.approx(lower[4]) and upper[5] == pytest.approx(upper[4])
    assert upper[10] == pytest.approx(50.0 + 0.83 * 115.0) and upper[20] == pytest.approx(50.0 + 0.83 * 85.0)
    assert upper[14] > upper[15] + 20.0                                 # the step stays where the run begins
    # The same fat reads as no muscle in both runs; with one pair of lightnesses for all, the darker run's read as a fifth muscle.
    light = np.zeros((2, 30, 2), np.uint8)
    light[:, :15, :], light[:, 15:, :] = 165, 135
    fine = fine_skin.FineOutline(light, (0.66, 1.0, 0.66), (0.0, 0.5, 0.0), np.zeros(30, bool))
    assert fine_muscle._slab(fine, 18, 20).max() == pytest.approx((150.0 - 135.0) / 80.0)
    fine.lower, fine.upper = lower, upper
    assert fine_muscle._slab(fine, 8, 10).max() == pytest.approx(0.0, abs=0.02) and fine_muscle._slab(fine, 18, 20).max() == pytest.approx(0.0, abs=0.02)


def test_a_photograph_with_a_part_missing_is_found_and_a_growing_part_is_not():
    tissue = np.full(40, 100000.0)
    tissue[20] = 89000.0                                                # a tenth of the picture is missing
    tissue[30:] = 105000.0                                              # a new run: its tissue reads 5 % larger, and stays so
    slope = np.linspace(5000.0, 60000.0, 40)                            # a shoulder coming in: larger from photograph to photograph
    assert fine_muscle.partial(tissue).nonzero()[0].tolist() == [20]
    assert not fine_muscle.partial(slope).any()


def test_a_muscle_begins_no_nearer_the_skin_than_it_may_measured_in_space():
    # A ball of 20 mm on the fine grid: what lies nearer its surface than 3.6 mm is no muscle's, what lies deeper is.
    fine = (0.66, 1.0, 0.66)
    zz, yy, xx = np.mgrid[0:81, 0:51, 0:81]
    depth = 20.0 - np.sqrt(((zz - 40) * 0.66) ** 2 + ((yy - 25) * 1.0) ** 2 + ((xx - 40) * 0.66) ** 2)
    inside = depth > 0
    limit = fine_muscle.under_limit(inside, fine, 3.6)
    assert limit.shape == inside.shape and limit.dtype == np.float32
    assert limit[~inside].max() == 0.0 and limit[inside & (depth < 2.5)].max() == 0.0      # not in the skin, nor in the fat's place under it
    assert limit[depth > 5.0].min() == 1.0                              # all of what lies deeper
    half = depth[(limit > 0.4) & (limit < 0.6)]
    assert 3.3 < np.median(half) < 4.1                                  # and half of it at 3.6 mm, good to a third of a millimetre or so
    top = inside & (yy > 25) & (np.abs(zz - 40) < 4) & (np.abs(xx - 40) < 4)                # where the outline lies ABOVE (along the body): in space,
    assert limit[top & (depth < 2.5)].max() == 0.0                      # not only within a photograph
    # One least depth for every slice: the feet's and the head's own (shallower) beside the body's.
    per_slice = np.where(np.arange(51) < 25, 1.3, 3.6)
    mixed = fine_muscle.under_limit(inside, fine, per_slice)
    side = inside & (np.abs(depth - 2.4) < 0.3) & (np.abs(yy - 25) > 6)                     # 2.4 mm under the ball's side, clear of its ends
    assert mixed[side & (yy < 25)].min() > 0.9 and mixed[side & (yy > 25)].max() == 0.0
    assert (fine_muscle.under_limit(np.ones((8, 8, 8), bool), fine, 3.6) == 1.0).all()      # no outline in the block: all of it deep


def test_the_thin_parts_of_an_object_are_its_sheets_not_the_edges_of_its_thick_parts():
    mask = np.zeros((20, 20, 20), bool)
    mask[2:12, 2:12, 2:12] = True                                       # a thick block,
    mask[12:18, 5:17, 6:8] = True                                       # a sheet two voxels thick standing on it,
    mask[15, 15, 15] = True                                             # and a speck
    thin = fine_muscle.thin_parts(mask)
    assert thin[12:18, 5:17, 6:8].all() and not thin[2:12, 2:12, 2:12].any() and not thin[15, 15, 15]
    zz, yy, xx = np.mgrid[0:40, 0:40, 0:40]
    ball = np.sqrt((zz - 20) ** 2 + (yy - 20) ** 2 + (xx - 20) ** 2) < 15
    assert not fine_muscle.thin_parts(ball).any()                       # a round thing has no thin parts
    aslant = np.abs(zz - xx) < 2                                        # a sheet at 45 degrees, three voxels through along an axis
    assert fine_muscle.thin_parts(aslant & (yy > 2) & (yy < 37)).sum() > 0.9 * (aslant & (yy > 2) & (yy < 37)).sum()


def test_a_thin_sheet_counts_whatever_its_colour_and_an_aponeurosis_as_its_labels_have_it():
    shape = (6, 4, 12)
    cover = np.zeros(shape, np.float32)
    cover[:, :, 0:4] = 1.0                                              # muscle-red here,
    cover[:, :, 4:8] = 0.2                                              # pale here (a thin sheet with its fascia: a fifth red),
    tissue = np.ones(shape, np.float32)
    tissue[:, :, 10:] = 0.0                                             # and no tissue at all here
    mine = np.ones(shape, bool)
    thin = np.zeros(shape, bool)
    thin[:, :, 6:12] = True
    got = fine_muscle.counted(cover, tissue, mine, thin)
    assert (got[:, :, 0:4] == 1.0).all()                                # red: the object's
    assert np.allclose(got[:, :, 4:6], 0.2)                             # pale where its labels are thick: as much as is red
    assert (got[:, :, 6:10] == 1.0).all()                               # pale where its labels are thin: the object's all the same
    assert (got[:, :, 10:] == 0.0).all()                                # (not where there is nothing)
    assert (fine_muscle.counted(cover, tissue, np.zeros(shape, bool), thin)[:, :, 0:4] == 0.0).all()       # red that is not its own: not
    own = np.zeros(shape, bool)
    own[:, :, 2:11] = True
    sheet = fine_muscle.counted(cover, tissue, mine, None, own)
    assert (sheet[:, :, 2:10] == 1.0).all() and (sheet[:, :, :2] == 0.0).all() and (sheet[:, :, 10:] == 0.0).all()     # its labels' voxels that hold tissue, no more, no less


def test_an_aponeurosis_is_taken_a_little_tidier_than_its_labels_have_it():
    sheet = np.zeros((12, 30, 30), bool)
    sheet[8, 3:27, 3:27] = True                                         # a sheet one voxel thick,
    sheet[8, 10, 10] = False                                            # with a gap of a voxel in it,
    sheet[1, 2:5, 2:5] = True                                           # and a scrap of nine voxels well away from it
    tidy = fine_muscle.tidy_sheet(sheet)
    assert tidy[8, 10, 10] and tidy[8, 3:27, 3:27].all()                # the gap is closed, the sheet whole,
    assert not tidy[:5].any()                                           # the scrap left out,
    assert tidy.sum() == 24 * 24                                        # and it is no thicker and no wider for it
    assert not fine_muscle.tidy_sheet(np.zeros((4, 4, 4), bool)).any()
