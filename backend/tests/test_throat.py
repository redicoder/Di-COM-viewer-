"""The throat's parts that can be checked on made-up blocks: the jaw's axis under its joints (the condyles slide
forward as it opens), the tongue's root held, and the tongue lying down as the mouth opens.
Needs scikit-image and scipy (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import mouth, throat  # noqa: E402


class _Body:
    size_mm = (0.0, 0.0, 0.0)


class _CtToBody:
    """A CT whose slices go down the body, rows back, columns to his left, 1 mm each."""

    @staticmethod
    def grid_points(index):
        index = np.asarray(index, np.float64)
        return np.stack([index[:, 1], 200.0 - index[:, 0], index[:, 2]], axis=1)      # z back, y up, x left


def _mandible():
    """A jaw of bars: two upright parts (their tops the condyles), the body under them, the chin's bar in front."""
    data = np.zeros((60, 60, 80), np.uint8)
    for columns in (slice(10, 15), slice(65, 70)):
        data[10:50, 40:50, columns] = 1                                               # the upright part
        data[45:50, 5:50, columns] = 1                                                # the body
    data[45:50, 5:10, 10:70] = 1
    return data


def test_the_jaws_axis_lies_under_the_condyles_and_they_slide_forward():
    m = mouth.Mouth.__new__(mouth.Mouth)
    m.ct = {"raw": {"craniofacial_structures": (_mandible(), {1: "mandible"})}, "to_body": _CtToBody()}
    point, axis = mouth.find_hinge(_Body(), m)
    right, left = m.condyles
    assert right[0] < left[0] and np.allclose(axis, [1.0, 0.0, 0.0], atol=1e-6)
    assert point[1] == pytest.approx(right[1] - mouth.AXIS_BELOW_MM * 0.001)          # straight under the condyle's head
    assert point[0] == pytest.approx(right[0]) and point[2] == pytest.approx(right[2])
    # Turned about that axis, the condyle's head goes forward (as a real one slides onto the bone before its socket),
    # and a point at the chin goes down and back.
    m.hinge, m.axis, m.lip_down = point, axis, None
    chin = right + np.array([0.0, -0.045, 0.040])
    out = mouth.turned(m, np.array([right, chin]), np.array([1.0, 1.0]))
    slide = mouth.AXIS_BELOW_MM * 0.001 * np.sin(np.radians(mouth.OPEN_DEGREES))
    assert out[0, 2] - right[2] == pytest.approx(slide, rel=1e-6)
    assert out[1, 1] < chin[1] - 0.008 and out[1, 2] < chin[2]


def _mouth_with_a_row(throat_there: bool):
    """A grid of 1 mm voxels with a lower row of teeth (an arch whose edge is level at y = 20 mm) and a tongue."""
    m = mouth.Mouth.__new__(mouth.Mouth)
    m.grid = mouth.Grid(np.zeros(3), np.ones(3), (60, 40, 50))
    row = np.zeros(m.grid.shape, bool)
    for z in range(5, 30):
        row[z, 12:20, 8:11] = True
        row[z, 12:20, 39:42] = True
    row[5:8, 12:20, 8:42] = True
    m.teeth_lower = row
    m.tongue = np.zeros(m.grid.shape, bool)
    m.tongue[8:56, 5:30, 13:37] = True
    m.lip_down = np.array([0.0, -1.0, 0.0])

    class Face:
        ey = np.array([0.0, 1.0, 0.0])

    m.face = Face()
    m.throat = throat.Throat(None, 30.0, 25.0, 30.0, None, None, None, None, None, sink_from=(30.0, 52.0)) if throat_there else None
    return m


def test_the_tongue_lies_down_as_the_mouth_opens():
    m = _mouth_with_a_row(True)
    body = _Body()
    level = 20.0 - 1.5                                                                # the lower row's biting edge, less a millimetre and a half

    def pull_mm(z, y):
        return float(throat.sink(body, m, mouth.to_gltf(body, np.array([[z, y, 25.0]])))[0]) * mouth.LIP_PULL_MM

    high = pull_mm(15.0, level + 12.0)
    assert high == pytest.approx((1.0 - throat.KEEP_RELIEF) * 12.0, rel=0.03)         # most of the way down to the level
    assert pull_mm(15.0, level + 6.0) == pytest.approx(high / 2.0, rel=0.08)          # in proportion: its relief is kept, flatter
    assert pull_mm(15.0, level - 12.0) < 0.1                                          # what lies under the level stays
    # At its root it is drawn lower by SINK_ROOT_MM (a point as high over the level there goes that much further).
    assert pull_mm(54.0, level + 6.0) - pull_mm(15.0, level + 6.0) == pytest.approx((1.0 - throat.KEEP_RELIEF) * throat.SINK_ROOT_MM, rel=0.1)
    # Without a throat behind it nothing is drawn down.
    assert not throat.sink(body, _mouth_with_a_row(False), mouth.to_gltf(body, np.array([[15.0, level + 12.0, 25.0]]))).any()


def test_the_tongues_root_is_held_when_the_throat_is_behind_it():
    points = np.array([[10.0, 20.0, 25.0], [55.0, 20.0, 25.0]])                       # its tip, its root
    given = np.array([0.9, 0.9], np.float32)
    with_throat = mouth.with_the_tongue(_mouth_with_a_row(True), points, given)
    without = mouth.with_the_tongue(_mouth_with_a_row(False), points, given)
    assert with_throat[0] == pytest.approx(1.0) and without[0] == pytest.approx(1.0)  # the front goes with the jaw wholly
    assert with_throat[1] == pytest.approx(0.2, abs=0.02)                             # the root a fifth of the turn at most
    assert without[1] == pytest.approx(0.9)                                           # (as the flesh round it, where no throat is drawn)
