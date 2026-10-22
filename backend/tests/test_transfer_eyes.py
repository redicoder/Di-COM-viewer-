"""Eyes carried from one export's frame to another's land on the same photographed point."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import transfer_eyes as te  # noqa: E402


def export(cols, rows, top, bottom, every, factor, dims):
    px = 0.33 * factor
    photo = {"crop_photo_px": {"cols": [cols, cols + dims[0] * factor], "rows": [rows, rows + dims[2] * factor]},
             "slices": [top, bottom], "spacing_mm": [px, px, every]}
    body = {"dims": dims, "spacing_mm": [px, every, px],
            "size_m": [dims[0] * px / 1000, dims[1] * every / 1000, dims[2] * px / 1000]}
    return photo, body


def test_round_trip_lands_on_the_same_photo_point():
    head = export(cols=600, rows=300, top=1001, bottom=1225, every=1, factor=2, dims=[282, 225, 366])
    body = export(cols=200, rows=250, top=1002, bottom=2878, every=2, factor=4, dims=[436, 939, 250])
    a, b = te.Frame(*head), te.Frame(*body)
    p = [-0.0327, 0.0083, -0.0655]                                   # an eye in the head's frame
    col, row, slice_no = a.local_to_photo(p)
    q = b.photo_to_local(col, row, slice_no)
    col2, row2, slice2 = b.local_to_photo(q)
    assert abs(col - col2) < 1e-6 and abs(row - row2) < 1e-6 and abs(slice_no - slice2) < 1e-6
    # The same point is near the top of the whole body (the head is at high y) and off its centre line to the right.
    assert q[1] > 0.8 and q[0] < 0


def test_transfer_keeps_radius_and_moves_lid_and_front():
    head = export(600, 300, 1001, 1225, 1, 2, [282, 225, 366])
    body = export(200, 250, 1002, 2878, 2, 4, [436, 939, 250])
    head[1]["eyes"] = [{"centre_m": [-0.03, 0.01, -0.06], "radius_m": 0.011, "lid_line_y_m": 0.009, "skin_front_z_m": -0.084}]
    eyes = te.transfer(head[0], head[1], body[0], body[1])
    e = eyes[0]
    assert e["radius_m"] == 0.011
    assert e["lid_line_y_m"] < e["centre_m"][1], "the lid line stays below the centre"
    assert e["skin_front_z_m"] < e["centre_m"][2], "the skin's front stays in front of the centre"
    expected_dy = (0.009 - 0.01)                                     # 1 mm below, in metres
    assert abs((e["lid_line_y_m"] - e["centre_m"][1]) - expected_dy) < 1e-6


def test_region_box_is_the_source_export_in_the_target_frame():
    head = export(600, 300, 1001, 1225, 1, 2, [282, 225, 366])
    body = export(200, 250, 1002, 2878, 2, 4, [436, 939, 250])
    r = te.region_box(head[0], head[1], body[0], body[1])
    assert abs(r["size_m"][0] - head[1]["size_m"][0]) < 1e-6 and abs(r["size_m"][1] - head[1]["size_m"][1]) < 1e-6
    assert r["centre_m"][1] > 0.7, "the head sits at the top of the body"
