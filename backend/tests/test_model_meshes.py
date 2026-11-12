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
