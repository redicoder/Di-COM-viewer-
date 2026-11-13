"""Fat, muscles, skeleton and organs: every labelled object of the body as its own mesh.

Each object's voxels are blurred a little and contoured by marching cubes at the voxels' real spacing, decimated
to its share of the layer's triangle budget, and baked (openness from a blurred occupancy of the whole layer).
The fat is one mesh per fat object too; its inner faces (against the muscles) look away from the viewer and are
culled, so with the skin off the body shows its fat, and the muscles only where there is none.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import bonehub, eyes
from .common import LAYER_OF_CLASS, Baker, Body, Structure, decimate, load_structures, surface
from .palette import BONE, colour_of

SKIP = ("marker", "penis", "scrotum", "trachea lumen")      # markers are not anatomy; the outer genitals are skin
MIN_TRIANGLES = 600
GLOSS = {"fat": 150, "muscles": 128, "skeleton": 128, "organs": 128}


def objects_of(body: Body, layer: str) -> list[dict]:
    out = []
    for o in body.objects:
        if LAYER_OF_CLASS.get(o["layer"]) != layer or o["voxels"] == 0 or any(s in o["name"] for s in SKIP):
            continue
        out.append(o)
    return out


KEEP_WITH_BONEHUB = ("cartilage", "disc", "coccyx")      # what BoneHub does not label; the rest of our bones give way


def build(body: Body, layer: str, triangles: int, log=print) -> list[Structure]:
    """The structures of one layer (fat, muscles, skeleton or organs), about `triangles` in all."""
    lab = body.labels
    objs = objects_of(body, layer)
    named = []
    if layer == "skeleton" and bonehub.cache_path(body).exists():
        # The bones one by one from BoneHub (finer, and every one named); ours keep the cartilages and the discs.
        named, _, _ = bonehub.load_or_build(body, None, log)
        objs = [o for o in objs if any(k in o["name"] for k in KEEP_WITH_BONEHUB)]
    boxes = ndimage.find_objects(lab.astype(np.int32), max_label=255)
    baker = Baker(body)
    raw = []
    for o in objs:
        box = boxes[o["index"] - 1]
        if box is None:
            continue
        block = lab[box] == o["index"]
        if layer == "skeleton":                                # thin plates and marrow gaps: one solid bone
            block = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(block, 2), iterations=2))[2:-2, 2:-2, 2:-2]
        got = surface(block, body.spacing, 1.3 if o["voxels"] > 4000 else 0.8, [s.start for s in box])
        if got is not None and len(got[1]) >= 8:
            raw.append((o, got[0], got[1]))
    if named:
        # Bone of ours that BoneHub has nothing near (its arm bones stop short of the elbow; the hyoid): kept, unnamed.
        from scipy.spatial import cKDTree
        ours = np.isin(lab, [o["index"] for o in objects_of(body, layer) if not any(k in o["name"] for k in KEEP_WITH_BONEHUB)])
        centres = (np.argwhere(ours) + 0.5) * np.array(body.spacing)
        tree = cKDTree(np.concatenate([v[::3] for _, _, v, _ in named]))
        far = tree.query(centres, distance_upper_bound=12.0)[0] > 12.0     # the arms lie up to 8 mm apart in the CT and in the photographs
        rest = np.zeros(lab.shape, bool)
        rest[tuple((centres[far] / np.array(body.spacing)).astype(np.int64).T)] = True
        rest = ndimage.binary_opening(rest, iterations=1)
        parts, count = ndimage.label(rest)
        sizes = ndimage.sum(rest, parts, range(1, count + 1)) if count else []
        for k, box in enumerate(ndimage.find_objects(parts)):
            if box is None or sizes[k] < 1200:
                continue
            got = surface(parts[box] == k + 1, body.spacing, 1.0, [s.start for s in box])
            if got is not None and len(got[1]) >= 8:
                raw.append(({"name": f"bone (not named) {len(raw) + 1}", "layer": "bone", "index": 0}, got[0], got[1]))
    occupancy = baker.field(np.isin(lab, [o["index"] for o in objects_of(body, layer)]))
    total = sum(len(f) for _, _, f in raw) + sum(len(f) for _, _, _, f in named)
    share = triangles / max(1, total)
    out = []
    for code, name, v, f in named:
        v, f = decimate(v, f, max(MIN_TRIANGLES, len(f) * min(1.0, share)))
        v, f = body.to_gltf(v, f)
        out.append(Structure(name, layer, v, f, BONE, bake=baker.colours(v, f, occupancy, gloss=GLOSS[layer]), info={"source": "BoneHub", "code": code, "class": "bone"}))
    for o, v, f in raw:
        v, f = decimate(v, f, max(MIN_TRIANGLES, len(f) * min(1.0, share)))
        v, f = body.to_gltf(v, f)
        out.append(Structure(o["name"], layer, v, f, colour_of(o["name"], o["layer"]), bake=baker.colours(v, f, occupancy, gloss=GLOSS[layer]),
                             info={"label": int(o["index"]), "class": o["layer"]}))
    if layer == "organs":
        skin_cache = body.export / "model" / "skin.npz"
        if skin_cache.exists():                                # the eyeballs sit behind the skin's lids
            whole = body.export / "model" / "skin_surface.npz"
            out += eyes.build(load_structures(skin_cache)[0], log, load_structures(whole)[0] if whole.exists() else None)
    log(f"{layer}: {len(out)} structures, {sum(s.triangles for s in out)} triangles")
    return out
