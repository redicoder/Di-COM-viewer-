"""What lies under the face and in the neck, labelled on his own CT by TotalSegmentator's open tasks.

The labels we hold name nothing in the head and neck beyond bone, grey and white matter. TotalSegmentator
(Wasserthal et al., code Apache-2.0) has tasks for the head that are open for any use (not in its list of
licensed tasks): the chewing muscles, tongue and digastrics; the neck's muscles; the salivary glands, eyes,
optic nerves, pharynx and palate; the larynx's cartilages, hyoid, carotids and jugulars; the teeth; the eyes'
muscles. They are run once on the CT of the head and neck (ct_frame.volume) and the label volumes kept beside
the export; each label then becomes a mesh, placed in the body by ct_frame.CtToBody.

    segment(body, ct_dir)            # GPU, some minutes per task, weights downloaded on first use
    structures = build(body, ...)    # the meshes, for the muscles and the organs layers

A frozen body's CT is not what the tool was trained on (frozen tissue is less dense, and there is no contrast):
what it finds is checked by size before it is used, and a structure it finds almost nothing of is left out.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from . import ct_frame, fine_skin
from .common import Baker, Body, Structure, decimate, surface

FIRST, LAST = 1006, 1420                         # the photographs' slice numbers: the top of the head to the shoulders
TASKS = ["head_muscles", "headneck_muscles", "head_glands_cavities", "headneck_bones_vessels", "craniofacial_structures", "oculomotor_muscles"]

# label -> (layer, the name shown, sRGB colour, the least volume in cm3 to be believed); labels not listed are not used
MUSCLE, GLAND, CARTILAGE, ARTERY, VEIN, NERVE, TOOTH = (0.50, 0.23, 0.21), (0.80, 0.62, 0.50), (0.86, 0.84, 0.76), (0.66, 0.20, 0.18), (0.38, 0.42, 0.56), (0.92, 0.86, 0.66), (0.93, 0.91, 0.84)
USE = {
    "head_muscles": {
        "masseter": ("muscles", "masseter", MUSCLE, 6), "temporalis": ("muscles", "temporalis", MUSCLE, 8),
        "lateral_pterygoid": ("muscles", "lateral pterygoid", MUSCLE, 2), "medial_pterygoid": ("muscles", "medial pterygoid", MUSCLE, 2),
        "digastric": ("muscles", "digastric", MUSCLE, 1), "tongue": ("organs", "tongue", (0.72, 0.36, 0.36), 30),
    },
    "headneck_muscles": {
        "sternocleidomastoid": ("muscles", "sternocleidomastoid", MUSCLE, 10), "trapezius": ("muscles", "trapezius", MUSCLE, 30),
        "levator_scapulae": ("muscles", "levator scapulae", MUSCLE, 5), "anterior_scalene": ("muscles", "anterior scalene", MUSCLE, 1.5),
        "middle_scalene": ("muscles", "middle scalene", MUSCLE, 1.5), "posterior_scalene": ("muscles", "posterior scalene", MUSCLE, 1),
        "platysma": ("muscles", "platysma", MUSCLE, 2), "prevertebral": ("muscles", "prevertebral muscles", MUSCLE, 3),
        "sterno_thyroid": ("muscles", "sternothyroid", MUSCLE, 0.5), "thyrohyoid": ("muscles", "thyrohyoid", MUSCLE, 0.3),
        "superior_pharyngeal_constrictor": ("muscles", "superior pharyngeal constrictor", MUSCLE, 0.5),
        "middle_pharyngeal_constrictor": ("muscles", "middle pharyngeal constrictor", MUSCLE, 0.3),
        "inferior_pharyngeal_constrictor": ("muscles", "inferior pharyngeal constrictor", MUSCLE, 0.3),
    },
    "head_glands_cavities": {
        "parotid_gland": ("organs", "parotid gland", GLAND, 6), "submandibular_gland": ("organs", "submandibular gland", GLAND, 2),
        "optic_nerve": ("organs", "optic nerve", NERVE, 0.15), "soft_palate": ("organs", "soft palate", (0.80, 0.50, 0.48), 3),
    },
    "headneck_bones_vessels": {
        "thyroid_cartilage": ("skeleton", "thyroid cartilage", CARTILAGE, 2), "cricoid_cartilage": ("skeleton", "cricoid cartilage", CARTILAGE, 0.8),
        "hyoid": ("skeleton", "hyoid bone", (0.88, 0.84, 0.74), 0.5),
        "internal_carotid_artery": ("organs", "internal carotid artery", ARTERY, 0.5), "internal_jugular_vein": ("organs", "internal jugular vein", VEIN, 1),
    },
    "craniofacial_structures": {
        "teeth_upper": ("skeleton", "upper teeth", TOOTH, 3), "teeth_lower": ("skeleton", "lower teeth", TOOTH, 3),
    },
    "oculomotor_muscles": {
        "lateral_rectus_muscle": ("muscles", "lateral rectus", MUSCLE, 0.2), "medial_rectus_muscle": ("muscles", "medial rectus", MUSCLE, 0.2),
        "superior_rectus_muscle": ("muscles", "superior rectus", MUSCLE, 0.2), "inferior_rectus_muscle": ("muscles", "inferior rectus", MUSCLE, 0.2),
        "superior_oblique_muscle": ("muscles", "superior oblique", MUSCLE, 0.15), "inferior_oblique_muscle": ("muscles", "inferior oblique", MUSCLE, 0.1),
        "levator_palpebrae_superioris": ("muscles", "levator palpebrae superioris", MUSCLE, 0.15),
    },
}


def folder(body: Body) -> Path:
    return body.export / "model" / "ts_head"


def write_nifti(vol: ct_frame.CtVolume, path: Path) -> None:
    """The CT volume as NIfTI: voxel (column, row, slice); to the patient's right, front and head in RAS."""
    import nibabel as nib
    g = ct_frame.GRID_MM
    affine = np.array([[-g, 0, 0, -(ct_frame.GRID_ORIGIN[0] + 0.5 * g)], [0, -g, 0, -(ct_frame.GRID_ORIGIN[1] + 0.5 * g)], [0, 0, -1.0, 0], [0, 0, 0, 1.0]])
    nib.save(nib.Nifti1Image(np.ascontiguousarray(np.transpose(vol.hu, (2, 1, 0))), affine), str(path))


def segment(body: Body, ct_dir: Path, tasks=TASKS, log=print) -> None:
    """Runs the tasks on the head and neck CT; one multi-label NIfTI and its label names per task, kept."""
    from totalsegmentator.map_to_binary import class_map
    from totalsegmentator.python_api import totalsegmentator
    out = folder(body)
    out.mkdir(parents=True, exist_ok=True)
    vol = ct_frame.volume(ct_dir, FIRST, LAST, body.export / "model" / "ct_head.npz", log)
    ct_path = out / "ct.nii.gz"
    if not ct_path.exists():
        write_nifti(vol, ct_path)
    for task in tasks:
        target = out / f"{task}.nii.gz"
        if target.exists():
            log(f"head layers: {task} already there")
            continue
        log(f"head layers: {task} ...")
        totalsegmentator(str(ct_path), str(target), task=task, ml=True, quiet=True)
        (out / f"{task}.json").write_text(json.dumps({str(k): v for k, v in class_map[task].items()}))
        log(f"head layers: {task} done")


def read_labels(body: Body, task: str):
    """A task's label volume in the CtVolume's order (slices, rows, columns) and its names by value; None if not run."""
    import nibabel as nib
    path = folder(body) / f"{task}.nii.gz"
    if not path.exists():
        return None
    data = np.asarray(nib.load(str(path)).dataobj)
    names = {int(k): v for k, v in json.loads((folder(body) / f"{task}.json").read_text()).items()}
    return np.ascontiguousarray(np.transpose(data, (2, 1, 0))).astype(np.uint8), names


def side_of(label: str) -> tuple[str, str]:
    """('masseter', 'right') for masseter_right or eyeball_right; side '' where the label has none."""
    for side in ("right", "left"):
        if label.endswith("_" + side):
            return label[:-len(side) - 1], side
    return label, ""


def believed(body: Body, vol: ct_frame.CtVolume):
    """Yields (task, label, layer, name, colour, cm3, block, box) for every label that is used and big enough;
    labels left out are yielded with block None."""
    voxel_cm3 = float(np.prod(vol.spacing)) / 1000.0
    for task, wanted in USE.items():
        got = read_labels(body, task)
        if got is None:
            continue
        data, names = got
        boxes = ndimage.find_objects(data.astype(np.int32), max_label=int(data.max()))
        for value, label in sorted(names.items()):
            stem, side = side_of(label)
            if stem not in wanted or value > len(boxes) or boxes[value - 1] is None:
                continue
            layer, shown, colour, least = wanted[stem]
            box = boxes[value - 1]
            block = data[box] == value
            cm3 = float(block.sum()) * voxel_cm3
            name = f"{side} {shown}".strip()
            if cm3 < least:
                yield task, label, layer, name, colour, cm3, None, box
                continue
            parts, count = ndimage.label(block)                           # the biggest pieces only: specks lie elsewhere
            if count > 1:
                sizes = ndimage.sum(block, parts, range(1, count + 1))
                block = np.isin(parts, 1 + np.nonzero(sizes >= 0.15 * sizes.max())[0])
            yield task, label, layer, name, colour, cm3, block, box


def carve(body: Body, log=print) -> int:
    """Takes the named structures' places out of the body's unnamed muscle mass and fat, so each shows as itself
    and not as a lump inside the mass. Returns how many voxels were freed."""
    cache = body.export / "model" / "ct_head.npz"
    if not cache.exists() or not folder(body).exists():
        return 0
    vol = ct_frame.volume(None, FIRST, LAST, cache, log)
    to_body = ct_frame.CtToBody(body, vol)
    lab = body.labels
    loose = [o["index"] for o in body.objects if o["name"] in ("muscles", "subcutaneous fat")]
    spacing, dims = np.array(body.spacing), np.array(lab.shape)
    freed = 0
    lo, hi = dims.copy(), np.zeros(3, np.int64)
    for _, _, _, _, _, _, block, box in believed(body, vol):
        if block is None:
            continue
        index = np.argwhere(ndimage.binary_dilation(block)) + np.array([s.start for s in box]) + 0.5
        at = np.floor(to_body.grid_points(index) / spacing).astype(np.int64)
        at = at[((at >= 0) & (at < dims)).all(axis=1)]
        if len(at) == 0:
            continue
        lo, hi = np.minimum(lo, at.min(axis=0)), np.maximum(hi, at.max(axis=0) + 1)
        here = lab[at[:, 0], at[:, 1], at[:, 2]]
        hit = np.isin(here, loose)
        lab[at[hit, 0], at[hit, 1], at[hit, 2]] = 0
        freed += int(hit.sum())
    # What the carving left of the unnamed muscle between and round the named ones: shells and fins a voxel or two
    # thick. Only what has some body to it stays.
    muscle = next((o["index"] for o in body.objects if o["name"] == "muscles"), None)
    if muscle is not None and (hi > lo).all():
        region = tuple(slice(int(max(0, a - 3)), int(min(d, b + 3))) for a, b, d in zip(lo, hi, dims))
        mass = lab[region] == muscle
        thin = mass & ~ndimage.binary_opening(mass, structure=np.ones((3, 3, 3), bool))
        lab[region][thin] = 0
        freed += int(thin.sum())
    counts = np.bincount(lab.ravel(), minlength=256)
    for o in body.objects:
        o["voxels"] = int(counts[o["index"]])
    log(f"head layers: {freed} voxels of the unnamed muscle and fat given to named structures")
    return freed


_built: dict = {}


def structures(body: Body, layer: str, log=print) -> list[Structure]:
    """The head's and neck's named structures of one layer (built once per run)."""
    cache = body.export / "model" / "ct_head.npz"
    if not cache.exists() or not folder(body).exists():
        return []
    key = str(body.export)
    if key not in _built:
        _built[key] = build(body, None, log=log)
    return [s for s in _built[key] if s.layer == layer]


def build(body: Body, ct_dir: Path | None, triangles_each: int = 9000, log=print) -> list[Structure]:
    """Every believed label as a mesh in the body (all layers together; the caller sorts them by .layer)."""
    vol = ct_frame.volume(ct_dir, FIRST, LAST, body.export / "model" / "ct_head.npz", log)
    to_body = ct_frame.CtToBody(body, vol)
    spacing = vol.spacing
    baker = Baker(body)
    # What shades them: the muscles, bones and organs round them (not the skin and fat over them, or every one of
    # them would be baked as lying in the dark).
    deep = [o["index"] for o in body.objects if o["layer"] in ("muscle", "bone", "organ")]
    occupancy = baker.field(np.isin(body.labels, deep))
    out, report = [], []
    for task, label, layer, name, colour, cm3, block, box in believed(body, vol):
        if block is None:
            report.append(f"{name} {cm3:.1f} cm3 (left out: too little)")
            continue
        found = surface(block, spacing, 1.0, [s.start for s in box])
        if found is None or len(found[1]) < 8:
            continue
        v, f = found
        v_body = to_body.grid_points(v / np.array(spacing))               # the surface's millimetres are grid index times spacing
        v, f = decimate(v_body.astype(np.float32), f, triangles_each)
        v, f = body.to_gltf(v, f)
        out.append(Structure(name, layer, v, f, colour, bake=baker.colours(v, f, occupancy),
                             info={"source": "TotalSegmentator " + task, "label": label, "class": layer, "cm3": round(cm3, 1)}))
        report.append(f"{name} {cm3:.1f} cm3")
    log("head layers: " + "; ".join(report))
    tuck_under_skin(body, out, log=log)
    return out


def tuck_under_skin(body: Body, structures: list[Structure], least_mm: float = 1.8, log=print) -> int:
    """Draws under the skin what lies at it or outside it. The structures are placed from the CT, which fits the
    photographs to a millimetre or two; where a muscle lies right under the skin (the sternocleidomastoid on the
    neck, the temporalis) that is enough for it to show through. Such vertices go inwards, along the way the
    depth under the fine skin outline grows, until `least_mm` of skin lies over them. Returns how many moved."""
    fine = fine_skin.load(body)
    if fine is None or not structures:
        return 0
    size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]])       # z, y, x

    def to_mm(v):
        p = np.asarray(v, np.float64) * 1000.0
        return np.stack([-p[:, 2], p[:, 1], p[:, 0]], axis=1) + size / 2

    step = 2                                                                    # every second voxel of the outline: 1.3 x 2 x 1.3 mm
    spacing = np.array(fine.spacing, np.float64) * step
    origin = np.array(fine.origin_mm, np.float64)
    every = np.concatenate([to_mm(s.v) for s in structures])
    lo = np.maximum(np.floor((every.min(axis=0) - 8.0 - origin) / spacing).astype(int), 0)
    hi = np.minimum(np.ceil((every.max(axis=0) + 8.0 - origin) / spacing).astype(int), np.array(fine.cover.shape) // step)
    block = np.asarray(fine.cover[lo[0] * step:hi[0] * step:step, lo[1] * step:hi[1] * step:step, lo[2] * step:hi[2] * step:step]) > 127
    depth = ndimage.distance_transform_edt(np.pad(block, 1, constant_values=True), sampling=spacing)[1:-1, 1:-1, 1:-1].astype(np.float32)
    depth = ndimage.gaussian_filter(depth, 0.7)
    slope = np.gradient(depth, *spacing)
    corner = origin + lo * spacing * 1.0 + (step - 1) * np.array(fine.spacing) / 2      # the block's first voxel's corner (a coarse voxel spans `step` fine ones)
    moved, names = 0, []
    for s in structures:
        mm = to_mm(s.v)
        first = mm.copy()
        for _ in range(4):
            at = ((mm - corner) / spacing - 0.5).T
            d = ndimage.map_coordinates(depth, at, order=1, mode="nearest")
            shallow = d < least_mm
            if not shallow.any():
                break
            g = np.stack([ndimage.map_coordinates(c, at[:, shallow], order=1, mode="nearest") for c in slope], axis=1)
            g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
            mm[shallow] += g * (least_mm - d[shallow] + 0.2)[:, None]
        changed = np.linalg.norm(mm - first, axis=1) > 0.05
        if changed.any():
            p = mm - size / 2
            s.v = (np.stack([p[:, 2], p[:, 1], -p[:, 0]], axis=1) / 1000.0).astype(np.float32)
            moved += int(changed.sum())
            names.append(f"{s.name} {int(changed.sum())}")
    if moved:
        log("head layers: drawn under the skin (vertices): " + "; ".join(names))
    return moved
