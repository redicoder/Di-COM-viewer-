"""A picture of structures without Unity: a small z-buffer rasteriser in numpy, for checking a build by eye.

    python -m anatomy_model.preview out/photo_body/model/skin.npz --view face --out build/preview/face.png
    python -m anatomy_model.preview ../unity/Assets/Models/anatomy.glb --layers skeleton,organs --view chest --out x.png

(run from backend/tools, or with backend/tools on PYTHONPATH). Shading is plain: the per-vertex albedo (or the
structure's colour), a key and a fill light fixed to the camera, and the baked openness as ambient occlusion; no
shadows, no scattering. It shows shape, colour zones and artefacts; the real look is Unity's.

Views are named (VIEWS) or given as yaw,pitch,distance,x,y,z: yaw 0 looks at the body's front (from +z), yaw 90
from the patient's left (+x), pitch is the camera's elevation; the body stands in the frame (y up, head at +y).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from .common import Structure, load_structures, normals_of

# name: yaw deg, pitch deg, distance m, focus (x, y, z) m in glTF metres. The whole body is about 1.88 m along y.
VIEWS = {
    "front": (0, 0, 4.3, (0.0, 0.0, 0.0)),
    "back": (180, 0, 4.3, (0.0, 0.0, 0.0)),
    "left": (90, 0, 4.3, (0.0, 0.0, 0.0)),
    "right": (-90, 0, 4.3, (0.0, 0.0, 0.0)),
    "oblique": (35, 15, 4.3, (0.0, 0.0, 0.0)),
    "face": (0, 0, 0.62, (0.0, 0.835, 0.06)),
    "face_left": (55, 5, 0.62, (0.0, 0.835, 0.05)),
    "face_right": (-55, 5, 0.62, (0.0, 0.835, 0.05)),
    "head_top": (0, 60, 0.7, (0.0, 0.84, 0.03)),
    "chest": (0, 10, 1.3, (0.0, 0.42, 0.05)),
    "abdomen": (0, 10, 1.3, (0.0, 0.14, 0.05)),
    "pelvis": (0, 10, 1.2, (0.0, -0.08, 0.05)),
    "hands": (0, 25, 1.0, (0.0, 0.02, 0.12)),
    "legs": (0, 5, 2.4, (0.0, -0.50, 0.0)),
    "feet": (0, 20, 0.9, (0.0, -0.86, 0.06)),
    "feet_below": (0, -70, 0.9, (0.0, -0.90, 0.05)),
}


def camera(yaw: float, pitch: float, distance: float, focus) -> tuple[np.ndarray, np.ndarray]:
    """The camera's position and its rotation (rows: right, up, towards the viewer)."""
    cy, sy, cp, sp = np.cos(np.radians(yaw)), np.sin(np.radians(yaw)), np.cos(np.radians(pitch)), np.sin(np.radians(pitch))
    back = np.array([sy * cp, sp, cy * cp])                             # from the focus to the camera
    right = np.array([cy, 0.0, -sy])
    up = np.cross(back, right)
    return np.asarray(focus, np.float64) + back * distance, np.stack([right, up, back])


def lit_colours(s: Structure, rot: np.ndarray) -> np.ndarray:
    """Per-vertex display colour, float32 0..1."""
    n = normals_of(s.v, s.f) @ rot.T                                     # camera space: x right, y up, z to the viewer
    albedo = (np.asarray(s.albedo, np.float32) / 255.0) if s.albedo is not None else np.tile(np.array(s.colour, np.float32), (len(s.v), 1))
    albedo = albedo ** 2.2
    key = np.array([-0.45, 0.55, 0.70]); key /= np.linalg.norm(key)
    fill = np.array([0.70, 0.10, 0.70]); fill /= np.linalg.norm(fill)
    light = 0.30 + 0.80 * np.clip(n @ key, 0, 1) + 0.22 * np.clip(n @ fill, 0, 1)
    if s.bake is not None:
        light = light * (0.35 + 0.65 * (s.bake[:, 0].astype(np.float32) / 255.0) ** 1.5)
    return np.clip(albedo * light[:, None], 0, 1) ** (1 / 2.2)


def render(structures: list[Structure], view="front", size=(1280, 720), fov: float = 30.0, background=(38, 40, 44),
           out: Path | None = None) -> np.ndarray:
    """Renders the structures; returns the image (h, w, 3) uint8 and writes it when `out` is given."""
    if isinstance(view, str):
        view = VIEWS[view] if view in VIEWS else tuple(float(x) for x in view.split(","))
    if len(view) == 6:
        view = (view[0], view[1], view[2], view[3:])
    yaw, pitch, distance, focus = view
    pos, rot = camera(yaw, pitch, distance, focus)
    w, h = size
    focal = (h / 2) / np.tan(np.radians(fov) / 2)
    zbuf = np.full(h * w, np.inf, np.float32)
    img = np.empty((h * w, 3), np.float32)
    img[:] = np.array(background, np.float32) / 255.0

    for s in structures:
        if len(s.f) == 0 or s.streams:                                   # hair ribbons have no width until Unity gives it
            continue
        p = (np.asarray(s.v, np.float64) - pos) @ rot.T                  # camera space; in front of the camera z < 0
        depth = -p[:, 2]
        ok = depth > 0.02
        sx = w / 2 + focal * p[:, 0] / np.maximum(depth, 1e-6)
        sy = h / 2 - focal * p[:, 1] / np.maximum(depth, 1e-6)
        col = lit_colours(s, rot)
        f = s.f[ok[s.f].all(axis=1)]
        if len(f) == 0:
            continue
        x0, y0 = sx[f], sy[f]                                            # (m, 3)
        area = (x0[:, 1] - x0[:, 0]) * (y0[:, 2] - y0[:, 0]) - (x0[:, 2] - x0[:, 0]) * (y0[:, 1] - y0[:, 0])
        keep = area < 0                                                  # front faces (the screen's y points down)
        f, x0, y0, area = f[keep], x0[keep], y0[keep], area[keep]
        xmin, ymin = np.floor(x0.min(axis=1)), np.floor(y0.min(axis=1))
        span = np.maximum(np.ceil(x0.max(axis=1)) - xmin, np.ceil(y0.max(axis=1)) - ymin) + 1
        visible = (x0.max(axis=1) >= 0) & (x0.min(axis=1) < w) & (y0.max(axis=1) >= 0) & (y0.min(axis=1) < h)
        for k in (2, 4, 8, 16, 32, 64, 128, 256, 512):
            sel = np.nonzero(visible & (span <= k) & (span > (k // 2 if k > 2 else 0)))[0]
            chunk = max(1, 3_000_000 // (k * k))
            gx, gy = np.meshgrid(np.arange(k), np.arange(k))
            gx, gy = gx.ravel()[None, :], gy.ravel()[None, :]
            for start in range(0, len(sel), chunk):
                t = sel[start:start + chunk]
                px = xmin[t][:, None] + gx + 0.5                          # pixel centres (m, k*k)
                py = ymin[t][:, None] + gy + 0.5
                ax, ay, bx, by, cx, cy = x0[t, 0, None], y0[t, 0, None], x0[t, 1, None], y0[t, 1, None], x0[t, 2, None], y0[t, 2, None]
                w0 = (bx - px) * (cy - py) - (cx - px) * (by - py)
                w1 = (cx - px) * (ay - py) - (ax - px) * (cy - py)
                w2 = (ax - px) * (by - py) - (bx - px) * (ay - py)
                inside = (w0 <= 0) & (w1 <= 0) & (w2 <= 0) & (px >= 0) & (px < w) & (py >= 0) & (py < h)
                ti, si = np.nonzero(inside)
                if len(ti) == 0:
                    continue
                a = area[t][ti]
                b0, b1, b2 = w0[ti, si] / a, w1[ti, si] / a, w2[ti, si] / a
                tri = f[t][ti]
                d = (b0 * depth[tri[:, 0]] + b1 * depth[tri[:, 1]] + b2 * depth[tri[:, 2]]).astype(np.float32)
                pix = (py[ti, si].astype(np.int64)) * w + px[ti, si].astype(np.int64)
                c = b0[:, None] * col[tri[:, 0]] + b1[:, None] * col[tri[:, 1]] + b2[:, None] * col[tri[:, 2]]
                order = np.argsort(-d, kind="stable")                    # far first: the nearest is written last
                pix, d, c = pix[order], d[order], c[order]
                near = d < zbuf[pix]
                zbuf[pix[near]] = d[near]
                img[pix[near]] = c[near]
    image = (np.clip(img, 0, 1) * 255).astype(np.uint8).reshape(h, w, 3)
    if out is not None:
        from PIL import Image
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(image).save(out)
    return image


def load(path: Path) -> list[Structure]:
    path = Path(path)
    if path.suffix == ".glb":
        from .glb import read_glb
        return read_glb(path)
    return load_structures(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", type=Path, nargs="+", help="layer caches (.npz) and/or a model (.glb)")
    ap.add_argument("--view", default="front", help="a named view (%s) or yaw,pitch,distance,x,y,z" % ", ".join(VIEWS))
    ap.add_argument("--layers", default="", help="only these layers (comma separated)")
    ap.add_argument("--names", default="", help="only structures whose name contains one of these (comma separated)")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    structures = [s for src in args.source for s in load(src)]
    if args.layers:
        structures = [s for s in structures if s.layer in args.layers.split(",")]
    if args.names:
        structures = [s for s in structures if any(k in s.name for k in args.names.split(","))]
    w, h = (int(x) for x in args.size.split("x"))
    render(structures, args.view, (w, h), out=args.out)
    print(f"{args.out}: {len(structures)} structures, {sum(s.triangles for s in structures)} triangles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
