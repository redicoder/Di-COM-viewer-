"""
Build a dissection body: one CT -> a whole-body export plus region exports, each with layered anatomy labels.

    .venv\\Scripts\\python.exe tools\\build_body.py data\\visible_human_female.nrrd --dataset vhp-female

writes out\\<name>\\
    whole_body\\                       2 mm
    head\\ thorax\\ abdomen\\ pelvis\\    about 1 mm, at most 40 M voxels each
        volume.raw / volume.json      the CT for the viewer (as the converter writes it)
        labels.raw / labels.json      structure per voxel: layers, names (la / en / it), colours
        provenance.json               source, licence, credit, grid, thresholds, tool versions, git commit
    _cache\\seg\\                      1.5 mm whole-body CT + TotalSegmentator classes (reused on re-runs)
and lists the exports in out\\latest.txt (whole body first; N in the viewer cycles them).

Steps
  1. Load (DICOM folder, NRRD or anything app.export.load_any reads) and find the body's bounding box.
  2. TotalSegmentator `total` once, on a 1.5 mm grid over the whole body (its native resolution), in .venv-seg.
     Cached: re-runs with the same source skip it. Regions take their labels from this one run, so every export
     agrees and no organ is cut in half by a region's edge before it is recognised.
  3. Per export: resample the CT onto the export grid; the patient is every connected piece that overlaps the
     whole-body mask (the table and loose objects become air); labels are mapped by position in millimetres and
     smoothed; tissue classes from HU fill everything TotalSegmentator does not name (app.tissue); ids come from
     the stable table (app.label_table).
--roi x0,y0,z0,x1,y1,z1 exports one box (mm from the scan's corner: x towards the patient's left, y towards the
back, z towards the head) instead of the four regions. --no-ai skips step 2 (tissue classes only; tests, CI).

Only licensed or public bodies: name the dataset (--dataset) or give its licence (--licence); see LICENSES.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import ndimage

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.body import body_box, body_mask                                    # noqa: E402
from app.dicom_loader import Volume                                         # noqa: E402
from app.export import load_any, write_export                               # noqa: E402
from app.label_table import BY_KEY, LABELS, labels_json, load_names         # noqa: E402
from app.segmentation import Grid, drop_fragments, sample, smooth_labels    # noqa: E402
from app.tissue import LIVING, Thresholds, tissue_classes                   # noqa: E402

OUT = BACKEND / "out"
SEG_PYTHON = BACKEND / ".venv-seg" / "Scripts" / "python.exe"
SEG_SCRIPT = BACKEND / "tools" / "segment_organs.py"
SEG_SPACING = 1.5
BODY_HU = -500.0
AIR_HU = -1024

_NLM = {
    "licence": "National Library of Medicine Terms and Conditions; May 21, 2019",
    "credit": "Courtesy of the U.S. National Library of Medicine",
    "notice": "NLM does not endorse this product. The data may not reflect the most current or accurate data "
              "available from NLM.",
    "source": "NLM Visible Human Project, via NCI Imaging Data Commons (collection nlm_visible_human_project)",
    "doi": "10.5281/zenodo.12690049",
}
DATASETS = {
    "vhp-female": {"title": "Visible Human female, CT", **_NLM,
                   "series": "VHP-F, study Normal (fresh cadaver), 1 mm, two parts stitched by "
                             "tools/prepare_visible_human.py"},
    "vhp-male-frozen": {"title": "Visible Human male, frozen CT", **_NLM,
                        "series": "VHP-M, study Frozen, 1 mm, three parts stitched by tools/prepare_visible_human.py"},
}

REGIONS = {
    "whole_body": {"la": "Corpus humanum", "en": "Whole body", "it": "Corpo intero"},
    "head": {"la": "Caput et collum", "en": "Head and neck", "it": "Testa e collo"},
    "thorax": {"la": "Thorax", "en": "Thorax", "it": "Torace"},
    "abdomen": {"la": "Abdomen", "en": "Abdomen", "it": "Addome"},
    "pelvis": {"la": "Pelvis", "en": "Pelvis", "it": "Pelvi"},
    "roi": {"la": "Regio", "en": "Region", "it": "Regione"},
}


def log(msg: str) -> None:
    print(msg, flush=True)


def fit_spacing(size_mm: np.ndarray, spacing: float, budget: float) -> float:
    """The finest spacing >= `spacing` (0.05 mm steps) whose grid has at most `budget` voxels."""
    spacing = max(spacing, float(np.ceil((np.prod(size_mm) / budget) ** (1 / 3) * 20 - 1e-6) / 20))
    while np.prod(np.ceil(size_mm / spacing - 1e-6)) > budget:
        spacing += 0.05
    return round(spacing, 2)


# --------------------------------------------------------------------------- step 2: segmentation (cached)

class Segmentation:
    """The whole-body 1.5 mm grid: body mask and stable label ids (0 everywhere with --no-ai)."""

    def __init__(self, grid: Grid, body: np.ndarray, labels: np.ndarray, info: dict):
        self.grid, self.body, self.labels, self.info = grid, body, labels, info
        # Seed for each export's patient mask: one voxel in from the edge, so nothing that merely touches the
        # body's blocky 1.5 mm outline (table, cushions) is taken for the patient.
        self.seed = ndimage.binary_erosion(body).astype(np.uint8)


def to_unity(a: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(np.transpose(a, (1, 0, 2)))     # (z, y, x) <-> Unity's (posterior, superior, left)


def segment(src: Volume, src_sp: np.ndarray, lo: np.ndarray, hi: np.ndarray, cache: Path, source: Path,
            ai: bool, force: bool) -> Segmentation:
    grid = Grid.covering(lo, hi, SEG_SPACING)
    stamp = {"source": str(source.resolve()), "bytes": source.stat().st_size if source.is_file() else None,
             "mtime": source.stat().st_mtime, "grid": grid.to_json(), "body_hu": BODY_HU}
    stamp_file = cache / "stamp.json"
    cached = not force and stamp_file.exists() and json.loads(stamp_file.read_text()) == stamp \
        and (cache / "body.npy").exists()
    if cached:
        body = np.load(cache / "body.npy")
        log(f"Step 1/2 cached: whole-body grid {grid.shape} at {SEG_SPACING} mm")
    else:
        t0 = time.time()
        hu = np.rint(sample(src.data, (0, 0, 0), src_sp, grid, order=1, output=np.float32)).astype(np.int16)
        body = body_mask(hu, BODY_HU)
        hu[~body] = AIR_HU
        cache.mkdir(parents=True, exist_ok=True)
        for f in ("ts_labels.raw", "ts_labels.json"):
            (cache / f).unlink(missing_ok=True)
        write_export(_volume(src, hu, grid), cache)
        np.save(cache / "body.npy", body)
        stamp_file.write_text(json.dumps(stamp, indent=2))
        log(f"Step 1: whole-body grid {grid.shape} at {SEG_SPACING} mm ({time.time() - t0:.0f} s)")
        del hu

    labels = np.zeros(grid.shape, dtype=np.uint8)
    info: dict = {"ai": False}
    if ai:
        if not (cache / "ts_labels.raw").exists():
            if not SEG_PYTHON.exists():
                sys.exit("The AI environment (.venv-seg) is not installed; use --no-ai for tissue classes only")
            log("Step 2: TotalSegmentator `total` on the whole body (several minutes on a GPU) ...")
            proc = subprocess.Popen([str(SEG_PYTHON), "-u", str(SEG_SCRIPT), str(cache), "--raw"], cwd=BACKEND,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            for line in proc.stdout:
                if line.strip() and "%|" not in line:
                    log("  " + line.rstrip())
            if proc.wait() != 0:
                sys.exit(f"TotalSegmentator failed (exit code {proc.returncode})")
        else:
            log("Step 2 cached: TotalSegmentator classes")
        info = json.loads((cache / "ts_labels.json").read_text())
        ts = np.fromfile(cache / "ts_labels.raw", dtype=np.uint8).reshape(grid.shape[1], grid.shape[0], grid.shape[2])
        lut = np.zeros(256, dtype=np.uint8)
        for k, name in info["classes"].items():
            if name in BY_KEY:
                lut[int(k)] = BY_KEY[name].id
            else:
                log(f"  WARNING: TotalSegmentator class '{name}' is not in app/label_table.py; left unlabelled")
        labels = lut[to_unity(ts)]
        labels[~body] = 0
        labels, stray = drop_fragments(labels)
        log(f"  {stray} stray voxels removed (pieces of a structure far from the structure itself)")
        info = {"ai": True, **{k: v for k, v in info.items() if k != "classes"}, "stray_voxels_removed": stray}
    return Segmentation(grid, body, labels, info)


def _volume(src: Volume, hu: np.ndarray, grid: Grid, warnings: list[str] | None = None) -> Volume:
    s = grid.spacing_mm
    sx, sy, sz = src.spacing
    first_centre = np.asarray(grid.corner_mm) + 0.5 * s - 0.5 * np.array([sz, sy, sx])   # (z, y, x) from voxel 0
    origin = tuple(float(o + d) for o, d in zip(src.origin, first_centre[::-1]))
    return replace(src, data=hu, spacing=(s, s, s), origin=origin, value_range=(int(hu.min()), int(hu.max())),
                   warnings=list(warnings or []))


# --------------------------------------------------------------------------- regions from the labels

def label_z_range(seg: Segmentation, keys: list[str], trim: float = 0.005) -> tuple[float, float] | None:
    """Height range (mm) of the given structures, ignoring the outermost `trim` of their voxels at each end."""
    ids = [BY_KEY[k].id for k in keys]
    per_plane = np.isin(seg.labels, ids).sum(axis=(1, 2))
    total = per_plane.sum()
    if total == 0:
        return None
    cum = np.cumsum(per_plane) / total
    k0, k1 = int(np.searchsorted(cum, trim)), int(np.searchsorted(cum, 1 - trim))
    z0, s = seg.grid.corner_mm[0], seg.grid.spacing_mm
    return z0 + k0 * s, z0 + (k1 + 1) * s


def regions(seg: Segmentation, extent: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """z ranges from landmarks, x / y from the body inside that range. Missing landmarks skip the region."""
    lungs = [k for k in BY_KEY if k.startswith("lung_")]
    z = {
        "head": (label_z_range(seg, ["vertebrae_C4"]), None),
        "thorax": (label_z_range(seg, lungs), label_z_range(seg, lungs + ["clavicula_left", "clavicula_right"])),
        "abdomen": (label_z_range(seg, ["vertebrae_L5"]), label_z_range(seg, ["liver", "spleen"])),
        "pelvis": (label_z_range(seg, ["hip_left", "hip_right"]),) * 2,
    }
    body_top = seg.grid.corner_mm[0] + (np.nonzero(seg.body.any(axis=(1, 2)))[0][-1] + 1) * seg.grid.spacing_mm
    bounds = {}
    if z["head"][0]:
        bounds["head"] = (z["head"][0][0], body_top + 6)
    if z["thorax"][0]:
        bounds["thorax"] = (z["thorax"][0][0] - 15, z["thorax"][1][1] + 15)
    if z["abdomen"][0] and z["abdomen"][1]:
        bounds["abdomen"] = (z["abdomen"][0][0] - 10, z["abdomen"][1][1] + 15)
    if z["pelvis"][0]:
        bounds["pelvis"] = (z["pelvis"][0][0] - 40, z["pelvis"][0][1] + 15)

    out = {}
    s, (cz, cy, cx) = seg.grid.spacing_mm, seg.grid.corner_mm
    for name, (z0, z1) in bounds.items():
        k0 = max(0, int(np.floor((z0 - cz) / s)))
        k1 = min(seg.grid.shape[0], int(np.ceil((z1 - cz) / s)))
        sub = seg.body[k0:k1]
        ys = np.nonzero(sub.any(axis=(0, 2)))[0]
        xs = np.nonzero(sub.any(axis=(0, 1)))[0]
        lo = np.array([z0, cy + ys[0] * s - 6, cx + xs[0] * s - 6])
        hi = np.array([z1, cy + (ys[-1] + 1) * s + 6, cx + (xs[-1] + 1) * s + 6])
        out[name] = (np.clip(lo, 0, extent), np.clip(hi, 0, extent))
    return out


# --------------------------------------------------------------------------- step 3: one export

def build_export(name: str, lo: np.ndarray, hi: np.ndarray, spacing: float, budget: float, src: Volume,
                 src_sp: np.ndarray, seg: Segmentation, th: Thresholds, out_dir: Path, prov: dict) -> Path:
    t0 = time.time()
    spacing = fit_spacing(hi - lo, spacing, budget)
    grid = Grid.covering(lo, hi, spacing)
    log(f"{name}: {grid.shape[2]}x{grid.shape[1]}x{grid.shape[0]} voxels at {spacing} mm "
        f"({np.prod(grid.shape) / 1e6:.0f} M)")

    hu = np.rint(sample(src.data, (0, 0, 0), src_sp, grid, order=1, output=np.float32)).astype(np.int16)
    seg_sp = (seg.grid.spacing_mm,) * 3
    seed = sample(seg.seed, seg.grid.corner_mm, seg_sp, grid, order=0) > 0
    body = body_mask(hu, BODY_HU, seed=seed)
    del seed
    hu[~body] = AIR_HU

    labels = sample(seg.labels, seg.grid.corner_mm, seg_sp, grid, order=0)
    if labels.any():
        labels = smooth_labels(labels)
    labels[~body] = 0
    tissue = tissue_classes(hu, spacing, body, labels > 0, th)
    labels = np.where(labels > 0, labels, tissue)
    del tissue, body

    d = out_dir / name
    d.mkdir(parents=True, exist_ok=True)
    title = {lang: f"{prov['dataset'].get('title', '')} - {REGIONS[name][lang]}".strip(" -") for lang in REGIONS[name]}
    vol = _volume(src, hu, grid, [f"Built by tools/build_body.py ({name})"])
    meta = write_export(vol, d, extra={"title": title, "region": name, "credit": prov["dataset"].get("credit", ""),
                                       "notice": prov["dataset"].get("notice", ""), "origin_lps_mm": list(vol.origin)})
    del vol, hu
    to_unity(labels).tofile(d / "labels.raw")
    present = set(int(i) for i in np.unique(labels)) - {0}
    lj = labels_json(present, load_names())
    lj["credit"] = prov["dataset"].get("credit", "")
    (d / "labels.json").write_text(json.dumps(lj, indent=2, ensure_ascii=False), encoding="utf-8")

    p = dict(prov)
    p.update({"export": name, "region": REGIONS[name], "created": datetime.now().isoformat(timespec="seconds"),
              "grid": {**grid.to_json(), "origin_lps_mm": meta.get("origin_lps_mm"),
                       "dims_xyz": [meta["dim_x"], meta["dim_y"], meta["dim_z"]]},
              "labels_present": len(present)})
    (d / "provenance.json").write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"  {len(present)} structures, {time.time() - t0:.0f} s -> {d}")
    return d


# --------------------------------------------------------------------------- provenance helpers

def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BACKEND, capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=BACKEND, capture_output=True, text=True).stdout
        return sha + ("-dirty" if dirty.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version
    out = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "pydicom"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            pass
    return out


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> list[Path]:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="DICOM folder or .nrrd / .nhdr")
    ap.add_argument("--name", help="output folder under out/ (default: the source's name)")
    ap.add_argument("--dataset", choices=sorted(DATASETS), help="known dataset: licence and credit filled in")
    ap.add_argument("--licence", help="licence of the source, for anything not in --dataset")
    ap.add_argument("--credit", default="", help="credit line required by the licence")
    ap.add_argument("--spacing", type=float, default=2.0, help="whole-body spacing in mm (default 2)")
    ap.add_argument("--region-spacing", type=float, default=None,
                    help="finest region spacing in mm (default: the scan's own, about 1)")
    ap.add_argument("--region-voxels", type=float, default=40e6, help="voxel budget per region (default 40 M)")
    ap.add_argument("--roi", help="x0,y0,z0,x1,y1,z1 in mm: export this box instead of the four regions")
    ap.add_argument("--no-regions", action="store_true", help="whole body only")
    ap.add_argument("--no-ai", action="store_true", help="skip TotalSegmentator: tissue classes only")
    ap.add_argument("--force", action="store_true", help="redo the cached steps")
    ap.add_argument("--fat", help="fat HU range lo,hi (default -190,-30)")
    ap.add_argument("--muscle", help="muscle HU range lo,hi (default 30,100)")
    ap.add_argument("--out-root", default=str(OUT), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if not args.dataset and not args.licence:
        sys.exit("Name the dataset (--dataset) or give its licence (--licence): only licensed or public bodies")
    dataset = dict(DATASETS[args.dataset]) if args.dataset else {"title": "", "licence": args.licence,
                                                                 "credit": args.credit}
    th = LIVING
    if args.fat:
        th = replace(th, fat=tuple(float(v) for v in args.fat.split(",")))
    if args.muscle:
        th = replace(th, muscle=tuple(float(v) for v in args.muscle.split(",")))

    source = Path(args.source)
    name = args.name or source.stem.split(".")[0]
    out_root = Path(args.out_root)
    out_dir = out_root / name

    t0 = time.time()
    log(f"Loading {source} ...")
    src = load_any(source)
    if not src.is_hu:
        sys.exit("build_body needs a CT in Hounsfield units")
    sx, sy, sz = src.spacing
    src_sp = np.array([sz, sy, sx])
    extent = np.array(src.data.shape) * src_sp
    box = body_box(src, margin_mm=6.0, threshold=BODY_HU)
    if box is None:
        sys.exit("No body found in the scan")
    lo = np.array([b.start for b in box]) * src_sp
    hi = np.array([b.stop for b in box]) * src_sp
    log(f"  {src.data.shape[2]}x{src.data.shape[1]}x{src.data.shape[0]} at {sx:.3g}x{sy:.3g}x{sz:.3g} mm; "
        f"body {hi[2] - lo[2]:.0f} x {hi[1] - lo[1]:.0f} x {hi[0] - lo[0]:.0f} mm")

    seg = segment(src, src_sp, lo, hi, out_dir / "_cache" / "seg", source, ai=not args.no_ai, force=args.force)

    prov = {
        "dataset": dataset,
        "source": {"path": source.name, "bytes": source.stat().st_size if source.is_file() else None,
                   "sha256": sha256(source), "dims_xyz": [int(n) for n in src.data.shape[::-1]],
                   "spacing_mm_xyz": [float(v) for v in src.spacing]},
        "tissue_thresholds": th.to_json(),
        "segmentation": seg.info,
        "pipeline": {"command": ["tools/build_body.py"] + (argv if argv is not None else sys.argv[1:]),
                     "git_commit": git_commit(), "label_table_size": len(LABELS)},
        "tools": versions(),
    }

    native = args.region_spacing or float(np.ceil(src_sp.max() * 20 - 1e-6) / 20)
    exports = [("whole_body", lo, hi, args.spacing, 64e6)]
    if args.roi:
        x0, y0, z0, x1, y1, z1 = (float(v) for v in args.roi.split(","))
        exports.append(("roi", np.clip([z0, y0, x0], 0, extent), np.clip([z1, y1, x1], 0, extent), native,
                        args.region_voxels))
    elif not args.no_regions:
        found = regions(seg, extent)
        for r in ("head", "thorax", "abdomen", "pelvis"):
            if r in found:
                exports.append((r, *found[r], native, args.region_voxels))
            else:
                log(f"{r}: skipped (landmarks not found{'; run with the AI' if args.no_ai else ''})")

    folders = [build_export(n, a, b, s, budget, src, src_sp, seg, th, out_dir, prov)
               for n, a, b, s, budget in exports]
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "latest.txt").write_text("\n".join(str(f) for f in folders) + "\n", encoding="utf-8")
    log(f"Done in {time.time() - t0:.0f} s; {out_root / 'latest.txt'} lists {len(folders)} exports")
    return folders


if __name__ == "__main__":
    main()
