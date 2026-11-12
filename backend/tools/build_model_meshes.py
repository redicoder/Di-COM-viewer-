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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anatomy_model import bonehub, fine_skin  # noqa: E402
from anatomy_model import layers as object_layers  # noqa: E402
from anatomy_model import skin  # noqa: E402
from anatomy_model.common import LAYERS, Body, load_structures, save_structures  # noqa: E402
from anatomy_model.glb import write_glb  # noqa: E402

BUDGET = {"fat": 0.14, "muscles": 0.30, "skeleton": 0.31, "organs": 0.25}      # shares of --triangles; the skin has its own
PREVIEWS = {"skin": ["front", "face", "face_left", "chest", "hands", "feet"], "fat": ["front", "chest"], "muscles": ["front", "chest", "legs"],
            "skeleton": ["front", "face", "chest", "hands"], "organs": ["chest", "abdomen"]}


def build_layer(body: Body, layer: str, triangles: int):
    if layer == "skin":
        return skin.build(body, triangles)
    return object_layers.build(body, layer, triangles)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("export", type=Path)
    ap.add_argument("out", type=Path, nargs="?", help="the GLB to write (omit to build caches and previews only)")
    ap.add_argument("--triangles", type=int, default=1_400_000, help="about this many for fat, muscles, skeleton and organs together")
    ap.add_argument("--skin-triangles", type=int, default=600_000, help="the skin's surface (the hair comes on top)")
    ap.add_argument("--photos", type=Path, help="the photographs' folder: (re)reads the fine skin outline from them first (about 12 minutes)")
    ap.add_argument("--bones", type=Path, help="BoneHub's folder of .seg.nrrd files: reads and fits the 142 named bones first (about 4 minutes)")
    ap.add_argument("--layers", default="", help="rebuild only these layers (comma separated); the others come from the cache")
    ap.add_argument("--preview", type=Path, help="write pictures of the rebuilt layers into this folder")
    args = ap.parse_args()
    body = Body(args.export)
    if args.photos:
        fine_skin.extract(body, args.photos)
    fine = fine_skin.load(body)
    if fine is not None:
        body.keep_inside(fine_skin.inside_export(body, fine))      # nothing under the skin may reach outside it
    if args.bones:
        bonehub.cache_path(body).unlink(missing_ok=True)
        bonehub.load_or_build(body, args.bones)
    if bonehub.cache_path(body).exists():                          # whole bones for the landmarks (ours stop where the SIO stops)
        placed, _, _ = bonehub.load_or_build(body, None)
        body.extra_bones = {}
        for _, name, v, f in placed:
            g, _ = body.to_gltf(v, f)
            body.extra_bones[name] = (g.min(axis=0).astype(float), g.max(axis=0).astype(float))
    cache = args.export / "model"
    chosen = [x for x in args.layers.split(",") if x] or LAYERS
    unknown = [x for x in chosen if x not in LAYERS]
    if unknown:
        raise SystemExit(f"unknown layer(s) {unknown}; layers are {LAYERS}")
    structures = []
    for layer in LAYERS:
        path = cache / f"{layer}.npz"
        if layer in chosen or not path.exists():
            built = build_layer(body, layer, args.skin_triangles if layer == "skin" else int(args.triangles * BUDGET[layer]))
            save_structures(path, built)
            if args.preview:
                from anatomy_model.preview import render
                for view in PREVIEWS[layer]:
                    render(built, view, out=args.preview / f"{layer}_{view}.png")
        else:
            built = load_structures(path)
            print(f"{layer}: {len(built)} structures from the cache")
        structures += built
    if args.out:
        write_glb(args.out, structures)
        print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, {len(structures)} structures, {sum(s.triangles for s in structures)} triangles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
