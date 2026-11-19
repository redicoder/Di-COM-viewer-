"""The feet under the skin, on a made-up pair of legs: the fat's surface is the skin's moved in, and what lies under
the skin lies under that.
Needs scipy, scikit-image and pyfqmr (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
pytest.importorskip("pyfqmr")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import feet, fine_skin  # noqa: E402
from anatomy_model.common import Structure  # noqa: E402

RADIUS, HALF_APART, HEIGHT = 30.0, 60.0, 300          # two round legs, millimetres
SPACING = (0.66, 1.0, 0.66)


def legs():
    """(the fine outline, the body's box (z, y, x mm), the skin's mesh in glTF metres)."""
    nz, nx = 160, 340
    zz, xx = np.mgrid[0:nz, 0:nx]
    z_mm, x_mm = (zz + 0.5) * SPACING[0], (xx + 0.5) * SPACING[2]
    size = np.array([nz * SPACING[0], float(HEIGHT), nx * SPACING[2]])
    centre_z, centre_x = size[0] / 2, size[2] / 2
    section = np.zeros((nz, nx), bool)
    for side in (-1, 1):
        section |= np.hypot(z_mm - centre_z, x_mm - (centre_x + side * HALF_APART)) < RADIUS
    cover = np.repeat(section[:, None, :], HEIGHT, axis=1).astype(np.uint8) * 255
    fine = fine_skin.FineOutline(cover, SPACING, (0.0, 0.0, 0.0), np.zeros(HEIGHT, bool))
    v, f = [], []
    rings, around = HEIGHT + 1, 192                     # triangles of a millimetre, as the skin's are in the feet
    for side in (-1, 1):
        start = len(v)
        for j in range(rings):
            for i in range(around):
                a = 2 * np.pi * i / around
                v.append((centre_z + RADIUS * np.sin(a), 1.0 * j, centre_x + side * HALF_APART + RADIUS * np.cos(a)))
        for j in range(rings - 1):
            for i in range(around):
                p, q = start + j * around + i, start + j * around + (i + 1) % around
                f += [(p, q, p + around), (q, q + around, p + around)]
    mm = np.array(v)
    gltf = feet.to_gltf(size, mm)
    f = np.array(f, np.uint32)
    # wound counter-clockwise seen from outside
    from anatomy_model.common import outward
    return fine, size, gltf, outward(gltf, f)


def depth_under(size, v):
    """How far each vertex lies under the nearer leg's surface, mm."""
    mm = feet.to_mm(size, v)
    far = np.minimum(*[np.hypot(mm[:, 0] - size[0] / 2, mm[:, 2] - (size[2] / 2 + side * HALF_APART)) for side in (-1, 1)])
    return RADIUS - far


def test_gltf_and_millimetres_are_each_others_inverse():
    size = np.array([100.0, 300.0, 200.0])
    mm = np.array([[10.0, 20.0, 30.0], [90.0, 280.0, 150.0]])
    assert np.allclose(feet.to_mm(size, feet.to_gltf(size, mm)), mm, atol=1e-3)


def test_the_fat_in_the_feet_is_the_skin_moved_in():
    fine, size, _, _ = legs()
    sv, sf = feet.sock(fine, size)
    assert len(sf) > 500
    mm = feet.to_mm(size, sv)
    assert mm[:, 1].max() < feet.UP_MM                                  # the feet only
    under = depth_under(size, sv)
    sides = (mm[:, 1] > 8.0) & (mm[:, 1] < feet.UP_MM - feet.LAP_MM)    # (the legs end flat below: there the depth is counted from the end)
    assert under[sides].min() > feet.FAT_MM - 0.5 and under[sides].max() < feet.FAT_MM + 0.8      # under the skin all over, and close under it
    rim = mm[:, 1] > feet.UP_MM - 2.0
    assert rim.any() and under[rim].min() > feet.RIM_MM - 0.7           # its rim lies deeper: under the labels' fat
    assert mm[:, 1].min() > feet.FAT_MM - 0.6                           # under the end faces as well
    edges = np.linalg.norm(sv[sf[:, 0]] - sv[sf[:, 1]], axis=1) * 1000.0
    assert 1.0 < np.median(edges) < 3.5                                 # in triangles of about EDGE_MM
    # Wound to look outwards (in glTF's axes): away from each leg's axis.
    tri = sv[sf[sides[sf].all(axis=1)]].astype(np.float64)
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    centre = tri.mean(axis=1)
    out = centre.copy()
    out[:, 0] -= np.sign(centre[:, 0]) * HALF_APART / 1000.0            # each leg's axis runs up through x = -+HALF_APART, z = 0
    out[:, 1] = 0.0
    assert (np.einsum("ij,ij->i", normal, out) > 0).mean() > 0.97
    # Nothing of him below UP_MM: no sock.
    empty = fine_skin.FineOutline(np.zeros_like(fine.cover), fine.spacing, fine.origin_mm, fine.fallback)
    assert len(feet.sock(empty, size)[1]) == 0


def test_what_lies_under_the_skin_of_the_feet_lies_under_the_fat():
    fine, size, _, _ = legs()
    centre = np.array([size[0] / 2, 0.0, size[2] / 2 + HALF_APART])
    heights = np.array([40.0, 120.0, 190.0, 215.0, 260.0])
    points = centre + np.stack([np.full(5, RADIUS - 1.0), heights, np.zeros(5)], axis=1)       # a bone's vertices 1 mm under the skin
    deep = centre + np.array([[5.0, 100.0, 5.0]])
    bone = Structure("a bone", "skeleton", feet.to_gltf(size, np.concatenate([points, deep])), np.array([[0, 1, 2], [2, 3, 4], [0, 4, 5]], np.uint32), (1, 1, 1))
    hair = Structure("hair", "skin", bone.v.copy(), bone.f.copy(), (0, 0, 0), streams={"NORMAL": None})
    moved = feet.drawn_under(fine, size, [bone, hair])
    assert moved == {"a bone": 4}                                       # the four in the feet; ribbons are not touched
    under = depth_under(size, bone.v)
    assert (under[:3] > feet.UNDER_MM - 0.4).all()                      # in the feet: under the fat's surface
    assert 1.0 < under[3] < under[2]                                    # passing back above them
    assert abs(under[4] - 1.0) < 0.05 and np.allclose(feet.to_mm(size, bone.v)[5], deep[0], atol=0.01)     # above the feet, and deep: as they were


def test_a_toes_bones_are_moved_as_a_whole_into_the_toe():
    fine, size, _, _ = legs()
    centre = np.array([size[0] / 2, 0.0, size[2] / 2 - HALF_APART])
    # A small bone, 8 mm thick, whose one side lies 0.5 mm under the skin: 3 mm further in, the whole of it lies deep enough.
    rng = np.random.default_rng(3)
    blob = rng.normal(size=(300, 3))
    blob = blob / np.linalg.norm(blob, axis=1, keepdims=True) * np.array([4.0, 12.0, 4.0])
    bone = centre + np.array([0.0, 40.0, RADIUS - 4.5]) + blob
    move = feet.fit(fine, bone)
    assert move[1] == 0 and move[0] == 0 and -4 <= move[2] <= -2         # across the body only, inwards, and no further than needed
    assert (depth_under(size, feet.to_gltf(size, bone + move)) > feet.UNDER_MM - 0.5).all()
    # A bone that lies deep already stays.
    assert not feet.fit(fine, centre + np.array([0.0, 40.0, 5.0]) + blob).any()
    # In the build: the toe's bone goes as a whole (every vertex by the same), a bone that reaches above the toes does not.
    f = np.array([[0, 1, 2]], np.uint32)
    toe = Structure("phalanges", "skeleton", feet.to_gltf(size, bone), f, (1, 1, 1))
    shin = Structure("a long bone", "skeleton", feet.to_gltf(size, bone + np.array([0.0, 60.0, 0.0]) * (np.arange(300)[:, None] > 150)), f, (1, 1, 1))
    before = feet.to_mm(size, toe.v)
    feet.drawn_under(fine, size, [toe, shin])
    after = feet.to_mm(size, toe.v)
    assert np.allclose(after - before, (after - before)[0], atol=0.3) and abs((after - before)[0, 2] - move[2]) < 0.3
    assert (depth_under(size, shin.v) > feet.UNDER_MM - 0.5).all()        # (drawn in vertex by vertex)


def test_what_is_left_of_a_toes_bone_near_the_skin_goes_towards_its_own_axis():
    fine, size, _, _ = legs()
    centre = np.array([size[0] / 2, 0.0, size[2] / 2 - HALF_APART])
    rng = np.random.default_rng(5)
    blob = rng.normal(size=(400, 3))
    blob = blob / np.linalg.norm(blob, axis=1, keepdims=True) * np.array([4.0, 14.0, 4.0])
    bone = centre + np.array([0.0, 40.0, RADIUS - 5.0]) + blob          # its outer side lies 1 mm under the skin
    axis_x = centre[2] + RADIUS - 5.0
    out = feet.to_axis(fine, bone)
    moved = np.linalg.norm(out - bone, axis=1) > 0.05
    assert 20 < moved.sum() < 250                                       # the side towards the skin, not the whole of it
    assert (depth_under(size, feet.to_gltf(size, out)) > feet.UNDER_MM - 0.4).all()
    before, after = np.hypot(bone[:, 0] - centre[0], bone[:, 2] - axis_x), np.hypot(out[:, 0] - centre[0], out[:, 2] - axis_x)
    assert (after <= before + 0.3).all()                                # nearer its own axis, or where it was: never further out
    assert np.abs(out[:, 1] - bone[:, 1]).max() < 1.5                   # and across its length, not along it
