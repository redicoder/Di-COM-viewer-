"""Naming teeth by their place in the row: where the teeth part along the row, and how they are counted off.
Needs scipy (backend/.venv-seg); skipped without scikit-image, which the package imports."""
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import teeth  # noqa: E402


def row_profile(lengths_mm, gaps_mm, dip=0.35):
    """How much tooth along a row: a hump per tooth, the humps touching with a dip to `dip` of their height, or
    parted by a space where gaps_mm says so (one entry per joint)."""
    out = []
    for k, length in enumerate(lengths_mm):
        n = int(length / teeth.BIN_MM)
        t = np.linspace(0.0, np.pi, n)
        out.append(100.0 * (dip + (1.0 - dip) * np.sin(t)))
        if k < len(gaps_mm) and gaps_mm[k] > 0:
            out.append(np.zeros(int(gaps_mm[k] / teeth.BIN_MM)))
    return np.concatenate(out)


def test_the_row_parts_where_the_crowns_touch_and_where_a_tooth_is_missing():
    lengths = [8.5, 6.5, 7.5, 7.0, 10.0, 9.0]
    found = teeth.cuts_of(row_profile(lengths, [0, 0, 0, 7.0, 0]))
    assert len(found) == 6
    got = [(b - a) * teeth.BIN_MM for a, b in found]
    assert np.allclose(got, lengths, atol=1.2)
    assert found[4][0] - found[3][1] > 5.0 / teeth.BIN_MM                 # the space where a tooth is missing stays a space


def test_a_shallow_dip_within_a_molar_is_not_a_cut():
    molar = row_profile([5.0, 5.0], [0], dip=0.9)                         # two cusps, a groove between: one tooth
    assert len(teeth.cuts_of(molar)) == 1


def test_teeth_are_counted_off_from_the_midline():
    full = [("tooth", w) for w in teeth.WIDTH["upper"][:7]]
    assert teeth.name_side(full, "upper") == teeth.SLOTS[:7]
    # A first molar missing with its space left: the two behind are the second and the third.
    gap = [("tooth", 8.5), ("tooth", 6.5), ("tooth", 7.5), ("tooth", 7.0), ("tooth", 7.0), ("space", 10.0), ("tooth", 9.5), ("tooth", 8.5)]
    assert teeth.name_side(gap, "upper")[-2:] == ["second molar", "third molar"]
    # A premolar lost long ago and the space closed: the molar behind is still known for a molar by its length.
    closed = [("tooth", 5.0), ("tooth", 5.5), ("tooth", 7.0), ("tooth", 7.0), ("tooth", 11.0), ("tooth", 10.5)]
    assert teeth.name_side(closed, "lower")[-2:] == ["first molar", "second molar"]
    # Front teeth the scan did not part: one long piece, unnamed, counted as the teeth it holds.
    fused = [("tooth", 17.0), ("tooth", 7.0)]
    assert teeth.name_side(fused, "lower") == [None, "first premolar"]
