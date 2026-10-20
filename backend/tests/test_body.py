"""Dissection body pipeline: stable label ids, names, tissue classes, grids, build_body end to end (no AI)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from make_test_series import build_phantom, write_series                     # noqa: E402
from app.body import body_mask                                                # noqa: E402
from app.label_table import BONE, FAT, LABELS, LAYERS, MUSCLE, SKIN, SOFT_TISSUE, labels_json, load_names  # noqa: E402
from app.segmentation import Grid, drop_fragments, sample                     # noqa: E402
from app.tissue import tissue_classes                                         # noqa: E402


# ----------------------------------------------------------------- label table

def test_label_ids_never_change():
    """Lessons and saved selections store ids: a recorded key must keep its id (new keys may be added)."""
    recorded = json.loads((ROOT / "tests" / "label_ids.json").read_text())
    current = {label.key: label.id for label in LABELS}
    changed = {k: (v, current.get(k)) for k, v in recorded.items() if current.get(k) != v}
    assert not changed, f"label ids changed or removed: {changed}"
    reused = set(current.values()) & {v for k, v in recorded.items() if k not in current}
    assert not reused


def test_label_ids_fit_uint8_and_are_unique():
    ids = [label.id for label in LABELS]
    assert len(ids) == len(set(ids))
    assert all(0 < i < 255 for i in ids)


def test_every_label_and_layer_has_three_names():
    names = load_names()
    for label in LABELS:
        n = names["labels"][label.key]
        assert all(n.get(lang, "").strip() for lang in ("la", "en", "it")), label.key
    for layer in LAYERS:
        assert all(names["layers"][layer.key].get(lang, "").strip() for lang in ("la", "en", "it")), layer.key


def test_labels_json_schema():
    j = labels_json({SKIN, 14})
    assert [layer["id"] for layer in j["layers"]] == ["skin", "fat", "muscle", "skeleton", "organs", "vessels",
                                                      "nervous"]
    assert [layer["order"] for layer in j["layers"]] == list(range(7))
    liver = next(lab for lab in j["labels"] if lab["key"] == "liver")
    assert liver["id"] == 14 and liver["layer"] == "organs" and liver["names"]["la"] == "Hepar"
    assert liver["name"] == "Liver"            # plain string for the current viewer
    assert {lab["id"] for lab in j["labels"]} == {SKIN, 14}


# ----------------------------------------------------------------- tissue classes

@pytest.fixture(scope="module")
def phantom():
    s = 1.5
    hu = build_phantom(128, 128, 96, s, s, s)        # body 40 HU, fat ring -90, lungs -800, spine 900
    return hu, s


def idx(mm_x, mm_y, mm_z, shape, s):
    nz, ny, nx = shape
    return (int(round(mm_z / s + nz / 2 - 0.5)), int(round(mm_y / s + ny / 2 - 0.5)),
            int(round(mm_x / s + nx / 2 - 0.5)))


def test_tissue_classes_on_phantom(phantom):
    hu, s = phantom
    body = body_mask(hu, -500)
    t = tissue_classes(hu, s, body)
    at = lambda x, y, z: t[idx(x, y, z, hu.shape, s)]
    assert at(0, 0, 0) == MUSCLE                      # body interior, 40 HU
    assert at(0, 25, 30) == MUSCLE
    assert at(80, 0, 20) == FAT                       # fat ring (outer 18 % of the ellipse), inside the skin
    assert at(0, 45, 0) == BONE                       # spine
    assert at(38, -5, 0) == 0                         # lung: gas stays empty
    assert at(0, 0, 0) != SKIN and t[0, 0, 0] == 0    # outside the body
    assert at(84.5, 0, 0) == SKIN                     # outer edge of the body (x radius 85 mm)
    assert at(78, 0, 0) != SKIN                       # 7 mm inside: below the 3 mm skin


def test_no_skin_on_cut_faces(phantom):
    """The phantom's body runs through the top and bottom of the volume: those faces are cuts, not skin."""
    hu, s = phantom
    t = tissue_classes(hu, s, body_mask(hu, -500))
    top, mid = t[-1], t[t.shape[0] // 2]
    assert (top == SKIN).sum() == (mid == SKIN).sum()       # only the side ring, as on any slice
    assert top[idx(40, 0, 0, hu.shape, s)[1:]] == MUSCLE         # inside of the top face: tissue, not skin


def test_labelled_voxels_keep_their_label(phantom):
    hu, s = phantom
    body = body_mask(hu, -500)
    labelled = np.zeros_like(body)
    labelled[40:50, 60:70, 60:70] = True
    t = tissue_classes(hu, s, body, labelled)
    assert not t[labelled].any()
    assert set(np.unique(t)) <= {0, SKIN, FAT, MUSCLE, BONE, SOFT_TISSUE}


# ----------------------------------------------------------------- grids

def test_grid_sampling_lines_up_in_mm():
    """A labelled 1 mm voxel lands on the 0.5 mm voxels that cover the same millimetres."""
    a = np.zeros((10, 10, 10), np.uint8)
    a[3, 4, 5] = 7                                       # covers z 3..4, y 4..5, x 5..6 mm
    g = Grid((0.0, 0.0, 0.0), 0.5, (20, 20, 20))
    b = sample(a, (0, 0, 0), (1.0, 1.0, 1.0), g, order=0)
    assert set(map(tuple, np.argwhere(b == 7))) == {(z, y, x) for z in (6, 7) for y in (8, 9) for x in (10, 11)}
    c = sample(a, (0, 0, 0), (1.0, 1.0, 1.0), Grid((2.0, 3.0, 4.0), 1.0, (3, 3, 3)), order=0)  # shifted crop
    assert c[1, 1, 1] == 7 and c.sum() == 7


def test_drop_fragments_keeps_real_pieces():
    a = np.zeros((40, 40, 40), np.uint8)
    a[2:12, 2:12, 2:12] = 5            # 1000 voxels: the structure
    a[30:32, 30:32, 30:32] = 5         # 8 voxels far away: stray
    a[2:12, 20:30, 2:12] = 6           # two real halves of another structure (e.g. a rib crossing the edge)
    a[20:30, 20:30, 2:12] = 6
    a[35, 35, 35] = 7                  # a structure that is only one voxel stays
    b, removed = drop_fragments(a)
    assert removed == 8 and not (b[30:32, 30:32, 30:32]).any()
    assert (b == 6).sum() == 2000 and (b == 7).sum() == 1 and (b == 5).sum() == 1000


def test_grid_covering():
    g = Grid.covering([0, 0, 0], [10.2, 20, 30], 2.0)
    assert g.shape == (6, 10, 15)
    assert np.allclose(np.asarray(g.corner_mm) + g.size_mm / 2, [5.1, 10, 15])     # centred on the box


# ----------------------------------------------------------------- build_body end to end

def test_build_body_end_to_end(tmp_path):
    import build_body

    src = tmp_path / "phantom_ct"
    write_series(build_phantom(), src, 1.5, 1.5, 2.0)          # 128 x 128 x 96 at 1.5 x 1.5 x 2 mm
    out_root = tmp_path / "out"
    folders = build_body.main([str(src), "--no-ai", "--licence", "synthetic test phantom", "--credit", "none",
                               "--out-root", str(out_root), "--roi", "20,20,20,150,150,150"])
    assert [f.name for f in folders] == ["whole_body", "roi"]
    assert (out_root / "latest.txt").read_text().split() == [str(f) for f in folders]

    wb = folders[0]
    meta = json.loads((wb / "volume.json").read_text())
    assert meta["spacing_mm"] == [2.0, 2.0, 2.0] and meta["is_hu"]
    n = meta["dim_x"] * meta["dim_y"] * meta["dim_z"]
    labels = np.fromfile(wb / "labels.raw", np.uint8)
    assert labels.size == n and (wb / "volume.raw").stat().st_size == 2 * n
    labels = labels.reshape(meta["dim_z"], meta["dim_y"], meta["dim_x"])        # (posterior, superior, left)

    lj = json.loads((wb / "labels.json").read_text(encoding="utf-8"))
    assert len(lj["layers"]) == 7
    assert {lab["id"] for lab in lj["labels"]} == {SKIN, FAT, MUSCLE, BONE, SOFT_TISSUE}
    assert set(np.unique(labels)) == {0, SKIN, FAT, MUSCLE, BONE, SOFT_TISSUE}

    # Orientation survives: the R marker (bone sphere on the patient's right) is at low x, the A cube at low z.
    mid_y = meta["dim_y"] // 2
    bone_x = np.nonzero((labels[:, mid_y, :] == BONE).any(axis=0))[0]
    assert bone_x[0] < meta["dim_x"] * 0.2
    centre_x = meta["dim_x"] // 2
    bone_z = np.nonzero(labels[:, mid_y, centre_x] == BONE)[0]
    assert bone_z.min() < meta["dim_z"] * 0.3 and bone_z.max() > meta["dim_z"] * 0.6   # A cube front, spine back

    prov = json.loads((wb / "provenance.json").read_text(encoding="utf-8"))
    assert prov["dataset"]["licence"] == "synthetic test phantom"
    assert prov["segmentation"]["ai"] is False
    assert prov["tissue_thresholds"]["fat"] == [-190.0, -30.0]
    assert prov["grid"]["spacing_mm"] == 2.0 and prov["pipeline"]["git_commit"]

    roi = json.loads((folders[1] / "volume.json").read_text())
    assert roi["region"] == "roi" and roi["dim_x"] * roi["spacing_mm"][0] == pytest.approx(130, abs=2)


def test_build_body_requires_a_licence(tmp_path):
    import build_body

    with pytest.raises(SystemExit):
        build_body.main([str(tmp_path), "--no-ai", "--out-root", str(tmp_path / "out")])
