"""The model as a GLB: one node per layer (outermost first), one child mesh per structure.

Per vertex: POSITION, NORMAL, COLOR_0 = the bake (openness, thickness / 60 mm, curvature / 0.25 per mm, gloss with
128 = the material's own), TEXCOORD_0 = (albedo red, albedo green), TEXCOORD_1 = (albedo blue, extra): the albedo in
sRGB 0..1 (the structure's colour where it has no per-vertex albedo), `extra` the layer's own use (skin: hair
density). The two texture coordinates are data, not a UV map: the meshes have none. The material carries the
structure's colour as baseColorFactor for other viewers; Unity's LabModel.shader reads the per-vertex albedo.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

from .common import LAYERS, Structure, normals_of

FLOAT, UBYTE, UINT = 5126, 5121, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963


def srgb_to_linear(c):
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c]


def vertex_data(s: Structure):
    """The structure's per-vertex streams as written: normals, bake, uv0 (r, g), uv1 (b, extra)."""
    n = len(s.v)
    normals = normals_of(s.v, s.f).astype(np.float32)
    bake = s.bake if s.bake is not None else np.tile(np.array([255, 255, 82, 128], np.uint8), (n, 1))
    if s.albedo is not None:
        rgb = np.asarray(s.albedo, np.float32) / 255.0
    else:
        rgb = np.tile(np.array(s.colour, np.float32), (n, 1))
    extra = np.zeros(n, np.float32) if s.extra is None else np.asarray(s.extra, np.float32) / 255.0
    uv0 = np.ascontiguousarray(rgb[:, :2], np.float32)
    uv1 = np.ascontiguousarray(np.stack([rgb[:, 2], extra], axis=1), np.float32)
    return normals, np.ascontiguousarray(bake, np.uint8), uv0, uv1


def flip_v(uv: np.ndarray) -> np.ndarray:
    """glTF importers turn texture coordinates upside down (v -> 1 - v) for engines whose textures start at the
    bottom; our coordinates are data, so they are stored turned and arrive as they were meant."""
    out = np.array(uv, np.float32)
    out[:, 1] = 1.0 - out[:, 1]
    return out


def write_glb(path: Path, structures: list[Structure], generator: str = "dissection-table build_model_meshes") -> None:
    blob = bytearray()
    views, accessors, meshes, materials, nodes, scene_nodes = [], [], [], [], [], []

    def accessor(data: np.ndarray, component: int, kind: str, target: int, normalized: bool = False, bounds: bool = False) -> int:
        while len(blob) % 4:
            blob.append(0)
        raw = data.tobytes()
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(raw), "target": target})
        blob.extend(raw)
        a = {"bufferView": len(views) - 1, "componentType": component, "count": int(len(data) if kind != "SCALAR" else data.size), "type": kind}
        if normalized:
            a["normalized"] = True
        if bounds:
            a["min"], a["max"] = data.min(axis=0).tolist(), data.max(axis=0).tolist()
        accessors.append(a)
        return len(accessors) - 1

    for layer in LAYERS:
        children = []
        for s in (x for x in structures if x.layer == layer):
            if len(s.f) == 0:
                continue
            attributes = {"POSITION": accessor(np.ascontiguousarray(s.v, np.float32), FLOAT, "VEC3", ARRAY_BUFFER, bounds=True)}
            if s.streams:                                                 # ready attributes (hair ribbons)
                for key, data in s.streams.items():
                    data = np.ascontiguousarray(data)
                    if data.dtype == np.uint8:
                        attributes[key] = accessor(data, UBYTE, "VEC4", ARRAY_BUFFER, normalized=True)
                    else:
                        attributes[key] = accessor(data.astype(np.float32), FLOAT, {2: "VEC2", 3: "VEC3", 4: "VEC4"}[data.shape[1]], ARRAY_BUFFER)
            else:
                normals, bake, uv0, uv1 = vertex_data(s)
                attributes["NORMAL"] = accessor(normals, FLOAT, "VEC3", ARRAY_BUFFER)
                attributes["COLOR_0"] = accessor(bake, UBYTE, "VEC4", ARRAY_BUFFER, normalized=True)
                attributes["TEXCOORD_0"] = accessor(flip_v(uv0), FLOAT, "VEC2", ARRAY_BUFFER)
                attributes["TEXCOORD_1"] = accessor(flip_v(uv1), FLOAT, "VEC2", ARRAY_BUFFER)
            indices = accessor(np.ascontiguousarray(s.f, np.uint32).ravel(), UINT, "SCALAR", ELEMENT_ARRAY_BUFFER)
            materials.append({"name": s.name, "pbrMetallicRoughness": {"baseColorFactor": srgb_to_linear(s.colour) + [1.0],
                                                                      "metallicFactor": 0.0, "roughnessFactor": 0.6}})
            meshes.append({"name": s.name, "primitives": [{"attributes": attributes, "indices": indices, "material": len(materials) - 1}]})
            node = {"name": s.name, "mesh": len(meshes) - 1}
            if s.info:
                node["extras"] = s.info
            nodes.append(node)
            children.append(len(nodes) - 1)
        if children:
            nodes.append({"name": layer, "children": children})
            scene_nodes.append(len(nodes) - 1)
    doc = {"asset": {"version": "2.0", "generator": generator}, "scene": 0, "scenes": [{"nodes": scene_nodes}],
           "nodes": nodes, "meshes": meshes, "materials": materials, "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": len(blob) + (-len(blob) % 4)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as out:
        out.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        out.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        out.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


def read_glb(path: Path) -> list[Structure]:
    """Reads a GLB written by write_glb back into structures (for previews and tests)."""
    data = Path(path).read_bytes()
    magic, _, _ = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise ValueError(f"{path} is not a GLB")
    jlen, _ = struct.unpack_from("<II", data, 12)
    doc = json.loads(data[20:20 + jlen])
    start = 20 + jlen + 8
    types = {FLOAT: np.float32, UBYTE: np.uint8, UINT: np.uint32, 5123: np.uint16}
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}

    def get(index: int) -> np.ndarray:
        a = doc["accessors"][index]
        view = doc["bufferViews"][a["bufferView"]]
        dtype, w = types[a["componentType"]], width[a["type"]]
        arr = np.frombuffer(data, dtype, a["count"] * w, start + view["byteOffset"] + a.get("byteOffset", 0))
        return arr.reshape(-1, w) if w > 1 else arr

    out = []
    for layer_node in (doc["nodes"][i] for i in doc["scenes"][0]["nodes"]):
        for child in (doc["nodes"][i] for i in layer_node.get("children", [])):
            prim = doc["meshes"][child["mesh"]]["primitives"][0]
            at = prim["attributes"]
            colour = doc["materials"][prim["material"]]["pbrMetallicRoughness"]["baseColorFactor"][:3]
            colour = tuple(1.055 * x ** (1 / 2.4) - 0.055 if x > 0.0031308 else 12.92 * x for x in colour)
            s = Structure(child["name"], layer_node["name"], get(at["POSITION"]).copy(), get(prim["indices"]).reshape(-1, 3).copy(), colour,
                          info=child.get("extras", {}))
            if "COLOR_0" in at and "TANGENT" not in at:
                s.bake = get(at["COLOR_0"]).copy()
            if "TANGENT" in at:                                           # hair ribbons: attributes as written
                s.streams = {key: get(index).copy() for key, index in at.items() if key != "POSITION"}
            elif "TEXCOORD_0" in at and "TEXCOORD_1" in at:
                uv0, uv1 = flip_v(get(at["TEXCOORD_0"])), flip_v(get(at["TEXCOORD_1"]))
                s.albedo = np.round(np.clip(np.stack([uv0[:, 0], uv0[:, 1], uv1[:, 0]], axis=1), 0, 1) * 255).astype(np.uint8)
                s.extra = np.round(np.clip(uv1[:, 1], 0, 1) * 255).astype(np.uint8)
            out.append(s)
    return out
