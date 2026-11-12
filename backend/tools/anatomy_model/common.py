"""The body export, a structure's mesh with its per-vertex data, and the mesh operations every layer shares."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage, sparse
from skimage import measure

LAYERS = ["skin", "fat", "muscles", "skeleton", "organs"]          # outermost first
LAYER_OF_CLASS = {"skin": "skin", "fat": "fat", "muscle": "muscles", "bone": "skeleton", "organ": "organs"}
THICK_MAX_MM = 60.0            # the bake's thickness saturates here (SkinBake.ThickMaxMm in Unity)
CURV_MAX = 0.25                # 1/mm (SkinBake.CurvMax)


@dataclass
class Structure:
    """One named mesh of the model.

    v       float32 (n, 3)  glTF metres: x patient left, y up, z front, origin at the centre of the body's box
    f       uint32 (m, 3)   triangles wound counter-clockwise seen from outside
    colour  sRGB 0..1       the structure's own colour (its albedo where `albedo` is None)
    bake    uint8 (n, 4)    openness (ambient occlusion), tissue behind the surface / 60 mm, curvature / 0.25 per mm,
                            gloss (128 = the material's own, 255 = twice as glossy, 0 = matte)
    albedo  uint8 (n, 3)    sRGB per vertex, or None
    extra   uint8 (n,)      the layer's own use (skin: hair density), or None
    streams dict            ready vertex attributes by glTF name (NORMAL, TANGENT, COLOR_0, TEXCOORD_0, TEXCOORD_1),
                            written as they are in place of the above: hair ribbons (hair.py)
    """
    name: str
    layer: str
    v: np.ndarray
    f: np.ndarray
    colour: tuple
    bake: np.ndarray | None = None
    albedo: np.ndarray | None = None
    extra: np.ndarray | None = None
    info: dict = field(default_factory=dict)
    streams: dict | None = None

    @property
    def triangles(self) -> int:
        return int(len(self.f))


class Body:
    """A photographed-body export (prepare_photo_volume.py --unity with labels): grids in array order z, y, x."""

    def __init__(self, export: Path):
        self.export = Path(export)
        self.meta = json.loads((self.export / "body.json").read_text())
        dx, dy, dz = self.meta["dims"]
        sx, sy, sz = self.meta["spacing_mm"]
        self.dims = (dz, dy, dx)
        self.spacing = (float(sz), float(sy), float(sx))                 # mm, array order z, y, x
        self.size_mm = (dx * sx, dy * sy, dz * sz)                       # x, y, z
        self._labels = None
        self._objects = None
        self._depth = None

    # ---- grids -------------------------------------------------------------------------------------------------
    def _load_labels(self):
        table = json.loads((self.export / self.meta.get("label_table", "labels.json")).read_text())
        lab = np.fromfile(self.export / self.meta.get("labels", "labels.raw"), np.uint8).reshape(self.dims)
        objects = [dict(o) for o in table["objects"]]
        # The body is the big connected pieces of tissue; the label card's letters and other specks are not him.
        parts, n = ndimage.label(lab > 0)
        sizes = ndimage.sum(lab > 0, parts, range(1, n + 1))
        keep = np.isin(parts, 1 + np.nonzero(sizes >= 0.002 * sizes.max())[0])
        lab[~keep] = 0
        del parts, keep
        # The muscle mass without names of its own is one structure (its pieces differ only in how they were labelled).
        generic = [o for o in objects if o["layer"] == "muscle" and ("unclassified" in o["name"] or "by colour" in o["name"])]
        if generic:
            first = generic[0]["index"]
            for o in generic[1:]:
                lab[lab == o["index"]] = first
            generic[0]["name"] = "muscles"
            # A blank photograph at a joint between the specimen's blocks reads as a whole slice of "muscle": nothing
            # of the muscle mass is one or two slices thin along the body, so such sheets are dropped.
            mass = lab == first
            lab[mass & ~ndimage.binary_opening(mass, structure=np.ones((1, 3, 1), bool))] = 0
            objects = [o for o in objects if o not in generic[1:]]
        # The same for the fat under the skin: the SIO's unclassified tissue of the trunk and the arms and the fat
        # found by colour elsewhere are one layer (the fat round the organs keeps its own name).
        loose = [o for o in objects if o["layer"] == "fat" and "visceral" not in o["name"]]
        if loose:
            first = loose[0]["index"]
            for o in loose[1:]:
                lab[lab == o["index"]] = first
            loose[0]["name"] = "subcutaneous fat"
            # Where a blank photograph left a slice or two between fat and fat unlabelled, or read as skin, it is fat.
            fat = lab == first
            skin_ids = [o["index"] for o in objects if o["layer"] == "skin"]
            lab[ndimage.binary_closing(fat, structure=np.ones((1, 7, 1), bool)) & ((lab == 0) | np.isin(lab, skin_ids))] = first
            objects = [o for o in objects if o not in loose[1:]]
        counts = np.bincount(lab.ravel(), minlength=256)
        for o in objects:
            o["voxels"] = int(counts[o["index"]])
        self._labels, self._objects = lab, objects

    def keep_inside(self, inside: np.ndarray) -> None:
        """Drops the labels outside a mask (the fine skin's inside: fine_skin.inside_export)."""
        lab = self.labels
        lab[~inside] = 0
        counts = np.bincount(lab.ravel(), minlength=256)
        for o in self._objects:
            o["voxels"] = int(counts[o["index"]])

    @property
    def labels(self) -> np.ndarray:
        """uint8 object index per voxel (0 = none), cleaned: specks dropped, the unnamed muscle mass merged."""
        if self._labels is None:
            self._load_labels()
        return self._labels

    @property
    def objects(self) -> list[dict]:
        """The label table after cleaning: {index, name, layer (skin, fat, muscle, bone, organ), voxels, ...}."""
        if self._objects is None:
            self._load_labels()
        return self._objects

    def object_named(self, name: str) -> dict | None:
        return next((o for o in self.objects if o["name"] == name), None)

    def depth_mm(self) -> np.ndarray:
        """The skin-depth map: millimetres below the outer skin (holes filled), 0 outside; float32 (z, y, x)."""
        if self._depth is None:
            unit = float(self.meta.get("skin_depth_unit_mm", 0.25))
            raw = np.fromfile(self.export / self.meta.get("skin_depth", "depth.raw"), np.uint8).reshape(self.dims)
            self._depth = raw.astype(np.float32) * unit
        return self._depth

    # ---- frames ------------------------------------------------------------------------------------------------
    def to_gltf(self, v_zyx_mm: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Array order z, y, x in millimetres -> glTF metres, centred on the body; faces wound outward."""
        x = v_zyx_mm[:, 2] - self.size_mm[0] / 2
        y = v_zyx_mm[:, 1] - self.size_mm[1] / 2
        z = -(v_zyx_mm[:, 0] - self.size_mm[2] / 2)
        v = (np.stack([x, y, z], axis=1) / 1000.0).astype(np.float32)
        return v, outward(v, f)

    def to_voxel(self, v_gltf: np.ndarray, step: int = 1) -> np.ndarray:
        """glTF metres -> voxel indices (3, n) in array order z, y, x, for scipy.ndimage.map_coordinates; `step` for
        a grid subsampled by [::step] (its voxel k sits at full-resolution voxel k * step)."""
        p = np.asarray(v_gltf, np.float64) * 1000.0
        zyx_mm = np.stack([-p[:, 2] + self.size_mm[2] / 2, p[:, 1] + self.size_mm[1] / 2, p[:, 0] + self.size_mm[0] / 2], axis=0)
        return (zyx_mm / np.array(self.spacing)[:, None] - 0.5) / step

    def sample(self, grid: np.ndarray, v_gltf: np.ndarray, step: int = 1, order: int = 1) -> np.ndarray:
        """A grid's value at points given in glTF metres."""
        return ndimage.map_coordinates(grid, self.to_voxel(v_gltf, step), order=order, mode="nearest")


# ---- meshes ------------------------------------------------------------------------------------------------------
def outward(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    """The faces wound so that the mesh's signed volume is positive (counter-clockwise seen from outside)."""
    f = np.asarray(f, np.uint32)
    a, b, c = (v[f[:, k]].astype(np.float64) for k in range(3))
    centre = v.mean(axis=0).astype(np.float64)
    if np.einsum("ij,ij->i", a - centre, np.cross(b - centre, c - centre)).sum() < 0:
        f = f[:, ::-1].copy()
    return f


def normals_of(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Area-weighted vertex normals, float64 (n, 3)."""
    v = np.asarray(v, np.float64)
    n = np.zeros_like(v)
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)


def surface(mask: np.ndarray, spacing, sigma_mm: float, origin=(0, 0, 0)):
    """Vertices (n, 3 in the array's z, y, x order, mm) and faces of a boolean block's smoothed surface, or None.
    `origin` is the block's first voxel in the full grid."""
    f = ndimage.gaussian_filter(np.pad(mask, 3).astype(np.float32), [sigma_mm / s for s in spacing])
    if f.max() <= 0.5:
        f = np.pad(mask, 3).astype(np.float32)               # too thin to survive the blur: its voxels as they are
        if f.max() <= 0.5:
            return None
    v, faces, _, _ = measure.marching_cubes(f, 0.5, spacing=spacing)
    return v + (np.array(origin) - 3 + 0.5) * np.array(spacing), faces


def level_set(field: np.ndarray, level: float, spacing, origin=(0, 0, 0)):
    """Marching cubes on a scalar field (z, y, x): vertices in the array's order in mm (voxel centres at
    (index + 0.5) * spacing), faces. The field is padded so a surface that meets the grid's edge is closed."""
    lo = float(field.min())
    f = np.pad(field, 1, constant_values=min(lo, level - 1.0) if lo < level else level - 1.0)
    v, faces, _, _ = measure.marching_cubes(f, level, spacing=spacing)
    return v + (np.array(origin) - 1 + 0.5) * np.array(spacing), faces


def decimate(v: np.ndarray, f: np.ndarray, target: float, agg: float = 7.0):
    """Quadric decimation to about `target` triangles (fast_simplification); untouched when already under it.
    A lower `agg` raises the error allowed more gently from sweep to sweep: slower, but the triangles that remain
    are where the shape needs them and not where the last sweep happened to stop."""
    if len(f) <= target:
        return np.asarray(v, np.float32), np.asarray(f, np.uint32)
    import fast_simplification
    v2, f2 = fast_simplification.simplify(np.ascontiguousarray(v, np.float32), np.ascontiguousarray(f, np.uint32), target_count=int(target), agg=agg)
    return np.asarray(v2, np.float32), np.asarray(f2, np.uint32)


def decimate_regions(v: np.ndarray, f: np.ndarray, region: np.ndarray, edge_mm: list[float], log=None):
    """Decimates a mesh region by region: `region` gives each vertex its region (0, 1, ...), `edge_mm[r]` the edge
    length wanted there (v in metres). A triangle belongs to the highest-numbered region among its vertices (the
    finer side, when regions are numbered coarse to fine). Each region is decimated on its own with its border
    vertices left where they are, so the regions meet exactly and the mesh stays closed."""
    import pyfqmr
    v = np.asarray(v, np.float64)
    tri_region = region[f].max(axis=1)
    out_v, out_f, offset = [], [], 0
    for r in range(len(edge_mm)):
        part = f[tri_region == r]
        if len(part) == 0:
            continue
        used = np.unique(part)
        remap = np.full(len(v), -1, np.int64)
        remap[used] = np.arange(len(used))
        pv, pf = v[used], remap[part]
        a, b, c = pv[pf[:, 0]], pv[pf[:, 1]], pv[pf[:, 2]]
        area_mm2 = float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum()) / 2 * 1e6
        target = int(area_mm2 / (0.433 * edge_mm[r] ** 2))
        if target < len(pf):
            simplifier = pyfqmr.Simplify()
            simplifier.setMesh(pv, pf)
            simplifier.simplify_mesh(target_count=max(target, 100), aggressiveness=5, preserve_border=True, verbose=False)
            pv, pf, _ = simplifier.getMesh()
        if log:
            log(f"skin region {r}: {len(pf)} triangles at about {edge_mm[r]} mm")
        out_v.append(np.asarray(pv, np.float64))
        out_f.append(np.asarray(pf, np.int64) + offset)
        offset += len(pv)
    v2, f2 = np.concatenate(out_v), np.concatenate(out_f)
    # The regions' shared border vertices are the same points twice: one again.
    key = np.round(v2 * 1e7).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    f2 = inverse.reshape(-1)[f2]
    good = (f2[:, 0] != f2[:, 1]) & (f2[:, 1] != f2[:, 2]) & (f2[:, 0] != f2[:, 2])
    return v2[first].astype(np.float32), f2[good].astype(np.uint32)


def taubin(v: np.ndarray, f: np.ndarray, iterations: int = 10, lam: float = 0.5, mu: float = -0.53, weight: np.ndarray | None = None) -> np.ndarray:
    """Taubin smoothing: a Laplacian step in, a slightly larger one out, so the surface smooths without shrinking.
    `weight` (n,) in 0..1 scales the smoothing per vertex (0 leaves a vertex where it is)."""
    n = len(v)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    adj = sparse.coo_matrix((np.ones(len(i), np.float32), (i, j)), shape=(n, n)).tocsr()
    adj.data[:] = 1.0
    degree = np.asarray(adj.sum(axis=1)).ravel()
    degree[degree == 0] = 1.0
    out = np.asarray(v, np.float32).copy()
    w = None if weight is None else np.asarray(weight, np.float32)[:, None]
    for _ in range(iterations):
        for factor in (lam, mu):
            step = factor * ((adj @ out) / degree[:, None] - out)
            out = out + (step if w is None else step * w)
    return out


def relax(v: np.ndarray, f: np.ndarray, iterations: int, radius: float | np.ndarray, step: float = 0.6) -> np.ndarray:
    """Smoothing that stays within what the data cannot tell: each vertex moves towards the mean of its neighbours
    but never further than `radius` (metres; a number or one per vertex) from where it started. A surface contoured
    from pixels stands in steps one pixel high (terraces like a map's contour lines over a flat belly); the true
    surface lies within half a pixel of every step, so letting each vertex move that far turns the stairs into the
    slope they came from and leaves alone every shape larger than a pixel (constrained surface nets, Gibson 1998)."""
    n = len(v)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    adj = sparse.coo_matrix((np.ones(len(i), np.float32), (i, j)), shape=(n, n)).tocsr()
    adj.data[:] = 1.0
    degree = np.asarray(adj.sum(axis=1)).ravel()
    degree[degree == 0] = 1.0
    start = np.asarray(v, np.float32)
    out = start.copy()
    limit = np.broadcast_to(np.asarray(radius, np.float32), (n,))[:, None]
    for _ in range(iterations):
        out = out + step * ((adj @ out) / degree[:, None] - out)
        move = out - start
        far = np.linalg.norm(move, axis=1, keepdims=True)
        out = start + move * np.minimum(1.0, limit / np.maximum(far, 1e-12))
    return out


def components(f: np.ndarray, n_vertices: int) -> np.ndarray:
    """The connected piece each vertex belongs to (ids 0.., biggest pieces not ordered)."""
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    adj = sparse.coo_matrix((np.ones(len(i), np.int8), (i, j)), shape=(n_vertices, n_vertices))
    _, ids = sparse.csgraph.connected_components(adj, directed=False)
    return ids


def keep_big_pieces(v: np.ndarray, f: np.ndarray, min_share: float = 0.02):
    """Drops the mesh's connected pieces smaller than `min_share` of the biggest (by triangle count)."""
    ids = components(f, len(v))
    tri_ids = ids[f[:, 0]]
    counts = np.bincount(tri_ids)
    good = counts >= min_share * counts.max()
    keep_f = good[tri_ids]
    if keep_f.all():
        return v, f
    used = np.zeros(len(v), bool)
    used[f[keep_f].ravel()] = True
    remap = np.cumsum(used) - 1
    return v[used], remap[f[keep_f]].astype(np.uint32)


# ---- the bake --------------------------------------------------------------------------------------------------
class Baker:
    """What a game bakes per vertex, from the volume the meshes came from (SkinBake's encoding in the colour):
    r how open the room above the surface is, g the tissue behind it (mm / 60), b curvature / 0.25 per mm,
    a gloss (128 = the material's own)."""

    STEP = 2                                                   # fields at half resolution

    def __init__(self, body: Body):
        self.body = body

    def field(self, mask: np.ndarray, sigma_mm: float = 7.0) -> np.ndarray:
        """A blurred occupancy: 0.24 five millimetres over a flat surface, more in a crevice, less on a ridge."""
        s = self.STEP
        return ndimage.gaussian_filter(mask[::s, ::s, ::s].astype(np.float32), [sigma_mm / (sp * s) for sp in self.body.spacing])

    def depth(self, mask: np.ndarray) -> np.ndarray:
        s = self.STEP
        return ndimage.distance_transform_edt(mask[::s, ::s, ::s], sampling=[sp * s for sp in self.body.spacing]).astype(np.float32)

    def sample(self, grid: np.ndarray, v: np.ndarray, n: np.ndarray, out_mm: float) -> np.ndarray:
        """A half-resolution field at the vertices moved out_mm along their normals."""
        return self.body.sample(grid, np.asarray(v, np.float64) + n * (out_mm / 1000.0), step=self.STEP)

    def colours(self, v: np.ndarray, f: np.ndarray, occupancy: np.ndarray, depth: np.ndarray | None = None, gloss: int = 128) -> np.ndarray:
        n = normals_of(v, f)
        occ = self.sample(occupancy, v, n, 5.0)
        open_ = np.clip(1.0 - (occ - 0.24) * 1.7, 0.0, 1.0)
        thick = np.full(len(v), THICK_MAX_MM) if depth is None else np.clip(2.0 * self.sample(depth, v, n, -3.0) + 3.0, 0.0, THICK_MAX_MM)
        c = np.empty((len(v), 4), np.uint8)
        c[:, 0] = np.round(open_ * 255)
        c[:, 1] = np.round(thick / THICK_MAX_MM * 255)
        c[:, 2] = np.round(np.clip(curvature(v, f, n) / CURV_MAX, 0.0, 1.0) * 255)
        c[:, 3] = gloss
        return c


def curvature(v: np.ndarray, f: np.ndarray, n: np.ndarray | None = None) -> np.ndarray:
    """Mean curvature per vertex in 1/mm: how fast the normal turns along the edges that meet there (v in metres)."""
    if n is None:
        n = normals_of(v, f)
    v = np.asarray(v, np.float64)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    d = np.linalg.norm(v[i] - v[j], axis=1) * 1000.0
    turn = np.linalg.norm(n[i] - n[j], axis=1) / np.maximum(d, 1e-6)
    total = np.zeros(len(v))
    count = np.zeros(len(v))
    for a in (i, j):
        np.add.at(total, a, turn)
        np.add.at(count, a, 1.0)
    return total / np.maximum(count, 1.0)


# ---- a layer's structures on disk (so layers can be rebuilt one at a time) --------------------------------------
def save_structures(path: Path, structures: list[Structure]) -> None:
    arrays, table = {}, []
    for k, s in enumerate(structures):
        entry = {"name": s.name, "layer": s.layer, "colour": list(s.colour), "info": s.info, "has": []}
        arrays[f"v{k}"], arrays[f"f{k}"] = np.asarray(s.v, np.float32), np.asarray(s.f, np.uint32)
        for key in ("bake", "albedo", "extra"):
            a = getattr(s, key)
            if a is not None:
                arrays[f"{key}{k}"] = np.asarray(a, np.uint8)
                entry["has"].append(key)
        if s.streams:
            entry["streams"] = sorted(s.streams)
            for key, a in s.streams.items():
                arrays[f"s_{key}_{k}"] = a
        table.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, table=np.array(json.dumps(table)), **arrays)


def load_structures(path: Path) -> list[Structure]:
    with np.load(path, allow_pickle=False) as z:
        table = json.loads(str(z["table"]))
        out = []
        for k, e in enumerate(table):
            s = Structure(e["name"], e["layer"], z[f"v{k}"], z[f"f{k}"], tuple(e["colour"]), info=e.get("info", {}))
            for key in e["has"]:
                setattr(s, key, z[f"{key}{k}"])
            if e.get("streams"):
                s.streams = {key: z[f"s_{key}_{k}"] for key in e["streams"]}
            out.append(s)
    return out
