"""The feet's outline from made-up photographs: toes that lie side by side stay separate toes, what is not him is
left out, and one photograph's flaw is taken out by its neighbours.
Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from scipy import ndimage  # noqa: E402

from anatomy_model import fine_skin  # noqa: E402

GELATIN, SKIN, TEAL_LINE, DARK = (20, 50, 110), (230, 200, 150), (150, 195, 180), (30, 12, 10)


def photograph(shape=(300, 700)):
    rgb = np.zeros(shape + (3,), np.uint8)
    rgb[...] = GELATIN
    return rgb, np.mgrid[0:shape[0], 0:shape[1]]


def disc(rgb, grid, centre, radius, colour):
    yy, xx = grid
    rgb[(yy - centre[0]) ** 2 + (xx - centre[1]) ** 2 < radius ** 2] = colour


def test_two_toes_side_by_side_stay_two_toes():
    rgb, grid = photograph()
    disc(rgb, grid, (150, 100), 17, SKIN)
    disc(rgb, grid, (150, 131), 17, SKIN)                               # pressed together: without a line between them, one piece
    assert ndimage.label(fine_skin.toes_outline(rgb.copy())[0])[1] == 1
    rgb[130:171, 115:116] = TEAL_LINE                                   # a line of gelatin one pixel wide between them, mixed with the skin beside it
    body, carved = fine_skin.toes_outline(rgb)
    assert ndimage.label(body)[1] == 2
    gap = np.flatnonzero(~body[150, 100:131])
    assert 4 <= len(gap) <= 7                                           # widened to about a millimetre and a half (0.33 mm pixels)
    assert carved.any() and not (carved & body).any()
    # Above the toes no cleft is looked for, and nothing is carved.
    body, carved = fine_skin.toes_outline(rgb, clefts=False)
    assert not carved.any()


def test_a_hole_that_is_not_gelatin_is_filled_and_gelatin_between_touching_toes_stays():
    rgb, grid = photograph()
    disc(rgb, grid, (150, 300), 40, SKIN)
    disc(rgb, grid, (150, 300), 6, DARK)                                # dark marrow, a vessel: not tissue by its colour, but his
    disc(rgb, grid, (150, 320), 5, GELATIN)                             # gelatin enclosed by him in this photograph: between two toes that touch
    body, _ = fine_skin.toes_outline(rgb)
    assert body[150, 300] and not body[150, 320]
    body, _ = fine_skin.toes_outline(rgb, clefts=False)                 # above the toes a foot has no hollows: every hole is filled
    assert body[150, 300] and body[150, 320]


def test_what_is_greener_than_red_or_too_small_is_not_him():
    rgb, grid = photograph()
    disc(rgb, grid, (150, 300), 40, SKIN)
    disc(rgb, grid, (150, 365), 5, (120, 150, 130))                     # a greenish tube lying against his skin
    disc(rgb, grid, (60, 500), 3, SKIN)                                 # a scrap of something tissue-coloured, 3 mm2
    body, _ = fine_skin.toes_outline(rgb)
    assert body[150, 300] and not body[150, 365] and not body[60, 500]
    allowed = np.zeros(body.shape, bool)
    allowed[:, :310] = True
    assert not fine_skin.toes_outline(rgb, allowed)[0][150, 320]        # and nothing outside where he may be


def test_a_leg_is_its_tissue_and_not_the_frost_round_it():
    rgb, grid = photograph((400, 400))
    yy, xx = grid
    far = np.hypot(yy - 200, xx - 200)
    FROST, PALE_FAT, VEIN = (165, 175, 146), (182, 189, 149), (30, 14, 12)
    rgb[far < 96] = FROST                                               # a rim of frost, 2 mm of it: pale, greenish, hardly redder than blue
    rgb[far < 90] = PALE_FAT                                            # the fat under the skin, a little greener than red on this photograph
    rgb[far < 72] = SKIN
    disc(rgb, grid, (200, 114), 4, VEIN)                                # a vein that lies at the surface: black
    disc(rgb, grid, (40, 330), 7, SKIN)                                 # a scrap of something tissue-coloured out in the frost
    guide = far < 102                                                   # the export's mask: the frost with him, and a voxel more
    leg, _ = fine_skin.body_outline(rgb, guide)
    radius = np.sqrt(leg.sum() / np.pi)
    assert 88.5 < radius < 91.0                                         # to the fat's edge: not the frost, and not short of the fat
    assert leg[200, 114] and not leg[200, 109]                          # the vein's notch closed to half its depth (it was 8 pixels deep)
    assert not leg[40, 330]
    # The rule for the feet would have left that fat out (which is why it stops at the ankles).
    strict, _ = fine_skin.toes_outline(rgb, guide, clefts=False)
    assert np.sqrt(strict.sum() / np.pi) < 75


def test_gelatin_enclosed_by_him_stays_open_on_one_photograph_and_a_thin_film_is_closed_but_not_in_the_hands():
    rgb, grid = photograph((300, 500))
    rgb[60:240, 60:240] = SKIN                                          # a part of him,
    rgb[120:180, 120:180] = GELATIN                                     # with gelatin enclosed in it: a gap or a cavity, not to be told here
    disc(rgb, grid, (150, 90), 8, DARK)                                 # and a dark hollow that is not gelatin: his
    rgb[60:240, 244:400] = SKIN                                         # another part, a film of gelatin 4 pixels wide between the two
    guide = np.zeros(rgb.shape[:2], bool)
    guide[50:250, 50:410] = True
    him, carved = fine_skin.body_outline(rgb, guide)
    assert not him[150, 150] and him[150, 90]
    assert him[150, 241] and not carved.any()                           # the film closed: what lies pressed together is one
    hands = np.zeros(guide.shape, bool)
    hands[40:260, 200:420] = True
    him, carved = fine_skin.body_outline(rgb, guide, hands=hands)
    assert not him[150, 241] and ndimage.label(him)[1] == 2             # in the hands it is a cleft, and the two are two


def test_the_photographs_frame_is_not_a_vein_and_a_photograph_that_is_not_whole_is_found():
    rgb, grid = photograph((300, 500))
    rgb[60:240, 0:240] = SKIN                                           # an arm that reaches the photograph's edge,
    rgb[40:260, 0:14] = DARK                                            # where the black frame is
    disc(rgb, grid, (150, 236), 5, DARK)                                # and a vein at its other side
    guide = np.zeros(rgb.shape[:2], bool)
    guide[55:245, 0:245] = True
    him, _ = fine_skin.body_outline(rgb, guide)
    assert not him[150, 5] and him[150, 30] and him[150, 236]
    areas = np.array([9000.0 + 20 * k for k in range(30)])              # he widens slowly; on one photograph a twentieth of him is missing
    areas[14] *= 0.95
    assert np.flatnonzero(fine_skin.not_whole(areas)).tolist() == [14]


def test_the_head_is_its_tissue_with_its_cavities_filled_and_its_nostrils_as_notches():
    rgb, grid = photograph((400, 400))
    yy, xx = grid
    far = np.hypot(yy - 200, xx - 200)
    FROST = (165, 175, 146)
    rgb[far < 108] = FROST                                              # the halo round him,
    rgb[far < 100] = SKIN                                               # his head,
    rgb[150:250, 150:250] = GELATIN                                     # a sinus, filled with the gelatin: enclosed, his
    rgb[96:130, 190:210] = GELATIN                                      # and a nostril: a notch from the front, 20 pixels wide
    guide = far < 113                                                   # the export's mask: the halo with him
    head = fine_skin.head_outline(rgb, guide)
    assert head[200, 200]                                               # the sinus is him (below the head it would be left open:
    assert not fine_skin.body_outline(rgb, guide)[0][200, 200]          #  it might be a gap between his parts)
    assert not head[110, 200] and head[110, 180] and head[140, 200]     # the nostril stays a notch, and ends
    assert not head[200, 95] and head[200, 103]                         # and the halo is not him


def test_over_the_crown_what_reaches_beyond_the_photograph_below_is_not_him():
    rgb, grid = photograph((400, 400))
    yy, xx = grid
    far = np.hypot(yy - 200, xx - 200)
    rgb[far < 60] = SKIN                                                # the cut face,
    rgb[190:210, 255:300] = SKIN                                        # a spur of the skin below, showing through as red as tissue,
    disc(rgb, grid, (200, 120), 22, SKIN)                               # and a patch of it, wide, at the other side
    guide = far < 130
    below = far < 64                                                    # the photograph below: a millimetre and a third wider all round
    crown = fine_skin.head_outline(rgb, guide, below=below)
    assert crown[200, 200] and crown[200, 255]
    assert not crown[200, 280] and not crown[200, 120]
    assert abs(np.sqrt(crown.sum() / np.pi) - 60) < 1.5
    # Without the photograph below, both would be taken for him.
    assert fine_skin.head_outline(rgb, guide)[200, 280]
    # A photograph below that is at fault (next to nothing of him on it) is not believed.
    assert fine_skin.head_outline(rgb, guide, below=far < 20)[200, 250]


def test_a_cavity_in_him_is_filled_and_a_gap_between_his_parts_stays_open():
    cover = np.zeros((60, 30, 60), np.uint8)
    cover[10:50, 2:28, 10:50] = 255                                     # him, through 26 photographs
    cover[20:26, 8:20, 20:26] = 0                                       # a cavity: enclosed on every photograph it is on, and ends in him
    cover[36:42, 6:24, 30:36] = 0                                       # a gap: enclosed on these photographs,
    cover[36:50, 4:6, 30:36] = 0                                        # and open to his side on the two below them
    filled = fine_skin.fill_closed(cover, 1, 28, log=lambda *_: None)
    assert filled == 6 * 12 * 6
    assert (cover[20:26, 8:20, 20:26] == 255).all()
    assert not cover[36:42, 6:24, 30:36].any() and not cover[36:50, 4:6, 30:36].any()
    assert fine_skin.fill_closed(cover, 1, 28, log=lambda *_: None) == 0


def test_one_photographs_flaw_is_taken_out_by_its_neighbours():
    cover = np.zeros((20, 12, 20), np.uint8)
    cover[5:15, :, 5:15] = 255
    cover[5:9, 6, 5:15] = 0                                             # a dent on one photograph, and
    cover[5:9, 7, 5:15] = 0                                             # on the next: a slit two photographs thick
    cover[2:5, 3, 5:15] = 255                                           # a bump on one
    fine_skin.steady(cover, 0, 11)
    assert (cover[5:15, :, 5:15] == 255).all() and not cover[2:5].any()
    # What is three photographs thick is his: it stays.
    cover[0:5, 4:7, 5:15] = 255
    before = cover.copy()
    fine_skin.steady(cover, 0, 11)
    assert (cover == before).all()


def test_between_two_outlines_the_edge_moves_little_by_little():
    yy, xx = np.mgrid[0:200, 0:200]
    far = np.hypot(yy - 100, xx - 100)
    tight, wide = far < 40, far < 46                                    # the same leg read by two rules, 6 pixels apart
    shares = tight.astype(np.float32), wide.astype(np.float32)
    radii = [np.sqrt(fine_skin.passed_over(tight, wide, *shares, w).sum() / np.pi) for w in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert np.allclose(radii, [40.0, 41.5, 43.0, 44.5, 46.0], atol=0.8)
    assert (np.diff(radii) > 0.8).all()                                 # step by step, not all at once in the middle
    # Where the two agree, a pixel keeps the share measured for it.
    half = np.full(tight.shape, 0.5, np.float32)
    out = fine_skin.passed_over(tight, tight, half, half, 0.3)
    assert np.allclose(out, 0.5)


def test_a_step_between_two_photographs_is_found_and_becomes_a_slope():
    yy, xx = np.mgrid[0:160, 0:160]
    far = np.hypot(yy - 80, xx - 80)
    radius = [30.0 + 0.3 * k + (4.0 if k >= 20 else 0.0) for k in range(40)]       # a limb widening evenly, and a step of 2.6 mm
    cover = np.stack([(far < r).astype(np.uint8) * 255 for r in radius], axis=1)
    assert fine_skin.seams(cover, 5, 35, 0.66) == [(20, 20)]
    fine_skin.bridge(cover, 20 - 1 - fine_skin.SEAM_REACH, 20 + fine_skin.SEAM_REACH)
    assert fine_skin.seams(cover, 5, 35, 0.66) == []
    widths = np.sqrt((cover > 127).sum(axis=(0, 2)) / np.pi)
    assert np.abs(np.diff(widths)).max() < 1.5                           # (it was 4.3 at the step) a voxel or so from each slice to the next
    assert abs(widths[10] - radius[10]) < 0.3 and abs(widths[30] - radius[30]) < 0.3      # away from the seam nothing changed


def test_under_the_skin_means_along_the_body_too():
    from types import SimpleNamespace
    cover = np.zeros((40, 200, 40), np.uint8)
    cover[8:32, 160:190, 8:32] = 255                                    # a block of him that ends flat below and above (a fingertip)
    cover[8:32, 10:40, 8:32] = 255                                      # and one in the feet (a toe's pad)
    fine = fine_skin.FineOutline(cover, (0.66, 1.0, 0.66), (0.0, 0.5, 0.0), np.zeros(200, bool))
    body = SimpleNamespace(dims=(20, 100, 20), spacing=(1.32, 2.0, 1.32))
    inside = fine_skin.inside_export(body, fine)
    assert inside[10, 81:94, 10].all()                                  # the middle of the first
    assert not inside[10, 80, 10] and not inside[10, 94, 10]            # its first and last slice: the skin of the end faces
    assert not inside[4, 87, 10] and inside[5, 87, 10]                  # and one voxel in from its sides, as before
    assert inside[10, 6:19, 10].all() and not inside[10, 5, 10] and not inside[10, 19, 10]      # the same in the feet
    # A slice of the export's grid as the fine outline has it: not cut back.
    assert fine_skin.export_slice(body, fine, 80)[4, 10] and not fine_skin.export_slice(body, fine, 79)[10, 10]


def test_what_lies_at_the_skin_or_outside_it_is_drawn_in_and_what_lies_deep_stays():
    cover = np.zeros((80, 40, 80), np.uint8)
    cover[20:60, :, 20:60] = 255                                        # a limb: 13.2 to 39.6 mm across, either way
    fine = fine_skin.FineOutline(cover, (0.66, 1.0, 0.66), (0.0, 0.5, 0.0), np.zeros(40, bool))
    points = np.array([[26.4, 20.0, 26.4],                              # deep inside
                       [13.6, 20.0, 26.4],                              # under the skin by less than half a millimetre
                       [10.2, 21.0, 30.0],                              # 3 mm outside it
                       [1.2, 19.0, 28.0]])                              # 12 mm outside: further than anything is moved
    moved = fine_skin.drawn_under(fine, points, least_mm=1.2, most_mm=8.0)
    assert np.allclose(moved[0], points[0])
    for k in (1, 2):
        assert 14.1 < moved[k, 0] < 15.6                                # a millimetre and more under the skin now, and no further
        assert np.abs(moved[k, 1:] - points[k, 1:]).max() < 0.2         # straight in
    far = np.linalg.norm(moved[3] - points[3])
    assert 7.9 < far <= 8.0 + 1e-6 and moved[3, 0] > points[3, 0]
    # Nothing shallow: nothing changes.
    deep = np.array([[26.4, 20.0, 26.4], [30.0, 10.0, 22.0]])
    assert np.allclose(fine_skin.drawn_under(fine, deep), deep)
    # The least depth may be given point by point: where none is asked, a point under the skin stays.
    two = np.array([[13.6, 20.0, 26.4], [13.6, 24.0, 30.0]])
    moved = fine_skin.drawn_under(fine, two, least_mm=np.array([2.0, 0.0]))
    assert moved[0, 0] > 14.9 and np.allclose(moved[1], two[1])


def test_a_piece_that_does_not_hang_together_with_him_is_dropped():
    cover = np.zeros((30, 20, 30), np.uint8)
    cover[10:20, 4:, 10:20] = 255                                       # a toe, reaching the top of the slices
    cover[2:5, 2:8, 2:5] = 255                                          # a scrap beside it that ends before the top
    assert fine_skin.clean_toes(cover, 20, log=lambda *_: None) > 0
    assert not cover[2:5, 2:8, 2:5].any() and (cover[10:20, 4:, 10:20] == 255).all()
    assert fine_skin.clean_toes(cover, 20, log=lambda *_: None) == 0
