"""Brings the Segmented Internal Organs of the Visible Human Male (SIO; Höhne et al., University Medical Center
Hamburg-Eppendorf, CC BY 4.0, doi:10.5281/zenodo.15882018) into a photographed-body export of the same man
(prepare_photo_volume.py): over 200 labelled structures of the torso, from the shoulders to the upper thighs,
on his own photographs. The SIO is a 1 mm voxel model made from the same NLM photographs: each of its slices
is a photo (the same slice numbers) shrunk by three pixels (0.33 mm -> 0.99 mm) and cropped. The crop is not
documented and is not the same throughout (the SIO was aligned to the CT block by block, so it steps sideways by
a few millimetres at the specimen's joints), so it is measured on every slice: the body's outline in the SIO
slice is slid over the outline in our photo until they agree; a running median over nine slices drops any
slice where the outline misleads (the arms touching the trunk), and keeps the steps.

Writes into the export: labels.raw (uint8, the export's dims and layout, 0 = nothing / not covered, else an
index into the object table) and labels.json (the objects with their names and SIO label numbers, the
registration, the credit), and names them in body.json. Nearest-voxel resampling: labels do not blend.

Usage: python tools/import_sio_labels.py data/sio/VOXEL-MAN_segmented-internal-organs data/vhp_male_photos out/photo_body
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_photo_volume as ppv  # noqa: E402
from transfer_eyes import Frame  # noqa: E402

SIO_SCALE = 3                    # SIO voxel = 3 x 3 photo pixels (0.99 mm); measured: areas agree to 2 %
PHOTO_ROWS = 1216                # the photographs' height; SIO rows run as the photographs' (row 0 = back)
CREDIT = ("Segmented Internal Organs of the Visible Human Male, Höhne K.H., Pflesser B., Pommert A., Riemer M., "
          "Schiemann T., Schubert R., Tiede U., Schumacher U. (University Medical Center Hamburg-Eppendorf), "
          "CC BY 4.0, https://doi.org/10.5281/zenodo.15882018; based on the Visible Human Male, "
          "courtesy of the U.S. National Library of Medicine")


def read_objects(xlsx: Path) -> list[dict]:
    """The SIO object table (name, label numbers), read from the spreadsheet with the standard library."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    z = zipfile.ZipFile(xlsx)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    objects = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter("{%s}row" % ns["m"]):
        cells = []
        for c in row.findall("m:c", ns):
            v = c.find("m:v", ns)
            val = v.text if v is not None else ""
            cells.append(shared[int(val)] if c.get("t") == "s" and val else val)
        if cells and cells[0].strip():
            labels = [int(float(x)) for x in cells[1:] if str(x).strip()]
            if labels:
                objects.append({"name": cells[0].strip(), "labels": labels})
    return objects


def body_only(mask: np.ndarray) -> np.ndarray:
    """The largest piece of a 2D tissue mask (the body, not the label card beside it)."""
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == sizes.argmax()


def register(photo_mask: np.ndarray, sio_mask: np.ndarray, scale: int = SIO_SCALE) -> tuple[int, int, float]:
    """Where the SIO slice's top-left corner lies in the photo (row, col, native photo pixels), by sliding the
    SIO outline over the photo's outline shrunk the same way. Returns (row0, col0, agreement 0..1)."""
    small = ppv.block_mean(photo_mask[..., None].astype(np.uint8) * 255, scale)[..., 0] > 127
    a = small.astype(np.float32) - small.mean()
    b = sio_mask.astype(np.float32) - sio_mask.mean()
    pad = max(sio_mask.shape)
    big = np.zeros((small.shape[0] + 2 * pad, small.shape[1] + 2 * pad), np.float32)
    big[pad:pad + small.shape[0], pad:pad + small.shape[1]] = a
    c = fftconvolve(big, b[::-1, ::-1], mode="full")
    k = np.unravel_index(int(c.argmax()), c.shape)
    row0 = (k[0] - b.shape[0] + 1 - pad) * scale
    col0 = (k[1] - b.shape[1] + 1 - pad) * scale
    score = float(c.max() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9))
    return int(row0), int(col0), score


def resample(sio_labels: dict[int, np.ndarray], frame: Frame, offsets: dict[int, tuple[int, int]],
             scale: int = SIO_SCALE, photo_rows: int = PHOTO_ROWS) -> np.ndarray:
    """SIO label slices (by slice number; rows as the photographs', row 0 = back) onto the export's grid
    (x left, y up = slices, z back; the export's rows run front to back), each slice's corner at offsets[slice]
    = (photo row, photo col). Nearest voxel. Returns uint16 labels."""
    w, d, h = frame.dims
    out = np.zeros((h, d, w), np.uint16)                          # z, y(slices), x: the export's layout, x fastest
    ix = np.arange(w)
    iz = np.arange(h)
    col = frame.cols + (ix + 0.5) * frame.factor                  # native photo column of each export x
    row_front = frame.rows + (iz + 0.5) * frame.factor            # export rows: front to back
    row_native = (photo_rows - 1) - row_front                     # the photographs' rows: back to front
    for k in range(d):
        slice_no = int(round(frame.bottom - k * frame.every))
        lab = sio_labels.get(slice_no)
        if lab is None or slice_no not in offsets:
            continue
        row0, col0 = offsets[slice_no]
        cs = np.round((col - col0) / scale - 0.5).astype(int)
        rs = np.round((row_native - row0) / scale - 0.5).astype(int)
        okc = (cs >= 0) & (cs < lab.shape[1])
        okr = (rs >= 0) & (rs < lab.shape[0])
        if not okc.any() or not okr.any():
            continue
        block = lab[np.ix_(rs[okr], cs[okc])]
        out[np.ix_(iz[okr], [k], ix[okc])] = block[:, None, :]
    return out


def compress(labels16: np.ndarray, objects: list[dict]) -> tuple[np.ndarray, list[dict]]:
    """SIO label numbers (uint16, several per object) to one byte per object (index into the table, 0 = none)."""
    lut = np.zeros(65536, np.uint8)
    table = []
    for o in objects:
        if len(table) >= 255:
            raise ValueError("more than 255 objects")
        table.append({"index": len(table) + 1, "name": o["name"], "sio_labels": o["labels"]})
        for n in o["labels"]:
            lut[n] = len(table)
    out = lut[labels16]
    for t in table:
        t["voxels"] = int((out == t["index"]).sum())
    return out, table


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sio", help="the unpacked VOXEL-MAN_segmented-internal-organs folder (CT/, labels/, rgb/)")
    ap.add_argument("photos", help="folder of the colour photo DICOMs the export was made from")
    ap.add_argument("export", help="the export to receive the labels (photo_body)")
    ap.add_argument("--objects", help="SIO Object Labels.xlsx (default: beside the sio folder)")
    ap.add_argument("--smooth", type=int, default=9, help="running median over this many slices' offsets")
    args = ap.parse_args()
    import tifffile
    sio, export = Path(args.sio), Path(args.export)
    xlsx = Path(args.objects) if args.objects else sio.parent / "SIO Object Labels.xlsx"
    objects = read_objects(xlsx)
    label_files = {int(f.stem[len("labels"):]): f for f in (sio / "labels").glob("labels*.tif")}
    slices = sorted(label_files)
    print(f"{len(objects)} objects, {len(slices)} SIO slices {slices[0]}-{slices[-1]}")

    photos = ppv.index_slices(Path(args.photos))
    fits = []
    for i, n in enumerate(slices):
        if n not in photos:
            raise SystemExit(f"photo {n} is missing from {args.photos}")
        rgb = tifffile.imread(sio / "rgb" / f"rgb{n}.tif")
        sio_mask = body_only(ppv.tissue_mask(rgb))
        photo_mask = body_only(ppv.tissue_mask(ppv.read_photo(photos[n])[::-1]))     # the photographs' own rows
        fits.append(register(photo_mask, sio_mask))
        if i % 50 == 0:
            print(f"  slice {n}: SIO corner at photo row {fits[-1][0]}, col {fits[-1][1]}, agreement {fits[-1][2]:.3f}")
    rows0 = ppv.running_median(np.array([f[0] for f in fits], float), args.smooth).round().astype(int)
    cols0 = ppv.running_median(np.array([f[1] for f in fits], float), args.smooth).round().astype(int)
    offsets = {n: (int(r), int(c)) for n, r, c in zip(slices, rows0, cols0)}
    raw_rows, raw_cols = np.array([f[0] for f in fits]), np.array([f[1] for f in fits])
    outliers = int(((np.abs(raw_rows - rows0) > SIO_SCALE) | (np.abs(raw_cols - cols0) > SIO_SCALE)).sum())
    steps = sorted(set(zip(rows0.tolist(), cols0.tolist())))
    print(f"registration: SIO voxel = {SIO_SCALE} px; corners (row, col) used: {steps}; "
          f"{outliers} slices overruled by their neighbours; agreement {np.mean([f[2] for f in fits]):.3f}")

    frame = Frame(json.loads((export / "photo.json").read_text()), json.loads((export / "body.json").read_text()))
    labels = {n: tifffile.imread(f) for n, f in label_files.items()}
    vol16 = resample(labels, frame, offsets)
    vol, table = compress(vol16, objects)
    (export / "labels.raw").write_bytes(vol.tobytes())
    meta = {
        "dims": list(frame.dims), "format": "uint8 object index, 0 = none; layout as body.raw (x left fastest, y up, z back)",
        "objects": table, "slices": [slices[0], slices[-1]],
        "registration": {"sio_voxel_px": SIO_SCALE, "corners_by_slice": {str(n): list(offsets[n]) for n in slices},
                         "overruled_slices": outliers, "mean_agreement": round(float(np.mean([f[2] for f in fits])), 3)},
        "source": "Segmented Internal Organs of the Visible Human Male (VOXEL-MAN), Zenodo 10.5281/zenodo.15882018",
        "licence": "CC BY 4.0", "credit": CREDIT,
    }
    (export / "labels.json").write_text(json.dumps(meta, indent=2))
    body = json.loads((export / "body.json").read_text())
    body["labels"] = "labels.raw"
    body["label_table"] = "labels.json"
    (export / "body.json").write_text(json.dumps(body, indent=2))
    covered = int((vol > 0).sum())
    print(f"labelled voxels: {covered} ({covered / vol.size * 100:.1f} % of the export), "
          f"{sum(1 for t in table if t['voxels'])} objects present -> {export / 'labels.raw'}")


if __name__ == "__main__":
    main()
