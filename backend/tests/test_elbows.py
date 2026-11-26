"""The elbows' bones read from the photographs where the scanner's picture ends: on a made-up arm (a pale bone with
red marrow, deep in red muscle, under pale fat) and on made-up arm bones cut by a plane. And BoneHub's arm bones
moved onto the photographs' bone, which they lie a few millimetres beside.
Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from scipy import ndimage  # noqa: E402

from anatomy_model import elbows  # noqa: E402

SPACING = (0.66, 1.0, 0.66)
MIDDLE, ARM, FAT, BONE, MARROW = 43.0, 38.0, 4.0, 10.0, 3.0             # mm: the arm's middle line, its radius, its fat, its bone


def arm(scrap=None, film=True, bone=True, length=80):
    """An arm of 38 mm radius along y, 80 mm of it: 4 mm of pale fat under the skin, red muscle, and in its middle
    a pale bone of 10 mm radius with red marrow, from 5 mm to 5 mm short of its end. With a film of pale fascia
    one voxel thick through the muscle, and a pale ball `scrap` ((z, y, x), radius; mm) if asked for.
    Gives (cover, tissue, depth, the bone with its marrow, the points' mm)."""
    zz, yy, xx = np.mgrid[0:130, 0:length, 0:130]
    z, y, x = (zz + 0.5) * SPACING[0], (yy + 0.5) * SPACING[1], (xx + 0.5) * SPACING[2]
    r = np.hypot(z - MIDDLE, x - MIDDLE)
    tissue = r < ARM
    cover = np.where(tissue, 1.0, 0.0).astype(np.float32)               # red muscle,
    cover[tissue & (r > ARM - FAT)] = 0.0                               # pale fat under the skin,
    rod = (r < BONE) & (y > 5.0) & (y < length - 5.0)
    if bone:
        cover[rod & (r >= MARROW)] = 0.05                               # the pale bone (its marrow stays red)
    if film:
        cover[tissue & (xx == 105)] = 0.1                               # a sheet of fascia, 17 mm beside the bone
    if scrap is not None:
        centre, radius = scrap
        cover[np.sqrt((z - centre[0]) ** 2 + (y - centre[1]) ** 2 + (x - centre[2]) ** 2) < radius] = 0.05
    depth = ndimage.distance_transform_edt(tissue, sampling=SPACING)
    return cover, tissue, depth, rod, (z, y, x)


def cm3(mask):
    return float(mask.sum()) * float(np.prod(SPACING)) / 1000.0


def test_the_bone_is_the_pale_tissue_deep_in_the_muscle_with_its_marrow():
    cover, tissue, depth, rod, (z, y, x) = arm()
    got = elbows.mass(cover, tissue, depth, np.ones(cover.shape, bool), SPACING)
    r = np.hypot(z - MIDDLE, x - MIDDLE)
    assert got[(r < BONE - 1.0) & (y > 8.0) & (y < 72.0)].all()         # the bone, and the red marrow it encloses,
    assert not got[r > BONE + 1.0].any()                                # and nothing else: not the fat under the skin (pale,
    assert abs(cm3(got) - cm3(rod)) < 0.1 * cm3(rod)                    # but not deep), not the film of fascia (deep, but thin)


def test_what_is_not_allowed_is_not_bone():
    cover, tissue, depth, rod, (z, y, x) = arm()
    allowed = np.broadcast_to(x < MIDDLE, cover.shape)                  # (as beyond the CT's edge: one side of a plane)
    got = elbows.mass(cover, tissue, depth, allowed, SPACING)
    assert got.any() and not got[np.broadcast_to(x > MIDDLE + 2.0, cover.shape)].any()
    assert not elbows.mass(cover, tissue, depth, np.zeros(cover.shape, bool), SPACING).any()


def test_a_scrap_beside_the_bone_is_left_out_whatever_it_would_be_alone():
    small = ((MIDDLE - 21.0, 40.0, MIDDLE), 4.0)                        # 0.27 cm3: under PIECE_CM3
    cover, tissue, depth, rod, (z, y, x) = arm(scrap=small)
    got = elbows.mass(cover, tissue, depth, np.ones(cover.shape, bool), SPACING)
    assert not got[np.broadcast_to(z < MIDDLE - BONE - 2.0, cover.shape)].any()
    # A ball of 1.8 cm3: a piece by PIECE_CM3, but under PIECE_SHARE of the bone beside it: left out. Alone, it is kept.
    ball = ((MIDDLE - 21.0, 40.0, MIDDLE), 7.5)
    cover, tissue, depth, rod, (z, y, x) = arm(scrap=ball)
    beside = np.broadcast_to(z < MIDDLE - BONE - 2.0, cover.shape)
    size = 4.0 / 3.0 * np.pi * 7.5 ** 3 / 1000.0
    pale = rod & (np.hypot(z - MIDDLE, x - MIDDLE) >= MARROW)           # (a piece's size is its pale tissue's: the marrow is filled afterwards)
    assert elbows.PIECE_CM3 * 1.1 < size < 0.9 * elbows.PIECE_SHARE * cm3(pale)     # (what the test is about)
    got = elbows.mass(cover, tissue, depth, np.ones(cover.shape, bool), SPACING)
    assert got.any() and not got[beside].any()
    cover, tissue, depth, rod, _ = arm(scrap=ball, bone=False)
    alone = elbows.mass(cover, tissue, depth, np.ones(cover.shape, bool), SPACING)
    assert alone[beside].any() and abs(cm3(alone) - size) < 0.25 * size


def test_a_spur_on_the_bone_is_taken_off():
    cover, tissue, depth, rod, (z, y, x) = arm(film=False)
    spur = (np.abs(z - MIDDLE) < 1.5) & (np.abs(y - 40.0) < 1.6) & (x > MIDDLE) & (x < MIDDLE + 22.0)   # a peg 3 mm thick, 12 mm out of the bone
    cover[np.broadcast_to(spur, cover.shape)] = 0.05
    got = elbows.mass(cover, tissue, depth, np.ones(cover.shape, bool), SPACING)
    r = np.hypot(z - MIDDLE, x - MIDDLE)
    assert got[(r < BONE - 1.0) & (y > 8.0) & (y < 72.0)].all() and not got[r > BONE + 1.5].any()


def test_an_arm_of_muscle_only_has_no_bone():
    cover, tissue, depth, _, _ = arm(bone=False)
    assert not elbows.mass(cover, tissue, depth, np.ones(cover.shape, bool), SPACING).any()


def tube(a, b, radius, around=24, step=1.5):
    """A bone as a tube of vertices from `a` to `b` (mm; z, y, x)."""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    along = (b - a) / np.linalg.norm(b - a)
    u = np.cross(along, [1.0, 0.0, 0.0])
    u /= np.linalg.norm(u)
    w = np.cross(along, u)
    ts = np.arange(0.0, np.linalg.norm(b - a), step)
    angles = np.linspace(0.0, 2 * np.pi, around, endpoint=False)
    return np.array([a + t * along + radius * (np.cos(k) * u + np.sin(k) * w) for t in ts for k in angles])


ELBOW = np.array([150.0, 1250.0, 20.0])                                 # where the made-up arm's bones meet: beyond the edge
EDGE = 50.0


def cut_arm(side="right", edge=EDGE):
    """His arm's three bones as BoneHub has them: the humerus from the shoulder and the ulna and the radius from the
    wrist, all running out to the elbow, which lies 30 mm beyond the CT's edge, and all cut flat by that edge."""
    bones = {"humerus": tube((150.0, 1560.0, 95.0), ELBOW, 11.0),
             "ulna": tube((115.0, 900.0, 97.0), ELBOW, 7.0),
             "radius": tube((99.6, 900.0, 122.6), ELBOW + [-14.0, 0.0, 6.0], 6.0)}
    out = {}
    for name, v in bones.items():
        if edge is not None:
            v = v.copy()
            v[:, 2] = np.maximum(v[:, 2], edge)                         # what lay beyond the edge: a flat face on it
        if side == "left":
            v = v * [1.0, 1.0, -1.0] + [0.0, 0.0, 576.0]                # (x grows to his left)
        out[f"{side} {name}"] = v
    return out


def test_the_frame_of_an_elbow_is_found_from_the_bones_the_edge_cuts():
    fr = elbows.frame(cut_arm(), "right")
    assert fr is not None and fr.edge == pytest.approx(EDGE) and fr.inward == 1.0
    # The lines of the whole stretches meet where the bones would: to a few mm (a stretch of a leaning bone between two
    # levels is fitted a degree off its line, and the joint lies 200 mm on; what goes by it reaches REACH_MM, 36).
    assert np.linalg.norm(fr.joint - ELBOW) < 8.0
    assert fr.low < 1150.0 and fr.high > 1400.0                         # the stretch without bone: from the forearm's cut to the humerus's
    assert len(fr.lines) == 3
    assert elbows.from_lines(ELBOW, fr.lines) < 8.0
    start, end = fr.lines[0]                                            # the humerus's: from where it is whole, on past the joint
    assert start[2] > EDGE and start[1] > end[1]
    assert np.linalg.norm(end - ELBOW) == pytest.approx(elbows.BEYOND_MM, abs=5.0) and end[1] < ELBOW[1]


def test_the_left_arm_is_the_right_arms_mirror():
    right, left = elbows.frame(cut_arm(), "right"), elbows.frame(cut_arm("left"), "left")
    assert left.inward == -1.0 and left.edge == pytest.approx(576.0 - EDGE)
    assert np.allclose(left.joint * [1, 1, -1] + [0, 0, 576.0], right.joint, atol=0.5)
    assert (left.low, left.high) == pytest.approx((right.low, right.high))


def test_an_arm_the_edge_does_not_cut_has_no_frame_and_neither_has_one_without_its_bones():
    assert elbows.frame(cut_arm(edge=None), "right") is None            # whole: its outermost point is no cut
    assert elbows.frame(cut_arm(), "left") is None                      # (no left arm there)
    bones = cut_arm()
    del bones["right ulna"]
    assert elbows.frame(bones, "right") is None


def test_the_levels_at_which_a_bone_is_cut():
    v = cut_arm()["right humerus"]
    levels = elbows.cut_levels(v, EDGE, 1.0)
    # From the elbow up to where the humerus's near side (11 mm of bone from its line) comes clear of the edge: 177 mm.
    assert min(levels) <= ELBOW[1] + 4.0 and 1415.0 < max(levels) < 1435.0
    assert np.all(np.diff(levels) == 4.0)                               # (every level between)
    assert elbows.cut_levels(v, EDGE - 20.0, 1.0) == []


def test_how_far_a_point_lies_from_the_lines():
    lines = [(np.array([0.0, 0.0, 0.0]), np.array([0.0, 10.0, 0.0])), (np.array([20.0, 0.0, 0.0]), np.array([20.0, 0.0, 5.0]))]
    points = np.array([[3.0, 5.0, 0.0],                                 # beside the first,
                       [0.0, 14.0, 3.0],                                # past its end: measured to the end,
                       [20.0, 0.0, 2.0],                                # on the second,
                       [16.0, 0.0, 5.0]])
    assert np.allclose(elbows.from_lines(points, lines), [3.0, 5.0, 0.0, 4.0])
    assert elbows.from_lines(points.reshape(2, 2, 3), lines).shape == (2, 2)


def test_the_lines_are_those_of_the_bones_as_moved_and_the_cut_is_the_cts():
    bones = cut_arm()
    moved = {name: v + [2.0, 0.0, -3.0] for name, v in bones.items()}
    as_placed, as_moved = elbows.frame(bones, "right"), elbows.frame(bones, "right", lines_from=moved)
    assert (as_moved.edge, as_moved.low, as_moved.high, as_moved.top, as_moved.lows) == (as_placed.edge, as_placed.low, as_placed.high, as_placed.top, as_placed.lows)
    assert np.allclose(as_moved.joint - as_placed.joint, [2.0, 0.0, -3.0], atol=1e-6)
    assert as_placed.top == max(elbows.cut_levels(bones["right humerus"], EDGE, 1.0))
    assert set(as_placed.lows) == {"ulna", "radius"} and as_placed.low == min(as_placed.lows.values()) - 8.0


def test_a_bones_section_at_a_height():
    v = tube((100.0, 0.0, 50.0), (100.0, 100.0, 50.0), 10.0)
    middle, half = elbows.section(v, 50.0)
    assert np.allclose(middle, [100.0, 50.0], atol=0.3) and np.allclose(half, [10.0, 10.0], atol=0.3)
    assert elbows.section(v, 500.0) is None


def photograph(bone=True):
    """One photograph through the made-up arm: (cover, tissue, inside) over z, x."""
    cover, tissue, _, _, _ = arm(bone=bone)
    return cover[:, 40, :], tissue[:, 40, :], tissue[:, 40, :]


def test_the_bone_is_found_in_a_photograph_where_bonehub_has_its_section_beside_it():
    cover, tissue, inside = photograph()
    spacing, origin = (SPACING[0], SPACING[2]), (0.0, 0.0)
    got = elbows.bone_at(cover, tissue, inside, spacing, origin, (MIDDLE + 3.0, MIDDLE - 4.0), (9.0, 9.0))     # the section 5 mm beside
    middle, extent = got
    assert np.allclose(middle, [MIDDLE, MIDDLE], atol=0.7)              # the bone, with its red marrow: not the fat, not the film
    assert np.allclose(extent, [BONE, BONE], atol=0.9)
    assert elbows.bone_at(*photograph(bone=False), spacing, origin, (MIDDLE, MIDDLE), (9.0, 9.0)) is None      # nothing pale there
    assert elbows.bone_at(cover, tissue, inside, spacing, origin, (MIDDLE + 30.0, MIDDLE), (9.0, 9.0)) is None  # the section in the muscle
    # What lies on the section, but is not the bone alone, is not gone by: much wider than the section; too far from it.
    assert elbows.bone_at(cover, tissue, inside, spacing, origin, (MIDDLE, MIDDLE), (4.0, 4.0)) is None
    assert elbows.bone_at(cover, tissue, inside, spacing, origin, (MIDDLE + 15.0, MIDDLE), (9.0, 9.0)) is None


def test_a_bone_is_moved_wholly_at_its_cut_end_and_not_at_its_far_end():
    v = tube((100.0, 0.0, 50.0), (100.0, 200.0, 50.0), 10.0).astype(np.float32)
    got = elbows.turned(v, (3.0, -4.0), hold=50.0, far=200.0)           # (as a humerus: cut below, the shoulder above)
    assert got.dtype == v.dtype and np.array_equal(got[:, 1], v[:, 1])
    moved = got.astype(np.float64) - v
    assert np.allclose(moved[v[:, 1] <= 50.0], [3.0, 0.0, -4.0], atol=1e-4)
    assert np.allclose(moved[v[:, 1] > 198.6], 0.0, atol=0.05)
    half = np.abs(v[:, 1] - 125.0) < 1.0
    assert np.allclose(moved[half], [1.5, 0.0, -2.0], atol=0.05)
    other = elbows.turned(v, (3.0, -4.0), hold=150.0, far=0.0)          # (as a forearm bone: cut above, the wrist below)
    moved = other.astype(np.float64) - v
    assert np.allclose(moved[v[:, 1] >= 150.0], [3.0, 0.0, -4.0], atol=1e-4) and np.allclose(moved[v[:, 1] < 0.1], 0.0, atol=0.01)


def test_an_arms_bones_are_moved_onto_the_photographs_bone_next_to_their_cuts(monkeypatch):
    cover, tissue, _, _, _ = arm(film=False, length=140)
    fine = SimpleNamespace(spacing=SPACING, origin_mm=(0.0, 0.0, 0.0), cover=np.zeros(cover.shape, np.uint8))
    skin = SimpleNamespace(cover=(tissue * 255).astype(np.uint8))
    monkeypatch.setattr(elbows.fine_muscle, "_slab", lambda fine, a, b, with_tissue=False: (cover[:, a:b, :], tissue[:, a:b, :]))
    apart = np.array([3.0, 0.0, -4.0])                                  # BoneHub's bones: 5 mm beside the photographs'
    bones = {f"right {k}": tube((MIDDLE, 0.0, MIDDLE), (MIDDLE, 140.0, MIDDLE), 9.0) + apart for k in elbows.ARM}
    cut = SimpleNamespace(top=20.0, lows={"ulna": 120.0, "radius": 120.0})
    said = []
    got = elbows.onto_photographs(fine, skin, bones, "right", cut, log=said.append)
    assert set(got) == set(bones) and len(said) == 3
    was, now = bones["right humerus"], got["right humerus"]             # cut below 20 mm: found from 30 mm up, held to 40
    assert np.allclose((now - was)[was[:, 1] < 40.0], -apart, atol=0.8)
    assert np.allclose((now - was)[was[:, 1] > 138.0], 0.0, atol=0.1)   # the shoulder stays
    was, now = bones["right ulna"], got["right ulna"]                   # cut above 120 mm: found from 110 mm down
    assert np.allclose((now - was)[was[:, 1] > 100.0], -apart, atol=0.8)
    assert np.allclose((now - was)[was[:, 1] < 1.0], 0.0, atol=0.1)     # the wrist stays
    # No bone in the photographs there: BoneHub's are left where they are, and it is said.
    cover, tissue, _, _, _ = arm(film=False, bone=False, length=140)
    said = []
    assert elbows.onto_photographs(fine, skin, bones, "right", cut, log=said.append) == {}
    assert len(said) == 3 and all("left where BoneHub has it" in line for line in said)
