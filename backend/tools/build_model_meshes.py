"""The modelled body from real anatomy: every labelled structure of an export as its own smooth mesh, in one GLB.

    .venv-seg/Scripts/python tools/build_model_meshes.py out/photo_body ../unity/Assets/Models/anatomy.glb

Reads the export's labels (labels.raw / labels.json: the SIO structures, the tissue classes by colour, the bone
from CT) and makes, per object, a mesh of its surface: the object's voxels blurred a little, contoured by
marching cubes at the voxels' real spacing, decimated, in metres. The meshes fit inside one another exactly,
because they come from one body. The GLB has four parent nodes, outermost first: skin (the whole body's
surface, and a pair of briefs), muscles, skeleton, organs; each structure is a child named as the labels name
it, with a plain atlas colour as its material. Nothing of the photographs is in the file: shapes only.
glTF frame: x patient left, y up, z front (the export's z points back, so it is negated).
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage import measure

LAYERS = ["skin", "muscles", "skeleton", "organs"]
SKIN = (0.86, 0.69, 0.62)
BRIEFS = (0.84, 0.84, 0.84)
# The first keyword found in a structure's name gives its colour (sRGB).
ORGAN_COLOURS = [
    ("lung", (0.86, 0.60, 0.60)), ("liver", (0.40, 0.20, 0.17)), ("hepatic", (0.38, 0.42, 0.56)),
    ("gallbladder", (0.42, 0.46, 0.32)), ("cystic", (0.42, 0.46, 0.32)), ("spleen", (0.45, 0.22, 0.34)),
    ("pancreas", (0.88, 0.72, 0.50)), ("kidney", (0.55, 0.25, 0.20)), ("renal medulla", (0.66, 0.36, 0.30)),
    ("aorta", (0.66, 0.20, 0.18)), ("arter", (0.66, 0.20, 0.18)), ("pulmonary trunk", (0.40, 0.44, 0.60)),
    ("pulmonary veins", (0.82, 0.25, 0.22)), ("vein", (0.38, 0.42, 0.56)), ("vena cava", (0.38, 0.42, 0.56)),
    ("atrium", (0.70, 0.25, 0.24)), ("ventricle", (0.66, 0.20, 0.19)), ("myocardium", (0.62, 0.18, 0.17)),
    ("pericardium", (0.80, 0.55, 0.50)), ("stomach", (0.85, 0.60, 0.55)), ("cardia", (0.85, 0.60, 0.55)),
    ("curvature", (0.85, 0.60, 0.55)), ("duodenum", (0.86, 0.66, 0.56)), ("small intestine", (0.88, 0.66, 0.60)),
    ("colon", (0.80, 0.60, 0.50)), ("colic", (0.80, 0.60, 0.50)), ("caecum", (0.80, 0.60, 0.50)),
    ("rectum", (0.78, 0.56, 0.50)), ("ampulla", (0.78, 0.56, 0.50)), ("bladder", (0.86, 0.74, 0.56)),
    ("trachea", (0.86, 0.84, 0.78)), ("bronchi", (0.86, 0.84, 0.78)), ("larynx", (0.86, 0.84, 0.78)),
    ("thyroid", (0.56, 0.32, 0.28)), ("grey matter", (0.80, 0.74, 0.72)), ("white matter", (0.90, 0.88, 0.84)),
    ("prostate", (0.72, 0.52, 0.46)), ("seminal", (0.78, 0.62, 0.52)), ("testis", (0.84, 0.72, 0.66)),
]
ORGAN_DEFAULT = (0.78, 0.52, 0.48)
MUSCLE = (0.50, 0.23, 0.21)
BONE = (0.88, 0.84, 0.74)
SKIP = ("marker", "penis", "scrotum", "trachea lumen")      # markers are not anatomy; the outer genitals are skin


def colour_of(name, layer):
    if layer == "muscle":
        return MUSCLE
    if layer == "bone":
        return BONE
    for key, c in ORGAN_COLOURS:
        if key in name:
            return c
    return ORGAN_DEFAULT


def surface(mask, spacing, sigma_mm, origin):
    """Vertices (n,3 in the array's z,y,x order, mm) and faces of a boolean block's smoothed surface, or None."""
    f = ndimage.gaussian_filter(np.pad(mask, 3).astype(np.float32), [sigma_mm / s for s in spacing])
    if f.max() <= 0.5:
        f = np.pad(mask, 3).astype(np.float32)               # too thin to survive the blur: its voxels as they are
        if f.max() <= 0.5:
            return None
    v, faces, _, _ = measure.marching_cubes(f, 0.5, spacing=spacing)
    return v + (np.array(origin) - 3) * np.array(spacing), faces


def decimate(v, f, target):
    if len(f) <= target:
        return v, f
    import fast_simplification
    v2, f2 = fast_simplification.simplify(v.astype(np.float32), f.astype(np.uint32), target_count=int(target))
    return v2, f2


def normals_of(v, f):
    n = np.zeros_like(v)
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    length = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(length, 1e-12)


def to_gltf(v_zyx_mm, f, size_mm):
    """Array order z,y,x in mm -> glTF metres (x left, y up, z front), centred on the body; faces wound outward."""
    x = v_zyx_mm[:, 2] - size_mm[0] / 2
    y = v_zyx_mm[:, 1] - size_mm[1] / 2
    z = -(v_zyx_mm[:, 0] - size_mm[2] / 2)
    v = (np.stack([x, y, z], axis=1) / 1000.0).astype(np.float32)
    f = f.astype(np.uint32)
    a, b, c = v[f[:, 0]].astype(np.float64), v[f[:, 1]].astype(np.float64), v[f[:, 2]].astype(np.float64)
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:   # signed volume: negative is inside out
        f = f[:, ::-1].copy()
    return v, f


class Baker:
    """What a game bakes per vertex, from the volume the meshes came from (SkinBake's encoding in the colour):
    r how open the room above the surface is, g the tissue behind it (mm / 60), b curvature (a mild constant)."""

    def __init__(self, spacing, size_mm):
        self.spacing, self.size_mm = spacing, size_mm
        self.step = 2                                          # fields at half resolution

    def field(self, mask, sigma_mm=7.0):
        small = mask[::self.step, ::self.step, ::self.step].astype(np.float32)
        return ndimage.gaussian_filter(small, [sigma_mm / (s * self.step) for s in self.spacing])

    def depth(self, mask):
        small = mask[::self.step, ::self.step, ::self.step]
        return ndimage.distance_transform_edt(small, sampling=[s * self.step for s in self.spacing]).astype(np.float32)

    def sample(self, field, v_gltf, n_gltf, out_mm):
        """The field at the vertices moved out_mm along their normals (glTF metres -> half-resolution voxels)."""
        p = v_gltf.astype(np.float64) * 1000.0 + n_gltf * out_mm
        zyx = np.stack([-p[:, 2] + self.size_mm[2] / 2, p[:, 1] + self.size_mm[1] / 2, p[:, 0] + self.size_mm[0] / 2], axis=0)
        idx = zyx / (np.array(self.spacing)[:, None] * self.step) - 0.5 / self.step
        return ndimage.map_coordinates(field, idx, order=1, mode="nearest")

    def colours(self, v, f, occupancy, depth=None):
        n = normals_of(v.astype(np.float64), f)
        occ = self.sample(occupancy, v, n, 5.0)               # 0.24 over a flat surface, more in a crevice
        open_ = np.clip(1.0 - (occ - 0.24) * 1.7, 0.0, 1.0)
        thick = np.full(len(v), 60.0) if depth is None else np.clip(2.0 * self.sample(depth, v, n, -3.0) + 3.0, 0.0, 60.0)
        c = np.empty((len(v), 4), np.uint8)
        c[:, 0] = np.round(open_ * 255)
        c[:, 1] = np.round(thick / 60.0 * 255)
        c[:, 2] = round(0.08 / 0.25 * 255)
        c[:, 3] = 255
        return c


def srgb_to_linear(c):
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c]


def write_glb(path, layers):
    """layers: {layer: [(name, v, f, colour)]}."""
    blob = bytearray()
    views, accessors, meshes, materials, nodes = [], [], [], [], []
    scene_nodes = []

    def add(data, target):
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data)
        return len(views) - 1

    for layer in LAYERS:
        children = []
        for name, v, f, colour, bake in layers.get(layer, []):
            n = normals_of(v.astype(np.float64), f).astype(np.float32)
            pv, nv, iv = add(v.tobytes(), 34962), add(n.tobytes(), 34962), add(f.astype(np.uint32).tobytes(), 34963)
            cv = add(bake.tobytes(), 34962)
            accessors.append({"bufferView": pv, "componentType": 5126, "count": len(v), "type": "VEC3",
                              "min": v.min(axis=0).tolist(), "max": v.max(axis=0).tolist()})
            accessors.append({"bufferView": nv, "componentType": 5126, "count": len(n), "type": "VEC3"})
            accessors.append({"bufferView": iv, "componentType": 5125, "count": int(f.size), "type": "SCALAR"})
            accessors.append({"bufferView": cv, "componentType": 5121, "normalized": True, "count": len(bake), "type": "VEC4"})
            materials.append({"name": name, "pbrMetallicRoughness": {"baseColorFactor": srgb_to_linear(colour) + [1.0],
                                                                    "metallicFactor": 0.0, "roughnessFactor": 0.6}})
            meshes.append({"name": name, "primitives": [{"attributes": {"POSITION": len(accessors) - 4, "NORMAL": len(accessors) - 3, "COLOR_0": len(accessors) - 1},
                                                         "indices": len(accessors) - 2, "material": len(materials) - 1}]})
            nodes.append({"name": name, "mesh": len(meshes) - 1})
            children.append(len(nodes) - 1)
        nodes.append({"name": layer, "children": children})
        scene_nodes.append(len(nodes) - 1)
    doc = {"asset": {"version": "2.0", "generator": "dissection-table build_model_meshes"}, "scene": 0,
           "scenes": [{"nodes": scene_nodes}], "nodes": nodes, "meshes": meshes, "materials": materials,
           "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    with open(path, "wb") as out:
        out.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        out.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        out.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


def briefs_mask(lab, objects, spacing):
    """The body's voxels between the hip bones' top and just below the crotch, without the arms and hands."""
    by_name = {o["name"]: o["index"] for o in objects}
    hips = [by_name[n] for n in ("left hip bone", "right hip bone") if n in by_name]
    low = [by_name[n] for n in ("scrotum", "testis", "penis") if n in by_name]
    if not hips or not low:
        return None
    ys = np.nonzero(np.isin(lab, hips).any(axis=(0, 2)))[0]
    yl = np.nonzero(np.isin(lab, low).any(axis=(0, 2)))[0]
    y0 = max(0, int(yl.min()) - int(round(8 / spacing[1])))
    y1 = int(ys.min() + 0.50 * (ys.max() - ys.min()))        # well below the iliac crests, as briefs sit
    arms = [o["index"] for o in objects if "arm" in o["name"]]
    band = np.zeros(lab.shape, bool)
    block = (lab[:, y0:y1, :] > 0) & ~np.isin(lab[:, y0:y1, :], arms)
    block = ndimage.binary_opening(block, iterations=3)       # the hands lie against the thighs: cut the thin joins
    parts, n = ndimage.label(block)
    if n == 0:
        return None
    sizes = ndimage.sum(block, parts, range(1, n + 1))
    block = parts == (1 + int(np.argmax(sizes)))
    band[:, y0:y1, :] = ndimage.binary_dilation(block, iterations=3)
    band[:, y0:y1, :][ndimage.binary_erosion(block, iterations=3)] = False   # a shell of cloth, not a slab
    return band


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--triangles", type=int, default=1_400_000, help="about this many in all")
    args = ap.parse_args()
    meta = json.loads((args.export / "body.json").read_text())
    table = json.loads((args.export / "labels.json").read_text())
    dx, dy, dz = meta["dims"]
    sx, sy, sz = meta["spacing_mm"]
    spacing = (sz, sy, sx)                                     # array order z, y, x
    size_mm = (dx * sx, dy * sy, dz * sz)
    lab = np.fromfile(args.export / "labels.raw", np.uint8).reshape(dz, dy, dx)
    objects = table["objects"]
    # The body is the big connected pieces of tissue; the label card's letters and other specks are not him.
    parts, n = ndimage.label(lab > 0)
    sizes = ndimage.sum(lab > 0, parts, range(1, n + 1))
    keep = np.isin(parts, 1 + np.nonzero(sizes >= 0.002 * sizes.max())[0])
    lab[~keep] = 0
    del parts
    print(f"body: {int(keep.sum())} voxels in {int((sizes >= 0.002 * sizes.max()).sum())} piece(s), {n} pieces found", flush=True)
    # The muscle mass without names of its own is one structure (its pieces only differ in how they were labelled).
    generic = [o for o in objects if o["layer"] == "muscle" and ("unclassified" in o["name"] or "by colour" in o["name"])]
    if generic:
        first = generic[0]["index"]
        for o in generic[1:]:
            lab[lab == o["index"]] = first
        generic[0]["name"] = "muscles"
        # A blank photograph at a joint between the specimen's blocks reads as a whole slice of "muscle": nothing
        # of the muscle mass is one or two slices thin along the body, so such sheets are dropped.
        mass = lab == first
        thin = mass & ~ndimage.binary_opening(mass, structure=np.ones((1, 3, 1), bool))
        lab[thin] = 0
        generic[0]["voxels"] = int((lab == first).sum())
        objects = [o for o in objects if o not in generic[1:]]
    baker = Baker(spacing, size_mm)
    boxes = ndimage.find_objects(lab.astype(np.int32), max_label=255)
    layers = {k: [] for k in LAYERS}
    budget = {"skin": 0.16, "muscles": 0.30, "skeleton": 0.30, "organs": 0.24}

    # The skin: the whole body's surface, and the briefs over it.
    body_field, body_depth = baker.field(lab > 0), baker.depth(lab > 0)
    v, f = surface(lab > 0, spacing, 1.6, (0, 0, 0))
    v, f = decimate(v, f, args.triangles * budget["skin"] * 0.9)
    v, f = to_gltf(v, f, size_mm)
    layers["skin"].append(("skin", v, f, SKIN, baker.colours(v, f, body_field, body_depth)))
    print(f"skin: {len(f)} triangles", flush=True)
    band = briefs_mask(lab, objects, spacing)
    if band is not None:
        box = ndimage.find_objects(band.astype(np.int32))[0]
        v, f = surface(band[box], spacing, 1.6, [s.start for s in box])
        v, f = decimate(v, f, args.triangles * budget["skin"] * 0.1)
        v, f = to_gltf(v, f, size_mm)
        layers["skin"].append(("briefs", v, f, BRIEFS, baker.colours(v, f, body_field)))
        print(f"briefs: {len(f)} triangles", flush=True)

    todo = {"muscles": [], "skeleton": [], "organs": []}
    for o in objects:
        layer = {"muscle": "muscles", "bone": "skeleton", "organ": "organs"}.get(o["layer"])
        if layer is None or any(s in o["name"] for s in SKIP) or boxes[o["index"] - 1] is None:
            continue
        todo[layer].append(o)
    for layer, objs in todo.items():
        raw = []
        for o in objs:
            box = boxes[o["index"] - 1]
            sigma = 1.3 if o["voxels"] > 4000 else 0.8
            block = lab[box] == o["index"]
            if layer == "skeleton":                            # thin plates and marrow gaps: one solid bone
                block = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(block, 2), iterations=2))[2:-2, 2:-2, 2:-2]
            got = surface(block, spacing, sigma, [s.start for s in box])
            if got is not None and len(got[1]) >= 8:
                raw.append((o["name"], got[0], got[1]))
        # The layer's budget shared by surface (triangle count before decimation), no object under 600.
        own = {"muscles": "muscle", "skeleton": "bone", "organs": "organ"}[layer]
        occupancy = baker.field(np.isin(lab, [o["index"] for o in objs]))
        total = sum(len(f) for _, _, f in raw)
        share = args.triangles * budget[layer] / max(1, total)
        for name, v, f in raw:
            v, f = decimate(v, f, max(600, len(f) * min(1.0, share)))
            v, f = to_gltf(v, f, size_mm)
            layers[layer].append((name, v, f, colour_of(name, own), baker.colours(v, f, occupancy)))
        print(f"{layer}: {len(raw)} structures, {sum(len(x[2]) for x in layers[layer])} triangles", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_glb(args.out, layers)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
