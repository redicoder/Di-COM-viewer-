"""The drawn face muscles on a made-up head: a ball of skin (100 mm) round a ball of bone (90 mm). A band is a
closed, outward-wound slab that lies between the two, on the bone at its origin and under the skin at its end.
Needs scipy (backend/.venv-seg); skipped without scikit-image, which the package imports."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import face_muscles  # noqa: E402

SKIN, BONE = 100.0, 90.0


def ball_maps() -> face_muscles.Maps:
    shape = (int(160.0 / face_muscles.STEP_DEGREES), int(250.0 / face_muscles.STEP_DEGREES))
    skin = np.full(shape, SKIN, np.float32)
    return face_muscles.Maps(np.array([0.0, 1.0, 0.0]), np.eye(3), skin, np.full(shape, BONE, np.float32), face=skin.copy())


def point(maps, lon_deg: float, lat_deg: float, radius_mm: float) -> np.ndarray:
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    return maps.centre + np.array([np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)]) * radius_mm * 0.001


def edge_counts(f: np.ndarray) -> np.ndarray:
    edges = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return counts


def volume(v: np.ndarray, f: np.ndarray) -> float:
    a, b, c = (v[f[:, k]].astype(np.float64) for k in range(3))
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def test_a_band_runs_from_the_bone_to_under_the_skin_as_a_closed_slab():
    maps = ball_maps()
    v, f, along, across = face_muscles.band(maps, [point(maps, -10, -5, BONE), point(maps, 15, 10, SKIN)], (4.0, 6.0), 2.0, (None, 3.5), seated=0.3)
    assert (edge_counts(f) == 2).all()                                  # closed: every edge between two triangles
    assert volume(v - maps.centre, f) > 0                               # and wound outward
    r = np.linalg.norm(v.astype(np.float64) - maps.centre, axis=1) * 1000.0
    assert r.min() >= BONE + 0.15 and r.max() <= SKIN - 1.4             # in the soft tissue: not in the bone, not at the skin
    top = r[:len(r) // 2]
    start, end = top[along[:len(top)] < 0.1], top[along[:len(top)] > 0.9]
    assert start.max() < BONE + 3.0                                     # at its origin it lies on the bone
    assert abs(np.median(end) - (SKIN - 3.5)) < 0.3                     # at its end, 3.5 mm under the skin
    span = np.degrees(np.arccos(np.clip(maps.direction(point(maps, -10, -5, BONE)) @ maps.direction(point(maps, 15, 10, SKIN)), -1, 1)))
    assert 20 < span < 35 and len(np.unique(along)) >= int(np.radians(span) * 95 / face_muscles.GRID_MM)       # sampled every 1.4 mm or finer
    assert across.min() == -1.0 and across.max() == 1.0


def test_a_band_keeps_out_of_bone_that_rises_under_it():
    maps = ball_maps()
    maps.bone[:, :] = 97.0                                              # 3 mm of tissue only
    v, f, _, _ = face_muscles.band(maps, [point(maps, 0, 0, SKIN), point(maps, 20, 0, SKIN)], (5.0, 5.0), 2.5, (4.0, 4.0))
    r = np.linalg.norm(v.astype(np.float64) - maps.centre, axis=1) * 1000.0
    assert r.min() >= 97.0 + 0.15 and r.max() <= SKIN - 1.4
    assert (edge_counts(f) == 2).all()


def test_bone_far_under_the_skin_is_not_a_muscles_bed():
    maps = ball_maps()
    maps.bone[:, :] = 60.0                                              # an orbit, the nose's opening: 40 mm down
    v, _, along, _ = face_muscles.band(maps, [point(maps, 0, 0, SKIN), point(maps, 20, 0, SKIN)], (4.0, 4.0), 1.5, (None, 3.0))
    r = np.linalg.norm(v.astype(np.float64) - maps.centre, axis=1) * 1000.0
    assert r.min() > SKIN - 6.0                                         # it stays under the skin and does not dive for the bone


def test_a_muscle_keeps_nothing_under_skin_that_moves_with_a_lid():
    from anatomy_model.common import Structure
    # A strip of muscle 40 mm long under a strip of skin whose middle 10 mm moves with the lid.
    xs = np.linspace(0.0, 0.040, 41)
    v = np.array([[x, y, 0.0] for x in xs for y in (0.0, 0.004)], np.float32)
    f = np.array([[2 * k, 2 * k + 2, 2 * k + 1] for k in range(40)] + [[2 * k + 1, 2 * k + 2, 2 * k + 3] for k in range(40)], np.uint32)
    muscle = Structure("left orbicularis oculi", "muscles", v, f, (0.5, 0.2, 0.2))
    skin_v = np.array([[x, 0.002, 0.002] for x in xs], np.float64)
    moves = (xs > 0.0145) & (xs < 0.0255)
    out = face_muscles.without_moving_skin(muscle, skin_v, moves, log=lambda *_: None)
    kept = np.unique(np.asarray(out.f))
    assert 0 < len(out.f) < 80
    assert not ((v[kept, 0] > 0.0145) & (v[kept, 0] < 0.0255)).any()       # nothing of it under the moving skin
    assert (v[kept, 0] < 0.012).any() and (v[kept, 0] > 0.028).any()       # and it stays on either side
    # Skin that is far away says nothing about it.
    far = Structure("x orbicularis oculi", "muscles", v.copy(), f.copy(), (0.5, 0.2, 0.2))
    assert len(face_muscles.without_moving_skin(far, skin_v + np.array([0.0, 0.0, 0.05]), moves, log=lambda *_: None).f) == 80


def test_what_lies_in_skin_that_moves_with_a_lid_goes_with_it():
    from anatomy_model import lids
    # A sheet of skin, 40 x 20 mm, a millimetre between its vertices. Along x its lid weight rises from 0 to 0.5
    # (the skin under the brow, towards the lid) on the left eye; the fold stands out most half way.
    xs, ys = np.meshgrid(np.arange(0.0, 0.0401, 0.001), np.arange(0.0, 0.0201, 0.001), indexing="ij")
    skin_v = np.stack([xs.ravel(), ys.ravel(), np.full(xs.size, 0.010)], axis=1)
    weight = np.clip((xs.ravel() - 0.010) / 0.040, 0.0, None)
    fold = np.clip(1.0 - np.abs(xs.ravel() - 0.025) / 0.015, 0.0, 1.0)
    code = np.where(weight > 0, lids.SIDE_CODE["left"] + lids.FOLD_CODE * fold, 0.0)
    data2 = np.stack([weight, code], axis=1)
    under = np.array([[0.030, 0.010, 0.008],                            # a muscle's vertex 2 mm under the moving skin,
                      [0.030, 0.010, 0.0035],                           # one 6.5 mm under it,
                      [0.030, 0.010, -0.002],                           # one on the bone, 12 mm under it,
                      [0.004, 0.010, 0.008],                            # one under skin that does not move
                      [0.030, 0.010, 0.300]])                           # and one far away from all of it
    got = lids.carried(skin_v, data2, under)
    assert abs(got[0, 0] - 0.5) < 0.03                                  # the skin's own weight there,
    assert 0.0 < got[1, 0] < 0.45 * got[0, 0] + 0.2 and got[1, 0] < got[0, 0]      # less the deeper it lies,
    assert got[2, 0] == 0.0 and got[3, 0] == 0.0 and got[4, 0] == 0.0   # none on the bone, none under skin that stays
    assert 0.55 <= got[0, 1] <= 0.75                                    # the left eye's, with its share of the fold
    assert abs((got[0, 1] - 0.55) / lids.FOLD_CODE - fold[np.argmin(np.linalg.norm(skin_v - [0.030, 0.010, 0.010], axis=1))]) < 0.1
    assert (got[2:, 1] == 0.0).all()
    # Nothing that moves near: nothing to carry.
    assert lids.carried(skin_v, np.zeros_like(data2), under) is None
    assert lids.carried(skin_v, data2, under[4:]) is None


def test_a_set_of_vertices_is_closed_along_the_mesh():
    # A strip of 30 vertices in a row (each joined to the next): marked 5..9 and 12..20, a gap of two between.
    f = np.array([[k, k + 1, k + 1] for k in range(29)], np.int64)
    marked = np.zeros(30, bool)
    marked[5:10] = True
    marked[12:21] = True
    out = face_muscles.closed_on_mesh(marked, f)
    assert out[5:21].all()                                              # the gap of two between them is closed
    assert out[4] and not out[2] and not out[23]                        # grown by three rings and shrunk by two: one ring more at each end, no further
    assert face_muscles.closed_on_mesh(np.zeros(30, bool), f).sum() == 0
