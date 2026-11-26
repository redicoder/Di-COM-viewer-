"""Organs the labels have only as a thin wall: the windpipe, the bronchi, the heart's sac.

Every labelled object is blurred a little and contoured (layers.py). That makes a surface of anything a few voxels
thick, and rags of a wall that is one voxel thick. Three objects of the chest are such walls (looked at on
2026-11-26, when the organs were brought up to the skin's standard; docs/research/under_layers.md, section 7):

- THE WINDPIPE. The labels' "trachea" is its wall only: the C of cartilage round the front and the sides, one
  voxel thick, none of it thicker than two. The air inside is another object ("trachea lumen", which is not
  meshed: it is no organ). Contoured by itself the wall was a white ladder of ring fragments. The windpipe a
  student sees and takes hold of is the tube: its wall and what the wall encloses, as one solid.
- THE BRONCHI. The same lumen object runs on into the two main bronchi, inside the labels' "bronchi". Each voxel of
  the lumen is given to the wall it lies nearer (`airways`), so the windpipe ends where the bronchi begin and
  both are solid.
- THE HEART'S SAC. The labels' "pericardium" is two things: round the roots of the great vessels a thick mass
  (the sac's reflection with the fat about it: 18 600 of its 42 400 voxels lie in parts thicker than two voxels),
  and over the front of the heart a sheet one voxel thick, in holes. Behind and under the heart the labels have
  no sac at all (of the heart's nearest voxels outside it, a quarter are pericardium; most are fat). Contoured
  as it is, the sheet lay over the heart as a pale rag with the heart showing red through its holes: it read as
  the lungs being torn there. Closed up, it would hide the heart, and nothing in the app can yet open or take
  off a structure. So the sac is shown OPENED, as a prepared specimen has it (`opened`): the thin sheet is
  left out, and of its thick parts those that lie in front of the heart as well (tried with them: they are
  pads along the heart's front, and lay on it as pale drips), and the scraps that do not reach the great vessels
  (under the heart, on the diaphragm). What stays is the mass round the roots of the great vessels, above the
  heart, where a sac that has been cut away ends; the heart is seen whole between the lungs. When the sac can
  be cut, the whole of it can come back.

Nothing here is drawn: each shape is a set of the labels' own voxels (two objects' taken together, or a part of
one). What was done is said in each structure's info (NOTES).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

TRACHEA, LUMEN, BRONCHI, PERICARDIUM = "trachea", "trachea lumen", "bronchi", "pericardium"
HEART = ("myocardium", "right atrium", "right ventricle", "left atrium", "left ventricle")
ROOTS = ("ascending aorta", "pulmonary trunk", "superior vena cava")      # the great vessels where the sac ends on them
THICK_PIECE = 200               # pieces of a thick part smaller than this many voxels are left out (0.7 cm3)
NOTES = {
    TRACHEA: "the labels' wall of the windpipe (its cartilage, a voxel thick) together with the space it encloses (the labels' \"trachea lumen\"), as one tube",
    BRONCHI: "the labels' walls of the bronchi together with the space they enclose (the part of the labels' \"trachea lumen\" that runs on into them)",
    PERICARDIUM: "opened, as in a prepared specimen: the labels' sac where it is thicker than two voxels and does not lie in front of the heart "
                 "(the mass round the roots of the great vessels); its sheet over the heart, a voxel thick and in holes as labelled, is left out so that the heart is seen",
}


def airways(wall_a: np.ndarray, wall_b: np.ndarray, lumen: np.ndarray, spacing) -> tuple[np.ndarray, np.ndarray]:
    """Two walls and the lumen they share (bool, z, y, x) -> each wall with its part of the lumen, as two solids:
    every voxel of the lumen goes to the wall it lies nearer (to the first where they are equally near, or where
    there is no second wall)."""
    wall_a, wall_b, lumen = np.asarray(wall_a, bool), np.asarray(wall_b, bool), np.asarray(lumen, bool)
    if not wall_b.any():
        return wall_a | lumen, wall_b.copy()
    if not wall_a.any():
        return wall_a.copy(), wall_b | lumen
    to_b = ndimage.distance_transform_edt(~wall_b, sampling=spacing) < ndimage.distance_transform_edt(~wall_a, sampling=spacing)
    return wall_a | (lumen & ~to_b), wall_b | (lumen & to_b)


def thick(mask: np.ndarray, least: int = THICK_PIECE) -> np.ndarray:
    """The parts of an object's voxels (bool, z, y, x) into which a cube of three voxels fits, without the pieces
    of them smaller than `least` voxels: what is left of a wall when its thin sheet is taken away."""
    mask = np.asarray(mask, bool)
    box = np.ones((3, 3, 3), bool)
    out = ndimage.binary_opening(np.pad(mask, 2), structure=box)[2:-2, 2:-2, 2:-2]
    if not out.any():
        return out
    parts, count = ndimage.label(out, structure=box)
    sizes = np.asarray(ndimage.sum(out, parts, range(1, count + 1)))
    return np.isin(parts, 1 + np.flatnonzero(sizes >= least))


def opened(sac: np.ndarray, heart: np.ndarray, roots: np.ndarray | None = None, least: int = THICK_PIECE) -> np.ndarray:
    """The heart's sac opened (bool, z, y, x; z grows from his front to his back): its thick parts (`thick`) that
    have nothing of the `heart` behind them in their column, so that from the front the heart is seen whole;
    pieces smaller than `least` voxels left out, and, `roots` given (the great vessels at the heart), every
    piece that does not come within two voxels of them (scraps under the heart, on the diaphragm)."""
    heart = np.asarray(heart, bool)
    before = np.flip(np.logical_or.accumulate(np.flip(heart, 0), axis=0), 0)       # the heart here, or further back in this column
    out = thick(sac, 0) & ~before
    if not out.any():
        return out
    box = np.ones((3, 3, 3), bool)
    parts, count = ndimage.label(out, structure=box)
    keep = np.asarray(ndimage.sum(out, parts, range(1, count + 1))) >= least
    if roots is not None:
        near = ndimage.binary_dilation(np.asarray(roots, bool), structure=box, iterations=2)
        keep &= np.asarray(ndimage.maximum(near, parts, range(1, count + 1))) > 0
    return np.isin(parts, 1 + np.flatnonzero(keep))


def shapes(body) -> dict:
    """{object name: (the box's first voxel (z, y, x), bool block)} for the objects whose shape is not their own
    labels' voxels as they are (the module's text). Objects the labels do not have are left out."""
    lab = body.labels
    index = {o["name"]: int(o["index"]) for o in body.objects if o["voxels"]}
    out = {}

    def boxed(mask, lo):
        found = ndimage.find_objects(mask.astype(np.uint8))
        if not found or found[0] is None:
            return None
        box = found[0]
        return tuple(int(a + s.start) for a, s in zip(lo, box)), mask[box]

    def region(names, margin=3):
        """The box round the named objects (with a margin), and its first voxel."""
        ids = [index[n] for n in names if n in index]
        found = ndimage.find_objects(np.isin(lab, ids).astype(np.uint8)) if ids else []
        if not found or found[0] is None:
            return None, None
        box = tuple(slice(max(0, s.start - margin), min(n, s.stop + margin)) for s, n in zip(found[0], lab.shape))
        return box, tuple(s.start for s in box)

    if TRACHEA in index and LUMEN in index:
        box, lo = region((TRACHEA, BRONCHI, LUMEN))
        block = lab[box]
        tube, branches = airways(block == index[TRACHEA], block == index.get(BRONCHI, -1), block == index[LUMEN], body.spacing)
        for name, mask in ((TRACHEA, tube), (BRONCHI, branches)):
            got = boxed(mask, lo) if name in index else None
            if got is not None:
                out[name] = got
    if PERICARDIUM in index:
        box, lo = region((PERICARDIUM,) + HEART)
        roots = [index[n] for n in ROOTS if n in index]
        got = boxed(opened(lab[box] == index[PERICARDIUM], np.isin(lab[box], [index[n] for n in HEART if n in index]),
                           np.isin(lab[box], roots) if roots else None), lo)
        if got is not None:
            out[PERICARDIUM] = got
    return out
