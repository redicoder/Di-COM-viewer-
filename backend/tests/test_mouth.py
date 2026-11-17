"""The mouth's jaw weights on made-up blocks: the flesh on the lower jaw goes with it, the flesh on the upper stays,
nothing flows across the sheet between them, and a point turned about the hinge goes where the shader will take it.
Needs scikit-image and scipy (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import mouth  # noqa: E402
from anatomy_model.common import Structure, load_structures, save_structures  # noqa: E402
from anatomy_model.glb import read_glb, write_glb  # noqa: E402


def block():
    """Tissue 20 x 24 x 20 voxels: held at 0 along the top, at 1 along the bottom; a sheet half way up over the
    front three quarters (z < 15), none behind."""
    shape = (20, 24, 20)
    node = np.ones(shape, bool)
    zero, one = np.zeros(shape, bool), np.zeros(shape, bool)
    zero[:, -1, :] = True
    one[:, 0, :] = True
    side = np.zeros(shape, np.int8)
    side[:15, 12:, :] = 1
    side[:15, :12, :] = -1
    return node, zero, one, side


def test_nothing_flows_across_the_sheet_and_it_blends_behind_it():
    node, zero, one, side = block()
    w = mouth.solve_weights(node, zero, one, side, log=lambda *_: None)
    # In front, right at the sheet: its two sides differ by most of the whole step.
    assert w[2, 11, 10] - w[2, 12, 10] > 0.6
    assert w[2, 11, 10] > 0.8 and w[2, 12, 10] < 0.2
    # Behind the sheet's end the tissue is one piece: neighbours across that height differ little.
    assert abs(w[18, 11, 10] - w[18, 12, 10]) < 0.1
    assert 0.3 < w[18, 11, 10] < 0.7
    # And it is a blend everywhere: between the held values, rising towards the lower jaw.
    assert w.min() >= 0.0 and w.max() <= 1.0
    assert (np.diff(w[18, :, 10]) <= 1e-4).all()


def test_stiffen_gives_what_is_mostly_with_a_jaw_to_it_wholly():
    w = np.array([0.0, 0.05, 0.3, 0.5, 0.7, 0.95, 1.0], np.float32)
    s = mouth.stiffen(w)
    assert s[0] == 0.0 and s[1] == 0.0 and s[-1] == 1.0 and s[-2] == 1.0
    assert s[3] == pytest.approx(0.5)
    assert (np.diff(s) >= 0).all()
    assert s[2] == pytest.approx(1.0 - s[4], abs=1e-6)


def test_nearest_fill_takes_only_valid_values():
    values = np.array([[1.0, 5.0, 9.0]])
    valid = np.array([[True, False, False]])
    assert mouth.nearest_fill(values, valid).tolist() == [[1.0, 1.0, 1.0]]


def test_turned_carries_a_point_in_front_of_the_hinge_down_and_back():
    m = mouth.Mouth.__new__(mouth.Mouth)
    m.hinge, m.axis = np.array([0.0, 0.8, 0.0]), np.array([1.0, 0.0, 0.0])
    v = np.array([[0.0, 0.75, 0.11], [0.0, 0.75, 0.11], [0.02, 0.9, 0.05]])
    out = mouth.turned(m, v, np.array([1.0, 0.5, 0.0]))
    assert out[0, 1] < v[0, 1] - 0.025 and out[0, 2] < v[0, 2]          # the whole turn: down by centimetres, and back
    assert out[0, 1] < out[1, 1] < v[1, 1]                              # half the weight, half the way
    assert np.allclose(out[2], v[2])                                    # no weight: it stays
    assert np.linalg.norm(out[0] - m.hinge) == pytest.approx(np.linalg.norm(v[0] - m.hinge))


def test_fill_columns_carries_known_heights_over_the_domain():
    values = np.zeros((9, 9))
    known = np.zeros((9, 9), bool)
    known[:, 0], known[:, -1] = True, True
    values[:, -1] = 8.0
    h = mouth.fill_columns(values, known, np.ones((9, 9), bool), rounds=600)
    assert np.allclose(h[4], np.arange(9.0), atol=0.05)                 # a straight slope between the two known edges


def test_jaw_weights_survive_the_cache_and_the_glb(tmp_path):
    v = np.array([[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]], np.float32)
    f = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], np.uint32)
    weights = np.array([[0.0, 0.0], [0.25, 0.0], [0.5, 0.0], [1.0, 0.0]], np.float32)
    s = Structure("chin", "skin", v, f, (0.8, 0.6, 0.5), bake=np.full((4, 4), 200, np.uint8), albedo=np.full((4, 3), 180, np.uint8), extra=np.zeros(4, np.uint8), data3=weights)
    save_structures(tmp_path / "skin.npz", [s])
    assert np.allclose(load_structures(tmp_path / "skin.npz")[0].data3, weights)
    write_glb(tmp_path / "a.glb", [s])
    assert np.allclose(read_glb(tmp_path / "a.glb")[0].data3, weights, atol=1e-6)


def test_the_lower_lip_is_drawn_down_before_the_jaw_turns():
    m = mouth.Mouth.__new__(mouth.Mouth)
    m.hinge, m.axis = np.array([0.0, 0.8, 0.0]), np.array([1.0, 0.0, 0.0])
    m.lip_down = np.array([0.0, -1.0, 0.0])
    v = np.array([[0.0, 0.75, 0.11], [0.0, 0.75, 0.11]])
    out = mouth.turned(m, v, np.array([0.0, 0.0]), 1.0, np.array([1.0, 0.0]))
    assert out[0, 1] == pytest.approx(0.75 - mouth.LIP_PULL_MM * 0.001)     # the lip's own way down, the jaw not turned
    assert np.allclose(out[1], v[1])                                        # what is not of the lip stays
    half = mouth.turned(m, v, np.array([0.0, 0.0]), 0.5, np.array([1.0, 0.0]))
    assert half[0, 1] == pytest.approx(0.75 - 0.5 * mouth.LIP_PULL_MM * 0.001)


def test_the_upper_lip_is_lifted_by_itself_and_does_not_go_with_the_jaw():
    m = mouth.Mouth.__new__(mouth.Mouth)
    m.hinge, m.axis = np.array([0.0, 0.8, 0.0]), np.array([1.0, 0.0, 0.0])
    m.lip_down, m.lip_up = np.array([0.0, -1.0, 0.0]), np.array([0.0, 1.0, 0.0])
    v = np.array([[0.0, 0.76, 0.11], [0.0, 0.74, 0.11]])                    # a point of the upper lip, one of the lower
    pull = np.array([-1.0, 1.0])                                            # (a negative number: the upper lip's)
    out = mouth.turned(m, v, np.array([0.0, 0.0]), 1.0, pull)
    assert out[0, 1] == pytest.approx(0.76 + mouth.LIP_LIFT_MM * 0.001)     # up its own way
    assert out[1, 1] == pytest.approx(0.74 - mouth.LIP_PULL_MM * 0.001)     # the lower lip down its own
    only_jaw = mouth.turned(m, v, np.array([0.0, 0.0]), 1.0, pull, lift=0.0)
    assert np.allclose(only_jaw[0], v[0])                                   # the mouth opened, the upper lip not taken: it stays
    half = mouth.turned(m, v, np.array([0.0, 0.0]), 0.0, pull, lift=0.5)
    assert half[0, 1] == pytest.approx(0.76 + 0.5 * mouth.LIP_LIFT_MM * 0.001) and np.allclose(half[1], v[1])


def test_a_rows_biting_edge_is_each_tooths_tip_over_its_whole_footprint():
    # A lower tooth that leans: its tip (row 20) over one column, its root (top at row 12) under the next columns.
    row = np.zeros((30, 24, 30), bool)
    row[14, 10:21, 15] = True
    row[15:19, 4:13, 15] = True
    has, distance, edge = mouth.biting_edge(row, (0.66, 1.0, 0.66), upper=False)
    assert has[14, 15] and has[17, 15] and not has[5, 5]
    assert edge[17, 15] > 17.0                                              # under the root's columns the edge is still the tip's level (20), not the root's top (12)
    assert distance[14, 15] == 0.0 and distance[14, 20] == pytest.approx(5 * 0.66)


def test_a_drawn_muscle_is_moved_off_the_gum_and_into_the_lip():
    # A lower row of teeth (their edge at row 20) on a ridge of bone; a muscle sheet standing 1 mm before the ridge.
    m = mouth.Mouth.__new__(mouth.Mouth)
    m.grid = mouth.Grid(np.zeros(3), np.ones(3), (30, 40, 30))
    row = np.zeros(m.grid.shape, bool)
    row[10:13, 12:21, 4:26] = True
    bone = np.zeros(m.grid.shape, bool)
    bone[10:14, 0:14, 4:26] = True
    m.teeth_lower, m.lower = row, bone | row
    m.teeth_upper, m.upper = np.zeros(m.grid.shape, bool), np.zeros(m.grid.shape, bool)
    m.drawn_lower = m.drawn_upper = None
    m.u_of_x = m.grid.axis(2) - 15.0                                    # the mouth's middle is the grid's
    ridges = mouth.gum_ridges(m)
    assert ridges[11, 10, 15] and not ridges[11, 30, 15]                # the ridge under the teeth's edge; not over it
    m.u_of_x = m.grid.axis(2) + 20.0                                    # (a mouth that lies beside this ridge: the cheek's, left alone)
    assert not mouth.gum_ridges(m)[11, 10, 15]
    m.u_of_x = m.grid.axis(2) - 15.0

    class Him:
        size_mm = (0.0, 0.0, 0.0)

    ys = np.arange(4.0, 17.0, 1.0)
    v_mm = np.array([[9.0, y, x] for y in ys for x in (13.0, 17.0)])    # the sheet, 1 mm before the ridge's face (z = 10), in millimetres (z, y, x)
    f = np.array([[2 * k, 2 * k + 2, 2 * k + 1] for k in range(len(ys) - 1)], np.uint32)
    sheet = Structure("mentalis", "muscles", mouth.to_gltf(Him, v_mm).astype(np.float32), f, (0.5, 0.2, 0.2))
    assert mouth.clear_of_the_gums(Him, m, [sheet], log=lambda *_: None) == 1
    after = mouth.to_mm(Him, sheet.v)
    assert len(sheet.f) == len(f)                                       # nothing cut
    assert after[:, 0].max() < 8.0 and after[:, 0].min() > 5.5          # every point about 3 mm before the ridge now (its face lies at z = 10)
    assert np.abs(after[:, 1] - v_mm[:, 1]).max() < 1.0                 # moved straight out, not along the jaw
