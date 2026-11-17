"""The fine muscle outline's rules on made-up blocks: which labelled muscle a voxel's fine outline may belong to,
and what stands in for a blank photograph. Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
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
