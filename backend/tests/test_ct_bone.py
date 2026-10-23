"""Bone from the CT lands on the photographed body where the outlines say it is."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_ct_bone as cb  # noqa: E402
from transfer_eyes import Frame  # noqa: E402


def ellipse(shape, centre, radii):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return ((yy - centre[0]) / radii[0]) ** 2 + ((xx - centre[1]) / radii[1]) ** 2 <= 1.0


def test_register_finds_where_the_ct_sits_on_the_photo():
    photo = ellipse((1216, 2048), (640, 1000), (300, 520))            # the body, 0.33 mm pixels
    # The same body seen by a CT at 0.9375 mm whose field starts 60 mm above and 40 mm left of the photo's corner.
    ct = ellipse((512, 512), ((640 * 0.33 - 60) / 0.9375, (1000 * 0.33 - 40) / 0.9375), (300 * 0.33 / 0.9375, 520 * 0.33 / 0.9375))
    row, col, score = cb.register(photo, 0.33, ct, 0.9375)
    assert abs(row - 60) <= 1.5 and abs(col - 40) <= 1.5
    assert score > 0.8


def test_resample_puts_a_ct_pixel_on_the_right_export_voxel():
    photo = {"crop_photo_px": {"cols": [200, 320], "rows": [100, 180]}, "slices": [1300, 1319], "spacing_mm": [0.66, 0.66, 1]}
    body = {"dims": [60, 20, 40], "spacing_mm": [0.66, 1, 0.66], "size_m": [0.0396, 0.02, 0.0264]}
    frame = Frame(photo, body)
    mask = np.zeros((100, 100), bool)
    mask[30, 40] = True                                                # CT pixel: rows 30..31 x 0.9375 mm from its corner
    # The CT corner sits at (20 mm, 50 mm) on the photograph; the pixel covers photo rows (20 + 28.1..29.1 mm)
    # -> crop rows (48.1..49.1 mm - 33 mm) / 0.66 ... export z about 23; cols (50 + 37.5..38.4 - 66) / 0.66 ~ 33.
    out = cb.resample_slice(mask, 0.9375, (20.0, 50.0), frame)
    zs, xs = np.nonzero(out)
    assert len(zs) >= 1
    assert set(zs.tolist()) <= {22, 23, 24} and set(xs.tolist()) <= {32, 33, 34}


def test_bone_mask_drops_specks_and_fills_marrow():
    hu = np.full((60, 60), -100.0, np.float32)
    hu[20:40, 20:40] = 800.0                                          # a shaft's shell...
    hu[25:35, 25:35] = -50.0                                          # ...round yellow marrow
    hu[5, 5] = 900.0                                                   # a speck
    bone = cb.bone_mask(hu, 0.9375)
    assert bone[30, 30] and bone[20, 20]
    assert not bone[5, 5]
