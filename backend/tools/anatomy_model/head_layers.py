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


def each_under_skin(body: Body, structures: list[Structure], least_mm: float = 1.2, log=print) -> int:
    """tuck_under_skin for structures from anywhere in the body (the bones): each is measured by itself
    (fine_skin.drawn_under), at the outline's own fineness, and what stands outside the skin comes in as well.
    Returns how many vertices moved."""
    fine = fine_skin.load(body)
    if fine is None:
        return 0
    size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]])       # z, y, x
    moved, names = 0, []
    for s in structures:
        if len(s.v) == 0:
            continue
        p = np.asarray(s.v, np.float64) * 1000.0
        mm = np.stack([-p[:, 2], p[:, 1], p[:, 0]], axis=1) + size / 2
        new = fine_skin.drawn_under(fine, mm, least_mm)
        far = np.linalg.norm(new - mm, axis=1)
        if (far > 0.05).any():
            q = new - size / 2
            s.v = (np.stack([q[:, 2], q[:, 1], -q[:, 0]], axis=1) / 1000.0).astype(np.float32)
            moved += int((far > 0.05).sum())
            names.append(f"{s.name} {int((far > 0.05).sum())} (by up to {far.max():.1f} mm)")
    if moved:
        log(f"drawn under the skin, {moved} vertices: " + "; ".join(names))
    return moved


HEAD_MM = 1640.0                # the head, for faces_under_skin: what lies above this (mm up from the lowest photograph)
NECK_MM = 1540.0                # ... and the neck: from here up to the head
FEET_MM = 190.0                 # the feet: what lies below this (fine_skin.TOES_MM)
BAND_MM = 150.0                 # the rest of him is measured in bands this high
COARSE_MM = 1.8                 # the least depth where it is measured at half the outline's fineness (the neck, the trunk,
                                # the limbs): the depth read there may be up to a millimetre more than it is
JOINT_MM = 3.8                  # the least depth where photographs were passed over (see under_skin_everywhere); read coarsely
JOINT_REACH_MM = 12.0           # ... and for this far either side of them, less and less
SPREAD = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1 / 3, 1 / 3, 1 / 3], [0.5, 0.5, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.6, 0.2, 0.2], [0.2, 0.6, 0.2], [0.2, 0.2, 0.6]])


def head_depth(body: Body, fine: fine_skin.FineOutline, from_mm: float = HEAD_MM, to_mm: float | None = None, box: tuple | None = None, fine_grid: bool = True):
    """The depth under the skin throughout the head, or between two heights, or in a box of them (z0, z1, x0, x1:
    mm, the body's axes) (fine_skin.depth_near's field), measured once for a run: kept on the body.

    `fine_grid`: at the outline's own fineness if the box is not too large (a nostril is 6 mm across, the cleft
    between two fingers a millimetre and a half); without it at half of that, which is enough for the trunk and
    the limbs and an eighth of the work."""
    kept = getattr(body, "_head_depth", None)
    if kept is None:
        kept = body._head_depth = {}
    key = (from_mm, to_mm, box, fine_grid)
    if key in kept:
        return kept[key]
    spacing, origin = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64)
    j0 = max(0, int((from_mm - 8.0 - origin[1]) / spacing[1]))
    j1 = fine.cover.shape[1] if to_mm is None else min(fine.cover.shape[1], int((to_mm + 8.0 - origin[1]) / spacing[1]) + 1)
    if j1 <= j0:
        return None
    if box is None:
        him = np.asarray(fine.cover[:, j0:j1, :]) > 127
        zz, xx = np.flatnonzero(him.any(axis=(1, 2))), np.flatnonzero(him.any(axis=(0, 1)))
        if len(zz) == 0:
            return None
        corners = origin + (np.array([[zz[0], j0, xx[0]], [zz[-1], j1 - 1, xx[-1]]]) + 0.5) * spacing
    else:
        corners = np.array([[box[0], origin[1] + (j0 + 0.5) * spacing[1], box[2]], [box[1], origin[1] + (j1 - 0.5) * spacing[1], box[3]]])
    field = fine_skin.depth_near(fine, corners, 6.0, most_voxels=7e7 if fine_grid else 1.0)
    if field is None:
        return None
    kept[key] = field
    return field


def joints_of(fine: fine_skin.FineOutline) -> list[tuple[float, float]]:
    """The stretches of him (mm up, from and to) whose photographs were passed over (FineOutline.fallback)."""
    blank = np.flatnonzero(np.asarray(fine.fallback))
    if len(blank) == 0:
        return []
    origin, step = float(fine.origin_mm[1]), float(fine.spacing[1])
    return [(origin + run[0] * step, origin + (run[-1] + 1) * step) for run in np.split(blank, np.flatnonzero(np.diff(blank) > 1) + 1)]


def faces_under_skin(body: Body, structures: list[Structure], least_mm: float = 1.0, drop_mm: float = 0.5, from_mm: float = HEAD_MM, to_mm: float | None = None,
                     box: tuple | None = None, fine_grid: bool = True, joints: list | None = None, label: str = "head", log=print) -> tuple[int, int]:
    """In one part of him (above `from_mm`; or between two heights; or in a box of them, z0, z1, x0, x1): no
    TRIANGLE of a structure under the skin reaches the skin. Returns (vertices moved, triangles taken out).

    The other rules look at vertices (tuck_under_skin, each_under_skin). The head's skin, read from its tissue,
    has what the old outline smoothed over: the nostrils, the ear canals, the creases beside the nose and round
    the lids, each a few millimetres across; and the layers under it are meshed in triangles of 2 to 5 mm. A
    triangle whose corners all lie well under the skin can cross a crease, or a nostril from wall to wall (the
    fat showed yellow in both nostrils and in the ear). So points spread over every triangle are measured against
    the fine outline:

    - a triangle that comes nearer the skin than `least_mm` anywhere sinks: its corners go inwards, the way the
      depth grows, by what it lacks (three rounds: its neighbours' corners come with it). Where photographs
      were passed over (`joints`: from and to, mm up) the least is JOINT_MM, falling back to `least_mm` over
      JOINT_REACH_MM either side (under_skin_everywhere says why);
    - one that still lies nearer than `drop_mm` after that, or outside, is taken out: it crosses an opening its
      corners cannot leave (a nostril, an ear canal: there the layer under the skin has a hole too, as it has
      in him)."""
    fine = fine_skin.load(body)
    got = head_depth(body, fine, from_mm, to_mm, box, fine_grid) if fine is not None else None
    if got is None:
        return 0, 0
    depth, lo, step = got
    spacing, origin = np.array(fine.spacing, np.float64), np.array(fine.origin_mm, np.float64)
    size = np.array([body.size_mm[2], body.size_mm[1], body.size_mm[0]], np.float64)       # z, y, x

    def at(points):
        return (((points - origin) / spacing - 0.5 - lo) / step).T

    def deep(points):
        return ndimage.map_coordinates(depth, at(points), order=1, mode="nearest")

    def inwards(points):                                                        # the way the depth grows, at each point
        g = np.zeros((len(points), 3))
        for axis in range(3):
            h = np.zeros(3)
            h[axis] = spacing[axis] * step
            g[:, axis] = (deep(points + h) - deep(points - h)) / (2 * h[axis])
        return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)

    def least_at(heights):                                                      # the least depth wanted at each height
        need = np.full(np.shape(heights), float(least_mm))
        for a, b in joints or []:
            away = np.maximum(np.maximum(a - heights, heights - b), 0.0)
            need = np.maximum(need, least_mm + (JOINT_MM - least_mm) * np.clip(1.0 - away / JOINT_REACH_MM, 0.0, 1.0))
        return need

    moved, dropped, names = 0, 0, []
    for s in structures:
        if s.streams or len(s.v) == 0 or len(s.f) == 0:
            continue
        p = np.asarray(s.v, np.float64) * 1000.0
        mm = np.stack([-p[:, 2], p[:, 1], p[:, 0]], axis=1) + size / 2
        f = np.asarray(s.f, np.int64)
        here = (mm[:, 1] > from_mm) & (mm[:, 1] < (np.inf if to_mm is None else to_mm))
        if box is not None:
            here &= (mm[:, 0] > box[0]) & (mm[:, 0] < box[1]) & (mm[:, 2] > box[2]) & (mm[:, 2] < box[3])
        head = np.flatnonzero(here[f].all(axis=1))
        if len(head) == 0:
            continue
        first = mm.copy()

        def lacking():
            """Per triangle: how much it lacks of the depth wanted (positive: too shallow), and its least depth."""
            points = np.einsum("kw,nwc->nkc", SPREAD, mm[f[head]])
            d = deep(points.reshape(-1, 3)).reshape(-1, len(SPREAD))
            return (least_at(points[..., 1]) - d).max(axis=1), d.min(axis=1)

        for _ in range(3):
            lack, _ = lacking()
            bad = lack > 0
            if not bad.any():
                break
            lacks = np.zeros(len(mm))
            np.maximum.at(lacks, f[head[bad]].ravel(), np.repeat(np.minimum(lack[bad] + 0.3, 5.0), 3))
            todo = np.flatnonzero(lacks > 0)
            wanted = deep(mm[todo]) + lacks[todo]
            for _ in range(5):
                d = deep(mm[todo])
                shallow = d < wanted
                if not shallow.any():
                    break
                mm[todo[shallow]] += inwards(mm[todo[shallow]]) * np.minimum(wanted[shallow] - d[shallow] + 0.1, 2.0)[:, None]
        far = np.linalg.norm(mm - first, axis=1)
        over = far > 6.0                                                        # none by more than this
        mm[over] = first[over] + (mm[over] - first[over]) * (6.0 / far[over])[:, None]
        out = lacking()[1] < drop_mm
        changed = int((far > 0.05).sum())
        if changed:
            q = mm - size / 2
            s.v = (np.stack([q[:, 2], q[:, 1], -q[:, 0]], axis=1) / 1000.0).astype(np.float32)
        if out.any():
            keep = np.ones(len(f), bool)
            keep[head[out]] = False
            s.f = np.asarray(s.f)[keep]
        if changed or out.any():
            moved, dropped = moved + changed, dropped + int(out.sum())
            names.append(f"{s.name} {changed}/{int(out.sum())}")
    if names:
        log(f"{label}: no triangle under the skin reaches it: {moved} vertices moved in, {dropped} triangles across an opening taken out (vertices/triangles): " + "; ".join(names))
    return moved, dropped


def under_skin_everywhere(body: Body, structures: list[Structure], log=print) -> tuple[int, int]:
    """faces_under_skin for all of him, part by part. Returns (vertices moved, triangles taken out).

    First run in the head and the neck only (2026-11-24). Then, with every layer on, the body was looked at from
    sixteen sides and every pixel asked which mesh is in front (ModelSnapshot.RunThrough): 2620 pixels were not
    skin. Two things showed:

    - FAT, in three rings round him: at the knees, the hips and across the chest, exactly where photographs were
      passed over (FineOutline.fallback: frost over a cut face where two blocks of the specimen meet). The skin's
      mesh is let move 2.25 mm there when it is relaxed (skin.tolerance: the outline steps at those joints),
      0.45 mm elsewhere, and what lies under it was kept 1.4 mm under the OUTLINE. So there the least is JOINT_MM
      (2.8 mm truly, at the least: see the next paragraph);
    - the FINGERS' BONES at five fingertips (the right ring finger's by 5.7 mm): each finger's bones are moved as
      one piece into the finger (hands.under), and a finger that was bent otherwise in the CT than under the
      camera does not fit in as one piece. What still stands out goes in here, corner by corner.

    The head and the hands are measured at the outline's own 0.66 mm (the nostrils; the clefts between the
    fingers); the neck, the trunk and the limbs at half of that, in bands; the feet as the hands. A depth is
    counted from voxel to voxel (fine_skin.depth_near), so it reads half a voxel more than it is, and at half
    the fineness up to a whole millimetre: there the least is COARSE_MM, which is 0.8 mm truly at the least."""
    fine = fine_skin.load(body)
    if fine is None:
        return 0, 0
    joints = joints_of(fine)
    total = np.zeros(2, int)
    total += faces_under_skin(body, structures, label="head", log=log)
    total += faces_under_skin(body, structures, least_mm=COARSE_MM, from_mm=NECK_MM, to_mm=HEAD_MM + 10.0, fine_grid=False, joints=joints, label="neck", log=log)
    for k, (z0, z1, y0, y1, x0, x1) in enumerate(fine_skin.hand_boxes(body)):
        total += faces_under_skin(body, structures, from_mm=y0, to_mm=y1, box=(z0, z1, x0, x1), joints=joints, label=f"hand {k + 1}", log=log)
    total += faces_under_skin(body, structures, from_mm=-1.0, to_mm=FEET_MM + 10.0, joints=joints, label="feet", log=log)
    for a in np.arange(FEET_MM, NECK_MM, BAND_MM):
        total += faces_under_skin(body, structures, least_mm=COARSE_MM, from_mm=float(a), to_mm=float(min(a + BAND_MM, NECK_MM)) + 10.0, fine_grid=False,
                                  joints=joints, label=f"{a:.0f} to {min(a + BAND_MM, NECK_MM):.0f} mm up", log=log)
    return int(total[0]), int(total[1])
