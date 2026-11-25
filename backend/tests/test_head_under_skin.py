"""Nothing of a layer under the skin reaches the skin in the head, measured on triangles: on a made-up block of
him with a nostril in it.
Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import feet, fine_skin, head_layers  # noqa: E402
from anatomy_model.common import Structure  # noqa: E402

SPACING = (0.66, 1.0, 0.66)
FRONT = 20 * 0.66                                       # his front surface, mm from the grid's front


def block(tmp_path):
    """A block of him, 53 x 70 x 53 mm, with a pit in its front (a nostril: 6 mm across, 20 mm deep), as an
    outline kept beside a made-up export; returns (the body, its box z y x mm)."""
    cover = np.zeros((120, 80, 120), np.uint8)
    cover[20:100, 5:75, 20:100] = 255
    cover[20:50, 30:45, 55:64] = 0
    folder = tmp_path / "model"
    folder.mkdir()
    np.save(folder / fine_skin.CACHE, cover)
    (folder / (fine_skin.CACHE + ".json")).write_text(json.dumps({"spacing_mm": SPACING, "origin_mm": (0.0, 0.0, 0.0), "fallback": []}))
    size = np.array([120 * 0.66, 80.0, 120 * 0.66])
    return SimpleNamespace(export=tmp_path, size_mm=(size[2], size[1], size[0])), size


def sheet(size, name, z_mm, y_range, x_range, step=3.0):
    """A flat sheet of triangles facing the front, at z_mm."""
    ys, xs = np.arange(y_range[0], y_range[1] + 1e-6, step), np.arange(x_range[0], x_range[1] + 1e-6, step)
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    mm = np.stack([np.full(yy.size, z_mm), yy.ravel(), xx.ravel()], axis=1)
    f = []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            a = j * len(xs) + i
            f += [(a, a + 1, a + len(xs)), (a + 1, a + len(xs) + 1, a + len(xs))]
    return Structure(name, "fat", feet.to_gltf(size, mm), np.array(f, np.uint32), (1.0, 1.0, 1.0))


def depth_of(body, size, s):
    fine = fine_skin.load(body)
    points = np.einsum("kw,nwc->nkc", head_layers.SPREAD, feet.to_mm(size, s.v)[np.asarray(s.f, np.int64)]).reshape(-1, 3)
    return fine_skin.depths(fine, points)


def test_a_shallow_sheet_sinks_and_a_deep_one_stays(tmp_path):
    body, size = block(tmp_path)
    shallow = sheet(size, "shallow", FRONT + 0.3, (50, 68), (20, 55))      # a third of a millimetre under his front, beside the pit
    deep = sheet(size, "deep", FRONT + 9.0, (50, 68), (20, 55))
    before = deep.v.copy()
    moved, dropped = head_layers.faces_under_skin(body, [shallow, deep], from_mm=0.0, log=lambda *_: None)
    assert moved > 0 and dropped == 0
    assert depth_of(body, size, shallow).min() > 0.9                      # a millimetre of skin over all of it now
    assert np.array_equal(deep.v, before)
    assert head_layers.faces_under_skin(body, [shallow, deep], from_mm=0.0, log=lambda *_: None) == (0, 0)


def test_a_triangle_across_a_nostril_is_taken_out_and_the_rest_of_its_sheet_stays(tmp_path):
    body, size = block(tmp_path)
    across = sheet(size, "across", FRONT + 2.5, (20, 54), (26, 50), step=12.0)   # corners well under the skin, 12 mm apart: over the pit
    count = len(across.f)
    in_air = depth_of(body, size, across).reshape(-1, len(head_layers.SPREAD)).min(axis=1) < 0
    assert in_air.any() and not in_air.all()
    moved, dropped = head_layers.faces_under_skin(body, [across], from_mm=0.0, log=lambda *_: None)
    assert 0 < dropped < count and len(across.f) == count - dropped
    assert depth_of(body, size, across).min() >= 0.5                      # what is left of it lies under the skin


def test_below_the_head_nothing_is_touched(tmp_path):
    body, size = block(tmp_path)
    shallow = sheet(size, "shallow", FRONT + 0.3, (50, 68), (20, 55))
    before = shallow.v.copy()
    assert head_layers.faces_under_skin(body, [shallow], from_mm=70.0, log=lambda *_: None) == (0, 0)
    assert np.array_equal(shallow.v, before)


def test_the_depth_of_points_is_told_even_where_the_box_holds_only_him_or_nothing_of_him(tmp_path):
    body, _ = block(tmp_path)
    fine = fine_skin.load(body)
    assert fine_skin.depths(fine, np.array([[39.6, 40.0, 39.6]]), reach_mm=2.0)[0] == 99.0       # the middle of him
    assert fine_skin.depths(fine, np.array([[2.0, 40.0, 3.0]]), reach_mm=2.0)[0] == -99.0        # far out in front
    near = fine_skin.depths(fine, np.array([[FRONT + 2.0, 60.0, 30.0], [FRONT - 2.0, 60.0, 30.0]]))
    assert abs(near[0] - 2.0) < 0.6 and abs(near[1] + 2.0) < 0.6


def test_where_photographs_were_passed_over_what_lies_under_the_skin_lies_deeper(tmp_path):
    body, size = block(tmp_path)
    fine = fine_skin.load(body)
    fine.fallback[30:36] = True                                         # six photographs passed over, 30 to 36 mm up
    assert head_layers.joints_of(fine) == [(30.0, 36.0)]
    joints = head_layers.joints_of(fine)
    two = sheet(size, "two millimetres under", FRONT + 2.0, (8, 70), (16, 34), step=2.0)     # deep enough anywhere else (and beside the pit)
    before = feet.to_mm(size, two.v)
    moved, dropped = head_layers.faces_under_skin(body, [two], from_mm=0.0, joints=joints, log=lambda *_: None)
    assert moved > 0 and dropped == 0
    after = feet.to_mm(size, two.v)
    at_joint = (before[:, 1] > 30) & (before[:, 1] < 36)
    far = (before[:, 1] < 12) | (before[:, 1] > 54)
    # (z runs back: deeper is more. A depth reads half a voxel more than it is: 0.33 mm here.)
    assert (after[at_joint, 0] - FRONT).min() > head_layers.JOINT_MM - 0.4       # to JOINT_MM under the outline there
    assert np.abs(after[far] - before[far]).max() < 1e-4                # and as it was away from it
    # Without the joints nothing of it is too shallow.
    again = sheet(size, "again", FRONT + 2.0, (8, 70), (16, 34), step=2.0)
    assert head_layers.faces_under_skin(body, [again], from_mm=0.0, log=lambda *_: None) == (0, 0)
    # Measured at half the fineness, a depth may read up to a millimetre more than it is; so more is asked for
    # there (COARSE_MM), and what is a millimetre under the skin truly goes deeper.
    one = sheet(size, "a millimetre under", FRONT + 1.0, (8, 28), (16, 34), step=2.0)
    assert head_layers.faces_under_skin(body, [one], least_mm=head_layers.COARSE_MM, from_mm=0.0, fine_grid=False, log=lambda *_: None)[0] > 0
    assert (feet.to_mm(size, one.v)[:, 0] - FRONT).min() > 0.8


def test_a_part_of_him_is_measured_by_itself(tmp_path):
    body, size = block(tmp_path)
    shallow = sheet(size, "shallow", FRONT + 0.3, (50, 68), (20, 55))
    before = shallow.v.copy()
    # A box that does not hold it (a hand elsewhere): nothing is touched.
    assert head_layers.faces_under_skin(body, [shallow], from_mm=0.0, to_mm=79.0, box=(0.0, 79.0, 60.0, 79.0), log=lambda *_: None) == (0, 0)
    assert np.array_equal(shallow.v, before)
    # The box that holds it: it sinks.
    moved, _ = head_layers.faces_under_skin(body, [shallow], from_mm=0.0, to_mm=79.0, box=(0.0, 79.0, 10.0, 60.0), log=lambda *_: None)
    assert moved > 0 and depth_of(body, size, shallow).min() > 0.9


def test_a_band_leaves_what_lies_in_a_hand_to_the_hands_own_measure(tmp_path):
    body, size = block(tmp_path)
    shallow = sheet(size, "shallow", FRONT + 0.3, (50, 68), (20, 55))
    before = shallow.v.copy()
    hand = (0.0, 79.0, 45.0, 75.0, 10.0, 60.0)                          # a box that holds it
    assert head_layers.faces_under_skin(body, [shallow], from_mm=0.0, leave=[hand], log=lambda *_: None) == (0, 0)
    assert np.array_equal(shallow.v, before)
    elsewhere = (0.0, 79.0, 0.0, 20.0, 10.0, 60.0)                      # a box that does not
    assert head_layers.faces_under_skin(body, [shallow], from_mm=0.0, leave=[elsewhere], log=lambda *_: None)[0] > 0


def test_what_lies_under_the_fat_is_asked_more_of(tmp_path):
    body, size = block(tmp_path)
    # Two millimetres under the skin: deep enough for the fat itself, not for what lies under the fat.
    as_fat = sheet(size, "as fat", FRONT + 2.0, (50, 68), (16, 34), step=2.0)
    as_muscle = sheet(size, "as muscle", FRONT + 2.0, (50, 68), (16, 34), step=2.0)
    wanted = 1.0 + head_layers.UNDER_FAT_MM[0]
    assert head_layers.faces_under_skin(body, [as_fat], least_mm=1.0, from_mm=0.0, log=lambda *_: None) == (0, 0)
    assert head_layers.faces_under_skin(body, [as_muscle], least_mm=wanted, from_mm=0.0, log=lambda *_: None)[0] > 0
    assert (feet.to_mm(size, as_muscle.v)[:, 0] - FRONT).min() > wanted - 0.4      # (a depth reads a third of a millimetre more than it is)
