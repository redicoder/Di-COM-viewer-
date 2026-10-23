"""Tissue classes learnt from labelled voxels' colours come back for the same colours elsewhere."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import classify_tissue as ct  # noqa: E402


def block(colour, shape=(4, 12, 12)):
    rgba = np.zeros(shape + (4,), np.uint8)
    rgba[..., :3] = colour
    rgba[..., 3] = 255
    return rgba


def test_table_learns_fat_and_muscle_and_predicts_them():
    rng = np.random.default_rng(1)
    fat, muscle = block((150, 130, 90)), block((70, 35, 25))
    rgba = np.concatenate([fat, muscle], axis=2)                         # side by side in x
    rgba[..., :3] = np.clip(rgba[..., :3].astype(int) + rng.integers(-6, 7, rgba[..., :3].shape), 0, 255)
    depth = np.full(rgba.shape[:3], 12.0, np.float32)                   # deep: not the skin band
    cls = np.zeros(rgba.shape[:3], np.uint8)
    cls[:, :, :12] = ct.CLASSES.index("fat") + 1
    cls[:, :, 12:] = ct.CLASSES.index("muscle") + 1
    counts = np.zeros((ct.N_CELLS, len(ct.CLASSES)), np.int32)
    ct.count_cells(ct.features(rgba, depth, 1.0), cls, counts)
    probs = ct.smooth_table(counts)
    # The same two colours, slightly shifted, in another block.
    test = np.concatenate([block((146, 134, 94)), block((74, 32, 28))], axis=2)
    pred = ct.predict(ct.features(test, depth, 1.0), probs)
    assert (pred[:, :, :12] == ct.CLASSES.index("fat") + 1).mean() > 0.95
    assert (pred[:, :, 12:] == ct.CLASSES.index("muscle") + 1).mean() > 0.95


def test_outside_the_tissue_is_never_classed():
    rgba = block((150, 130, 90))
    rgba[:, :3, :, 3] = 0                                                # no tissue in the first rows
    depth = np.full(rgba.shape[:3], 5.0, np.float32)
    cell = ct.features(rgba, depth, 1.0)
    assert (cell[:, :3, :] == -1).all() and (cell[:, 3:, :] >= 0).all()
    probs = np.full((ct.N_CELLS, len(ct.CLASSES)), 0.2, np.float32)
    pred = ct.predict(cell, probs)
    assert (pred[:, :3, :] == 0).all() and (pred[:, 3:, :] > 0).all()


def test_specks_of_bone_become_muscle_but_a_bone_stays():
    bone, muscle = ct.CLASSES.index("bone") + 1, ct.CLASSES.index("muscle") + 1
    pred = np.full((1, 40, 40), muscle, np.uint8)
    pred[0, 5, 5] = bone                                                 # a speck
    pred[0, 15:30, 15:30] = bone                                         # a bone
    out = ct.unspeckle(pred, bone, muscle)
    assert out[0, 5, 5] == muscle and out[0, 20, 20] == bone
