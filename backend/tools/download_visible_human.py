"""
Download Visible Human data from NCI Imaging Data Commons (collection nlm_visible_human_project).
Runs in .venv-seg (it has idc-index):

    # colour cryosection photos of the male, slices 1001..1225 (the head), one file per slice
    .venv-seg\\Scripts\\python.exe tools\\download_visible_human.py photos data\\vhp_male_head_photos --first 1001 --last 1225
    # CT series, one sub-folder each (then tools/prepare_visible_human.py stitches them)
    .venv-seg\\Scripts\\python.exe tools\\download_visible_human.py ct data\\vhp_female_normal --patient VHP-F --study Normal

Photos are 7.3 MB each (1,878 for the male, 14 GB in all), so only the requested slice range is fetched: each
file's slice number is read from its first 16 KB (an HTTP range request) and cached in slice_index.json.
Files are saved as slice_NNNN.dcm. Already complete files are skipped.

Licence: "National Library of Medicine Terms and Conditions; May 21, 2019". Credit: "Courtesy of the U.S.
National Library of Medicine". See LICENSES.md.
"""
from __future__ import annotations

import argparse
import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

COLLECTION = "nlm_visible_human_project"
PHOTO_BYTES = 2048 * 1216 * 3


def https(url: str) -> str:
    return url.replace("s3://idc-open-data/", "https://idc-open-data.s3.amazonaws.com/")


def client():
    from idc_index import index
    return index.IDCClient()


def photo_series(c, patient: str) -> str:
    df = c.sql_query(f"SELECT SeriesInstanceUID FROM index WHERE collection_id = '{COLLECTION}' AND "
                     f"PatientID = '{patient}' AND Modality = 'XC' AND SeriesDescription = 'Fullcolor - direct digital'")
    if len(df) != 1:
        raise SystemExit(f"Expected one full-colour photo series for {patient}, found {len(df)}")
    return df.SeriesInstanceUID[0]


def slice_number(url: str) -> int:
    import pydicom

    req = urllib.request.Request(https(url), headers={"Range": "bytes=0-16383"})
    with urllib.request.urlopen(req, timeout=60) as r:
        head = r.read()
    return int(round(float(pydicom.dcmread(io.BytesIO(head), stop_before_pixels=True, force=True).SliceLocation)))


def photos(args) -> None:
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    index_file = dest / "slice_index.json"
    if index_file.exists():
        mapping = json.loads(index_file.read_text())
    else:
        c = client()
        urls = c.get_series_file_URLs(photo_series(c, args.patient))
        print(f"Reading the slice number of {len(urls)} photos ...", flush=True)
        with ThreadPoolExecutor(32) as ex:
            mapping = dict(zip(urls, ex.map(slice_number, urls)))
        index_file.write_text(json.dumps(mapping, indent=0))
    todo = [(u, loc) for u, loc in mapping.items() if args.first <= loc <= args.last]

    def fetch(item) -> int:
        url, loc = item
        out = dest / f"slice_{loc:04d}.dcm"
        if out.exists() and out.stat().st_size > PHOTO_BYTES:
            return 0
        urllib.request.urlretrieve(https(url), out)
        return 1

    with ThreadPoolExecutor(8) as ex:
        n = sum(ex.map(fetch, todo))
    print(f"Slices {args.first}..{args.last}: {len(todo)} photos, {n} downloaded into {dest}")


def ct(args) -> None:
    c = client()
    df = c.sql_query(f"SELECT SeriesInstanceUID, SeriesNumber, instanceCount FROM index WHERE collection_id = "
                     f"'{COLLECTION}' AND PatientID = '{args.patient}' AND StudyDescription = '{args.study}' AND "
                     f"Modality = 'CT' AND instanceCount > 1 ORDER BY instanceCount DESC")
    for i, r in enumerate(df.itertuples()):
        dest = Path(args.dest) / f"part{i}_s{r.SeriesNumber}_{r.instanceCount}"
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Series {r.SeriesNumber}: {r.instanceCount} slices -> {dest}", flush=True)
        c.download_from_selection(seriesInstanceUID=[r.SeriesInstanceUID], downloadDir=str(dest), dirTemplate=None,
                                  quiet=True, show_progress_bar=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="what", required=True)
    p = sub.add_parser("photos", help="colour cryosection photos, a slice range")
    p.add_argument("dest")
    p.add_argument("--patient", default="VHP-M", choices=["VHP-M", "VHP-F"])
    p.add_argument("--first", type=int, required=True)
    p.add_argument("--last", type=int, required=True)
    p.set_defaults(run=photos)
    q = sub.add_parser("ct", help="all CT series of one study")
    q.add_argument("dest")
    q.add_argument("--patient", default="VHP-M", choices=["VHP-M", "VHP-F"])
    q.add_argument("--study", default="Frozen", help="StudyDescription: Frozen (male) or Normal (fresh)")
    q.set_defaults(run=ct)
    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
