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
