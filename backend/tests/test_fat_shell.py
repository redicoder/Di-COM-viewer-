"""The fat's outer surface is the skin's outline moved in: on a made-up head and a made-up limb; it keeps under the
skin's mesh; an opening's rim is drawn smooth; and it is open over the red of the lips, each vertex round them marked
with its lip.
Needs scipy, scikit-image and pyfqmr (backend/.venv-seg); skipped without them."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("skimage")
pytest.importorskip("pyfqmr")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import fat_shell, feet, fine_skin, mouth  # noqa: E402
from anatomy_model.common import FAT_LOWER_LIP, FAT_SURFACE, FAT_UPPER_LIP, Structure  # noqa: E402

SPACING = (0.66, 1.0, 0.66)


def test_the_heads_surface_lies_a_millimetre_and_a_half_under_its_outline(monkeypatch):
    monkeypatch.setattr(fat_shell, "HEAD_MM", 30.0)                     # the made-up head begins 30 mm up
    zz, yy, xx = np.mgrid[0:130, 0:100, 0:130]
    centre = np.array([43.0, 62.0, 43.0])
    far = np.sqrt(((zz + 0.5) * 0.66 - centre[0]) ** 2 + ((yy + 0.5) * 1.0 - centre[1]) ** 2 + ((xx + 0.5) * 0.66 - centre[2]) ** 2)
    neck = np.hypot((zz + 0.5) * 0.66 - centre[0], (xx + 0.5) * 0.66 - centre[2])
    cover = ((far < 34.0) | ((neck < 20.0) & (yy < 62))).astype(np.uint8) * 255      # a ball of 34 mm on a neck of 20
    fine = fine_skin.FineOutline(cover, SPACING, (0.0, 0.0, 0.0), np.zeros(100, bool))
    size = np.array([130 * 0.66, 100.0, 130 * 0.66])
    v, f = fat_shell.surface_of_head(fine, size)
    assert len(f) > 2000
    mm = feet.to_mm(size, v)
    radius = np.linalg.norm(mm - centre, axis=1)
    above = mm[:, 1] > 66.0                                             # the ball's upper half, away from the neck
    assert abs(np.median(radius[above]) - (34.0 - fat_shell.LEVEL_MM)) < 0.35
    assert radius[above].max() < 34.0 - 0.9 and radius[above].min() > 34.0 - 2.3
    assert 30.0 - fat_shell.LAP_MM - 0.5 < mm[:, 1].min() < 30.0 - fat_shell.LAP_MM + 1.5      # it reaches LAP_MM below the head's beginning, and no further,
    round_neck = np.hypot(mm[:, 0] - centre[0], mm[:, 2] - centre[2])
    lowest, higher = mm[:, 1] < 23.5, (mm[:, 1] > 26.0) & (mm[:, 1] < 27.5)
    assert np.median(round_neck[lowest]) < np.median(round_neck[higher]) - 0.25     # sinking there: under the body's surface, which ends just above
    assert abs(np.median(round_neck[higher]) - (20.0 - fat_shell.LEVEL_MM - 0.4)) < 0.5
    edge = np.linalg.norm(v[f[:, 0]] - v[f[:, 1]], axis=1) * 1000.0
    assert 0.8 < np.median(edge) < 2.2                                  # in triangles of about EDGE_HEAD_MM


def test_the_bodys_surface_follows_the_outline_as_the_exports_grid_has_it(monkeypatch):
    monkeypatch.setattr(fat_shell, "HEAD_MM", 150.0)
    monkeypatch.setattr(fat_shell, "SLAB", 30)                          # three slabs: their shared slices are welded
    nz, ny, nx = 90, 90, 90
    zz, yy, xx = np.mgrid[0:nz, 0:ny, 0:nx]
    far = np.hypot((zz + 0.5) * 1.32 - 59.4, (xx + 0.5) * 1.32 - 59.4)
    occupancy = ((far < 40.0) & (yy >= 3)).astype(np.uint8) * 255       # a limb of 40 mm, standing on the third slice
    body = SimpleNamespace(spacing=(1.32, 2.0, 1.32))
    size = np.array([nz * 1.32, ny * 2.0, nx * 1.32])
    v, f = fat_shell.surface_of_body(body, None, size, occupancy=occupancy)
    assert len(f) > 500
    mm = feet.to_mm(size, v)
    side = (mm[:, 1] > 20.0) & (mm[:, 1] < 140.0)
    radius = np.hypot(mm[side, 0] - 59.4, mm[side, 2] - 59.4)
    assert abs(np.median(radius) - (40.0 - fat_shell.BODY_LEVEL_MM)) < 0.6
    assert radius.max() < 40.0 - 0.8
    assert mm[:, 1].max() < 152.5                                       # it ends just above the head's beginning
    assert not fat_shell.rim_of(f, len(v))[side].any()                  # no seam where one slab's slices end and the next's begin


def test_the_surface_keeps_under_the_skins_mesh():
    xs, zs = np.meshgrid(np.arange(-0.02, 0.0201, 0.002), np.arange(-0.02, 0.0201, 0.002), indexing="ij")
    skin = np.stack([xs.ravel(), np.zeros(xs.size), zs.ravel()], axis=1)       # the skin: flat, looking up
    normals = np.tile([0.0, 1.0, 0.0], (len(skin), 1))
    v = np.array([[0.0, -0.0030, 0.0],                                  # 3 mm under it: deep enough
                  [0.004, -0.0004, 0.003],                              # 0.4 mm under it
                  [0.008, 0.0010, -0.005],                              # a millimetre OUT of it
                  [0.0, -0.0300, 0.0]], np.float32)                     # far from it: not its business
    out = fat_shell.under_the_mesh(v, skin, normals)
    assert np.allclose(out[0], v[0]) and np.allclose(out[3], v[3])
    for k in (1, 2):
        assert abs(out[k, 1] + fat_shell.UNDER_MESH_MM / 1000.0) < 2e-5 and np.allclose(out[k, [0, 2]], v[k, [0, 2]])


def test_an_openings_rim_is_drawn_smooth_and_the_rest_stays():
    # A strip of triangles whose upper rim is a saw: its teeth 2 mm high, 2 mm apart.
    n = 40
    lower = np.stack([np.arange(n) * 0.002, np.zeros(n), np.zeros(n)], axis=1)
    upper = np.stack([np.arange(n) * 0.002, 0.010 + 0.002 * (np.arange(n) % 2), np.zeros(n)], axis=1)
    v = np.concatenate([lower, upper]).astype(np.float32)
    f = np.array([[k, k + 1, n + k] for k in range(n - 1)] + [[k + 1, n + k + 1, n + k] for k in range(n - 1)], np.int64)
    rim = fat_shell.rim_of(f, len(v))
    assert rim.all()                                                    # a strip is all rim
    which = np.zeros(len(v), bool)
    which[n:] = True                                                    # the opening's side only
    out = fat_shell.smooth_rims(v, f, which)
    inner = slice(n + 8, 2 * n - 8)                                     # (its two ends stay where they are)
    assert np.ptp(out[inner, 1]) < 0.0002                               # the teeth are gone (they were 2 mm),
    assert abs(out[inner, 1].mean() - 0.011) < 0.0003                   # the rim lies along their middle,
    assert np.array_equal(out[:n], v[:n])                               # and the other rim is as it was


def test_what_lies_in_an_eyes_space_is_told():
    pit = np.zeros((6, 6, 6), bool)
    pit[2:4, 2:4, 2:4] = True
    body = SimpleNamespace(spacing=(1.32, 2.0, 1.32), eye_pits=[((10, 20, 30), pit)])
    size = np.array([100.0, 200.0, 100.0])
    inside = feet.to_gltf(size, np.array([[(12 + 0.5) * 1.32, (22 + 0.5) * 2.0, (32 + 0.5) * 1.32]]))
    beside = feet.to_gltf(size, np.array([[(14 + 0.5) * 1.32, (22 + 0.5) * 2.0, (32 + 0.5) * 1.32]]))       # a voxel beside it: within the margin
    far = feet.to_gltf(size, np.array([[(18 + 0.5) * 1.32, (22 + 0.5) * 2.0, (32 + 0.5) * 1.32]]))
    assert fat_shell.in_eye_pits(body, size, np.concatenate([inside, beside, far])).tolist() == [True, True, False]


def test_skin_that_looks_the_other_way_is_another_parts_and_is_not_measured_against():
    # The trunk's fat, looking up; 1 mm over it the skin of an arm that lies on the trunk, looking DOWN.
    xs, zs = np.meshgrid(np.arange(-0.01, 0.0101, 0.002), np.arange(-0.01, 0.0101, 0.002), indexing="ij")
    arm = np.stack([xs.ravel(), np.full(xs.size, 0.001), zs.ravel()], axis=1)
    arm_n = np.tile([0.0, -1.0, 0.0], (len(arm), 1))
    v = np.array([[0.0, 0.0, 0.0]], np.float32)
    own = np.array([[0.0, 1.0, 0.0]])
    assert np.allclose(fat_shell.under_the_mesh(v, arm, arm_n, own), v)            # left where it is,
    assert fat_shell.under_the_mesh(v, arm, arm_n)[0, 1] > 0.001                   # where, measured against it, it would be pushed through the arm
    # And no vertex is moved by more than most_mm.
    skin = np.stack([xs.ravel(), np.zeros(xs.size), zs.ravel()], axis=1)
    out = fat_shell.under_the_mesh(np.array([[0.0, 0.005, 0.0]], np.float32), skin, np.tile([0.0, 1.0, 0.0], (len(skin), 1)), most_mm=3.0)
    assert abs(out[0, 1] - 0.002) < 1e-5


def test_the_fat_is_open_over_the_red_of_the_lips_and_says_which_lip_each_vertex_is_of():
    class Flat:                                                         # a face whose own frame is the model's, in millimetres
        origin = np.zeros(3)
        ex, ey, ez = np.eye(3)

        def local(self, v):
            p = np.asarray(v, np.float64) * 1000.0
            return p[:, 0], p[:, 1], p[:, 2]

    m = mouth.Mouth.__new__(mouth.Mouth)
    m.face, m.lip_w = Flat(), lambda u: 0.3 + 0.0 * np.asarray(u, np.float64)
    xs, ys = np.arange(-40.0, 40.1, 1.0), np.arange(-15.0, 15.1, 1.0)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    v = (np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, 14.0)], axis=1) / 1000.0).astype(np.float32)     # 14 mm before the eyes: under the lips' skin
    n = len(ys)
    f = np.array([t for i in range(len(xs) - 1) for j in range(n - 1)
                  for t in ([i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1], [i * n + j, (i + 1) * n + j + 1, i * n + j + 1])], np.uint32)
    bake = np.stack([np.arange(len(v)) % 251] * 4, axis=1).astype(np.uint8)
    fat = Structure(fat_shell.FAT, "fat", v.copy(), f.copy(), (0.9, 0.8, 0.4), bake=bake.copy(), extra=np.full(len(v), FAT_SURFACE, np.uint8))
    said = []
    body = SimpleNamespace(mouth=m)
    cut = fat_shell.lips(body, [fat], log=said.append)
    assert cut > 500 and len(fat.f) == len(f) - cut and "opened over the red of the lips" in said[0]
    assert len(fat.extra) == len(fat.v) == len(fat.bake) and fat.f.max() < len(fat.v)
    u, g = fat.v[:, 0] * 1000.0, fat.v[:, 1] * 1000.0 - 0.3
    middle = np.abs(u) < 3.0
    assert g[middle & (g > 0)].min() > fat_shell.LIPS_UP_MM - 1.0       # in the middle it ends where the red does, above
    assert g[middle & (g < 0)].max() < -(fat_shell.LIPS_DOWN_MM - 1.0)  # and below;
    corner = (np.abs(u) > 21.0) & (np.abs(u) < 24.0)
    assert g[corner & (g > 0)].min() > fat_shell.LIPS_EDGE_MM[0] - 1.0 and g[corner & (g > 0)].min() < 4.5      # towards the corners the opening narrows,
    assert g[corner & (g < 0)].max() < -(fat_shell.LIPS_EDGE_MM[1] - 1.0)       # but keeps off the line, most below it (the lower lip's inner side),
    past = (np.abs(u) > 27.0) & (np.abs(u) < 28.5)
    assert np.abs(g[past]).min() > 1.0                                  # a little past the corners it is open still,
    assert (np.abs(u) > 32.0).sum() == (np.abs(v[:, 0] * 1000.0) > 32.0).sum()         # and beyond that nothing is taken
    assert ((fat.extra & FAT_SURFACE) > 0).all()                        # it is all the surface still;
    near = np.abs(u) < 28.0
    assert ((fat.extra[near & (g > 0)] & FAT_UPPER_LIP) > 0).all() and ((fat.extra[near & (g < 0)] & FAT_LOWER_LIP) > 0).all()
    assert (fat.extra[np.abs(u) > 30.0] == FAT_SURFACE).all()           # away from the mouth no lip is marked
    # Every vertex keeps its bake (those the opening's rim moved are found by it, not by their place).
    far = (np.abs(g) > 10.0) | (np.abs(u) > 33.0)
    first = {tuple(np.round(p * 1e6).astype(int)): k for k, p in enumerate(v)}
    assert all(fat.bake[k, 0] == first[tuple(np.round(fat.v[k] * 1e6).astype(int))] % 251 for k in np.flatnonzero(far)[::7])
    # The labels' coarse fat is cut as well, but its rim is not drawn smooth: its corners stay where they are
    # (drawn towards the middle of neighbours 20 mm away, one stood out of the skin under the nose).
    coarse_v = np.array([[-20.0, -10.0, 12.0], [0.0, -14.0, 12.0], [20.0, -10.0, 12.0],       # three corners under the lips,
                         [-10.0, 0.3, 12.0], [10.0, 0.3, 12.0],                                # two on the lip line,
                         [-10.0, -29.0, 12.0], [10.0, -29.0, 12.0]], np.float32) / 1000.0      # two further down
    coarse_f = np.array([[0, 1, 3], [1, 4, 3], [1, 2, 4], [0, 5, 1], [1, 6, 2]], np.uint32)

    def with_coarse(mark):
        return Structure(fat_shell.FAT, "fat", np.concatenate([v, coarse_v]), np.concatenate([f, coarse_f + len(v)]), (0.9, 0.8, 0.4),
                         extra=np.concatenate([np.full(len(v), FAT_SURFACE, np.uint8), np.full(len(coarse_v), mark, np.uint8)]))

    def strays(s):                                                      # how far its corners lie from where they were, mm
        mine = s.v[np.abs(s.v[:, 2] - 0.012) < 1e-6]
        return [float(np.linalg.norm(coarse_v - p, axis=1).min()) * 1000.0 for p in mine]

    labels = with_coarse(0)
    fat_shell.lips(body, [labels], log=said.append)
    assert len(strays(labels)) == 5 and max(strays(labels)) < 1e-3      # (the two on the line went, with their three triangles)
    surface = with_coarse(FAT_SURFACE)
    fat_shell.lips(body, [surface], log=said.append)
    assert max(strays(surface)) > 3.0                                   # (were they the surface's, the middle one would be drawn in by millimetres)
    # Without a mouth, or without the marks (no fine outline: the labels' fat as it was), nothing is done.
    plain = Structure(fat_shell.FAT, "fat", v, f, (0.9, 0.8, 0.4))
    assert fat_shell.lips(body, [plain], log=said.append) == 0 and fat_shell.lips(SimpleNamespace(), [fat], log=said.append) == 0
