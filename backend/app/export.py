"""
Export a DICOM series to volume.raw + volume.json (same layout the /raw endpoint serves).
Lets Unity work proceed from a file without the server running.

    python -m app.export data/phantom_ct out/phantom --spacing 1.0 --max-dim 512
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .body import remove_table
from .dicom_loader import Volume, load_series
from .lungs import lungs_only
from .nrrd_loader import is_nrrd, load_nrrd
from .volume import pack_for_unity, resample


def load_any(source: str | Path, series_uid: str | None = None) -> Volume:
    """A DICOM folder, or a single .nrrd/.nhdr volume file."""
    return load_nrrd(source) if is_nrrd(source) else load_series(source, series_uid)


def write_export(vol: Volume, out_dir: str | Path, lungs: bool = False) -> dict:
    """Write volume.raw + volume.json for Unity; returns the metadata."""
    raw, meta = pack_for_unity(vol)
    meta["lungs_only"] = lungs
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "volume.raw").write_bytes(raw)
    (out / "volume.json").write_text(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("series_folder", help="DICOM folder, or a .nrrd/.nhdr file")
    ap.add_argument("out_dir")
    ap.add_argument("--series-uid", default=None)
    ap.add_argument("--spacing", type=float, default=None, help="isotropic target spacing in mm")
    ap.add_argument("--max-dim", type=int, default=512)
    ap.add_argument("--lungs-only", action="store_true",
                    help="keep only lungs + airways (chest CT), everything else becomes air")
    ap.add_argument("--remove-table", action="store_true",
                    help="keep only the patient: scanner table, mattress and cushions become air (CT)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    vol = resample(load_any(args.series_folder, args.series_uid), args.spacing, args.max_dim)
    if args.remove_table:
        vol = remove_table(vol)
    if args.lungs_only:
        vol = lungs_only(vol)
    meta = write_export(vol, args.out_dir, args.lungs_only)
    out = Path(args.out_dir)
    print(f"Wrote {out/'volume.raw'} ({meta['byte_length']/1e6:.1f} MB) dims={meta['dim_x']}x{meta['dim_y']}x{meta['dim_z']}")
    for w in meta["warnings"]:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
