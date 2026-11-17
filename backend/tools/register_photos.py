"""Lines the Visible Human colour photographs up with each other.

    .venv-seg\\Scripts\\python.exe tools\\register_photos.py data\\vhp_male_photos --also data\\vhp_male_head_photos

The photographs come in runs. Within a run every picture lies on the one before it; from one run to the next the
whole picture is moved sideways by whole pixels, 6 to 14 of them (2 to 4.6 mm): six times between the hips and the
head of the male. Stacked as they come, the body has a step right round it at each of those places: in the skin, in
every label fitted to the photographs, in every surface contoured from them.

What is measured: every photograph against the one before it (bottom to top), by phase correlation of the
body's own picture (how light its tissue is; the grey bar and the number card at the picture's top are left
out, they are laid by hand). The body itself changes by less than a pixel from one photograph to the next, or,
where a part slants through the stack (a foot, the top of the skull), by the same pixel or two for many
photographs running. A RUN BEGINS where one photograph lies JUMP_PX or more off what its neighbours on both
sides say (the median of the four before and the four after), while those neighbours agree with each other, AND
the picture's left half and its right half, measured apart, say the same. That last test matters: where the two
legs, or the two sides of the skull's top, move differently from one photograph to the next, the whole picture's
correlation hops between them and shows lone jumps of a millimetre that are no jump of the picture (five such were
found, at the ankles, a shin and the top of the head; each half told another story, and they are left alone).
So a jump of about a millimetre cannot be told safely by this; the six found are 5 to 13 pixels (1.7 to 4.3 mm).

What is written: `registration.json` in the photographs' folder: for every slice number the whole pixels its
picture is to be moved by (rows, columns) to lie where the first run lies (the feet's), the runs, and the
measurements themselves. `prepare_photo_volume.read_photo` moves every picture by it, so everything that reads
photographs (the exports, the SIO labels' import, the fine skin, the fine muscles) reads them lined up.
Photographs that are blank or not whole (the joints between the specimen's four blocks) cannot be measured and
are taken to lie as the run before them does: a block that was laid a little aside from the one under it is not
found by this.

An export made BEFORE the photographs were lined up need not be made again if all its photographs lie in one run
(the head's do): its voxels are those same photographs, only its place among the others is another.
`--export out\\photo_head` moves its record of where it was cropped from (photo.json) by that run's move, and with it
where the CT's slices were found to lie on it (labels.json), and leaves every voxel as it is.

Checked against an independent source: the Segmented Internal Organs' own crop of the same photographs (which its
makers aligned to the CT) steps at the same four photographs of the trunk by the same amounts
(docs/research/muscle_surface.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_photo_volume as ppv  # noqa: E402

TOP_STRIP = 210                 # rows (front to back) at the picture's top that hold the grey bar and the number card
JUMP_PX = 3.0                   # a run begins where a photograph lies this far (pixels) off what its neighbours say
QUIET_PX = 1.5                  # and those neighbours lie within this of each other's middle
PEAK = 0.04                     # the correlation's peak (0..1) under which a measurement is not believed
HALVES_PX, HALVES_SHARE = 1.5, 0.3      # the picture's two halves must each say what the whole says: within the first (pixels), or
                                # within the second as a share of the jump where that is more (a jump of 13 pixels is measured
                                # to 2 or 3 on a half of the shoulders, where the picture changes fast)
MIN_TISSUE = 8000               # pixels of tissue under which a photograph is blank


def picture(rgb: np.ndarray) -> np.ndarray | None:
    """What is compared between two photographs: the tissue's lightness (0 elsewhere), without the top strip;
    None for a blank photograph."""
    r, b = rgb[..., 0].astype(np.int16), rgb[..., 2].astype(np.int16)
    tissue = (r > b + 8) & (r > 25)                              # redder than blue (the gelatin), and not the black frame
    tissue[:TOP_STRIP] = False
    if tissue.sum() < MIN_TISSUE:
        return None
    return rgb.astype(np.float32).mean(axis=-1) * tissue


def shift_between(before: np.ndarray, after: np.ndarray, px: float = 1.0):
    """How far the second picture's content lies from the first's, by phase correlation: (rows, columns) in pixels
    times `px`, and the correlation's peak (0..1: 1 the same picture moved, near 0 no likeness)."""
    from scipy import fft
    shape = [fft.next_fast_len(int(n), real=True) for n in before.shape]
    fa, fb = fft.rfft2(before - before.mean(), s=shape), fft.rfft2(after - after.mean(), s=shape)
    cross = fb * np.conj(fa)
    corr = fft.irfft2(cross / np.maximum(np.abs(cross), 1e-9), s=shape)
    i = np.unravel_index(int(np.argmax(corr)), corr.shape)
    rows, cols = [float(x if x < n // 2 else x - n) * px for x, n in zip(i, shape)]
    return rows, cols, float(corr[i])


def measure(files: dict[int, Path], numbers: list[int], log=print) -> np.ndarray:
    """Per photograph (in the order given: bottom to top) its shift against the last whole one before it:
    (rows, columns, peak, how many photographs back that one lies); peak -1: blank, or the first."""
    out = np.zeros((len(numbers), 4))
    out[:, 2] = -1.0
    last, last_k = None, -1
    for k, number in enumerate(numbers):
        path = files.get(number)
        now = None if path is None else picture(ppv.read_photo(path, registered=False))
        if now is None:
            continue
        if last is not None:
            out[k] = (*shift_between(last, now), k - last_k)
        last, last_k = now, k
        if k % 200 == 0:
            log(f"register: photograph {number} ({k + 1}/{len(numbers)})")
    return out


def jumps(shifts: np.ndarray, jump_px: float = JUMP_PX, quiet_px: float = QUIET_PX, peak: float = PEAK) -> np.ndarray:
    """Where runs begin: per photograph the whole pixels (rows, columns) its run lies off the run before it, zero
    for all others. `shifts`: measure's result."""
    shifts = np.asarray(shifts, np.float64)
    n = len(shifts)
    believed = (shifts[:, 2] >= peak) & (shifts[:, 3] == 1)          # measured against the photograph right before it, with a clear peak
    out = np.zeros((n, 2))
    for k in range(n):
        if not believed[k]:
            continue
        near = [j for j in list(range(k - 4, k)) + list(range(k + 1, k + 5)) if 0 <= j < n and believed[j]]
        if len(near) < 4:
            continue
        middle = np.median(shifts[near, :2], axis=0)
        closest = [j for j in (k - 2, k - 1, k + 1, k + 2) if j in near]
        if len(closest) < 3 or np.abs(shifts[closest, :2] - middle).max() > quiet_px:
            continue                                                 # its neighbours do not agree: nothing can be said here
        off = shifts[k, :2] - middle
        if np.abs(off).max() >= jump_px:
            out[k] = np.where(np.abs(off) >= 2.0, np.round(off), 0.0)    # (a pixel the other way is what the neighbours differ by too)
    return out


def agree(whole, halves) -> bool:
    """Whether the picture's two halves, measured apart, both say what the whole picture's jump says: `whole` the
    jump (rows, columns), `halves` each half's own shift at that photograph less its neighbours' (None where a half
    has no body in it)."""
    whole = np.asarray(whole, np.float64)
    within = max(HALVES_PX, HALVES_SHARE * float(np.abs(whole).max()))
    return len(halves) == 2 and all(h is not None and np.abs(np.asarray(h, np.float64) - whole).max() <= within for h in halves)


def confirm(files: dict[int, Path], numbers: list[int], shifts: np.ndarray, jump: np.ndarray, log=print) -> np.ndarray:
    """Keeps of the jumps found those the picture's left and right halves both show (see the module's text): each
    half is measured at the photograph and at the one before and the one after it."""
    out = np.zeros_like(jump)
    for k in np.flatnonzero(np.abs(jump).sum(axis=1)):
        pictures = {j: picture(ppv.read_photo(files[numbers[j]], registered=False)) for j in (k - 2, k - 1, k, k + 1) if 0 <= j < len(numbers) and numbers[j] in files}
        if any(pictures.get(j) is None for j in (k - 2, k - 1, k, k + 1)):
            log(f"register: the jump at photograph {numbers[k]} cannot be checked (a blank photograph beside it): left alone")
            continue
        halves = []
        width = pictures[k].shape[1] // 2
        for part in (slice(0, width), slice(width, None)):
            if min((pictures[j][:, part] > 0).sum() for j in pictures) < MIN_TISSUE // 2:
                halves.append(None)
                continue
            before, at, after = (np.array(shift_between(pictures[a][:, part], pictures[b][:, part])[:2]) for a, b in ((k - 2, k - 1), (k - 1, k), (k, k + 1)))
            halves.append(at - (before + after) / 2.0)
        said = [None if h is None else [round(float(x), 1) for x in h] for h in halves]
        if agree(jump[k], halves):
            out[k] = jump[k]
            log(f"register: a run begins at photograph {numbers[k]} ({k} from the bottom): the picture jumps {jump[k].astype(int).tolist()} px; its halves: {said}")
        else:
            log(f"register: photograph {numbers[k]} ({k} from the bottom) looked like a jump of {jump[k].astype(int).tolist()} px, but the picture's halves say {said}: left alone")
    return out


def moves(jump: np.ndarray) -> np.ndarray:
    """Per photograph the whole pixels (rows, columns) to move its picture by, so that it lies where the first
    run lies: less the sum of the jumps up to it."""
    return (-np.cumsum(np.asarray(jump, np.float64), axis=0)).astype(int)


def runs_of(numbers: list[int], move: np.ndarray) -> list[dict]:
    out = []
    for k, number in enumerate(numbers):
        if k == 0 or (move[k] != move[k - 1]).any():
            out.append({"from_slice": int(number), "from_photograph_bottom_up": k, "move_px": [int(move[k][0]), int(move[k][1])]})
    return out


def move_export(export: Path, table: dict, log=print) -> tuple[int, int]:
    """Moves an export that was made from the photographs as they came to where they lie now: its crop's record,
    by the one move all its photographs share (an export across two runs has a step in it and must be made again:
    refused). Returns the move (rows, columns)."""
    photo_path = export / "photo.json"
    photo = json.loads(photo_path.read_text())
    if photo.get("registered"):
        raise SystemExit(f"{export} is already built on the photographs as lined up")
    top, bottom = photo["slices"]
    found = sorted({table.get(n, (0, 0)) for n in range(top, bottom + 1)})
    if len(found) != 1:
        raise SystemExit(f"{export} holds photographs of {len(found)} runs (moves {found}): it has their steps in it and must be made again with prepare_photo_volume.py")
    rows, cols = found[0]
    crop = photo["crop_photo_px"]
    photo["crop_photo_px"] = {"rows": [crop["rows"][0] + rows, crop["rows"][1] + rows], "cols": [crop["cols"][0] + cols, crop["cols"][1] + cols]}
    photo["registered"] = True
    photo["moved"] = {"by_px": [rows, cols], "crop_before": crop, "why": "made from the photographs as they came; all of them lie in one run, so only its place was moved (tools/register_photos.py --export)"}
    photo_path.write_text(json.dumps(photo, indent=2))
    labels_path = export / "labels.json"
    if labels_path.exists():
        labels = json.loads(labels_path.read_text())
        corners = (labels.get("ct_bone") or {}).get("corners_mm_by_slice")
        if corners:                                                  # where each CT image's corner fell on its photograph: row, column (mm)
            labels["ct_bone"]["corners_mm_by_slice"] = {n: [round(v[0] + rows * ppv.PIXEL_MM, 2), round(v[1] + cols * ppv.PIXEL_MM, 2)] for n, v in corners.items()}
            labels_path.write_text(json.dumps(labels, indent=2))
    log(f"register: {export} moved by {rows} rows, {cols} columns (its crop is now {photo['crop_photo_px']}); its voxels are as they were")
    return rows, cols


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("photos", type=Path, help="the folder of colour photograph DICOMs (all of them)")
    ap.add_argument("--also", type=Path, action="append", default=[], help="another folder holding some of the same photographs: given the same table")
    ap.add_argument("--first", type=int, help="top slice number (default: the lowest in the folder)")
    ap.add_argument("--last", type=int, help="bottom slice number (default: the highest)")
    ap.add_argument("--reuse", action="store_true", help="take the measurements kept in the folder's registration.json (twenty minutes saved) and only find the runs again")
    ap.add_argument("--export", type=Path, action="append", default=[], help="an export made before the photographs were lined up, all of whose photographs lie in one run: "
                                                                             "moved to its place by the folder's registration, nothing else done")
    args = ap.parse_args()
    if args.export:
        table = ppv.registration(args.photos)
        if table is None:
            raise SystemExit(f"{args.photos} has no {ppv.REGISTRATION}: measure it first (run without --export)")
        for export in args.export:
            move_export(export, table)
        return
    files = ppv.index_slices(args.photos)
    first, last = args.first or min(files), args.last or max(files)
    numbers = list(range(last, first - 1, -1))                       # bottom to top
    kept = args.photos / ppv.REGISTRATION
    if args.reuse and kept.exists():
        measured = json.loads(kept.read_text())["measured_by_slice"]
        shifts = np.array([measured[str(n)] for n in numbers], np.float64)
    else:
        shifts = measure(files, numbers)
    jump = confirm(files, numbers, shifts, jumps(shifts))
    move = moves(jump)
    runs = runs_of(numbers, move)
    blank = [int(n) for n, s in zip(numbers, shifts) if s[2] < 0][1:]
    info = {"what": "whole pixels (rows front to back, columns to the patient's left) to move each photograph's picture by, so that all lie as the first run does; "
                    "prepare_photo_volume.read_photo applies it",
            "method": "phase correlation of each photograph's tissue against the one before it; a run begins at a lone jump (tools/register_photos.py)",
            "pixel_mm": ppv.PIXEL_MM, "runs": runs, "blank_slices": blank,
            "move_px_by_slice": {str(n): [int(m[0]), int(m[1])] for n, m in zip(numbers, move)},
            "measured_by_slice": {str(n): [float(s[0]), float(s[1]), round(float(s[2]), 3), int(s[3])] for n, s in zip(numbers, shifts)}}
    for folder in [args.photos] + args.also:
        (folder / ppv.REGISTRATION).write_text(json.dumps(info))
        print(f"register: wrote {folder / ppv.REGISTRATION}")
    print(f"register: {len(runs)} runs; they begin at (slice number, photograph from the bottom, move in pixels): "
          + "; ".join(f"{r['from_slice']} ({r['from_photograph_bottom_up']}): {r['move_px']}" for r in runs))
    odd = [(int(n), [int(s[0]), int(s[1])], round(float(s[2]), 2)) for n, s, j in zip(numbers, shifts, jump)
           if s[2] >= 0 and np.abs(s[:2]).max() >= JUMP_PX and not j.any()]
    print(f"register: {len(blank)} photographs blank; {len(odd)} lie {JUMP_PX:g} px or more off the one before them without being a run's beginning "
          f"(a slanting part, or the first after a blank one): {odd[:40]}")


if __name__ == "__main__":
    main()
