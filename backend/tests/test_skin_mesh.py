"""The skin mesh extractor: a closed, outward-facing surface at the body's outer skin."""
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import extract_skin_mesh as esm  # noqa: E402


def ball_export(folder: Path, r_mm: float = 20.0, px: float = 1.0) -> Path:
    """An export folder holding only what the extractor reads: body.json and a depth.raw of a ball."""
    n = int(2 * r_mm / px) + 10
    zz, yy, xx = np.mgrid[0:n, 0:n, 0:n]
    centre = (n - 1) / 2
    dist = np.sqrt((zz - centre) ** 2 + (yy - centre) ** 2 + (xx - centre) ** 2) * px
    depth = np.clip(r_mm - dist, 0, None)                             # mm inside the ball, 0 outside
    (folder / "depth.raw").write_bytes(np.clip(np.rint(depth / 0.25), 0, 255).astype(np.uint8).tobytes())
    (folder / "body.json").write_text(json.dumps({"dims": [n, n, n], "spacing_mm": [px, px, px], "skin_depth": "depth.raw",
                                                  "skin_depth_unit_mm": 0.25}))
    return folder


def test_ball_meshes_to_a_sphere_of_its_radius_facing_out(tmp_path):
    ball_export(tmp_path)
    depth, spacing = esm.load_depth(tmp_path)
    verts, faces = esm.surface(depth, spacing, level_mm=0.4, smooth_mm=1.0)
    verts = esm.taubin(verts, faces)
    verts, faces = esm.decimate(verts, faces, 2000)
    vn = esm.normals(verts, faces)
    centre = np.full(3, (depth.shape[0] - 1) / 2)
    radii = np.linalg.norm(verts - centre, axis=1)
    assert abs(radii.mean() - 19.6) < 0.6, f"the surface lies 0.4 mm under a 20 mm skin: {radii.mean():.2f}"
    assert radii.std() < 0.35, "and is round"
    outward = np.einsum("ij,ij->i", vn, verts - centre) > 0
    assert outward.mean() > 0.98, "normals face out"
    assert 1500 <= len(faces) <= 2000, f"decimated to the budget: {len(faces)}"


def test_mesh_file_layout(tmp_path):
    ball_export(tmp_path)
    depth, spacing = esm.load_depth(tmp_path)
    verts, faces = esm.surface(depth, spacing, 0.4, 1.0)
    vn = esm.normals(verts, faces)
    esm.write_mesh(tmp_path / "skin.mesh", verts, faces, vn)
    data = (tmp_path / "skin.mesh").read_bytes()
    assert data[:4] == b"SKIN"
    nv, ni = struct.unpack("<II", data[4:12])
    assert nv == len(verts) and ni == faces.size
    assert len(data) == 12 + nv * 12 * 2 + ni * 4
    first = np.frombuffer(data[12:24], "<f4")
    assert np.allclose(first, verts[0])
