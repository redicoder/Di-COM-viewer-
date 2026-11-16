"""The drawn vessels and nerves on a made-up head (a ball of skin, 100 mm, round a ball of bone, 90 mm): a tube is a
closed, outward-wound mesh of the radius asked for; a course keeps under the skin and out of the bone.
Needs scipy (backend/.venv-seg); skipped without scikit-image, which the package imports."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import face_muscles, face_vessels  # noqa: E402

SKIN, BONE = 100.0, 90.0


def ball_maps() -> face_muscles.Maps:
    shape = (int(160.0 / face_muscles.STEP_DEGREES), int(250.0 / face_muscles.STEP_DEGREES))
    skin = np.full(shape, SKIN, np.float32)
    return face_muscles.Maps(np.array([0.0, 1.0, 0.0]), np.eye(3), skin, np.full(shape, BONE, np.float32), face=skin.copy())


def point(maps, lon_deg: float, lat_deg: float, radius_mm: float) -> np.ndarray:
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    return maps.centre + np.array([np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)]) * radius_mm * 0.001


def test_a_tube_is_closed_wound_outward_and_as_thick_as_asked():
    points = np.stack([np.linspace(0.0, 0.05, 40), 0.004 * np.sin(np.linspace(0, 6, 40)), np.zeros(40)], axis=1)
    v, f = face_vessels.tube(points, np.linspace(1.5, 0.75, 40))
    edges = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    assert (counts == 2).all()
    a, b, c = (v[f[:, k]].astype(np.float64) for k in range(3))
    assert np.einsum("ij,ij->i", a, np.cross(b, c)).sum() > 0               # a positive volume: wound outward
    ring = v[:8].astype(np.float64)
    assert np.allclose(np.linalg.norm(ring - points[0], axis=1), 0.0015, atol=2e-5)
    last = v[39 * 8:40 * 8].astype(np.float64)
    assert np.allclose(np.linalg.norm(last - points[-1], axis=1), 0.00075, atol=2e-5)


def test_a_course_keeps_under_the_skin_and_out_of_the_bone():
    maps = ball_maps()
    stops = [(point(maps, -20, 0, 93.0), None, False), (point(maps, 0, 10, SKIN), 4.0, False), (point(maps, 25, 5, SKIN), 12.0, False)]
    line = face_vessels.course(maps, maps.bone, stops, 3.0)
    r = np.linalg.norm(line - maps.centre, axis=1) * 1000.0
    assert r.max() <= SKIN - (1.5 + face_vessels.COVER_MM) + 0.05           # its upper side stays under the skin's cover
    assert r.min() >= BONE + 1.5 + 0.3                                      # the last stop asks for 12 mm down: the bone holds it up
    assert abs(r[0] - 93.0) < 0.6                                           # it begins where the first stop's point is
    steps = np.linalg.norm(np.diff(line, axis=0), axis=1) * 1000.0
    assert steps.max() < 2.0                                                # sampled finely all along
    free = [(point(maps, -20, 0, 80.0), None, True), (point(maps, -10, 0, 80.0), None, True)]
    deep = np.linalg.norm(face_vessels.course(maps, maps.bone, free, 3.0) - maps.centre, axis=1) * 1000.0
    assert deep.max() < 82.0                                                # a stretch marked free may lie deeper than the bone's surface


def test_a_winding_course_sways_but_ends_where_it_should():
    maps = ball_maps()
    stops = [(point(maps, -20, 0, SKIN), 6.0, False), (point(maps, 20, 0, SKIN), 6.0, False)]
    plain = face_vessels.course(maps, maps.bone, stops, 2.0)
    winding = face_vessels.course(maps, maps.bone, stops, 2.0, wind_mm=2.0)
    assert np.linalg.norm(winding[0] - plain[0]) < 1e-4 and np.linalg.norm(winding[-1] - plain[-1]) < 1e-4
    sway = np.abs(winding[:, 1] - plain[:, 1]).max() * 1000.0
    assert 1.0 < sway < 2.6
