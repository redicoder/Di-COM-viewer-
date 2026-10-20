"""
Command-line conversion, used by the viewer's "Open scan" button (same pipeline as dicom_converter_app.py).

    .venv\\Scripts\\python.exe -u tools\\convert_cli.py <zip | folder | .nrrd> [--quality standard|high|ultra|fast]
        [--organs] [--lungs auto|yes|no] [--keep-table] [--name NAME]

Prints progress lines; the last line is "RESULT <folder>" on success. Writes out\\latest.txt like the window
does, so the viewer loads the result with VolumeLoader.LoadLatestAsync().
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dicom_converter_app as app  # noqa: E402

QUALITY = {
    "standard": "Standard (recommended)",
    "high": "High detail (needs more RAM)",
    "ultra": "Ultra (finest; 8 GB GPU, close other apps)",
    "fast": "Fast (smoothest on the 3D display)",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--quality", choices=list(QUALITY), default="standard")
    ap.add_argument("--organs", action="store_true", help="AI organ labels (TotalSegmentator)")
    ap.add_argument("--lungs", choices=("auto", "yes", "no"), default="auto", help="auto = only for chest CT")
    ap.add_argument("--keep-table", action="store_true")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    def log(line: str) -> None:
        # The real stdout: app.analyse() temporarily redirects sys.stdout into this same log.
        sys.__stdout__.write(line + "\n")
        sys.__stdout__.flush()
    handler = logging.Handler()
    handler.emit = lambda rec: log(rec.getMessage())
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    try:
        src = Path(args.source)
        folder = app.prepare_source(src, log)
        series = app.analyse(folder, log)
        s = series[0]
        if len(series) > 1:
            log(f"{len(series)} series found; using the largest ({s['n']} slices)")
        lungs = args.lungs == "yes" or (args.lungs == "auto" and app.looks_like_chest(s))
        name = app.safe_name(args.name or (src.stem if src.is_file() else src.name))
        outputs = app.convert(folder, s, name, app.QUALITY[QUALITY[args.quality]], lungs, log,
                              table=not args.keep_table, organs=args.organs)
        log(f"RESULT {outputs[0]}")
        return 0
    except Exception as e:
        log(traceback.format_exc().rstrip())
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
