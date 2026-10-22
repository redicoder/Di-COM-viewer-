"""Carries the eyes found in one photographed-body export (the head at 0.66 mm, where the finder works) into
another export of the same photographs (the whole body at 1.3 x 2 mm, where it does not), through the
coordinates the two share: the photo's column and row, and the slice number. Also records the source as a
REGION of the target (its box in the target's local metres), so the lab can draw the finer export in place of
the coarser one there: the face at full detail on the whole body.

Both exports come from prepare_photo_volume.py, which writes photo.json (crop_photo_px, slices, spacing_mm) and
body.json (dims, size_m, eyes in body-local metres with the origin at the centre). Writes the eyes into the
target's body.json.

Usage: python tools/transfer_eyes.py backend/out/photo_head backend/out/photo_body
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PIXEL_MM = 0.33


class Frame:
    """An export's mapping between body-local metres and the photographs' (column, row, slice)."""

    def __init__(self, photo: dict, body: dict):
        self.dims = body["dims"]                                     # W (x), D (slices, y), H (rows, z)
        self.size = body["size_m"]
        self.cols = photo["crop_photo_px"]["cols"][0]
        self.rows = photo["crop_photo_px"]["rows"][0]
        self.factor = round(body["spacing_mm"][0] / PIXEL_MM)
        top, bottom = photo["slices"]
        self.bottom = bottom
        self.every = round((bottom - top) / max(self.dims[1] - 1, 1))

    def local_to_photo(self, p: list[float]) -> tuple[float, float, float]:
        w, d, h = self.dims
        ix = (p[0] / self.size[0] + 0.5) * w - 0.5
        k = (p[1] / self.size[1] + 0.5) * d - 0.5
        iz = (p[2] / self.size[2] + 0.5) * h - 0.5
        return self.cols + (ix + 0.5) * self.factor, self.rows + (iz + 0.5) * self.factor, self.bottom - k * self.every

    def photo_to_local(self, col: float, row: float, slice_no: float) -> list[float]:
        w, d, h = self.dims
        ix = (col - self.cols) / self.factor - 0.5
        iz = (row - self.rows) / self.factor - 0.5
        k = (self.bottom - slice_no) / self.every
        return [((ix + 0.5) / w - 0.5) * self.size[0], ((k + 0.5) / d - 0.5) * self.size[1], ((iz + 0.5) / h - 0.5) * self.size[2]]


def transfer(src_photo: dict, src_body: dict, dst_photo: dict, dst_body: dict) -> list[dict]:
    a, b = Frame(src_photo, src_body), Frame(dst_photo, dst_body)
    eyes = []
    for e in src_body.get("eyes", []):
        centre = b.photo_to_local(*a.local_to_photo(e["centre_m"]))
        lid = b.photo_to_local(*a.local_to_photo([e["centre_m"][0], e["lid_line_y_m"], e["centre_m"][2]]))
        front = b.photo_to_local(*a.local_to_photo([e["centre_m"][0], e["centre_m"][1], e["skin_front_z_m"]]))
        eyes.append({"centre_m": centre, "radius_m": e["radius_m"], "lid_line_y_m": lid[1], "skin_front_z_m": front[2]})
    return eyes


def region_box(src_photo: dict, src_body: dict, dst_photo: dict, dst_body: dict) -> dict:
    """The source export's box inside the target's local metres: its centre and size."""
    a, b = Frame(src_photo, src_body), Frame(dst_photo, dst_body)
    half = [s / 2 for s in src_body["size_m"]]
    corners = [b.photo_to_local(*a.local_to_photo([sx * half[0], sy * half[1], sz * half[2]]))
               for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    return {"name": src_body.get("region_name", "head"), "folder": None,
            "centre_m": [(lo[i] + hi[i]) / 2 for i in range(3)], "size_m": [hi[i] - lo[i] for i in range(3)]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="export whose body.json has the eyes (the head)")
    ap.add_argument("target", help="export to receive them (the whole body)")
    args = ap.parse_args()
    src, dst = Path(args.source), Path(args.target)
    load = lambda p: json.loads(p.read_text())  # noqa: E731
    eyes = transfer(load(src / "photo.json"), load(src / "body.json"), load(dst / "photo.json"), load(dst / "body.json"))
    if len(eyes) < 2:
        raise SystemExit(f"{src} has no eyes to carry over")
    body = load(dst / "body.json")
    body["eyes"] = eyes
    body["eyes_from"] = src.name
    region = region_box(load(src / "photo.json"), load(src / "body.json"), load(dst / "photo.json"), body)
    region["folder"] = src.name
    body["regions"] = [r for r in body.get("regions", []) if r.get("folder") != src.name] + [region]
    print("region", region["name"], "centre", [round(c, 4) for c in region["centre_m"]], "size", [round(c, 4) for c in region["size_m"]])
    (dst / "body.json").write_text(json.dumps(body, indent=2))
    for e in eyes:
        print("eye at", [round(c, 4) for c in e["centre_m"]], "m, radius", round(e["radius_m"] * 1000, 1), "mm")
    print(f"-> {dst / 'body.json'}")


if __name__ == "__main__":
    main()
