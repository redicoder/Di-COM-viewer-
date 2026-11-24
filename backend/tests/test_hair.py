"""No hair passes through him: a strand ends where it would run into him (a finger that lies on the belly) or into
the cloth, and the strands that stay are the very ones they were.
Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import fine_skin, hair  # noqa: E402


def straight(starts, step, rings=7):
    """Centre lines (k, rings, 3) running along x from each start, `step` metres a ring."""
    along = np.arange(rings)[None, :, None] * np.array([step, 0.0, 0.0])[None, None, :]
    return np.asarray(starts, np.float64)[:, None, :] + along


def test_a_strand_ends_where_it_would_enter_and_a_stump_is_not_grown():
    wall = 0.0105                                                       # a finger's side: everything beyond x = 10.5 mm is him

    def within(points):
        return points[:, 0] > wall

    pts = straight([[0.000, 0.0, 0.0],                                  # ends at 6 mm: never reaches the finger
                    [0.006, 0.0, 0.0],                                  # its sixth and seventh ring would lie in the finger
                    [0.0098, 0.0, 0.0]], 0.001)                         # its second ring already would
    out, keep, shortened = hair.trimmed(pts, within)
    assert keep.tolist() == [True, True, False] and shortened == 1
    assert np.array_equal(out[0], pts[0])
    assert np.allclose(out[1, 0], pts[1, 0]) and np.allclose(out[1, -1], pts[1, 4])     # from its root to its last ring outside,
    assert np.allclose(np.diff(out[1, :, 0]), 0.004 / 6)                                # in as many rings, laid closer
    assert not within(out[1]).any()


def test_the_strands_that_stay_are_the_very_ones_they_were():
    rng_roots = np.random.default_rng(3)
    k = 400
    roots = np.stack([rng_roots.uniform(-0.03, 0.03, k), np.zeros(k), rng_roots.uniform(-0.03, 0.03, k)], axis=1)
    normals = np.tile([0.0, 1.0, 0.0], (k, 1))
    flow = np.tile([1.0, 0.0, 0.0], (k, 1))
    kind = hair.KINDS["belly_line"]
    rings = kind.segments + 1
    free = hair.ribbons(roots, normals, flow, kind, np.random.default_rng(5))

    def within(points):                                                 # a finger lying across the hair's way
        return (points[:, 0] > 0.012) & (points[:, 0] < 0.026) & (points[:, 1] < 0.02)

    told = {}
    cut = hair.ribbons(roots, normals, flow, kind, np.random.default_rng(5), within=within, report=told)
    assert 0 < told["grown"] < k and told["shortened"] > 0
    assert len(cut[0]) == told["grown"] * rings * 2 and len(cut[2]) == told["grown"] * kind.segments * 2
    assert int(cut[2].max()) == len(cut[0]) - 1
    # No ring of a strand that is grown lies in the finger (the roots under it are the skin layer's to leave out).
    lines = cut[0].reshape(told["grown"], rings, 2, 3)[:, 1:, 0, :].reshape(-1, 3)
    assert not within(lines).any()
    # A strand rooted well away from the finger is found again exactly, with its width, seed and colour.
    far = np.flatnonzero(roots[:, 0] < -0.02)
    whole = free[0].reshape(k, rings * 2, 3)
    kept = cut[0].reshape(told["grown"], rings * 2, 3)
    first = {tuple(np.round(s[0], 7)): i for i, s in enumerate(kept)}
    for i in far[:20]:
        j = first[tuple(np.round(whole[i, 0], 7))]
        assert np.array_equal(kept[j], whole[i])
        assert np.array_equal(cut[1]["TEXCOORD_1"].reshape(told["grown"], rings * 2, 2)[j], free[1]["TEXCOORD_1"].reshape(k, rings * 2, 2)[i])
        assert np.array_equal(cut[1]["COLOR_0"].reshape(told["grown"], rings * 2, 4)[j], free[1]["COLOR_0"].reshape(k, rings * 2, 4)[i])


def test_how_much_of_each_of_the_exports_voxels_is_him():
    cover = np.zeros((40, 20, 40), np.uint8)
    cover[10:31, 4:16, 10:30] = 255                                     # him; his edge at z = 31 runs through the export's voxels there
    fine = fine_skin.FineOutline(cover, (0.66, 1.0, 0.66), (0.0, 0.0, 0.0), np.zeros(20, bool))
    body = SimpleNamespace(dims=(20, 10, 20), spacing=(1.32, 2.0, 1.32))
    full = fine_skin.occupancy(body, fine)
    assert full.shape == (20, 10, 20) and full.dtype == np.uint8
    assert full[10, 5, 10] == 255 and full[2, 5, 10] == 0 and full[10, 0, 10] == 0
    assert 120 <= full[15, 5, 10] <= 135                                # half of that voxel is him


def test_a_hands_own_skin_looks_away_from_its_bones_and_the_belly_under_a_finger_does_not():
    from anatomy_model import hands
    # A finger lying on the belly: its bone a line along y, 7 mm over the belly's skin (z runs back: the belly's
    # skin at z = 20, the bone at z = 13, the finger's top at z = 6).
    bone = np.stack([np.full(40, 13.0), np.linspace(0.0, 39.0, 40), np.full(40, 50.0)], axis=1)
    skin = np.array([[6.0, 20.0, 50.0],                                 # the finger's top
                     [13.0, 20.0, 57.0],                                # its side
                     [20.0, 20.0, 50.0],                                # the belly, right under it
                     [20.0, 20.0, 60.0],                                # the belly beside it
                     [20.0, 20.0, 90.0]])                               # the belly, far from it
    normals = np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
    own = hands.own_skin(bone, skin, normals)
    assert own[0] == 1.0 and own[1] == 1.0
    assert own[2] == 0.0 and own[3] == 0.0 and own[4] == 0.0
    assert hands.own_skin(np.zeros((0, 3)), skin, normals).sum() == 0


def test_the_trunks_hair_ends_where_it_meets_a_hand_and_the_arms_hair_does_not():
    # A flat patch of skin, 60 x 60 mm; a strip of it (x from 10 to 20 mm) is a hand's own skin.
    xs, zs = np.meshgrid(np.arange(-0.03, 0.0301, 0.002), np.arange(-0.03, 0.0301, 0.002), indexing="ij")
    v = np.stack([xs.ravel(), np.zeros(xs.size), zs.ravel()], axis=1)
    cols = xs.shape[1]
    f = []
    for i in range(xs.shape[0] - 1):
        for j in range(cols - 1):
            a = i * cols + j
            f += [(a, a + cols, a + 1), (a + 1, a + cols, a + cols + 1)]
    f = np.array(f, np.int64)
    n = np.tile([0.0, 1.0, 0.0], (len(v), 1))
    hand = ((v[:, 0] > 0.010) & (v[:, 0] < 0.020)).astype(float)
    weight = (v[:, 0] < 0.008).astype(float)                            # the hair's roots: beside the hand, not on it
    info = {"sternum": (10.0, 0.0, 1.0), "arm_left": (np.array([-1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])), "arm_right": (np.array([-1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])),
            "hand_skin": hand}
    reg = {"belly_line": weight * 6.0, "forearm": weight * 6.0}         # (the belly line's flow runs towards x = 1, over the hand; the arm's too)
    grown = {s.info["hair"]: s for s in hair.build(v, f, n, reg, info, log=lambda *_: None)}
    free = {s.info["hair"]: s for s in hair.build(v, f, n, reg, dict(info, hand_skin=None), log=lambda *_: None)}

    def over_the_hand(s):
        p = np.asarray(s.v)
        # (within HAND_MM of one of the hand's vertices, which lie 2 mm apart and end with the patch)
        return int(((p[:, 0] > 0.012) & (p[:, 0] < 0.018) & (p[:, 1] < 0.0015) & (np.abs(p[:, 2]) < 0.029)).sum())

    assert over_the_hand(free["belly_line"]) > 0                        # without the rule the belly's hair lies over the hand,
    assert over_the_hand(grown["belly_line"]) == 0                      # with it none does,
    assert grown["belly_line"].info["strands"] < free["belly_line"].info["strands"]
    assert over_the_hand(grown["forearm"]) > 0                          # and the arm's own hair, which grows on a hand's back, is left alone
