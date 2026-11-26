"""Fat, muscles, skeleton and organs: every labelled object of the body as its own mesh.

Each object's voxels are blurred a little and contoured by marching cubes at the voxels' real spacing, decimated
to its share of the layer's triangle budget, and baked (openness from a blurred occupancy of the whole layer).
The fat is one mesh per fat object too; its inner faces (against the muscles) look away from the viewer and are
culled, so with the skin off the body shows its fat, and the muscles only where there is none.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from . import bonehub, elbows, eyes, face_muscles, face_vessels, fat_shell, feet, fine_muscle, hands, head_layers, leg_muscles, mouth, skull_bones, teeth, thin_organs
from .common import LAYER_OF_CLASS, Baker, Body, Structure, decimate, load_structures, normals_of, solid_of, surface
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
    if layer == "muscles":                                 # the face's muscles are drawn whole (face_muscles.py): the labels' scraps of them go
        face_muscles.clear_scraps(body, log)
    objs = objects_of(body, layer)
    named = []
    if layer == "skeleton" and bonehub.cache_path(body).exists():
        # The bones one by one from BoneHub (finer, and every one named); ours keep the cartilages and the discs.
        named, _, _ = bonehub.load_or_build(body, None, log)
        objs = [o for o in objs if any(k in o["name"] for k in KEEP_WITH_BONEHUB)]
    boxes = ndimage.find_objects(lab.astype(np.int32), max_label=255)
    baker = Baker(body)
    raw = []
    fine = set()
    muscle_outline = fine_muscle.load(body) if layer == "muscles" else None
    if muscle_outline is not None:
        # The muscles' own surfaces from the photographs (fine_muscle.py): each labelled muscle keeps its place and
        # its name and takes the muscle-coloured voxels there at 0.66 mm. One that comes out empty keeps its labels'.
        raw = fine_muscle.surfaces(body, muscle_outline, objs, getattr(body, "original_labels", None), log=log)
        fine = {int(o["index"]) for o, _, _ in raw}
        if any(o["name"] == fine_muscle.WHOLE for o, _, _ in raw):
            # The arms' masses are part of the whole mass's surface there (fine_muscle.MASSES): they are not meshed once
            # more from their labels. (They were: each arm's muscle was in the model twice, a fine surface and a coarse
            # one a millimetre apart at the most, and each showed through the other in patches: the arms' "lace".)
            fine |= {int(o["index"]) for o in objs if o["name"] in fine_muscle.MASSES}
        log(f"fine muscles: {len(raw)} of {len(objs)} muscle objects from the photographs, {sum(len(f) for _, _, f in raw)} triangles before decimation")
    # Organs the labels have only as a thin wall (the windpipe, the bronchi, the heart's sac) take another set of the
    # labels' voxels than their own as they are (thin_organs.py).
    reshaped = thin_organs.shapes(body) if layer == "organs" else {}
    for o in objs:
        if int(o["index"]) in fine:
            continue
        box = boxes[o["index"] - 1]
        if box is None:
            continue
        block = lab[box] == o["index"]
        if o["name"] in reshaped:
            first, block = reshaped[o["name"]]
            box = tuple(slice(a, a + n) for a, n in zip(first, block.shape))
        if layer == "skeleton":                                # thin plates and marrow gaps: one solid bone
            block = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(block, 2), iterations=2))[2:-2, 2:-2, 2:-2]
        voxels = int(block.sum()) if o["name"] in reshaped else o["voxels"]
        got = surface(block, body.spacing, 1.3 if voxels > 4000 else 0.8, [s.start for s in box])
        if got is not None and len(got[1]) >= 8:
            raw.append((o, got[0], got[1]))
    shown = None
    if named:
        # The bones as they are shown, on the labels' grid: what each of BoneHub's meshes fills. Two things go by it,
        # which went by the labels' own bone before, and the labels' bone does not lie where BoneHub's does (a wrist up
        # to 8 mm beside): what counts as bone BoneHub has not got (below), and the shading baked into the bones (the
        # occupancy, further down: the wrists' small bones were dark on their open sides and light in their clefts).
        # The elbows lie beyond the CT's edge, which cuts BoneHub's arm bones: their bones are read from the photographs
        # (elbows.py) and stand in the skeleton as BoneHub's do. BoneHub's arm bones lay 4 to 5 mm from the same bones
        # in the photographs: each is given back moved onto the photographs' bone at its cut end, so the two meet.
        read, named = elbows.read(body, named, log)
        shown = np.zeros(lab.shape, bool)
        for _, _, v, f in list(named) + [(None, name, v, f) for name, v, f in read]:
            got = solid_of(v, f, lab.shape, body.spacing)
            if got is not None:
                first, block = got
                shown[tuple(slice(a, a + n) for a, n in zip(first, block.shape))] |= block
        # Bone of ours that BoneHub has nothing near (its arm bones stop short of the elbow; the hyoid): kept, unnamed.
        # Not what lies inside one of BoneHub's bones (the middle of a thick bone is further than 12 mm from its own
        # surface), and not the labels' bones of the hands: BoneHub has every bone of a hand, and where a finger lay
        # bent otherwise in the CT the labels' own piece of it stood beside BoneHub's as a second, nameless bone.
        from scipy.spatial import cKDTree
        ours = np.isin(lab, [o["index"] for o in objects_of(body, layer) if not any(k in o["name"] for k in KEEP_WITH_BONEHUB) and o["name"] not in hands.LABELS])
        ours &= ~shown
        centres = (np.argwhere(ours) + 0.5) * np.array(body.spacing)
        tree = cKDTree(np.concatenate([v[::3] for _, _, v, _ in named] + [v[::3] for _, v, _ in read]))
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
                shown[box] |= parts[box] == k + 1
        shown |= np.isin(lab, [o["index"] for o in objs])          # (and the cartilages and the discs, which are the labels' own)
    occupancy = baker.field(shown if shown is not None else np.isin(lab, [o["index"] for o in objects_of(body, layer)]))
    total = sum(len(f) for _, _, f in raw) + sum(len(f) for _, _, _, f in named)
    share = triangles / max(1, total)
    out = []
    for code, name, v, f in named:
        v, f = decimate(v, f, max(MIN_TRIANGLES, len(f) * min(1.0, share)))
        v, f = body.to_gltf(v, f)
        out.append(Structure(name, layer, v, f, BONE, bake=baker.colours(v, f, occupancy, gloss=GLOSS[layer]), info={"source": "BoneHub", "code": code, "class": "bone"}))
    for name, v, f in (read if named else []):
        v, f = decimate(v, f, max(MIN_TRIANGLES, min(len(f), elbows.TRIANGLES)))
        v, f = body.to_gltf(v, f)
        out.append(Structure(name, layer, v, f, BONE, bake=baker.colours(v, f, occupancy, gloss=GLOSS[layer]), info={"source": elbows.SOURCE, "class": "bone"}))
    if named:
        # No bone at the skin or outside it. The bones are placed from the CT, where a finger or a toe does not lie
        # just where the photographs have it: a few of their vertices stood out of the skin (a little finger's by
        # 5 mm, the toes' and the left ankle's by 1). The skull is measured on and split afterwards: left as it is.
        # The feet's own bones are seen to with the feet (feet.under, below: a toe's bones are not to be drawn in
        # along the way the depth grows), and the fingers' with the hands (hands.under), for the same reason.
        head_layers.each_under_skin(body, [s for s in out if s.name not in (skull_bones.WHOLE, "mandible") and not feet.wholly_in(body, s) and not hands.is_finger(s.name)], log=log)
        hands.under(body, out, log)
    for o, v, f in raw:
        v_mm, f = decimate(v, f, max(MIN_TRIANGLES, len(f) * min(1.0, share)))
        v, f = body.to_gltf(v_mm, f)
        albedo, info = None, {"label": int(o["index"]), "class": o["layer"]}
        if o["name"] in reshaped:
            info["shape"] = thin_organs.NOTES[o["name"]]
        if int(o.get("index", 0)) in fine:                     # lighter and darker as the photographs are under its surface, pale where a tendon or fascia lies
            n = normals_of(v, f)
            albedo = fine_muscle.tone(body, v_mm, np.stack([-n[:, 2], n[:, 1], n[:, 0]], axis=1), colour_of(o["name"], o["layer"]), f)
            info["source"] = ("the labels' object, whole (an aponeurosis: pale by nature, not read by colour), on the photographs' grid of 0.66 mm (fine_muscle.py)"
                              if o["name"] in fine_muscle.SHEETS else
                              "the labels' object; its surface from the photographs' muscle-coloured voxels at 0.66 mm (fine_muscle.py)")
        out.append(Structure(o["name"], layer, v, f, colour_of(o["name"], o["layer"]), bake=baker.colours(v, f, occupancy, gloss=GLOSS[layer]), albedo=albedo, info=info))
    if layer == "fat":                                     # the fat's surface is the skin's own, moved in: all over him,
        fat_shell.fat(body, out, baker, occupancy, GLOSS[layer], log)
        feet.fat(body, out, baker, occupancy, GLOSS[layer], log)          # and in the feet and the hands at their own fineness
        hands.fat(body, out, baker, occupancy, GLOSS[layer], log)
    out += head_layers.structures(body, layer, log)        # the head and neck, named on his CT
    out += leg_muscles.structures(body, layer, baker, occupancy, log)      # the hips' and legs' muscles, the knee's ligaments, the joints' cartilage
    own = set()                                            # what has its own place and is not to be moved under the skin (below)
    m = getattr(body, "mouth", None)
    if m is not None and layer in ("skeleton", "organs"):  # the teeth and the tongue as the mouth has them (finer, and fitting its space)
        mine = [s for s in (mouth.teeth(body, m, log) if layer == "skeleton" else [mouth.tongue(body, m, log)]) if s is not None]
        out = [s for s in out if s.name not in {x.name for x in mine}]
        if layer == "skeleton":
            mine = teeth.split(body, m, mine, log)             # each tooth by its name (its place in the row)
        out += mine
        own |= {s.name for s in mine}
        if layer == "skeleton" and mine:
            for s in out:
                if s.name in ("cranium and maxilla", "mandible"):
                    mouth.without_crowns(body, m, s, s.name != "mandible", log)
    if layer == "muscles":
        out += face_muscles.build(body, log)
    if layer == "skeleton":                                # the skull in its bones (the atlas fitted: skull_bones.py)
        whole = next((s for s in out if s.name == skull_bones.WHOLE), None)
        if whole is not None:
            out = [s for s in out if s is not whole] + skull_bones.split(body, whole, log)
    if layer == "organs":
        skin_cache = body.export / "model" / "skin.npz"
        out += face_vessels.build(body, log)                   # the face's vessels and nerves, drawn (generated)
        if skin_cache.exists():                                # the eyeballs sit behind the skin's lids
            whole = body.export / "model" / "skin_surface.npz"
            out += eyes.build(load_structures(skin_cache)[0], log, load_structures(whole)[0] if whole.exists() else None, body)
    if layer in ("muscles", "skeleton"):                   # and nothing of these stands above it there
        feet.under(body, out, log)
    if layer == "muscles":                                 # (the skeleton's part in the hands is seen to above, with its bones)
        hands.under(body, out, log)
    # Nothing of a layer under the skin reaches it anywhere, measured on the triangles (the nostrils, the ear
    # canals and the creases of the face are narrower than these layers' triangles; and with every layer on,
    # fat showed in rings where photographs were passed over, and fingers' bones at five fingertips). Not the
    # teeth and the tongue, which the mouth places, nor the eyeballs, which lie behind the lids by their own
    # rule (eyes.py).
    under = [s for s in out if s.name not in own and not s.name.endswith(" eyeball")]
    no_fat = None
    if m is not None:                                      # (under the red of the lips there is no fat to lie under: fat_shell.lips)
        size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]], np.float64)

        def no_fat(zyx_mm):
            q = np.asarray(zyx_mm, np.float64) - size / 2
            return fat_shell.red_of_the_lips(m, np.stack([q[:, 2], q[:, 1], -q[:, 0]], axis=1) / 1000.0)

    head_layers.under_skin_everywhere(body, under, log, under_fat=layer != "fat", no_fat=no_fat)
    if layer == "fat":                                     # and it is open over the red of the lips (last: its vertices are renumbered)
        fat_shell.lips(body, out, log)
    log(f"{layer}: {len(out)} structures, {sum(s.triangles for s in out)} triangles")
    return out
