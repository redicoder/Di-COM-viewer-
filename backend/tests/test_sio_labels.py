"""The SIO organ labels land on the photographed body where the photographs say they are."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_sio_labels as sio  # noqa: E402
from transfer_eyes import Frame  # noqa: E402


def ellipse(shape, centre, radii):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return ((yy - centre[0]) / radii[0]) ** 2 + ((xx - centre[1]) / radii[1]) ** 2 <= 1.0


def test_register_finds_the_crop_corner():
    photo = ellipse((1216, 2048), (640, 1000), (300, 520))        # a body outline, full photo pixels
    row0, col0 = 303, 402                                          # the SIO crop's corner, a multiple of 3 plus a bit
    small = sio.ppv.block_mean(photo[..., None].astype(np.uint8) * 255, 3)[..., 0] > 127
    crop = small[row0 // 3:row0 // 3 + 300, col0 // 3:col0 // 3 + 500]
    r, c, score = sio.register(photo, crop)
    assert abs(r - row0) <= 3 and abs(c - col0) <= 3
    assert score > 0.8


def test_resample_puts_a_label_where_the_photo_has_it():
    # An export of 60 x 20 x 40 voxels at 0.66 mm (factor 2), slices 1300 (top) to 1319, from a crop at
    # photo rows 100.. and cols 200.. (rows front to back, as prepare_photo_volume writes them).
    photo = {"crop_photo_px": {"cols": [200, 320], "rows": [100, 180]}, "slices": [1300, 1319], "spacing_mm": [0.66, 0.66, 1]}
    body = {"dims": [60, 20, 40], "spacing_mm": [0.66, 1, 0.66], "size_m": [0.0396, 0.02, 0.0264]}
    frame = Frame(photo, body)
    # SIO slice 1310 with its corner at photo row 1216 - 1 - 179 = 1036 (the back of our crop), col 200 -> the
    # SIO voxel (rs, cs) covers native rows 1036 + 3 rs .., cols 200 + 3 cs ... One labelled voxel at rs=5, cs=10.
    row0, col0 = 1036, 200
    lab = np.zeros((40, 60), np.uint16)
    lab[5, 10] = 513
    out = sio.resample({1310: lab}, frame, {1310: (row0, col0)})
    assert out.shape == (40, 20, 60)
    k = (frame.bottom - 1310) // frame.every                       # export slice index of SIO slice 1310
    z, y, x = np.nonzero(out)
    assert set(y.tolist()) == {k}
    # The voxel's photo columns 230..232 are export x = (col - 200) / 2 - 0.5 -> 14.5..16: x in {15, 16} or so.
    assert set(x.tolist()) <= {14, 15, 16}
    # Its native rows 1051..1053 are front rows 1215 - row = 162..164 -> export z = (162 - 100) / 2 - 0.5 = 30.5..32.
    assert set(z.tolist()) <= {30, 31, 32}
    assert out[z, y, x].tolist() == [513] * len(z)


def test_compress_maps_every_label_of_an_object_to_one_index():
    objects = [{"name": "liver", "labels": [3001, 3002]}, {"name": "spleen", "labels": [3300]}]
    vol = np.array([[[0, 3001, 3002, 3300, 9999]]], np.uint16)
    out, table = sio.compress(vol, objects)
    assert out.dtype == np.uint8
    assert out.tolist() == [[[0, 1, 1, 2, 0]]]
    assert table[0]["name"] == "liver" and table[0]["voxels"] == 2 and table[1]["voxels"] == 1
