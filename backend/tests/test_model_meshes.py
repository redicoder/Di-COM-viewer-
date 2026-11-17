"""The anatomy model builder on a small made-up body: meshes face outward, land where the voxels are, survive the
GLB round trip, and the preview draws them. Needs scikit-image (backend/.venv-seg); skipped without it."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import layers, skin  # noqa: E402
from anatomy_model.common import Body, Structure, load_structures, normals_of, save_structures  # noqa: E402
from anatomy_model.glb import read_glb, write_glb  # noqa: E402

DIMS = (44, 60, 36)                 # x, y, z voxels
SPACING = (1.32, 2.0, 1.32)         # mm


def make_export(folder: Path) -> Path:
    """An ellipsoid of skin over fat over muscle, a bone through it and one organ off centre."""
    dx, dy, dz = DIMS
    z, y, x = np.mgrid[0:dz, 0:dy, 0:dx].astype(np.float32)
    r = np.sqrt(((x - dx / 2) / (dx * 0.42)) ** 2 + ((y - dy / 2) / (dy * 0.45)) ** 2 + ((z - dz / 2) / (dz * 0.42)) ** 2)
    lab = np.zeros((dz, dy, dx), np.uint8)
    lab[r < 1.0] = 1                                                    # skin
    lab[r < 0.9] = 2                                                    # fat
    lab[r < 0.75] = 3                                                   # muscle
    lab[(np.abs(x - dx / 2) < 3) & (np.abs(z - dz / 2) < 3) & (r < 0.7)] = 4      # bone
    organ = np.sqrt((x - dx * 0.65) ** 2 + ((y - dy * 0.55) * 1.5) ** 2 + (z - dz / 2) ** 2) < 5
    lab[organ & (r < 0.7)] = 5
    lab.tofile(folder / "labels.raw")
    names = [("skin (by colour)", "skin"), ("fat (by colour)", "fat"), ("muscle (by colour)", "muscle"), ("femur", "bone"), ("liver", "organ")]
    objects = [{"index": k + 1, "name": n, "layer": c, "voxels": int((lab == k + 1).sum())} for k, (n, c) in enumerate(names)]
    (folder / "labels.json").write_text(json.dumps({"objects": objects}))
    (folder / "body.json").write_text(json.dumps({"dims": list(DIMS), "spacing_mm": list(SPACING), "labels": "labels.raw", "label_table": "labels.json"}))
    return folder


def signed_volume_mm3(s: Structure) -> float:
    a, b, c = (s.v[s.f[:, k]].astype(np.float64) * 1000.0 for k in range(3))
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def test_layers_are_outward_meshes_where_the_voxels_are(tmp_path):
    body = Body(make_export(tmp_path))
    organs = layers.build(body, "organs", 4000, log=lambda *_: None)
    assert [s.name for s in organs] == ["liver"]
    liver = organs[0]
    voxel_mm3 = float(np.prod(SPACING))
    volume = signed_volume_mm3(liver)
    assert volume > 0, "the mesh is inside out"
    assert abs(volume - body.object_named("liver")["voxels"] * voxel_mm3) < 0.25 * volume
    # The mesh sits on the organ's voxels: its centroid is the voxels' centroid (voxel centres at index + 0.5).
    zyx = np.argwhere(body.labels == body.object_named("liver")["index"]).mean(axis=0) + 0.5
    want = np.array([zyx[2] * SPACING[0] - body.size_mm[0] / 2, zyx[1] * SPACING[1] - body.size_mm[1] / 2,
                     -(zyx[0] * SPACING[2] - body.size_mm[2] / 2)]) / 1000.0
    assert np.abs(liver.v.mean(axis=0) - want).max() < 0.0012
    # The normals point away from the centroid, and the bake is there.
    n = normals_of(liver.v, liver.f)
    assert (np.einsum("ij,ij->i", n, liver.v - liver.v.mean(axis=0)) > 0).mean() > 0.95
    assert liver.bake.shape == (len(liver.v), 4) and liver.bake.dtype == np.uint8
    for layer, count in (("fat", 1), ("muscles", 1), ("skeleton", 1)):
        assert len(layers.build(body, layer, 4000, log=lambda *_: None)) == count


def test_skin_without_fine_outline_and_the_glb_round_trip(tmp_path):
    body = Body(make_export(tmp_path))
    built = skin.build(body, 6000, log=lambda *_: None)
    assert built[0].name == "skin" and signed_volume_mm3(built[0]) > 0
    built[0].albedo = np.tile(np.array([200, 150, 120], np.uint8), (len(built[0].v), 1))
    built[0].extra = np.full(len(built[0].v), 64, np.uint8)
    everything = built + layers.build(body, "organs", 4000, log=lambda *_: None)
    path = tmp_path / "model.glb"
    write_glb(path, everything)
    back = read_glb(path)
    assert [(s.name, s.layer) for s in back] == [(s.name, s.layer) for s in everything]
    assert np.allclose(back[0].v, built[0].v) and np.array_equal(back[0].f, built[0].f)
    assert np.array_equal(back[0].bake, built[0].bake)
    assert np.array_equal(back[0].albedo, built[0].albedo) and np.array_equal(back[0].extra, built[0].extra)
    # A structure without per-vertex albedo carries its own colour in every vertex.
    liver = back[-1]
    assert np.abs(liver.albedo.astype(int) - np.round(np.array(everything[-1].colour) * 255)).max() <= 1
    cache = tmp_path / "cache.npz"
    save_structures(cache, everything)
    again = load_structures(cache)
    assert np.array_equal(again[0].albedo, built[0].albedo) and again[-1].albedo is None


def test_magnify_and_shrink_are_inverse_and_continuous():
    rng = np.random.default_rng(3)
    v = rng.uniform(-0.5, 0.5, (2000, 3))
    bubbles = [(np.array([0.0, 0.3, 0.05]), 0.1, 1.8), (np.array([0.1, -0.2, 0.0]), 0.12, 2.0), (np.array([0.02, 0.28, 0.04]), 0.06, 1.5)]
    assert np.abs(skin.shrink(skin.magnify(v, bubbles), bubbles) - v).max() < 1e-9
    # Neighbouring points stay neighbours (no tear at a bubble's edge).
    a = np.array([[0.0, 0.3 + 0.0999, 0.05], [0.0, 0.3 + 0.1001, 0.05]])
    assert np.linalg.norm(np.diff(skin.magnify(a, bubbles[:1]), axis=0)) < 0.001


def test_weld_joins_the_slabs_shared_vertices():
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0.0000001], [0, 1, 0], [1, 1, 0]], np.float64)
    f = np.array([[0, 1, 2], [3, 5, 4]])
    v2, f2 = skin.weld(v, f, 1e-3)
    assert len(v2) == 4 and len(f2) == 2 and len(np.unique(f2)) == 4


def test_preview_draws_the_structures(tmp_path):
    pytest.importorskip("PIL")
    from anatomy_model.preview import render
    body = Body(make_export(tmp_path))
    organs = layers.build(body, "organs", 4000, log=lambda *_: None)
    image = render(organs, (20, 10, 0.07, tuple(organs[0].v.mean(axis=0))), size=(320, 240), out=tmp_path / "liver.png")
    drawn = (image != np.array([38, 40, 44], np.uint8)).any(axis=2)
    assert 0.02 < drawn.mean() < 0.9 and (tmp_path / "liver.png").exists()


def test_every_layer_has_its_triangles():
    """(The skin has its own number and no share in the others' budget: asked for its share, the build of a whole
    model stopped at its first layer.)"""
    import build_model_meshes as build
    assert build.triangles_for("skin", 1_400_000, 900_000, True) == 900_000
    for layer in build.LAYERS:
        assert build.triangles_for(layer, 1_400_000, 900_000, False) > 0
    plain, fine = build.triangles_for("muscles", 1_000_000, 0, False), build.triangles_for("muscles", 1_000_000, 0, True)
    assert fine == pytest.approx(plain * build.FINE_MUSCLES) and build.triangles_for("fat", 1_000_000, 0, True) == build.triangles_for("fat", 1_000_000, 0, False)


def test_the_space_cleared_round_the_eyes_is_not_a_hole_in_him():
    """(The skin's fine outline is guided by where he is: the labels, with the eyes' cleared space put back.)"""
    from anatomy_model import fine_skin

    class Him:
        labels = np.ones((12, 10, 14), np.uint8)
        eye_pits = []

    pit = np.zeros((4, 3, 5), bool)
    pit[:2, 1, 1:4] = True                                              # cleared from the front (z runs back) inwards
    Him.labels[0:4, 5:8, 2:7][pit] = 0
    Him.eye_pits = [((0, 5, 2), pit)]
    assert not (Him.labels > 0).all()
    assert fine_skin.whole_body(Him).all()
    Him.eye_pits = []
    assert not fine_skin.whole_body(Him).all()                          # without the record of it, a hole stays a hole


def test_the_closed_lids_line_is_the_deep_furrow_not_the_nearest_crease():
    from anatomy_model import zones
    assert zones.deepest_furrow([(-6.5, -0.53), (-4.0, -0.21)]) == 0     # (the right eye, as measured: the crease over the line is a fifth as deep)
    assert zones.deepest_furrow([(-6.5, -0.59)]) == 0
    assert zones.deepest_furrow([(-8.5, -0.50), (-5.5, -0.47)]) == 1     # two about as deep: the one where lids meet on a globe
    assert zones.deepest_furrow([]) is None


def test_a_bone_laid_aside_is_moved_onto_the_bodys_own_bone():
    """(BoneHub's skull against his own: the move that puts most of its surface on the bone of the labels.)"""
    from scipy import ndimage
    from anatomy_model import bonehub
    spacing = np.array((1.32, 2.0, 1.32))
    own = np.zeros((60, 40, 60), bool)
    z, y, x = np.mgrid[0:60, 0:40, 0:60]
    centre = np.array([30.0, 20.0, 30.0])
    r = np.sqrt((((z - centre[0]) * spacing[0]) / 22.0) ** 2 + (((y - centre[1]) * spacing[1]) / 26.0) ** 2 + (((x - centre[2]) * spacing[2]) / 18.0) ** 2)
    own[(r < 1.0) & (r > 0.9)] = True                                   # a hollow shell 2 mm thick: a skull of sorts
    away = ndimage.distance_transform_edt(~own, sampling=spacing).astype(np.float32)
    shell = (np.argwhere((r < 0.97) & (r > 0.93)) + 0.5) * spacing      # points in the shell's middle, in millimetres
    laid = shell - np.array([3.0, 4.0, -5.0])                           # the same bone, laid 3 mm before, 4 mm under and 5 mm beside it
    move, before, after = bonehub.best_move(away, spacing, np.zeros(3, int), laid)
    assert move == pytest.approx((3.0, 4.0, -5.0), abs=0.5)
    assert after > 0.95 and before < 0.6
    move, before, after = bonehub.best_move(away, spacing, np.zeros(3, int), shell)
    assert move == (0.0, 0.0, 0.0) and before == after                  # one that lies right stays


def test_the_heads_bones_are_drawn_out_in_the_plane_and_not_along_the_body():
    from anatomy_model import bonehub
    v = np.array([[100.0, 1700.0, 300.0], [190.0, 1750.0, 300.0], [100.0, 1700.0, 225.0]])
    out = bonehub.widened(v, (100.0, 300.0), 0.968)
    assert np.allclose(out[0], v[0])                                    # the middle stays
    assert out[1, 0] == pytest.approx(100.0 + 90.0 / 0.968) and out[1, 1] == 1750.0       # 90 mm before the middle: 3 mm further
    assert out[2, 2] == pytest.approx(300.0 - 75.0 / 0.968) and out[2, 0] == 100.0
