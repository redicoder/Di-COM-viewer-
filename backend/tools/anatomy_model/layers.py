"""Fat, muscles, skeleton and organs: every labelled object of the body as its own mesh.

Each object's voxels are blurred a little and contoured by marching cubes at the voxels' real spacing, decimated
to its share of the layer's triangle budget, and baked (openness from a blurred occupancy of the whole layer).
The fat is one mesh per fat object too; its inner faces (against the muscles) look away from the viewer and are
culled, so with the skin off the body shows its fat, and the muscles only where there is none.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from .common import LAYER_OF_CLASS, Baker, Body, Structure, decimate, surface
from .palette import colour_of

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


def build(body: Body, layer: str, triangles: int, log=print) -> list[Structure]:
    """The structures of one layer (fat, muscles, skeleton or organs), about `triangles` in all."""
    lab = body.labels
    objs = objects_of(body, layer)
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
    occupancy = baker.field(np.isin(lab, [o["index"] for o in objs]))
    total = sum(len(f) for _, _, f in raw)
    share = triangles / max(1, total)
    out = []
    for o, v, f in raw:
        v, f = decimate(v, f, max(MIN_TRIANGLES, len(f) * min(1.0, share)))
        v, f = body.to_gltf(v, f)
        out.append(Structure(o["name"], layer, v, f, colour_of(o["name"], o["layer"]), bake=baker.colours(v, f, occupancy, gloss=GLOSS[layer]),
                             info={"label": int(o["index"]), "class": o["layer"]}))
    log(f"{layer}: {len(out)} structures, {sum(s.triangles for s in out)} triangles")
    return out
