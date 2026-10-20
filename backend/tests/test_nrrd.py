"""NRRD loading must give exactly the DICOM result, whatever space, axis order, flips, type or encoding the file uses."""
import gzip
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from app.dicom_loader import load_series  # noqa: E402
from app.nrrd_loader import load_nrrd  # noqa: E402
from make_test_series import build_phantom, write_series  # noqa: E402

SX, SY, SZ = 1.5, 1.5, 2.0


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    folder = tmp_path_factory.mktemp("phantom_dicom")
    write_series(build_phantom(nx=48, ny=40, nz=32, sx=SX, sy=SY, sz=SZ), folder, SX, SY, SZ)
    return load_series(folder)


def write_nrrd(path: Path, lps_zyx: np.ndarray, *, space="left-posterior-superior", order=(0, 1, 2),
               flip=(False, False, False), dtype="<i2", type_name="short", encoding="raw"):
    """Write the LPS (z, y, x) array as an NRRD whose file axes run along patient axes `order`
    (fastest first), optionally reversed, in the given space."""
    spacing = {0: SX, 1: SY, 2: SZ}
    to_space = np.array((-1, -1, 1) if space == "right-anterior-superior" else (1, 1, 1), dtype=float)
    data = lps_zyx
    for p, f in zip((0, 1, 2), flip):                      # flip along patient axis p (numpy axis 2 - p)
        if f:
            data = np.flip(data, axis=2 - p)
    # numpy axis for patient p is 2 - p; the file wants its fastest axis (order[0]) last in numpy order.
    data = np.transpose(data, [2 - p for p in reversed(order)])
    dirs = []
    for p in order:
        v = np.zeros(3)
        v[p] = spacing[p] * (-1 if flip[p] else 1)
        dirs.append("(" + ",".join(f"{c:g}" for c in v * to_space) + ")")
    sizes = " ".join(str(data.shape[2 - i]) for i in range(3))
    header = (f"NRRD0004\ntype: {type_name}\ndimension: 3\nspace: {space}\nsizes: {sizes}\n"
              f"space directions: {' '.join(dirs)}\nkinds: domain domain domain\nendian: little\n"
              f"encoding: {encoding}\nspace origin: (0,0,0)\n\n")
    payload = np.ascontiguousarray(data).astype(dtype).tobytes()
    if encoding == "gzip":
        payload = gzip.compress(payload)
    path.write_bytes(header.encode() + payload)


@pytest.mark.parametrize("variant", [
    dict(),
    dict(encoding="gzip", dtype="<i4", type_name="int"),
    dict(space="right-anterior-superior"),
    dict(flip=(True, False, True)),
    dict(order=(2, 0, 1)),
    dict(order=(1, 2, 0), flip=(False, True, False), space="right-anterior-superior", encoding="gzip"),
    dict(dtype="<f4", type_name="float"),
])
def test_nrrd_matches_dicom(reference, tmp_path, variant):
    path = tmp_path / "vol.nrrd"
    write_nrrd(path, reference.data, **variant)
    vol = load_nrrd(path)
    assert vol.data.shape == reference.data.shape
    assert np.array_equal(vol.data, reference.data)
    assert np.allclose(vol.spacing, reference.spacing)
    assert vol.is_hu


def test_rejects_non_3d(tmp_path):
    path = tmp_path / "bad.nrrd"
    path.write_bytes(b"NRRD0004\ntype: short\ndimension: 2\nsizes: 4 4\nencoding: raw\n\n" + bytes(32))
    with pytest.raises(ValueError):
        load_nrrd(path)
