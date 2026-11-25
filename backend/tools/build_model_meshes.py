"""The modelled body from real anatomy: every labelled structure of an export as its own smooth mesh, in one GLB.

    .venv-seg/Scripts/python tools/build_model_meshes.py out/photo_body ../unity/Assets/Models/anatomy.glb
    .venv-seg/Scripts/python tools/build_model_meshes.py out/photo_body ../unity/Assets/Models/anatomy.glb --layers skin --preview ../build/preview

Reads the export's labels (labels.raw / labels.json: the SIO structures, the tissue classes by colour, the bone
from CT) and makes the layers, outermost first: skin (the whole body's surface, and a pair of briefs), fat,
muscles, skeleton, organs; each structure is a mesh named as the labels name it. The meshes fit inside one
another, because they come from one body. Nothing of the photographs is in the file: shapes, an atlas colour per
structure (or per vertex) and the shading bake.

Each layer is cached beside the export (<export>/model/<layer>.npz): --layers rebuilds only those named and takes
the others from the cache, so one layer can be worked on without waiting for the rest. --preview renders
pictures of the layers just built (anatomy_model.preview), without Unity.
The package anatomy_model/ holds the parts (see its __init__.py); the GLB's layout is in anatomy_model/glb.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anatomy_model import bonehub, fine_muscle, fine_skin, head_layers, leg_muscles, mouth, names, skull_bones, throat  # noqa: E402
from anatomy_model import layers as object_layers  # noqa: E402
from anatomy_model import skin  # noqa: E402
from anatomy_model.common import LAYERS, Body, load_structures, save_structures  # noqa: E402
from anatomy_model.glb import write_glb  # noqa: E402

BUDGET = {"fat": 0.14, "muscles": 0.30, "skeleton": 0.31, "organs": 0.25}      # shares of --triangles; the skin has its own
FINE_MUSCLES = 2.4              # times the muscles' share when their surfaces come from the photographs (their relief needs the triangles)
PREVIEWS = {"skin": ["front", "face", "face_left", "eyes", "mouth", "ear_left", "profile_left", "chest", "hands", "feet"], "fat": ["front", "chest"], "muscles": ["front", "chest", "legs"],
            "skeleton": ["front", "face", "chest", "hands"], "organs": ["chest", "abdomen"]}


def triangles_for(layer: str, triangles: int, skin_triangles: int, fine_muscles: bool) -> int:
    """A layer's triangles: the skin has its own number; the others their share of `triangles`, the muscles FINE_MUSCLES
    times theirs when their surfaces come from the photographs."""
    if layer == "skin":
        return int(skin_triangles)
    return int(triangles * BUDGET[layer] * (FINE_MUSCLES if layer == "muscles" and fine_muscles else 1.0))


def build_layer(body: Body, layer: str, triangles: int, reuse_surface: bool = False):
    if layer == "skin":
        return skin.build(body, triangles, reuse_surface=reuse_surface)
    return object_layers.build(body, layer, triangles)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("out", type=Path, nargs="?", help="the GLB to write (omit to build caches and previews only)")
    ap.add_argument("--triangles", type=int, default=1_400_000, help="about this many for fat, muscles, skeleton and organs together")
    ap.add_argument("--skin-triangles", type=int, default=900_000, help="the skin's surface (the hair comes on top)")
    ap.add_argument("--photos", type=Path, help="the photographs' folder: (re)reads the fine skin outline from them first (about 12 minutes)")
    ap.add_argument("--muscle-photos", type=Path, help="the photographs' folder: (re)reads the muscles' fine outline from them first (about 14 minutes); "
                                                       "the muscles layer is then meshed from it")
    ap.add_argument("--bones", type=Path, help="BoneHub's folder of .seg.nrrd files: reads and fits the 142 named bones first (about 4 minutes)")
    ap.add_argument("--atlas", type=Path, help="BodyParts3D's folder (its .obj files and isa_element_parts.txt): fits its skull bones to his skull first, "
                                               "so the skull is built as its named bones (once; about half a minute)")
    ap.add_argument("--legs", type=Path, help="the University of Denver set's folder of STL files (VHM_Left_Muscle_..._smooth.stl): places the hips' and legs' named "
                                              "muscles, the knee's ligaments and the joints' cartilage first (once; about a minute)")
    ap.add_argument("--head-ct", type=Path, help="the frozen CT's folder: labels the head and neck on it with TotalSegmentator's open tasks first (GPU, once)")
    ap.add_argument("--layers", default="", help="rebuild only these layers (comma separated); the others come from the cache")
    ap.add_argument("--skin-reuse", action="store_true", help="keep the skin's surface of the last build; redo its colour zones, lids and hair only")
    ap.add_argument("--preview", type=Path, help="write pictures of the rebuilt layers into this folder")
    args = ap.parse_args()
    body = Body(args.export)
    body.eyes_measured = skin.measured_eyes(body)                    # before the labels are read: they are cleared round the eyes
    if args.photos:
        fine_skin.extract(body, args.photos)
    fine = fine_skin.load(body)
    if fine is not None:
        body.keep_inside(fine_skin.inside_export(body, fine))      # nothing under the skin may reach outside it
    if args.muscle_photos:
        fine_muscle.extract(body, args.muscle_photos)
    body.original_labels = body.labels.copy()                      # before the named structures are taken out of the unnamed masses (fine_muscle.surfaces)
    if args.head_ct:
        head_layers.segment(body, args.head_ct)
    head_layers.carve(body)                                        # the named head and neck structures out of the unnamed mass
    if args.bones:
        bonehub.cache_path(body).unlink(missing_ok=True)
        bonehub.load_or_build(body, args.bones)
    if bonehub.cache_path(body).exists():                          # whole bones for the landmarks (ours stop where the SIO stops)
        placed, _, _ = bonehub.load_or_build(body, None)
        body.extra_bones = {}
        for _, name, v, f in placed:
            g, _ = body.to_gltf(v, f)
            body.extra_bones[name] = (g.min(axis=0).astype(float), g.max(axis=0).astype(float))
        if args.atlas:                                             # the skull's bones: the atlas fitted to his skull
            _, _, whole_v, whole_f = next(b for b in placed if b[1] == skull_bones.WHOLE)
            skull_bones.fit_atlas(body, args.atlas, whole_v, whole_f)
        if args.legs:                                              # the hips' and legs' muscles, placed by their own bones on BoneHub's
            leg_muscles.cache_path(body).unlink(missing_ok=True)
            leg_muscles.load_or_build(body, args.legs)
    elif args.atlas or args.legs:
        raise SystemExit("--atlas and --legs need the BoneHub bones first (run once with --bones)")
    leg_muscles.carve(body)                                        # the named leg muscles out of the unnamed mass
    cache = args.export / "model"
    body.head_ct_dir = args.head_ct
    whole_skin = cache / "skin_surface.npz"
    if whole_skin.exists() and len(body.eyes_measured or []) == 2:  # the mouth, measured on the skin as last built (the skin layer measures it again on a new surface)
        from anatomy_model.zones import Face
        surface = load_structures(whole_skin)[0]
        mouth.prepare(body, Face(skin.landmarks(body), surface.v), surface.v, args.head_ct)
    chosen = [x for x in args.layers.split(",") if x] or LAYERS
    unknown = [x for x in chosen if x not in LAYERS]
    if unknown:
        raise SystemExit(f"unknown layer(s) {unknown}; layers are {LAYERS}")
    structures = []
    for layer in LAYERS:
        path = cache / f"{layer}.npz"
        if layer in chosen or not path.exists():
            built = build_layer(body, layer, triangles_for(layer, args.triangles, args.skin_triangles, fine_muscle.load(body) is not None), args.skin_reuse)
            save_structures(path, built)
            if args.preview:
                from anatomy_model.preview import render
                for view in PREVIEWS[layer]:
                    render(built, view, out=args.preview / f"{layer}_{view}.png")
        else:
            built = load_structures(path)
            print(f"{layer}: {len(built)} structures from the cache")
        structures += built
    if getattr(body, "mouth", None) is not None:                   # every structure's share in the jaw's turn
        throat.tuck(structures, body, body.mouth)                  # (first: nothing of the layers under the skin stands in the throat as drawn)
        moved = mouth.assign(structures, body, body.mouth)
        print(f"mouth: {moved} structures go with the jaw, wholly or in part")
    if args.out:
        write_glb(args.out, structures)
        # What Unity needs to know beside the meshes (the importer does not hand over a node's extras).
        skin_info = next((s.info for s in structures if s.name == "skin"), {})
        args.out.with_suffix(".json").write_text(json.dumps({"eyes": skin_info.get("eyes"), "mouth": skin_info.get("mouth"), "landmarks": skin_info.get("landmarks")}, indent=1))
        print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, {len(structures)} structures, {sum(s.triangles for s in structures)} triangles)")
        # Every structure's name in Latin, English and Italian, and whether it is read from him or drawn: the table
        # the app reads when a structure is tapped (it stops the build if a structure has no name).
        names.write(args.out.parent.parent / "StreamingAssets" / "anatomy" / "model_names.json", structures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
