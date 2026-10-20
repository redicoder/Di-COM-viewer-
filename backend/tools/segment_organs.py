"""
AI organ labels for an exported volume, using TotalSegmentator (Apache-2.0, runs on the CPU).

Runs in the separate .venv-seg environment (PyTorch + TotalSegmentator):

    .venv-seg\\Scripts\\python.exe tools\\segment_organs.py out\\<name> [--full]

Reads out\\<name>\\volume.raw + volume.json, segments it, merges TotalSegmentator's ~117 classes into the
organ groups below and writes, next to the volume:
    labels.raw   uint8, same grid and byte order as volume.raw, 0 = no organ
    labels.json  {"labels": [{"id", "name", "color": [r, g, b], "opacity", "visible"}]}
Unity's VolumeLoader picks these up and offers the Organs preset. Bones and muscles are left out on purpose:
the skeleton comes from the CT values themselves.

With an NVIDIA GPU (CUDA PyTorch) the full 1.5 mm models run by default: much finer organs (pancreas,
adrenals, vessels). Without one, the 3 mm --fast model runs on the CPU in a few minutes. --fast / --full
override the choice. Big volumes are segmented in three overlapping parts to stay within RAM.
Organ boundaries are smoothed before saving so surfaces render without voxel staircases.
The first run of each model downloads its weights into %USERPROFILE%\\.totalsegmentator.

--raw (used by tools/build_body.py) writes TotalSegmentator's own classes instead, unsmoothed:
    ts_labels.raw   uint8 class ids, same grid and byte order as volume.raw
    ts_labels.json  {"classes": {id: name}, model, versions}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.segmentation import smooth_labels  # noqa: E402

# (display name, RGB, relative opacity, TotalSegmentator class-name fragments). Order = label id order.
GROUPS = [
    ("Heart", (0.85, 0.10, 0.12), 1.0, ("heart", "atrial_appendage")),
    ("Arteries", (1.00, 0.30, 0.22), 1.0, ("aorta", "brachiocephalic_trunk", "subclavian_artery",
                                          "common_carotid_artery", "iliac_artery", "pulmonary_artery")),
    ("Veins", (0.25, 0.40, 0.95), 1.0, ("vena_cava", "brachiocephalic_vein", "portal_vein", "iliac_vena",
                                       "pulmonary_vein")),
    ("Lungs", (0.70, 0.82, 1.00), 0.25, ("lung_",)),
    ("Airways", (0.55, 0.80, 0.95), 0.8, ("trachea",)),
    ("Esophagus", (0.90, 0.55, 0.50), 1.0, ("esophagus",)),
    ("Liver", (0.60, 0.22, 0.12), 1.0, ("liver",)),
    ("Gallbladder", (0.30, 0.70, 0.25), 1.0, ("gallbladder",)),
    ("Stomach", (0.98, 0.62, 0.40), 1.0, ("stomach",)),
    ("Pancreas", (1.00, 0.85, 0.30), 1.0, ("pancreas",)),
    ("Spleen", (0.55, 0.15, 0.40), 1.0, ("spleen",)),
    ("Kidneys", (0.80, 0.38, 0.20), 1.0, ("kidney",)),
    ("Adrenal glands", (1.00, 0.55, 0.00), 1.0, ("adrenal",)),
    ("Small bowel", (0.95, 0.72, 0.62), 0.8, ("small_bowel", "duodenum")),
    ("Colon", (0.78, 0.55, 0.32), 0.8, ("colon",)),
    ("Bladder", (0.95, 0.88, 0.30), 1.0, ("urinary_bladder",)),
    ("Prostate", (0.60, 0.40, 0.75), 1.0, ("prostate",)),
    ("Thyroid", (0.35, 0.75, 0.60), 1.0, ("thyroid",)),
    ("Brain", (0.95, 0.75, 0.78), 0.6, ("brain",)),
    ("Spinal cord", (1.00, 0.95, 0.55), 1.0, ("spinal_cord",)),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", help="folder with volume.raw + volume.json from app.export / the converter")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="1.5 mm models (default with a CUDA GPU)")
    mode.add_argument("--fast", action="store_true", help="3 mm model (default on the CPU)")
    ap.add_argument("--no-smooth", action="store_true", help="keep the raw, voxel-stepped organ boundaries")
    ap.add_argument("--raw", action="store_true",
                    help="write TotalSegmentator's own classes (ts_labels.raw/json, unsmoothed) for build_body.py "
                         "instead of the organ groups")
    args = ap.parse_args()

    import nibabel as nib
    import torch
    from totalsegmentator.map_to_binary import class_map
    from totalsegmentator.python_api import totalsegmentator

    gpu = torch.cuda.is_available()
    fast = args.fast or (not args.full and not gpu)

    out = Path(args.out_dir)
    meta = json.loads((out / "volume.json").read_text())
    if not meta.get("is_hu"):
        sys.exit("Organ labels need a CT volume (Hounsfield units)")
    if meta.get("lungs_only"):
        sys.exit("This is a lungs-only export; run on the full volume instead")

    # Unity layout (z=posterior, y=superior, x=patient left) -> NIfTI voxel axes (left, posterior, superior)
    # with a RAS affine: +left is -x, +posterior is -y in RAS.
    u = np.fromfile(out / "volume.raw", dtype="<i2").reshape(meta["dim_z"], meta["dim_y"], meta["dim_x"])
    lps = np.transpose(u, (2, 0, 1))
    s_left, s_sup, s_post = meta["spacing_mm"]
    img = nib.Nifti1Image(np.ascontiguousarray(lps), np.diag([-s_left, -s_post, s_sup, 1.0]))

    # Voxels at the model's own resolution decide whether to split (whole-body CT at 1.5 mm: ~90 M).
    model_mm = 3.0 if fast else 1.5
    model_voxels = np.prod([n * s / model_mm for n, s in zip(lps.shape, (s_left, s_post, s_sup))])
    split = model_voxels > 25e6
    device = "gpu" if gpu else "cpu"
    print(f"Segmenting {lps.shape} voxels with TotalSegmentator ({'fast 3 mm' if fast else 'full 1.5 mm'} model, "
          f"{torch.cuda.get_device_name(0) if gpu else 'CPU'}{', in 3 parts' if split else ''}) ...", flush=True)
    t0 = time.time()
    seg = totalsegmentator(img, None, ml=True, fast=fast, device=device, force_split=split, quiet=False)
    labels = np.asarray(seg.dataobj).astype(np.int32)
    if labels.shape != lps.shape:
        sys.exit(f"Segmentation grid {labels.shape} does not match the volume {lps.shape}")
    seconds = time.time() - t0
    print(f"Segmentation done in {seconds:.0f} s", flush=True)

    names = class_map["total"]
    if args.raw:
        if labels.max() > 255:
            sys.exit("More than 255 classes")
        np.ascontiguousarray(np.transpose(labels.astype(np.uint8), (1, 2, 0))).tofile(out / "ts_labels.raw")
        from importlib.metadata import version
        (out / "ts_labels.json").write_text(json.dumps({
            "task": "total", "model": "fast 3 mm" if fast else "full 1.5 mm", "seconds": round(seconds),
            "totalsegmentator": version("TotalSegmentator"), "torch": torch.__version__,
            "device": torch.cuda.get_device_name(0) if gpu else "CPU",
            "classes": {str(i): n for i, n in names.items()}}, indent=2))
        print(f"Wrote {out / 'ts_labels.raw'} and ts_labels.json ({len(np.unique(labels)) - 1} classes found)", flush=True)
        return
    grouped = np.zeros(lps.shape, dtype=np.uint8)
    entries = []
    for name, rgb, opacity, fragments in GROUPS:
        ids = [i for i, n in names.items() if any(f in n for f in fragments)]
        mask = np.isin(labels, ids) & (grouped == 0)
        voxels = int(mask.sum())
        if voxels == 0:
            continue
        grouped[mask] = len(entries) + 1
        entries.append({"id": len(entries) + 1, "name": name, "color": list(rgb), "opacity": opacity, "visible": True})
        ml = voxels * s_left * s_sup * s_post / 1000.0
        print(f"  {name:15s} {ml:8.0f} mL", flush=True)
    if not entries:
        sys.exit("No organs found")
    if not args.no_smooth:
        grouped = smooth_labels(grouped)

    np.ascontiguousarray(np.transpose(grouped, (1, 2, 0))).tofile(out / "labels.raw")   # back to Unity layout
    (out / "labels.json").write_text(json.dumps({"labels": entries}, indent=2))
    print(f"Wrote {out / 'labels.raw'} and labels.json ({len(entries)} organ groups)", flush=True)


if __name__ == "__main__":
    main()
