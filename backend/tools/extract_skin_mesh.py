"""The body's skin as a mesh, from a photographed-body export (prepare_photo_volume.py --unity).

The Anatomy Lab draws the skin as an ordinary mesh (lit, shadowed, fast) over the photo volume, which still holds
everything underneath. The surface comes from the export's skin-depth map (depth.raw: millimetres below the outer
skin, holes filled, 0 outside), so it is the outer envelope alone: no sinuses, no mouth cavity. Marching cubes at
a small depth, Taubin smoothing (no shrinkage), decimation to the triangle budget, smooth normals.

Writes skin.mesh (little-endian: "SKIN" + uint32 vertex count + uint32 index count, float32 positions in body
millimetres on the texture axes [x left, y up, z back], float32 normals, uint32 indices, triangles wound
counter-clockwise seen from outside) and skin.json beside the export.

Usage: python tools/extract_skin_mesh.py backend/out/photo_head --triangles 250000
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np
from scipy import ndimage, sparse
from skimage import measure


def load_depth(folder: Path) -> tuple[np.ndarray, np.ndarray]:
    """depth.raw as (z, y, x) in millimetres, and the voxel spacing (x, y, z) in mm."""
    meta = json.loads((folder / "body.json").read_text())
    w, d, h = meta["dims"]
    unit = float(meta.get("skin_depth_unit_mm", 0.25))
    raw = np.fromfile(folder / meta.get("skin_depth", "depth.raw"), np.uint8)
    if raw.size != w * d * h:
        raise SystemExit(f"depth.raw has {raw.size} bytes, expected {w * d * h}")
    return raw.reshape(h, d, w).astype(np.float32) * unit, np.array(meta["spacing_mm"], np.float32)


def surface(depth: np.ndarray, spacing: np.ndarray, level_mm: float, smooth_mm: float) -> tuple[np.ndarray, np.ndarray]:
    """Marching cubes on the depth map at level_mm below the skin, after a light smoothing (mm, isotropic)."""
    sigma = (smooth_mm / spacing[2], smooth_mm / spacing[1], smooth_mm / spacing[0])
    field = ndimage.gaussian_filter(depth, sigma)
    # Pad so the surface is closed where the body meets the export's edges (the cut neck).
    field = np.pad(field, 1)
    verts, faces, _, _ = measure.marching_cubes(field, level=level_mm, spacing=(spacing[2], spacing[1], spacing[0]))
    verts -= np.array([spacing[2], spacing[1], spacing[0]])         # undo the padding
    verts = verts[:, ::-1].copy()                                     # (z, y, x) mm -> (x, y, z) mm
    # marching_cubes winds its triangles to face the field's decrease (outward, the depth grows inward) and the
    # axis reversal above mirrors them: the two together leave the winding facing outward (test_skin_mesh).
    return verts, faces


def taubin(verts: np.ndarray, faces: np.ndarray, iterations: int = 10, lam: float = 0.5, mu: float = -0.53) -> np.ndarray:
    """Taubin smoothing: a Laplacian step in, a slightly larger one out, so the surface smooths without shrinking."""
    n = len(verts)
    i = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2], faces[:, 1], faces[:, 2], faces[:, 0]])
    j = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0], faces[:, 0], faces[:, 1], faces[:, 2]])
    adj = sparse.coo_matrix((np.ones(len(i), np.float32), (i, j)), shape=(n, n)).tocsr()
    adj.data[:] = 1.0
    degree = np.asarray(adj.sum(axis=1)).ravel()
    degree[degree == 0] = 1.0
    v = verts.astype(np.float32)
    for _ in range(iterations):
        for factor in (lam, mu):
            mean = (adj @ v) / degree[:, None]
            v = v + factor * (mean - v)
    return v


def decimate(verts: np.ndarray, faces: np.ndarray, triangles: int) -> tuple[np.ndarray, np.ndarray]:
    if len(faces) <= triangles:
        return verts, faces
    import fast_simplification
    reduction = 1.0 - triangles / len(faces)
    out_v, out_f = fast_simplification.simplify(verts.astype(np.float32), faces.astype(np.int64), target_reduction=reduction)
    return np.asarray(out_v, np.float32), np.asarray(out_f, np.int64)


def normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Area-weighted vertex normals."""
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    fn = np.cross(b - a, c - a)
    vn = np.zeros_like(verts, dtype=np.float64)
    for k in range(3):
        np.add.at(vn, faces[:, k], fn)
    length = np.linalg.norm(vn, axis=1)
    length[length == 0] = 1.0
    return (vn / length[:, None]).astype(np.float32)


def write_mesh(path: Path, verts: np.ndarray, faces: np.ndarray, vn: np.ndarray) -> None:
    with path.open("wb") as f:
        f.write(b"SKIN")
        f.write(struct.pack("<II", len(verts), faces.size))
        f.write(verts.astype("<f4").tobytes())
        f.write(vn.astype("<f4").tobytes())
        f.write(faces.astype("<u4").tobytes())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="an export folder with body.json and depth.raw")
    ap.add_argument("--triangles", type=int, default=300000, help="triangle budget after decimation")
    ap.add_argument("--level", type=float, default=0.4, help="mm below the outer skin to place the surface")
    ap.add_argument("--smooth", type=float, default=1.0, help="mm of smoothing of the depth map before meshing")
    args = ap.parse_args()
    folder = Path(args.folder)
    depth, spacing = load_depth(folder)
    verts, faces = surface(depth, spacing, args.level, args.smooth)
    print(f"marching cubes: {len(verts)} vertices, {len(faces)} triangles")
    verts = taubin(verts, faces)
    verts, faces = decimate(verts, faces, args.triangles)
    print(f"decimated: {len(verts)} vertices, {len(faces)} triangles")
    vn = normals(verts, faces)
    write_mesh(folder / "skin.mesh", verts, faces, vn)
    meta = json.loads((folder / "body.json").read_text())
    meta["skin_mesh"] = "skin.mesh"
    (folder / "body.json").write_text(json.dumps(meta, indent=2))
    (folder / "skin.json").write_text(json.dumps({
        "vertices": int(len(verts)), "triangles": int(len(faces)), "units": "mm on the texture axes (x left, y up, z back)",
        "level_mm": args.level, "smooth_mm": args.smooth, "source": "depth.raw of " + str(folder.name)}, indent=2))
    print(f"-> {folder / 'skin.mesh'}")


if __name__ == "__main__":
    main()
