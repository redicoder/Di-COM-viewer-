"""Organs the labels have only as a thin wall, on made-up blocks: the windpipe and the bronchi as solids that share
one lumen, and the heart's sac opened. Needs scipy (backend/.venv-seg); skipped without it."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("scipy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import thin_organs  # noqa: E402

SPACING = (1.32, 2.0, 1.32)


def tube():
    """A tube standing along y: its wall one voxel thick round a lumen of 5 x 5 voxels. The upper half of the wall
    is one object's (the windpipe's), the lower half another's (a bronchus's); the lumen is one object throughout."""
    shape = (11, 20, 11)
    solid = np.zeros(shape, bool)
    solid[2:9, :, 2:9] = True
    lumen = np.zeros(shape, bool)
    lumen[3:8, :, 3:8] = True
    wall = solid & ~lumen
    upper, lower = wall.copy(), wall.copy()
    upper[:, :10, :] = False
    lower[:, 10:, :] = False
    return upper, lower, lumen, solid


def test_the_windpipe_and_the_bronchi_are_solids_and_share_the_lumen_between_them():
    upper, lower, lumen, solid = tube()
    a, b = thin_organs.airways(upper, lower, lumen, SPACING)
    assert np.array_equal(a | b, solid) and not (a & b).any()           # together the whole tube, and no voxel is given twice
    assert a[5, 15, 5] and not b[5, 15, 5]                              # the lumen up in the windpipe is the windpipe's,
    assert b[5, 4, 5] and not a[5, 4, 5]                                # down in the bronchus the bronchus's
    assert a[:, 12:, :].sum() == solid[:, 12:, :].sum() and b[:, :8, :].sum() == solid[:, :8, :].sum()
    # No second wall: the first takes all of the lumen (and the other way round).
    alone, none = thin_organs.airways(upper | lower, np.zeros_like(upper), lumen, SPACING)
    assert np.array_equal(alone, solid) and not none.any()
    none, alone = thin_organs.airways(np.zeros_like(upper), upper | lower, lumen, SPACING)
    assert np.array_equal(alone, solid) and not none.any()


def test_the_thick_part_of_a_wall_is_what_a_cube_of_three_voxels_fits_into():
    mask = np.zeros((24, 24, 24), bool)
    mask[4:14, 4:14, 4:14] = True                                       # a mass of ten voxels each way,
    mask[14:22, 6:12, 8] = True                                         # a sheet one voxel thick running off it,
    mask[18:22, 18:22, 18:22] = True                                    # and a small mass of four voxels each way (64 voxels)
    thick = thin_organs.thick(mask, least=200)
    assert thick[4:14, 4:14, 4:14].all() and thick.sum() == 1000        # the mass whole, the sheet gone, the small mass left out
    assert thin_organs.thick(mask, least=0)[18:22, 18:22, 18:22].all()   # (asked for every piece, it stays)
    assert not thin_organs.thick(np.zeros((5, 5, 5), bool)).any()


def test_the_opened_sac_leaves_the_heart_to_be_seen_from_the_front():
    shape = (30, 30, 30)                                                # z from the front (0) to the back
    heart = np.zeros(shape, bool)
    heart[12:22, 6:18, 10:20] = True
    sac = np.zeros(shape, bool)
    sac[6:12, 6:18, 10:20] = True                                       # a pad of the sac lying before the heart,
    sac[10:24, 18:24, 8:22] = True                                      # the mass over the heart, round the vessels' roots,
    sac[12:20, 0:5, 22:28] = True                                       # and a mass beside and under the heart, away from them
    roots = np.zeros(shape, bool)
    roots[14:18, 24:30, 13:17] = True                                   # a great vessel going up out of the mass
    out = thin_organs.opened(sac, heart, roots, least=50)
    assert not out[6:12, 6:18, 10:20].any()                             # nothing of it before the heart,
    assert out[10:24, 18:24, 8:22].all()                                # the mass at the roots whole,
    assert not out[12:20, 0:5, 22:28].any()                             # the mass that reaches no great vessel left out,
    assert thin_organs.opened(sac, heart, None, least=50)[12:20, 0:5, 22:28].all()         # (which stays where no vessels are told)
    columns = heart.any(axis=0)
    assert not (out.any(axis=0) & columns)[6:18, :].any()               # and seen from the front no voxel of it lies over the heart


def test_the_shapes_are_made_from_the_labels_objects_and_only_where_the_labels_have_them():
    upper, lower, lumen, solid = tube()
    lab = np.zeros(upper.shape, np.uint8)
    lab[upper], lab[lower], lab[lumen] = 1, 2, 3
    objects = [{"name": "trachea", "index": 1, "voxels": int(upper.sum())}, {"name": "bronchi", "index": 2, "voxels": int(lower.sum())},
               {"name": "trachea lumen", "index": 3, "voxels": int(lumen.sum())}, {"name": "pericardium", "index": 4, "voxels": 0}]
    got = thin_organs.shapes(SimpleNamespace(labels=lab, objects=objects, spacing=SPACING))
    assert set(got) == {"trachea", "bronchi"}                           # (the labels have no sac here)
    whole = np.zeros(lab.shape, bool)
    for name in got:
        first, block = got[name]
        box = tuple(slice(a, a + n) for a, n in zip(first, block.shape))
        assert not (whole[box] & block).any()
        whole[box] |= block
    assert np.array_equal(whole, solid)                                 # each block lies where it belongs: together they are the tube
    assert set(thin_organs.NOTES) == {"trachea", "bronchi", "pericardium"}
