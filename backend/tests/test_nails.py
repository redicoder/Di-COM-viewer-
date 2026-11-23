"""The nails, on a made-up digit: a round-ended stick of skin with a bone in it, and its neighbour beside it.
Needs scipy and scikit-image (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import nails  # noqa: E402

RADIUS, LENGTH = 8.0, 60.0                               # a digit 16 mm thick; millimetres, the body's axes (z, y, x)
POINTS = np.array([0.0, -1.0, 0.0])                      # it points down the body


def capsule(centre_x: float, rings: int = 60, around: int = 48):
    """A digit's skin: vertices and faces. Its end is at y = 0, its root at y = LENGTH (open)."""
    v, f = [], []
    for j in range(rings):
        t = j / (rings - 1)
        if t < 0.25:                                     # the rounded end
            angle = (t / 0.25) * np.pi / 2
            y, r = RADIUS * (1 - np.cos(angle)), RADIUS * np.sin(angle)
        else:
            y, r = RADIUS + (t - 0.25) / 0.75 * (LENGTH - RADIUS), RADIUS
        r = max(r, 0.05)
        for i in range(around):
            a = 2 * np.pi * i / around
            v.append((r * np.cos(a), y, centre_x + r * np.sin(a)))
    for j in range(rings - 1):
        for i in range(around):
            p, q = j * around + i, j * around + (i + 1) % around
            f += [(p, q, p + around), (q, q + around, p + around)]
    return np.array(v), np.array(f, np.int64)


def bone(centre_x: float, off: float = 0.0):
    """The digit's bones: a thin stick along its middle, from 5 mm short of its end to its root."""
    rng = np.random.default_rng(2)
    n = 900
    y = rng.uniform(5.0, LENGTH - 2.0, n)
    a = rng.uniform(0, 2 * np.pi, n)
    return np.stack([off + 2.5 * np.cos(a), y, centre_x + 2.5 * np.sin(a)], axis=1)


def test_a_ray_meets_the_first_triangle_in_its_way():
    square = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[1, 0, 0], [1, 1, 0], [0, 1, 0]],
                       [[0, 0, 3], [1, 0, 3], [0, 1, 3]]], np.float64)
    far = nails.first_hits(np.array([[0.2, 0.2, -2.0], [0.2, 0.2, 1.0], [5.0, 5.0, -2.0]]), np.array([[0, 0, 1.0]] * 3), square)
    assert np.allclose(far[:2], [2.0, 2.0]) and np.isinf(far[2])


def test_the_outline_is_widest_in_the_middle_and_rounded_at_both_ends():
    g = nails.half_width(np.array([0.0, 0.1, 0.4, 0.6, 0.9, 1.0]))
    assert g[2] == g[3] == 1.0 and g[0] < g[1] < 1.0 and g[5] < g[4] < 1.0 and g.min() > 0.6


def test_a_nail_lies_on_the_back_of_the_digits_end():
    v, f = capsule(0.0)
    back = np.array([-1.0, 0.0, 0.0])                    # the limb's back looks to the front
    nail = nails.frame("left third toe", bone(0.0), back, [bone(20.0), bone(-20.0)], v, f)
    assert nail is not None
    assert np.linalg.norm(nail.tip - [0.0, 0.0, 0.0]) < 0.6 and nail.along @ POINTS > 0.99      # its end, and the way it points
    assert nail.out @ back > 0.99 and abs(nail.out @ nail.along) < 1e-6
    assert abs(nail.digit[0] - 2 * RADIUS) < 0.6 and abs(nail.digit[1] - 2 * RADIUS) < 0.6
    width, length = nails.SIZES["third toe"]
    assert nail.width == pytest.approx(min(width, nails.WIDTH_SHARE * nail.digit[0])) and nail.length == pytest.approx(length * nail.width / width)
    assert nail.inset == pytest.approx(nails.INSET * nail.digit[1])
    # The plate: over the skin, on its back, within the nail's size.
    got = nails.plate(nail, v[f])
    assert got is not None
    pv, pf, colour = got
    top = pv[:nails.ROWS * nails.COLUMNS]
    far = np.hypot(top[:, 0], top[:, 2])
    on_the_digit = top[:, 1] > RADIUS + 0.5              # (short of that the digit's end turns down, and the plate goes straight on)
    assert np.abs(far[on_the_digit] - RADIUS - nails.ABOVE_MM).max() < 0.25
    assert (top[:, 0] < 0).all()                         # on the back
    assert np.ptp(top[:, 2]) <= nail.width + 0.2 and np.ptp(top[:, 1]) <= nail.length + nails.FREE_MM + 0.3
    assert top[:, 1].min() >= nail.inset - nails.FREE_MM  # it does not reach past the digit's end
    assert len(colour) == len(pv) and pf.max() < len(pv)
    tri = pv[pf[:(nails.ROWS - 1) * (nails.COLUMNS - 1) * 2]]
    assert (np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]) @ nail.out > 0).all()        # looking out of the back
    # The skin under it takes the nail bed's colour; the pad's side does not, nor the skin beyond the nail.
    from anatomy_model import feet
    size = np.array([200.0, 200.0, 200.0])
    normal = v - np.stack([np.zeros(len(v)), np.maximum(v[:, 1], RADIUS), np.zeros(len(v))], axis=1)
    normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    under, fold, bed = nails.on_skin([nail], feet.to_gltf(size, v), np.stack([normal[:, 2], normal[:, 1], -normal[:, 0]], axis=1), size)
    q, s_, h = nail.local(v)
    middle = (h > 0) & (q > 0.25) & (q < 0.75) & (np.abs(s_) < nail.width * 0.3)
    assert middle.sum() > 5 and (under[middle] > 0.95).all() and (bed[middle] == nails.BED_TOE).all()
    assert under[h < -1.0].max() == 0 and under[q > 1.3].max() == 0 and under[np.abs(s_) > nail.width * 0.62].max() == 0
    assert fold.max() > 0.5 and (fold[under > 0.95] < 0.05).all()         # the fold lies round the nail, not under it


def test_a_bone_that_lies_beside_its_digit_still_finds_the_digits_end():
    v, f = capsule(0.0)
    nail = nails.frame("left third toe", bone(0.0, off=2.5), np.array([-1.0, 0.0, 0.0]), [bone(20.0)], v, f)
    assert nail is not None and nail.tip[1] < 1.5 and nail.along @ POINTS > 0.99


def test_the_thumbs_back_is_where_the_skin_lies_nearest_its_bone_and_not_towards_a_finger():
    v, f = capsule(0.0)
    stick = bone(0.0)
    stick[:, 2] += 4.0                                   # the bone lies towards the digit's one side: that is its back
    nail = nails.frame("left thumb", stick, None, [bone(-22.0)], v, f)
    assert nail is not None and nail.out @ np.array([0.0, 0.0, 1.0]) > 0.9
    # ... unless a finger lies that way: then not.
    nail = nails.frame("left thumb", stick, None, [bone(22.0)], v, f)
    assert nail is not None and nail.out @ np.array([0.0, 0.0, 1.0]) < np.cos(np.radians(55.0))


def test_a_limbs_back_is_the_side_where_the_skin_is_nearer_its_long_bones():
    # Five long bones side by side in a plane, 3 mm under one face of a slab of skin and 15 mm over the other.
    rng = np.random.default_rng(4)
    long = [np.stack([rng.normal(0, 1.0, 200), rng.uniform(0, 60, 200), x + rng.normal(0, 1.5, 200)], axis=1) for x in (-30, -15, 0, 15, 30)]
    def face(z):
        a, b, c, d = [z, -20, -60], [z, 80, -60], [z, 80, 60], [z, -20, 60]
        return [[a, b, c], [a, c, d]]
    slab = np.array(face(-3.0) + face(15.0), np.float64)
    back = nails.limb_back(long, slab)
    assert back @ np.array([-1.0, 0.0, 0.0]) > 0.98
