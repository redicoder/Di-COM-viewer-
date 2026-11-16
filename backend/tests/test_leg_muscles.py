"""The Denver set's leg muscles: reading its STL files (binary and text), its names made plain, its axes turned to
the body's, and a closed mesh made solid on the body's grid. Needs scikit-image and scipy (backend/.venv-seg)."""
import struct
import sys
import types
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import leg_muscles  # noqa: E402
from anatomy_model.common import surface  # noqa: E402

TETRA_V = np.array([[0.0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]])
TETRA_F = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])


def write_binary(path: Path) -> None:
    with open(path, "wb") as fh:
        fh.write(b"\0" * 80 + struct.pack("<I", len(TETRA_F)))
        for tri in TETRA_F:
            fh.write(struct.pack("<3f", 0, 0, 0) + b"".join(struct.pack("<3f", *TETRA_V[i]) for i in tri) + struct.pack("<H", 0))


def write_text(path: Path) -> None:
    lines = ["solid t"]
    for tri in TETRA_F:
        lines += [" facet normal 0 0 0", "  outer loop"] + [f"   vertex {TETRA_V[i][0]:e} {TETRA_V[i][1]:e} {TETRA_V[i][2]:e}" for i in tri] + ["  endloop", " endfacet"]
    path.write_text("\n".join(lines + ["endsolid t"]) + "\n")


@pytest.mark.parametrize("writer", [write_binary, write_text])
def test_an_stl_file_is_read_with_its_corners_joined(tmp_path, writer):
    writer(tmp_path / "a.stl")
    v, f = leg_muscles.read_stl(tmp_path / "a.stl")
    assert v.shape == (4, 3) and f.shape == (4, 3)                       # 12 corners in the file, 4 points
    assert sorted(map(tuple, v.tolist())) == sorted(map(tuple, TETRA_V.tolist()))
    assert np.allclose(sorted(np.linalg.norm(v[f[:, 0]] - v[f[:, 1]], axis=1)), sorted(np.linalg.norm(TETRA_V[TETRA_F[:, 0]] - TETRA_V[TETRA_F[:, 1]], axis=1)))


def test_the_sets_names_are_made_plain_and_what_the_body_has_is_left_out():
    assert leg_muscles.plain_name("Left", "Muscle", "VastusLateralis") == "left vastus lateralis"
    assert leg_muscles.plain_name("Right", "Muscle", "Semitendonosus") == "right semitendinosus"          # spelt so in one folder
    assert leg_muscles.plain_name("Right", "Muscle", "Semitendinosus") == "right semitendinosus"
    assert leg_muscles.plain_name("Left", "Muscle", "BicepsFemorisLongus") == "left biceps femoris, long head"
    assert leg_muscles.plain_name("Left", "Muscle", "Illiacus") is None                                    # the body's own labels have it
    assert leg_muscles.plain_name("Right", "Muscle", "PsoasMajor") is None
    assert leg_muscles.plain_name("Left", "Bone", "Femur") is None                                         # BoneHub's bones are in the body
    assert leg_muscles.plain_name("Left", "Ligament", "ACL") == "left anterior cruciate ligament"
    assert leg_muscles.plain_name("Right", "Cartilage", "TibialMedial") == "right medial cartilage of the tibia at the knee"


def test_the_sets_axes_are_turned_to_the_bodys():
    # Their x to his left, y to his front, z down -> the body's z (back), y (up), x (left).
    front_low_left = np.array([[30.0, 200.0, 900.0]])
    assert leg_muscles.to_body_axes(front_low_left).tolist() == [[-200.0, -900.0, 30.0]]


def test_a_closed_mesh_is_made_solid_on_the_bodys_grid():
    z, y, x = np.mgrid[0:40, 0:40, 0:40].astype(np.float32) + 0.5
    ball = (z - 20) ** 2 + (y - 20) ** 2 + (x - 20) ** 2 < 12 ** 2
    v_mm, f = surface(ball, (1.0, 1.0, 1.0), 0.8)
    body = types.SimpleNamespace(spacing=(1.32, 2.0, 1.32), dims=(31, 20, 31))
    lo, block = leg_muscles.solid(body, v_mm, f)
    volume = block.sum() * 1.32 * 2.0 * 1.32
    true = 4 / 3 * np.pi * 12 ** 3
    assert 0.9 * true < volume < 1.5 * true                              # the ball's volume and the voxels its surface touches (voxels of 1.3 x 2 mm)
    centre = np.round(np.array([20, 20, 20]) / np.array(body.spacing)).astype(int) - lo
    assert block[tuple(centre)]                                           # filled, not a shell
