"""
DICOM -> Unity converter window. Double-click "Convert DICOM for Unity.bat", or:

    .venv\\Scripts\\pythonw.exe tools\\dicom_converter_app.py

1. Choose a .zip or a folder of DICOM files. A zip is extracted to data\\<name> (non-DICOM files such as
   LICENSE go to data\\<name>_extras, so Weasis can import the folder cleanly); a folder is read in place.
2. The series in it are analysed (same checks as inspect_series.py) and the largest usable one is selected.
3. Convert writes out\\<name>\\volume.raw + volume.json, plus out\\<name>_lungs for a chest CT, and lists
   them in out\\latest.txt. Unity's VolumeLoader loads the first one on Play; N during Play cycles them.
"""
from __future__ import annotations

import contextlib
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tools"))

import pydicom  # noqa: E402

import inspect_series as insp  # noqa: E402
from app.body import crop_to_body, remove_table  # noqa: E402
from app.export import load_any, write_export  # noqa: E402
from app.lungs import lungs_only  # noqa: E402
from app.nrrd_loader import describe_nrrd, is_nrrd  # noqa: E402
from app.volume import resample  # noqa: E402

DATA, OUT = BACKEND / "data", BACKEND / "out"
LATEST = OUT / "latest.txt"
# TotalSegmentator lives in its own environment (PyTorch + many pinned packages) so it cannot break this one.
SEG_PYTHON = BACKEND / ".venv-seg" / "Scripts" / "python.exe"
SEG_SCRIPT = BACKEND / "tools" / "segment_organs.py"

# Voxel budgets. Unity keeps ~6 bytes/voxel, plus ~24 bytes/voxel while lighting gradients are computed.
QUALITY = {
    "Standard (recommended)": insp.SOFT_LIMIT_VOXELS,
    "High detail (needs more RAM)": 64_000_000,
    "Ultra (finest; 8 GB GPU, close other apps)": 100_000_000,
    "Fast (smoothest on the 3D display)": 15_000_000,
}
CHEST_WORDS = ("CHEST", "THORAX", "THOR", "LUNG", "PULM", "TORAX")


# --------------------------------------------------------------------------- pipeline (no UI)

def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_").lower()[:40] or "scan"


def unique_dir(parent: Path, name: str) -> Path:
    candidate, i = parent / name, 2
    while candidate.exists():
        candidate, i = parent / f"{name}_{i}", i + 1
    return candidate


def is_dicom(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            if f.read(132)[128:132] == b"DICM":
                return True
        # Some exports omit the 128-byte preamble; force-read and require a real DICOM tag.
        return "SOPClassUID" in pydicom.dcmread(path, stop_before_pixels=True, force=True)
    except Exception:
        return False


def prepare_source(src: Path, log) -> Path:
    """Return what to load: a DICOM folder (as is, or extracted from a zip into data\\), or an NRRD file."""
    if src.is_dir():
        log(f"Reading folder in place: {src}")
        return src
    if is_nrrd(src):
        log(f"NRRD volume file: {src}  ({src.stat().st_size / 1e6:.0f} MB)")
        return src
    if not zipfile.is_zipfile(src):
        raise ValueError(f"{src.name} is not a zip, a folder or an NRRD file (.nrrd / .nhdr)")

    target = unique_dir(DATA, safe_name(src.stem))
    log(f"Extracting {src.name} -> {target}")
    with zipfile.ZipFile(src) as zf:
        root = target.resolve()
        for member in zf.infolist():
            dest = (target / member.filename).resolve()
            if root not in dest.parents and dest != root:          # refuse "../" paths in the zip
                raise ValueError(f"Unsafe path in zip: {member.filename}")
        zf.extractall(target)

    extras = target.parent / f"{target.name}_extras"
    moved = 0
    for p in [p for p in target.rglob("*") if p.is_file()]:
        if p.name.upper() != "DICOMDIR" and not is_dicom(p):
            dest = extras / p.relative_to(target)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), dest)
            moved += 1
    if moved:
        log(f"Moved {moved} non-DICOM file(s) (licence, notes) to {extras.name}")
    return target


def analyse(folder: Path, log) -> list[dict]:
    if is_nrrd(folder):
        s = describe_nrrd(folder)
        log(f"  {s['cols']} x {s['rows']} x {s['n']} voxels, "
            f"{s['fov'][0]:.0f} x {s['fov'][1]:.0f} x {s['fov'][2]:.0f} mm, finest spacing {s['native_min_spacing']:.2f} mm")
        return [s]
    series, unreadable = insp.scan(folder)
    log(f"{len(series)} series found, {unreadable} non-image file(s) skipped")
    if not series:
        raise ValueError("No DICOM images found. Is this the right zip/folder?")
    usable = []
    for uid, items in sorted(series.items(), key=lambda kv: -len(kv[1])):
        out = _Capture(log)
        with contextlib.redirect_stdout(out):
            info = insp.describe(uid, items)
        out.flush()
        if info:
            usable.append(info)
    if not usable:
        raise ValueError("None of the series can be converted (see the reasons above).")
    return usable


def looks_like_chest(s: dict) -> bool:
    text = f"{s.get('body_part', '')} {s.get('description', '')}".upper()
    return s["modality"] == "CT" and any(w in text for w in CHEST_WORDS)


def segment_organs(out_dir: Path, log) -> bool:
    """Run tools/segment_organs.py in .venv-seg, streaming its output to the log."""
    if not SEG_PYTHON.exists():
        log("Organ labels skipped: the AI environment (.venv-seg) is not installed")
        return False
    proc = subprocess.Popen([str(SEG_PYTHON), "-u", str(SEG_SCRIPT), str(out_dir)], cwd=BACKEND,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in proc.stdout:
        line = line.rstrip()
        if line and "%|" not in line:          # skip tqdm progress-bar redraws
            log(line)
    if proc.wait() != 0:
        log(f"Organ labels failed (exit code {proc.returncode}); the volume itself is fine")
        return False
    return True


def convert(folder: Path, s: dict, name: str, voxel_limit: int, lungs: bool, log, table: bool = True,
            organs: bool = False) -> list[Path]:
    vol = load_any(folder, None if is_nrrd(folder) else s["uid"])
    if table:
        # Crop the air around the patient first, so the voxel budget goes into the body: finer spacing.
        vol = crop_to_body(vol)
        nz, ny, nx = vol.data.shape
        sx, sy, sz = vol.spacing
        s = dict(s, fov=(nx * sx, ny * sy, nz * sz))
    spacing, dims = insp.choose_spacing(s, voxel_limit)
    log(f"Converting at {spacing} mm -> {dims[0]}x{dims[1]}x{dims[2]} voxels ...")
    vol = resample(vol, spacing, max(dims))
    if table:
        log("Removing the scanner table ...")
        vol = remove_table(vol)
    for w in vol.warnings:
        log(f"Note: {w}")

    outputs = [OUT / name]
    for stale in ("labels.raw", "labels.json"):        # labels from an earlier conversion no longer match
        (outputs[0] / stale).unlink(missing_ok=True)
    meta = write_export(vol, outputs[0])
    log(f"Wrote {outputs[0]}  ({meta['byte_length'] / 1e6:.0f} MB)")
    if organs and vol.is_hu:
        log("Finding internal organs with TotalSegmentator (a few minutes on the CPU; the first run also "
            "downloads the AI model) ...")
        segment_organs(outputs[0], log)

    if lungs:
        log("Extracting the lungs ...")
        try:
            lung_dir = OUT / f"{name}_lungs"
            write_export(lungs_only(vol), lung_dir, lungs=True)
            outputs.append(lung_dir)
            log(f"Wrote {lung_dir}  (lungs only)")
        except ValueError as e:
            log(f"Lungs-only version skipped: {e}")

    LATEST.write_text("\n".join(str(p) for p in outputs) + "\n", encoding="utf-8")
    log(f"Unity will load: {outputs[0]}" + ("  (N in Play mode switches to the lungs)" if len(outputs) > 1 else ""))
    return outputs


class _Capture:
    """File-like object that forwards complete printed lines to the log."""

    def __init__(self, log):
        self.log, self.buf = log, ""

    def write(self, text):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                self.log(line)

    def flush(self):
        if self.buf.strip():
            self.log(self.buf)
        self.buf = ""


# --------------------------------------------------------------------------- window

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.folder: Path | None = None
        self.series: list[dict] = []
        self.outputs: list[Path] = []
        self.busy = False

        root.title("DICOM -> Unity converter")
        root.geometry("840x660")
        root.minsize(640, 460)
        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="DICOM -> Unity converter", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frm, text="1. Choose a scan   2. Check the settings   3. Convert, then press Play in Unity").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        pick = ttk.Frame(frm)
        pick.grid(row=2, column=0, columnspan=3, sticky="we")
        self.btn_zip = ttk.Button(pick, text="Choose file (ZIP / NRRD)...", command=self.choose_zip)
        self.btn_zip.pack(side="left")
        self.btn_dir = ttk.Button(pick, text="Choose folder...", command=self.choose_folder)
        self.btn_dir.pack(side="left", padx=6)
        self.src_label = ttk.Label(pick, text="No scan selected", foreground="#666")
        self.src_label.pack(side="left", padx=6)

        ttk.Label(frm, text="Name").grid(row=3, column=0, sticky="w", pady=(10, 2))
        self.name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.name_var).grid(row=3, column=1, columnspan=2, sticky="we", pady=(10, 2))

        ttk.Label(frm, text="Series").grid(row=4, column=0, sticky="w", pady=2)
        self.series_box = ttk.Combobox(frm, state="readonly")
        self.series_box.grid(row=4, column=1, columnspan=2, sticky="we", pady=2)
        self.series_box.bind("<<ComboboxSelected>>", lambda _: self.on_series_selected())

        ttk.Label(frm, text="Quality").grid(row=5, column=0, sticky="w", pady=2)
        self.quality_box = ttk.Combobox(frm, state="readonly", values=list(QUALITY))
        self.quality_box.current(0)
        self.quality_box.grid(row=5, column=1, columnspan=2, sticky="we", pady=2)

        self.table_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Remove the scanner table and cushions (recommended for CT)",
                        variable=self.table_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.lungs_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Also make a lungs-only version (chest CT: glass lungs with the vessel tree)",
                        variable=self.lungs_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self.organs_var = tk.BooleanVar(value=SEG_PYTHON.exists())
        ttk.Checkbutton(frm, text="Find internal organs with AI (heart, liver, stomach, pancreas ... ; a few minutes)",
                        variable=self.organs_var).grid(row=8, column=0, columnspan=3, sticky="w", pady=(0, 2))

        act = ttk.Frame(frm)
        act.grid(row=9, column=0, columnspan=3, sticky="we", pady=(10, 6))
        self.btn_convert = ttk.Button(act, text="Convert for Unity", command=self.start_convert, state="disabled")
        self.btn_convert.pack(side="left")
        self.btn_open = ttk.Button(act, text="Open output folder", command=self.open_output, state="disabled")
        self.btn_open.pack(side="left", padx=6)
        self.btn_copy = ttk.Button(act, text="Copy Unity path", command=self.copy_path, state="disabled")
        self.btn_copy.pack(side="left")
        self.progress = ttk.Progressbar(act, mode="indeterminate", length=160)
        self.progress.pack(side="right")

        self.log_box = tk.Text(frm, height=14, wrap="word", font=("Consolas", 9), state="disabled",
                               background="#111", foreground="#ddd", insertbackground="#ddd")
        self.log_box.grid(row=10, column=0, columnspan=3, sticky="nsew")
        frm.rowconfigure(10, weight=1)
        self.status = ttk.Label(frm, text="Ready.", foreground="#444")
        self.status.grid(row=11, column=0, columnspan=3, sticky="w", pady=(6, 0))

        handler = logging.Handler()
        handler.emit = lambda rec: self.log(f"{rec.levelname}: {rec.getMessage()}")
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        root.after(100, self.pump)

    # thread-safe logging: workers enqueue, the UI thread drains
    def log(self, text: str):
        self.events.put(("log", text))

    def pump(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", payload + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "analysed":
                    self.on_analysed(*payload)
                elif kind == "converted":
                    self.on_converted(payload)
                elif kind == "error":
                    self.set_busy(False, "Failed - see the log.")
                    messagebox.showerror("Conversion problem", payload)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def set_busy(self, busy: bool, status: str):
        self.busy = busy
        self.status.configure(text=status)
        for b in (self.btn_zip, self.btn_dir):
            b.configure(state="disabled" if busy else "normal")
        self.btn_convert.configure(state="disabled" if busy or not self.series else "normal")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def run(self, target, *args):
        def work():
            try:
                target(*args)
            except Exception as e:
                self.log(traceback.format_exc().rstrip())
                self.events.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()

    # --- step 1: choose + analyse
    def choose_zip(self):
        path = filedialog.askopenfilename(
            title="Choose a DICOM zip or an NRRD volume",
            filetypes=[("Scans", "*.zip *.nrrd *.nhdr"), ("ZIP archives", "*.zip"), ("NRRD volumes", "*.nrrd *.nhdr"),
                       ("All files", "*.*")])
        if path:
            self.start_analyse(Path(path))

    def choose_folder(self):
        path = filedialog.askdirectory(title="Choose a folder with DICOM files")
        if path:
            self.start_analyse(Path(path))

    def start_analyse(self, src: Path):
        self.series, self.outputs = [], []
        self.series_box.configure(values=[])
        self.series_box.set("")
        self.btn_open.configure(state="disabled")
        self.btn_copy.configure(state="disabled")
        self.src_label.configure(text=str(src))
        self.name_var.set(safe_name(src.stem if src.is_file() else src.name))
        self.log(f"\n=== {src}")
        self.set_busy(True, "Analysing ...")

        def work():
            folder = prepare_source(src, self.log)
            self.events.put(("analysed", (folder, analyse(folder, self.log))))
        self.run(work)

    def on_analysed(self, folder: Path, series: list[dict]):
        self.folder, self.series = folder, series
        labels = [f"{s['modality']}  {s['description']}  -  {s['n']} slices, "
                  f"{s['fov'][0]:.0f}x{s['fov'][1]:.0f}x{s['fov'][2]:.0f} mm" for s in series]
        self.series_box.configure(values=labels)
        self.series_box.current(0)
        self.on_series_selected()
        self.set_busy(False, "Check the settings, then click Convert for Unity.")

    def on_series_selected(self):
        s = self.series[self.series_box.current()]
        self.lungs_var.set(looks_like_chest(s))

    # --- step 2: convert
    def start_convert(self):
        name = safe_name(self.name_var.get())
        self.name_var.set(name)
        if (OUT / name).exists() and not messagebox.askyesno(
                "Replace?", f"out\\{name} already exists. Replace it with this conversion?"):
            return
        # Read every widget value here: tkinter must not be touched from the worker thread.
        folder, s = self.folder, self.series[self.series_box.current()]
        limit, lungs, table = QUALITY[self.quality_box.get()], self.lungs_var.get(), self.table_var.get()
        organs = self.organs_var.get()
        self.set_busy(True, "Converting ...")
        self.run(lambda: self.events.put(("converted", convert(folder, s, name, limit, lungs, self.log, table, organs))))

    def on_converted(self, outputs: list[Path]):
        self.outputs = outputs
        self.btn_open.configure(state="normal")
        self.btn_copy.configure(state="normal")
        self.set_busy(False, "Done. In Unity: press Play (or N if it is already playing).")
        self.log("Done.")

    def open_output(self):
        if self.outputs:
            os.startfile(self.outputs[0].parent)

    def copy_path(self):
        if self.outputs:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(self.outputs[0]))
            self.status.configure(text=f"Copied: {self.outputs[0]}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
