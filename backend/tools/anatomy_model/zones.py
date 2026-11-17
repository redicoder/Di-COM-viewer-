"""Where things are on the skin: landmarks, the regions of hair, and the skin's own colour per vertex.

There is no painted texture. The eye centres come with the export; the nose, the mouth and the chin are read from
the face's profile; the sternum, the arms' and the legs' bones come from the labels. From those, each skin vertex
gets weights 0..1 for the regions that matter to its look (lips, lids, brows, scalp, beard, areola, chest, belly
line, arms, legs, soles), and from the weights its colour, its gloss and how much hair grows there.

Sizes and colours follow docs/research/skin_features_hair_maps.md and palette.md (measured from photographs
where the report says so, typical values where it says they are from memory); they are starting values, tuned by
eye against renders. Everything is in glTF metres: x patient left, y up, z front.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage, sparse

from .common import Body

MM = 0.001

# sRGB 0..255. Skin: between a living light-skinned man's chest (palette.md: 204,168,143) and a fresh body's pallor.
SKIN_BASE = (210, 170, 150)
LIP_UPPER = (166, 116, 110)                 # living lips (palette.md: skin x 0.90, 0.57, 0.71) paled towards a dead man's
LIP_LOWER = (176, 124, 118)
AREOLA = (138, 94, 82)                      # palette.md: skin x 0.62, 0.48, 0.48 in the same photographs, paled a little
NIPPLE = (126, 84, 74)
SOLE = (214, 168, 138)
STUBBLE_TINT = (0.80, 0.82, 0.86)           # shaved hair seen through skin: the skin's colour times this
MOUTH_WIDTH = 52.0                          # mm
LIP_UP, LIP_DOWN = 6.0, 7.5                 # mm of vermilion above and below the lip line, in the midline (a dead man's lips thin)
NOSE_TO_LIPS = 22.0                         # mm from under the nose to the lip line


def smooth(x, lo, hi):
    """0 below lo, 1 above hi, smooth between (lo > hi runs the other way)."""
    t = np.clip((np.asarray(x, np.float64) - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def bone_box(body: Body, name: str):
    """(min, max) corners in glTF metres of a labelled object (or of a bone given by name in body.extra_bones), or None."""
    extra = getattr(body, "extra_bones", None)
    if extra and name in extra:
        return extra[name]
    o = body.object_named(name)
    if o is None or o["voxels"] == 0:
        return None
    box = ndimage.find_objects((body.labels == o["index"]).astype(np.uint8))[0]
    sz, sy, sx = body.spacing
    lo = np.array([box[2].start * sx - body.size_mm[0] / 2, box[1].start * sy - body.size_mm[1] / 2, -(box[0].stop * sz - body.size_mm[2] / 2)]) * MM
    hi = np.array([box[2].stop * sx - body.size_mm[0] / 2, box[1].stop * sy - body.size_mm[1] / 2, -(box[0].start * sz - body.size_mm[2] / 2)]) * MM
    return lo, hi


class Face:
    """The face's own frame (u to the patient's left, w up, d forward, millimetres from the point between the
    eyes) and what was read from the profile."""

    def __init__(self, marks: dict, v: np.ndarray):
        eyes = np.asarray(marks["eyes"], np.float64).reshape(2, 3)
        right, left = (eyes[0], eyes[1]) if eyes[0][0] < eyes[1][0] else (eyes[1], eyes[0])
        self.origin = (right + left) / 2
        self.ex = (left - right) / np.linalg.norm(left - right)
        up = np.array([0.0, 1.0, 0.0])
        self.ey = up - self.ex * (up @ self.ex)
        self.ey /= np.linalg.norm(self.ey)
        self.ez = np.cross(self.ex, self.ey)
        self.half_ipd = float(np.linalg.norm(left - right)) / 2 / MM
        self.eye_w = {"right": float((right - self.origin) @ self.ey) / MM, "left": float((left - self.origin) @ self.ey) / MM}
        u, w, d = self.local(v)
        # The profile: how far forward the skin reaches, millimetre by millimetre down the midline.
        strip = (np.abs(u) < 4.0) & (w > -140) & (w < 40) & (d > 0)
        ws = np.arange(-140, 40)
        profile = np.full(len(ws), np.nan)
        rows = np.round(w[strip]).astype(int) + 140
        for k in np.unique(rows[(rows >= 0) & (rows < len(ws))]):
            profile[k] = d[strip][rows == k].max()
        good = ~np.isnan(profile)
        profile = np.interp(ws, ws[good], profile[good]) if good.sum() > 10 else np.zeros(len(ws))
        profile = ndimage.gaussian_filter1d(profile, 1.5)
        self.profile_w, self.profile_d = ws, profile
        nose = (ws > -65) & (ws < -12)
        tip = int(np.argmax(np.where(nose, profile, -1e9)))
        self.nose_tip_w, self.nose_tip_d = float(ws[tip]), float(profile[tip])
        below = np.nonzero((ws < ws[tip]) & (profile < profile[tip] - 8.0))[0]
        self.subnasale_w = float(ws[below.max()]) if len(below) else self.nose_tip_w - 12.0
        guess = self.subnasale_w - NOSE_TO_LIPS
        near = (ws > guess - 6) & (ws < guess + 6)
        # The lip line is the furrow between the lips, if the profile shows one near where it should be.
        self.stomion_w = float(ws[near][np.argmin(profile[near])]) if near.any() else guess
        self.chin_w = self.stomion_w - 34.0

    def local(self, v: np.ndarray):
        p = (np.asarray(v, np.float64) - self.origin) / MM
        return p @ self.ex, p @ self.ey, p @ self.ez

    def lid_line(self, v: np.ndarray, side: str) -> float | None:
        """Where the closed lids meet, millimetres above the eyes' level: the furrow across the eye's bulge, read
        from the skin's own relief (the deepest dip of the surface against its smoothed self)."""
        u, w, d = self.local(v)
        ue = (-1.0 if side == "right" else 1.0) * self.half_ipd
        we = self.eye_w[side]
        near = (np.abs(u - ue) < 9.0) & (w > we - 13.0) & (w < we + 9.0) & (d > 0)
        if near.sum() < 200:
            return None
        ws = np.arange(we - 13.0, we + 9.0, 0.5)
        wanted = (ws > we - 9.5) & (ws < we - 2.0)          # the lids meet below the middle of the globe; the crease under the eye lies lower
        rows = np.clip(((w[near] - ws[0]) / 0.5).astype(int), 0, len(ws) - 1)
        depth = np.full(len(ws), np.nan)
        for k in np.unique(rows):
            depth[k] = np.median(d[near][rows == k])
        good = ~np.isnan(depth)
        if good.sum() < len(ws) // 2:
            return None
        depth = np.interp(ws, ws[good], depth[good])
        dip = ndimage.gaussian_filter1d(depth, 1.0) - ndimage.gaussian_filter1d(depth, 7.0)
        # Of the furrows in that stretch, the lids' line is the deep one; among furrows about as deep (within a fifth
        # of the deepest), the one nearest to where lids meet on a globe (about 5 mm below its middle). (Nearest alone
        # took a shallow crease 2.5 mm over the right eye's lid line, a fifth as deep, when the skin's outline was
        # read again: -4.0 for the right eye and -6.5 for the left.)
        furrows = [k for k in range(1, len(ws) - 1) if wanted[k] and dip[k] < -0.04 and dip[k] <= dip[k - 1] and dip[k] <= dip[k + 1]]
        self.furrows = getattr(self, "furrows", {})
        self.furrows[side] = [(round(float(ws[k] - we), 1), round(float(dip[k]), 2)) for k in furrows]
        k = deepest_furrow([(float(ws[k] - we), float(dip[k])) for k in furrows])
        return None if k is None else float(ws[furrows[k]])

    def describe(self) -> str:
        return (f"face: eyes {2 * self.half_ipd:.0f} mm apart, nose tip {self.nose_tip_w:.0f} mm below them and {self.nose_tip_d:.0f} forward, "
                f"under the nose at {self.subnasale_w:.0f}, lip line at {self.stomion_w:.0f}")


def spread(values: np.ndarray, known: np.ndarray, f: np.ndarray, rounds: int = 40, smooth_rounds: int = 8) -> np.ndarray:
    """Fills the vertices that have no value from their neighbours over the mesh (outwards from the known ones),
    then smooths everything a little. values (k, c), known bool (k,)."""
    k = len(values)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    adj = sparse.coo_matrix((np.ones(len(i), np.float32), (i, j)), shape=(k, k)).tocsr()
    adj.data[:] = 1.0
    out = np.where(known[:, None], values, 0.0).astype(np.float64)
    have = known.astype(np.float64)
    for _ in range(rounds):
        total, count = adj @ out, adj @ have
        fill = (have == 0) & (count > 0)
        if not fill.any():
            break
        out[fill] = total[fill] / count[fill][:, None]
        have[fill] = 1.0
    out[have == 0] = 1.0
    degree = np.maximum(np.asarray(adj.sum(axis=1)).ravel(), 1.0)
    for _ in range(smooth_rounds):
        out = 0.5 * out + 0.5 * (adj @ out) / degree[:, None]
    return out


def deepest_furrow(furrows: list, about: float = -5.0, as_deep: float = 0.8) -> int | None:
    """Which of the furrows (each: mm above the eye's level, depth as a negative number) is the closed lids' line:
    the deepest, or among those at least `as_deep` times as deep the one nearest `about`. None for none."""
    if not furrows:
        return None
    most = min(d for _, d in furrows)
    deep = [k for k, (_, d) in enumerate(furrows) if d <= as_deep * most]
    return min(deep, key=lambda k: abs(furrows[k][0] - about))


def measure_globes(body: Body, name: str = "head") -> list[dict] | None:
    """The eyeballs measured in a region export's photographs: the dark glassy body of each eye, found round the
    centre the export recorded, gives the globe's height (its radius) and its centre across, up and in depth (from
    its back wall; its front is the lens and the cornea, which are not dark). Returns, per eye of body.meta["eyes"],
    {"centre_m": body metres (x left, y up, z back), "radius_m"}; None when the region is missing."""
    entry = next((r for r in body.meta.get("regions", []) if r.get("name") == name), None)
    eyes = body.meta.get("eyes") or []
    if entry is None or not eyes:
        return None
    folder = body.export.parent / entry["folder"]
    if not (folder / "body.raw").exists():
        return None
    meta = json.loads((folder / "body.json").read_text())
    dx, dy, dz = meta["dims"]
    sx, sy, sz = meta["spacing_mm"]
    rgba = np.fromfile(folder / "body.raw", np.uint8).reshape(dz, dy, dx, 4)
    centre, size = np.array(entry["centre_m"], np.float64), np.array(entry["size_m"], np.float64)
    out = []
    for e in eyes:
        local = (np.array(e["centre_m"]) - centre) / size + 0.5
        ix, iy, iz = (local * np.array([dx, dy, dz])).astype(int)
        rx, ry, rz = int(17 / sx), int(17 / sy), int(17 / sz)
        box = (slice(max(0, iz - rz), iz + rz), slice(max(0, iy - ry), iy + ry), slice(max(0, ix - rx), ix + rx))
        block = rgba[box].astype(np.int16)
        brightest = block[..., :3].max(axis=-1)
        dark = (brightest < 120) & (block[..., 3] > 100) & ((block[..., 0] - block[..., 2]) < 45)     # the vitreous: dark, hardly red
        dark = ndimage.binary_opening(dark, iterations=2)
        parts, count = ndimage.label(dark)
        if count == 0:
            out.append({"centre_m": list(e["centre_m"]), "radius_m": float(e["radius_m"])})
            continue
        sizes = ndimage.sum(dark, parts, range(1, count + 1))
        blob = parts == (1 + int(np.argmax(sizes)))
        zs, ys, xs = np.nonzero(blob)
        radius_mm = 0.5 * ((ys.max() - ys.min() + 1) * sy + (xs.max() - xs.min() + 1) * sx) / 2
        cy = (ys.min() + ys.max() + 1) / 2 + box[1].start
        cx = (xs.min() + xs.max() + 1) / 2 + box[2].start
        cz = (zs.max() + 1 + box[0].start) - radius_mm / sz                   # from the back wall forwards
        c = (np.array([cx, cy, cz]) / np.array([dx, dy, dz]) - 0.5) * size + centre
        out.append({"centre_m": [float(x) for x in c], "radius_m": float(radius_mm / 1000.0)})
    return out


def region_colour(body: Body, name: str, v: np.ndarray, n: np.ndarray, depths_mm=(1.2, 2.0, 2.8, 3.6)):
    """The photographs' own colour just under the skin, from a finer region export (the head at 0.66 mm): float
    (k, 3) sRGB 0..1 per vertex and a bool mask of the vertices the region covers; None when there is no such region."""
    entry = next((r for r in body.meta.get("regions", []) if r.get("name") == name), None)
    if entry is None:
        return None
    folder = body.export.parent / entry["folder"]
    if not (folder / "body.raw").exists():
        return None
    meta = json.loads((folder / "body.json").read_text())
    dx, dy, dz = meta["dims"]
    rgba = np.fromfile(folder / "body.raw", np.uint8).reshape(dz, dy, dx, 4)
    # The colour is wanted at the scale of lips and lids, not of voxels: blurred a little first (within the tissue),
    # or the surface, which crosses the voxels at a slant, would pick up their layers as bands.
    tissue = (rgba[..., 3] > 100).astype(np.float32)
    weight_field = np.maximum(ndimage.gaussian_filter(tissue, (1.3, 0.9, 1.3)), 1e-3)
    blurred = [ndimage.gaussian_filter(rgba[..., c].astype(np.float32) * tissue, (1.3, 0.9, 1.3)) / weight_field for c in range(3)]
    centre, size = np.array(entry["centre_m"], np.float64), np.array(entry["size_m"], np.float64)
    total = np.zeros((len(v), 3))
    weight = np.zeros(len(v))
    inside = np.ones(len(v), bool)
    for depth in depths_mm:
        p = np.asarray(v, np.float64) - n * (depth * MM)
        local = np.stack([p[:, 0], p[:, 1], -p[:, 2]], axis=1) - centre          # the body's metres: x left, y up, z back
        idx = (local / size + 0.5) * np.array([dx, dy, dz]) - 0.5
        ok = ((idx > 0) & (idx < np.array([dx, dy, dz]) - 1)).all(axis=1)
        inside &= ok
        coords = np.stack([idx[:, 2], idx[:, 1], idx[:, 0]], axis=0)
        alpha = ndimage.map_coordinates(tissue, coords, order=1, mode="nearest")
        for c in range(3):
            total[:, c] += ndimage.map_coordinates(blurred[c], coords, order=1, mode="nearest") * (alpha > 0.5)
        weight += alpha > 0.5
    colour = total / np.maximum(weight, 1.0)[:, None] / 255.0
    return colour, inside & (weight > 0)


def regions(body: Body, v: np.ndarray, n: np.ndarray, marks: dict) -> tuple[dict, dict]:
    """Per-vertex weights 0..1 by region, and the landmarks used (for the hair's directions and for the record)."""
    v = np.asarray(v, np.float64)
    k = len(v)
    out = {name: np.zeros(k) for name in ("lips_upper", "lips_lower", "lids", "brow", "scalp", "beard", "areola", "nipple", "chest", "belly_line",
                                          "forearm", "upper_arm", "thigh", "shin", "sole", "face_colour")}
    info = {}
    x, y, z = v[:, 0], v[:, 1], v[:, 2]

    # ---- the head ----
    if "eyes" in marks:
        face = Face(marks, v)
        info["face"] = face
        u, w, d = face.local(v)
        head = (w > -160) & (np.abs(u) < 130) & (d > -230)
        front = smooth(d, -25, -5) * smooth(n @ face.ez, -0.3, 0.1)
        # Lips: a lens along the lip line, the upper with its bow.
        t = np.clip(np.abs(u) / (MOUTH_WIDTH / 2), 0, 1)
        lens = np.sqrt(np.clip(1 - t ** 2, 0, 1)) ** 0.8
        bow = 1.0 - 0.22 * np.exp(-(u / 4.0) ** 2) + 0.10 * np.exp(-((np.abs(u) - 5.5) / 3.5) ** 2)
        rel = w - face.stomion_w + 1.2 * t ** 2                               # the corners turn down a little
        inside = (np.abs(u) < MOUTH_WIDTH / 2) & head
        out["lips_upper"] = inside * front * smooth(rel, -0.4, 0.6) * smooth(rel, LIP_UP * lens * bow + 0.8, LIP_UP * lens * bow - 0.8)
        out["lips_lower"] = inside * front * smooth(rel, 0.4, -0.6) * smooth(rel, -LIP_DOWN * lens - 0.8, -LIP_DOWN * lens + 0.8)
        for side, sign in (("right", -1.0), ("left", 1.0)):
            ue, we = sign * face.half_ipd, face.eye_w[side]
            out["lids"] = np.maximum(out["lids"], head * front * smooth(((u - ue) / 18.0) ** 2 + ((w - we) / 11.0) ** 2, 1.0, 0.55))
            # The brow: a band on the orbital rim, thick at its head near the nose, thin at its tail.
            s = sign * (u - ue)                                               # mm towards the temple from the eye's centre
            along = np.clip((s + 17.0) / 47.0, 0, 1)
            spine = we + 15.0 + 4.5 * np.sin(np.pi * np.clip(along / 0.7, 0, 1) / 2) - 5.0 * np.clip((along - 0.7) / 0.3, 0, 1) ** 1.5
            half = 4.8 - 2.9 * along
            band = smooth(np.abs(w - spine), half + 0.9, half - 0.9) * smooth(s, -19.0, -15.5) * smooth(s, 31.0, 27.0)
            out["brow"] = np.maximum(out["brow"], head * front * band)
        # The scalp: above a hairline that runs from the forehead back over the ears to the nape.
        line = np.interp(d, [-175, -150, -75, -5, 60], [-55, -50, 14, 62, 62])
        out["scalp"] = head * smooth(w - line, -3, 6) * smooth(w, -75, -60)
        # The beard: under the nose, the chin, the cheeks below a line from the ear to the mouth, the upper neck.
        cheek_top = np.interp(np.abs(u), [0, 22, 70, 90], [face.subnasale_w - 1.5, face.subnasale_w - 3.0, face.eye_w["left"] - 22.0, face.eye_w["left"] - 14.0])
        beard = head * smooth(w, cheek_top + 2.5, cheek_top - 4.0) * smooth(w, face.chin_w - 75.0, face.chin_w - 45.0) * smooth(d, -78, -60)
        beard *= 1.0 - np.maximum(out["lips_upper"], out["lips_lower"])
        heavy = np.exp(-(np.abs(u) / 34.0) ** 2) * smooth(w, face.chin_w - 30.0, face.chin_w - 10.0)          # moustache and chin densest
        out["beard"] = beard * (0.45 + 0.55 * heavy)
        info["crown"] = face.origin + (face.ex * 10.0 + face.ey * 88.0 - face.ez * 150.0) * MM
        info["lid_w"] = {side: face.lid_line(v, side) for side in ("right", "left")}
        # How much the face's own photographed colour is trusted: the middle of the face, not its rim (the gelatin
        # left a seam line and a blue-green halo round it).
        out["face_colour"] = head * front * smooth(np.hypot(u, w + 40.0), 86.0, 64.0)

    # ---- the trunk ----
    sternum = bone_box(body, "sternum")
    hips = [b for b in (bone_box(body, "left hip bone"), bone_box(body, "right hip bone")) if b is not None]
    mid_x = float(np.mean([sternum[0][0], sternum[1][0]])) if sternum else 0.0
    if sternum:
        notch_y, xiphoid_y = sternum[1][1], sternum[0][1]
        info["sternum"] = (notch_y, xiphoid_y, mid_x)
        front = smooth(n[:, 2], 0.0, 0.35)
        lateral = np.abs(x - mid_x)
        # The nipples: typical places (about 20 cm below the notch, 21 cm apart), unless the landmarks give them.
        for side, sign in (("right", -1.0), ("left", 1.0)):
            c = marks.get(f"nipple_{side}")
            if c is None:
                target = np.array([mid_x + sign * 0.105, notch_y - 0.17])
                near = (front > 0.5) & (np.hypot(x - target[0], y - target[1]) < 0.012)
                if not near.any():
                    continue
                c = v[near][np.argmax(z[near])]
            info[f"nipple_{side}"] = np.asarray(c, np.float64)
            r = np.linalg.norm(v - c, axis=1) / MM
            out["areola"] = np.maximum(out["areola"], smooth(r, 15.5, 11.5))
            out["nipple"] = np.maximum(out["nipple"], smooth(r, 4.6, 2.6))
        # Chest hair (the commonest pattern: over the breastbone and the pectorals, up to the collar bones).
        top, low = notch_y - 0.015, xiphoid_y - 0.03
        chest = front * smooth(y, low - 0.04, low + 0.02) * smooth(y, top + 0.03, top - 0.02) * smooth(lateral, 0.17, 0.11)
        out["chest"] = chest * (0.45 + 0.55 * np.exp(-(lateral / 0.06) ** 2)) * (1.0 - out["areola"])
        if hips:
            pubis_y = min(b[0][1] for b in hips) + 0.045
            belly = front * smooth(y, pubis_y, pubis_y + 0.03) * smooth(y, low + 0.02, low - 0.03) * smooth(lateral, 0.022, 0.006)
            out["belly_line"] = belly

    # ---- the limbs ----
    lab = body.labels
    for side in ("left", "right"):
        ids = [o["index"] for o in body.objects if "arm" in o["name"] and side in o["name"]] + [o["index"] for o in body.objects if o["name"] == f"bones of the {side} hand"]
        hum, rad = bone_box(body, f"{side} humerus"), bone_box(body, f"{side} radius")
        if not ids or hum is None or rad is None:
            continue
        field = ndimage.gaussian_filter(np.isin(lab, ids)[::2, ::2, ::2].astype(np.float32), 1.0)
        arm = smooth(body.sample(field, v - n * 0.004, step=2), 0.35, 0.65)
        elbow_y, wrist_y = hum[0][1], rad[0][1]
        info[f"arm_{side}"] = (np.array([(hum[0][0] + hum[1][0]) / 2, hum[1][1], (hum[0][2] + hum[1][2]) / 2]),
                               np.array([(rad[0][0] + rad[1][0]) / 2, wrist_y, (rad[0][2] + rad[1][2]) / 2]))
        out["upper_arm"] = np.maximum(out["upper_arm"], arm * smooth(y, elbow_y - 0.01, elbow_y + 0.03))
        out["forearm"] = np.maximum(out["forearm"], arm * smooth(y, elbow_y + 0.01, elbow_y - 0.03) * smooth(y, wrist_y - 0.075, wrist_y - 0.035))
    femurs = [b for b in (bone_box(body, "left femur"), bone_box(body, "right femur")) if b is not None]
    if femurs and hips:
        crotch_y = min(b[0][1] for b in hips) - 0.03
        knee_y = min(b[0][1] for b in femurs)
        floor_y = float(y.min())
        ankle_y = floor_y + 0.11
        not_arm = 1.0 - np.maximum(out["forearm"], out["upper_arm"])
        out["thigh"] = not_arm * smooth(y, crotch_y, crotch_y - 0.05) * smooth(y, knee_y - 0.02, knee_y + 0.03)
        out["shin"] = smooth(y, knee_y - 0.03, knee_y - 0.08) * smooth(y, ankle_y - 0.02, ankle_y + 0.03)
        out["sole"] = smooth(y, floor_y + 0.07, floor_y + 0.03) * smooth(-n[:, 1], 0.2, 0.6)
        info["legs"] = (crotch_y, knee_y, ankle_y)
    return out, info


def paint(body: Body, v: np.ndarray, n: np.ndarray, bake: np.ndarray, marks: dict, f: np.ndarray | None = None):
    """The skin's colour per vertex (uint8 sRGB), its hair mask (uint8), its gloss (uint8, 128 = the material's
    own), the region weights and the landmarks."""
    reg, info = regions(body, v, n, marks)
    k = len(v)
    colour = np.tile(np.array(SKIN_BASE, np.float64) / 255.0, (k, 1))

    def toward(target, weight):
        nonlocal colour
        colour = colour + (np.array(target, np.float64) / 255.0 - colour) * np.clip(weight, 0, 1)[:, None]

    def times(factor, weight):
        nonlocal colour
        colour = colour * (1.0 + (np.array(factor, np.float64) - 1.0) * np.clip(weight, 0, 1)[:, None])

    # The face: its own light and dark from the photographs (the lips as they are, the brown round the eyes, the
    # shadow of the shaved beard), as a ratio against his cheeks' colour laid over the clean skin tone. The body
    # keeps the clean tone: its photographed surface is frost and lividity; the face's is not.
    own = np.zeros(k)
    got = region_colour(body, "head", v, n) if reg["face_colour"].max() > 0 and f is not None else None
    if got is not None:
        photo, covered = got
        face = info["face"]
        u, w, _ = face.local(v)
        skin_like = covered & (reg["face_colour"] > 0.9) & (photo[:, 0] > photo[:, 2] + 0.06)
        cheeks = skin_like & (np.abs(u) > 22) & (np.abs(u) < 55) & (w < -15) & (w > -60)
        if cheeks.sum() > 200:
            reference = np.median(photo[cheeks], axis=0)
            ratio = np.clip(photo / np.maximum(reference, 1e-3), 0.5, 1.1)
            usable = covered & (photo[:, 0] > photo[:, 2] + 0.03)                 # not the blue-green of the gelatin
            # Only the face's vertices take part; where the gelatin tinted the photograph the neighbours' colour stands in.
            part = np.nonzero(reg["face_colour"] > 0)[0]
            index = np.full(k, -1, np.int64)
            index[part] = np.arange(len(part))
            faces = index[f[(index[f] >= 0).all(axis=1)]]
            ratio[part] = spread(ratio[part], usable[part], faces)
            own = reg["face_colour"]
            colour = colour * (1.0 + (ratio ** 0.6 - 1.0) * own[:, None])
            info["face_reference"] = [float(x) for x in reference]
    synthetic = 1.0 - own                                                     # painted zones only where the photographs are not used

    # Thin skin over little fat shows the blood under it (ears, the nose's wings, fingers, toes).
    thin = smooth(bake[:, 1].astype(np.float64) / 255.0 * 60.0, 16.0, 4.0)
    times((1.0, 0.93, 0.91), 0.7 * thin)
    times((0.95, 0.91, 0.90), reg["lids"] * synthetic)                      # palette.md: lid against the skin below the eye
    toward(SOLE, 0.6 * reg["sole"])
    # Where the hair was shaved, the stubble under the skin greys it.
    times(STUBBLE_TINT, 0.75 * reg["beard"] * synthetic)
    times(STUBBLE_TINT, 0.55 * reg["scalp"])
    times((0.86, 0.84, 0.84), 0.5 * reg["brow"])
    toward(AREOLA, 0.85 * reg["areola"])
    toward(NIPPLE, 0.8 * reg["nipple"])
    toward(LIP_UPPER, 0.6 * reg["lips_upper"] * synthetic)
    toward(LIP_LOWER, 0.6 * reg["lips_lower"] * synthetic)
    albedo = np.round(np.clip(colour, 0, 1) * 255).astype(np.uint8)

    hair = np.clip(np.maximum.reduce([reg["scalp"], reg["beard"], reg["brow"], 0.5 * reg["chest"], 0.5 * reg["belly_line"], 0.35 * reg["forearm"],
                                      0.2 * reg["upper_arm"], 0.35 * reg["thigh"], 0.35 * reg["shin"]]), 0, 1)
    gloss = np.full(k, 128.0)
    gloss += 55.0 * np.maximum(reg["lips_upper"], reg["lips_lower"])          # lips are smoother than skin
    gloss -= 45.0 * reg["sole"]
    gloss -= 30.0 * np.maximum(reg["scalp"], reg["beard"])                    # stubble breaks the highlight up
    return albedo, np.round(hair * 255).astype(np.uint8), np.clip(np.round(gloss), 0, 255).astype(np.uint8), reg, info
