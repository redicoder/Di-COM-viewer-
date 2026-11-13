"""The skull's bones on a made-up skull: a ball, and an atlas of two half balls (a "frontal" and an "occipital" bone)
that is bigger, shifted and a little turned. The atlas is fitted and the ball comes back as two named halves.
Needs scikit-image and scipy (backend/.venv-seg); skipped without them."""
import sys
import types
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import skull_bones  # noqa: E402
from anatomy_model.common import Structure, surface  # noqa: E402

SIZE = 80


def ball(keep=None):
    """A ball of 28 mm round the middle of an 80 mm block (array order z, y, x), or the part of it `keep` picks."""
    z, y, x = np.mgrid[0:SIZE, 0:SIZE, 0:SIZE].astype(np.float32) + 0.5
    mask = (z - 40) ** 2 + (y - 40) ** 2 + (x - 40) ** 2 < 28 ** 2
    if keep is not None:
        mask &= keep(z, y, x)
    return surface(mask, (1.0, 1.0, 1.0), 1.0)


def write_obj(path: Path, v_atlas: np.ndarray, f: np.ndarray) -> None:
    lines = ["# a made-up bone"] + [f"v {a:.4f} {b:.4f} {c:.4f}" for a, b, c in v_atlas] + [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in f]
    path.write_text("\n".join(lines) + "\n")


def make_atlas(folder: Path) -> Path:
    """The two halves in the atlas's own axes (x across, y front to back, z up), 1.12 times the size, shifted and
    turned 6 degrees about the upright axis."""
    folder.mkdir()
    rows = ["concept id\tname\telement file id"]
    turn = np.radians(6.0)
    for k, (name, keep) in enumerate((("frontal bone", lambda z, y, x: z < 40), ("occipital bone", lambda z, y, x: z >= 40))):
        v, f = ball(keep)                                               # the body's order: z back, y up, x left
        atlas = np.stack([v[:, 2] - 40, v[:, 0] - 40, v[:, 1] - 40], axis=1) * 1.12       # x, y (front to back), z (up)
        x = atlas[:, 0] * np.cos(turn) - atlas[:, 1] * np.sin(turn)
        y = atlas[:, 0] * np.sin(turn) + atlas[:, 1] * np.cos(turn)
        write_obj(folder / f"A{k}.obj", np.stack([x + 7.0, y - 130.0, atlas[:, 2] + 1500.0], axis=1), f)
        rows.append(f"FMA{k}\t{name.capitalize()}\tA{k}")
    (folder / "isa_element_parts.txt").write_text("\n".join(rows) + "\n")
    return folder


def test_the_atlas_is_fitted_and_the_skull_comes_back_as_its_bones(tmp_path):
    body = types.SimpleNamespace(export=tmp_path, size_mm=(float(SIZE), float(SIZE), float(SIZE)))
    v_mm, f = ball()
    quiet = lambda *_: None  # noqa: E731
    points, label, names = skull_bones.fit_atlas(body, make_atlas(tmp_path / "atlas"), v_mm, f, log=quiet)
    assert names == ["frontal bone", "occipital bone"]
    # Fitted: the atlas's outer points lie on the ball (the flat faces between the two halves have nothing to lie on).
    radius = np.linalg.norm(points - 40.0, axis=1)
    outer = radius > 20.0
    assert np.median(np.abs(radius[outer] - 28.0)) < 1.0
    gltf = (np.stack([v_mm[:, 2] - 40.0, v_mm[:, 1] - 40.0, -(v_mm[:, 0] - 40.0)], axis=1) / 1000.0).astype(np.float32)
    whole = Structure(skull_bones.WHOLE, "skeleton", gltf, f.astype(np.uint32), (0.88, 0.84, 0.74), bake=np.full((len(gltf), 4), 255, np.uint8))
    parts = skull_bones.split(body, whole, log=quiet)
    assert [p.name for p in parts] == ["frontal bone", "occipital bone"]
    assert sum(p.triangles for p in parts) == len(f)                    # every triangle of the skull is in one bone
    share = parts[0].triangles / len(f)
    assert 0.4 < share < 0.6
    assert parts[0].v[:, 2].mean() > 0.008 and parts[1].v[:, 2].mean() < -0.008       # the frontal in front (glTF z), the occipital behind
    # The line between them is darker in the bake (the suture), the rest as it was.
    assert parts[0].bake[:, 0].min() < 200 and np.median(parts[0].bake[:, 0]) == 255


def test_without_the_fitted_atlas_the_skull_stays_whole(tmp_path):
    body = types.SimpleNamespace(export=tmp_path, size_mm=(80.0, 80.0, 80.0))
    whole = Structure(skull_bones.WHOLE, "skeleton", np.zeros((3, 3), np.float32), np.array([[0, 1, 2]], np.uint32), (1, 1, 1))
    assert skull_bones.split(body, whole) == [whole]
