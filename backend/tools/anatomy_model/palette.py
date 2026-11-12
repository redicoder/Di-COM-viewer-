"""The tissues' colours (sRGB 0..1). A structure's colour is found by the first keyword in its name."""
from __future__ import annotations

SKIN = (0.86, 0.69, 0.62)
BRIEFS = (0.84, 0.84, 0.84)
FAT = (0.87, 0.68, 0.36)
MUSCLE = (0.50, 0.23, 0.21)
BONE = (0.88, 0.84, 0.74)
ORGAN_DEFAULT = (0.78, 0.52, 0.48)

ORGAN_COLOURS = [
    ("lung", (0.86, 0.60, 0.60)), ("liver", (0.50, 0.27, 0.24)), ("hepatic", (0.38, 0.42, 0.56)),
    ("gallbladder", (0.42, 0.46, 0.32)), ("cystic", (0.42, 0.46, 0.32)), ("spleen", (0.50, 0.31, 0.32)),
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


def colour_of(name: str, tissue_class: str) -> tuple:
    """tissue_class: the label table's layer of the object (skin, fat, muscle, bone, organ)."""
    if tissue_class == "muscle":
        return MUSCLE
    if tissue_class == "bone":
        return BONE
    if tissue_class == "fat":
        return FAT
    if tissue_class == "skin":
        return SKIN
    for key, c in ORGAN_COLOURS:
        if key in name:
            return c
    return ORGAN_DEFAULT
