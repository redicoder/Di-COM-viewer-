"""End-to-end check: phantom -> loader -> resample -> API. Run with `pytest -q`."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from make_test_series import build_phantom, write_series  # noqa: E402
from app.dicom_loader import load_series                     # noqa: E402
from app.volume import pack_for_unity, resample              # noqa: E402


@pytest.fixture(scope="module")
def phantom_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("data") / "phantom_ct"
    write_series(build_phantom(), d, 1.5, 1.5, 2.0)   # 128x128x96 @ 1.5x1.5x2.0 mm
    return d


def test_loader_sorts_and_rescales(phantom_dir):
    vol = load_series(phantom_dir)
    assert vol.data.shape == (96, 128, 128)
    assert vol.spacing == (1.5, 1.5, 2.0)
    assert vol.is_hu and vol.modality == "CT"
    assert vol.data.min() == -1000 and vol.data.max() == 1200
    # S marker (disc) must land in the LAST slices after sorting -> superior is at high z index
    assert (vol.data[-1] == 1200).sum() > 100 and (vol.data[0] == 1200).sum() == 0
    # R marker is on the patient's right -> low x index (columns), A marker -> low y index (rows)
    zz, yy, xx = np.nonzero(vol.data[:80] == 1200)
    assert xx.min() < 20 and yy.min() < 30


def test_unity_packing_axes(phantom_dir):
    vol = load_series(phantom_dir)
    raw, meta = pack_for_unity(vol)
    assert (meta["dim_x"], meta["dim_y"], meta["dim_z"]) == (128, 96, 128)
    assert meta["spacing_mm"] == [1.5, 2.0, 1.5]
    assert len(raw) == 128 * 96 * 128 * 2
    arr = np.frombuffer(raw, dtype="<i2").reshape(meta["dim_z"], meta["dim_y"], meta["dim_x"])
    # texture y (axis 1) is superior: the disc marker should be at the top row of texture y
    assert (arr[:, -1, :] == 1200).sum() > 100


def test_resample_isotropic(phantom_dir):
    vol = resample(load_series(phantom_dir), target_spacing_mm=1.5, max_dim=512)
    assert vol.data.shape == (128, 128, 128)
    assert all(abs(s - 1.5) < 1e-6 for s in vol.spacing)


def test_api(phantom_dir, monkeypatch):
    monkeypatch.setenv("DICOM_DATA_ROOT", str(phantom_dir.parent))
    import importlib
    import app.main as main
    importlib.reload(main)
    client = TestClient(main.app)
    r = client.post("/api/volume/load", json={"path": "phantom_ct", "target_spacing_mm": 1.5})
    assert r.status_code == 200, r.text
    vid = r.json()["volume_id"]
    assert client.get(f"/api/volume/{vid}/meta").json()["is_hu"] is True
    raw = client.get(f"/api/volume/{vid}/raw")
    assert raw.status_code == 200
    assert len(raw.content) == 128 ** 3 * 2
    assert raw.headers["X-Dim-Y"] == "128"
    assert client.post("/api/volume/load", json={"path": "../etc"}).status_code in (400, 404)
