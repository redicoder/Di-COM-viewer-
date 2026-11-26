"""A finger's bones made to follow a finger that lies bent otherwise than they do, on a made-up finger; and the
voxels a closed mesh fills. Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import fine_skin, hands  # noqa: E402
from anatomy_model.common import solid_of  # noqa: E402

SPACING = (0.66, 1.0, 0.66)
Z0, X0, KNUCKLE, RADIUS, LEAN = 20.0, 20.0, 50.0, 9.0, np.tan(np.radians(8.0))


def middle(y):
    """The finger's middle line: straight up to the knuckle, leaning 8 degrees backwards (towards +z) beyond it."""
    return Z0 + np.clip(np.asarray(y, np.float64) - KNUCKLE, 0.0, None) * LEAN


def finger():
    """A finger of 9 mm radius, 110 mm long, bent at 50 mm."""
    zz, yy, xx = np.mgrid[0:80, 0:112, 0:62]
    z, y, x = (zz + 0.5) * 0.66, (yy + 0.5) * 1.0, (xx + 0.5) * 0.66
    cover = ((np.hypot(z - middle(y), x - X0) < RADIUS) & (y < 110.0)).astype(np.uint8) * 255
    return fine_skin.FineOutline(cover, SPACING, (0.0, 0.0, 0.0), np.zeros(112, bool))


def bones(y0=10.0, y1=97.0, radius=4.0, around=20, along=60):
    """A finger's bones as the scanner had them, the finger straight, and as BoneHub has them: one piece. Its
    vertices (mm; z, y, x), standing at the finger's foot."""
    ys = np.linspace(y0, y1, along)
    angles = np.linspace(0.0, 2 * np.pi, around, endpoint=False)
    return np.array([[Z0 + radius * np.cos(a), y, X0 + radius * np.sin(a)] for y in ys for a in angles])


def test_a_fingers_bones_follow_a_finger_that_lies_bent_otherwise():
    fine = finger()
    v = bones()
    least = hands.UNDER_MM + hands.FOLLOW_SPARE_MM
    before = fine_skin.depths(fine, v, 12.0)
    assert (before < least).sum() > 100 and before.min() < 0.5          # towards its tip the bone lies at the skin (the finger leans away from it)
    out, bend = hands.following(fine, v)
    assert 2.0 <= bend <= hands.FOLLOW_MM + 1e-6
    assert (fine_skin.depths(fine, out, 12.0) > least - 0.6).all()      # all of it under the skin now, to its tip
    foot = v[:, 1] < KNUCKLE - 8.0
    assert np.abs(out[foot] - v[foot]).max() < 0.6                      # where it lay well in the finger it stays,
    tip = v[:, 1] > 90.0
    shift = (out[tip] - v[tip]).mean(axis=0)
    assert shift[0] > 2.0 and abs(shift[2]) < 1.0 and abs(shift[1]) < 1.0     # and its tip goes the way the finger leans, across its length
    moved = np.linalg.norm(out - v, axis=1)
    rings = moved.reshape(60, 20).mean(axis=1)
    assert np.abs(np.diff(rings)).max() < 1.5                           # it bends: no step from one stretch of it to the next


def test_bones_that_lie_well_in_their_finger_are_left_as_they_are():
    fine = finger()
    v = bones(y1=45.0)                                                  # only the finger's straight part
    out, bend = hands.following(fine, v)
    assert bend == 0.0 and np.allclose(out, v)
    few, bend = hands.following(fine, v[:10])                           # (too few vertices to be a bone: untouched)
    assert bend == 0.0 and np.allclose(few, v[:10])


def test_in_the_build_a_bent_fingers_bones_end_under_its_skin():
    fine = finger()
    v = bones()
    out, move, bend, thinned = hands.into_finger(fine, v)
    assert (fine_skin.depths(fine, out, 12.0) > hands.UNDER_MM - 0.6).all()
    assert bend > 0 or np.linalg.norm(move) > 0


def test_what_is_still_too_near_the_skin_goes_towards_the_bones_own_middle_line():
    fine = finger()
    # Bones that follow the bent finger, but too thick for it: 7.5 mm of radius in a finger of 9.
    ys = np.linspace(10.0, 100.0, 60)
    angles = np.linspace(0.0, 2 * np.pi, 20, endpoint=False)
    v = np.array([[middle(y) + 7.5 * np.cos(a), y, X0 + 7.5 * np.sin(a)] for y in ys for a in angles])
    assert (fine_skin.depths(fine, v, 12.0) < hands.UNDER_MM - 0.2).sum() > 500
    out = hands.to_middle(fine, v)
    assert (fine_skin.depths(fine, out, 12.0) > hands.UNDER_MM - 0.4).all()       # thinner, and under the skin all along the bend
    before = np.hypot(v[:, 0] - middle(v[:, 1]), v[:, 2] - X0)
    after = np.hypot(out[:, 0] - middle(out[:, 1]), out[:, 2] - X0)
    assert (after < before + 0.2).all() and after.min() > 5.5           # towards the finger's own bent middle, no further than it takes
    assert np.abs(out[:, 1] - v[:, 1]).max() < 1.5                      # across the length, not along it
    assert np.allclose(hands.to_middle(fine, bones(y1=45.0)), bones(y1=45.0))     # bones that lie deep enough stay


def test_the_voxels_a_closed_mesh_fills():
    # A box of 10 x 12 x 8 mm, as twelve big triangles, on voxels of 1.32 x 2 x 1.32 mm.
    lo, hi = np.array([20.0, 30.0, 40.0]), np.array([30.0, 42.0, 48.0])
    c = np.array([[z, y, x] for z in (lo[0], hi[0]) for y in (lo[1], hi[1]) for x in (lo[2], hi[2])])
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 7, 5], [4, 6, 7], [0, 5, 1], [0, 4, 5], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    first, block = solid_of(c, f, (60, 60, 60), (1.32, 2.0, 1.32))
    volume = block.sum() * 1.32 * 2.0 * 1.32
    assert 0.9 * 960 < volume < 1.6 * 960                               # the box, with the voxels its faces pass through
    middle_voxel = np.floor((lo + hi) / 2 / np.array([1.32, 2.0, 1.32])).astype(int) - np.array(first)
    assert block[tuple(middle_voxel)]                                   # filled, not a shell
    assert not block[0].any() and not block[-1].any()                   # with room round it in its block
    assert solid_of(c + 1000.0, f, (60, 60, 60), (1.32, 2.0, 1.32)) is None       # a mesh outside the grid fills none of it
