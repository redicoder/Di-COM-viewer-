"""
Stable label ids for dissection exports (labels.raw is uint8, so every id is < 255).

Ids never change between exports: lessons and saved selections refer to them. New structures get new ids
at the end; an id is never reused. TotalSegmentator labels are matched by class name, not by its own index,
so a different TotalSegmentator version cannot shift them.

Layers peel from the outside in (order 0 first). Names (la / en / it) live in backend/anatomy/anatomy_names.json
so teachers can correct them without touching code; colours start from the spec palette (§2.4).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ANATOMY_DIR = Path(__file__).resolve().parent.parent / "anatomy"
NAMES_FILE = ANATOMY_DIR / "anatomy_names.json"
INFO_FILE = ANATOMY_DIR / "anatomy_info.json"


@dataclass(frozen=True)
class Layer:
    key: str
    order: int
    color: tuple[float, float, float]


LAYERS = [
    Layer("skin", 0, (0.87, 0.67, 0.55)),
    Layer("fat", 1, (0.95, 0.85, 0.45)),
    Layer("muscle", 2, (0.60, 0.20, 0.18)),
    Layer("skeleton", 3, (0.93, 0.90, 0.82)),
    Layer("organs", 4, (0.75, 0.45, 0.40)),
    Layer("vessels", 5, (0.85, 0.10, 0.10)),
    Layer("nervous", 6, (0.85, 0.75, 0.70)),
]
LAYER_KEYS = {layer.key for layer in LAYERS}


@dataclass(frozen=True)
class Label:
    id: int
    key: str            # TotalSegmentator class name, or a tissue class
    layer: str
    color: tuple[float, float, float]
    opacity: float = 1.0
    info_key: str = ""  # shared description (all ribs -> "rib"); empty = key


# Tissue classes from HU (app.tissue): fixed ids 1..5.
SKIN, FAT, MUSCLE, BONE, SOFT_TISSUE = 1, 2, 3, 4, 5

ARTERY_RGB = (0.85, 0.10, 0.10)
VEIN_RGB = (0.20, 0.25, 0.70)


# TotalSegmentator `total` (v2) class names in a fixed order: id = 10 + position. Append only.
_SIDES = ("left", "right")
TS_KEYS = (
    "spleen", "kidney_right", "kidney_left", "gallbladder", "liver", "stomach", "pancreas",
    "adrenal_gland_right", "adrenal_gland_left", "lung_upper_lobe_left", "lung_lower_lobe_left",
    "lung_upper_lobe_right", "lung_middle_lobe_right", "lung_lower_lobe_right", "esophagus", "trachea",
    "thyroid_gland", "small_bowel", "duodenum", "colon", "urinary_bladder", "prostate", "kidney_cyst_left",
    "kidney_cyst_right", "sacrum",
    *(f"vertebrae_{v}" for v in ["S1"] + [f"L{i}" for i in range(5, 0, -1)] + [f"T{i}" for i in range(12, 0, -1)]
      + [f"C{i}" for i in range(7, 0, -1)]),
    "heart", "aorta", "pulmonary_vein", "brachiocephalic_trunk", "subclavian_artery_right",
    "subclavian_artery_left", "common_carotid_artery_right", "common_carotid_artery_left",
    "brachiocephalic_vein_left", "brachiocephalic_vein_right", "atrial_appendage_left", "superior_vena_cava",
    "inferior_vena_cava", "portal_vein_and_splenic_vein", "iliac_artery_left", "iliac_artery_right",
    "iliac_vena_left", "iliac_vena_right",
    *(f"{b}_{s}" for b in ("humerus", "scapula", "clavicula", "femur", "hip") for s in _SIDES),
    "spinal_cord",
    *(f"{m}_{s}" for m in ("gluteus_maximus", "gluteus_medius", "gluteus_minimus", "autochthon", "iliopsoas")
      for s in _SIDES),
    "brain", "skull",
    *(f"rib_{s}_{n}" for s in _SIDES for n in range(1, 13)),
    "sternum", "costal_cartilages",
)
TS_FIRST_ID = 10

# Colour / opacity per structure where it differs from its layer; spec palette first (§2.4).
_COLOR = {
    "spleen": (0.45, 0.12, 0.22), "kidney": (0.50, 0.15, 0.15), "gallbladder": (0.30, 0.55, 0.25),
    "liver": (0.55, 0.22, 0.16), "stomach": (0.85, 0.55, 0.45), "pancreas": (0.90, 0.75, 0.50),
    "adrenal_gland": (0.85, 0.60, 0.25), "lung": (0.90, 0.60, 0.60), "esophagus": (0.80, 0.50, 0.45),
    "trachea": (0.85, 0.80, 0.75), "thyroid_gland": (0.65, 0.25, 0.25), "small_bowel": (0.90, 0.65, 0.55),
    "duodenum": (0.90, 0.62, 0.50), "colon": (0.80, 0.60, 0.45), "urinary_bladder": (0.90, 0.80, 0.50),
    "prostate": (0.75, 0.50, 0.45), "kidney_cyst": (0.80, 0.75, 0.55), "heart": (0.70, 0.20, 0.20),
    "pulmonary_vein": (0.75, 0.20, 0.35), "portal_vein_and_splenic_vein": (0.25, 0.30, 0.65),
    "spinal_cord": (0.95, 0.90, 0.65), "brain": (0.85, 0.75, 0.70), "costal_cartilages": (0.80, 0.85, 0.85),
}
_OPACITY = {"lung": 0.35}
_VEINS = ("vein", "vena", "superior_vena_cava", "inferior_vena_cava")


def _info_key(key: str) -> str:
    """Shared description key: sides, lobes, rib numbers and vertebra numbers share one info card."""
    if key.startswith("rib_"):
        return "rib"
    if key.startswith("vertebrae_"):
        return {"S": "vertebra_sacral", "L": "vertebra_lumbar", "T": "vertebra_thoracic",
                "C": "vertebra_cervical"}[key[len("vertebrae_")]]
    if key.startswith("lung_"):
        return "lung"
    if key == "atrial_appendage_left":
        return "heart"
    if key.startswith("iliac_vena"):
        return "iliac_vein"
    for side in ("_left", "_right"):
        if key.endswith(side):
            return key[: -len(side)]
    return key


def _layer(key: str) -> str:
    base = _info_key(key)
    if base in ("spinal_cord", "brain"):
        return "nervous"
    if base in ("gluteus_maximus", "gluteus_medius", "gluteus_minimus", "autochthon", "iliopsoas"):
        return "muscle"
    if base.startswith("vertebra") or base in ("sacrum", "humerus", "scapula", "clavicula", "femur", "hip",
                                               "skull", "rib", "sternum", "costal_cartilages"):
        return "skeleton"
    if base in ("aorta", "pulmonary_vein", "brachiocephalic_trunk", "subclavian_artery", "common_carotid_artery",
                "brachiocephalic_vein", "superior_vena_cava", "inferior_vena_cava",
                "portal_vein_and_splenic_vein", "iliac_artery", "iliac_vein"):
        return "vessels"
    return "organs"


def _table() -> list[Label]:
    layer_rgb = {layer.key: layer.color for layer in LAYERS}
    t = [
        Label(SKIN, "skin", "skin", layer_rgb["skin"]),
        Label(FAT, "fat", "fat", layer_rgb["fat"]),
        Label(MUSCLE, "muscle", "muscle", layer_rgb["muscle"]),
        Label(BONE, "bone", "skeleton", layer_rgb["skeleton"]),
        Label(SOFT_TISSUE, "soft_tissue", "muscle", (0.78, 0.52, 0.48)),
    ]
    for i, key in enumerate(TS_KEYS):
        info, layer = _info_key(key), _layer(key)
        if layer == "vessels":
            rgb = _COLOR.get(info) or (VEIN_RGB if any(v in key for v in _VEINS) else ARTERY_RGB)
        else:
            rgb = _COLOR.get(info, layer_rgb[layer])
        t.append(Label(TS_FIRST_ID + i, key, layer, rgb, _OPACITY.get(info, 1.0), info))
    return t


LABELS: list[Label] = _table()
BY_ID = {label.id: label for label in LABELS}
BY_KEY = {label.key: label for label in LABELS}

assert len(BY_ID) == len(LABELS) and len(BY_KEY) == len(LABELS), "duplicate label id or key"
assert all(0 < label.id < 255 for label in LABELS), "labels.raw is uint8"
assert all(label.layer in LAYER_KEYS for label in LABELS)


def load_names(path: Path = NAMES_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def labels_json(present: set[int], names: dict | None = None) -> dict:
    """labels.json content for the ids present in a labels volume.

    Each label keeps a plain English "name" (what the current viewer reads) next to "names" {la, en, it}."""
    names = names if names is not None else load_names()
    layers = [{"id": layer.key, "order": layer.order, "name": names["layers"][layer.key],
               "color": list(layer.color)} for layer in LAYERS]
    labels = []
    for label in LABELS:
        if label.id not in present:
            continue
        n = names["labels"][label.key]
        labels.append({"id": label.id, "key": label.key, "layer": label.layer, "name": n["en"], "names": n,
                       "color": list(label.color), "opacity": label.opacity, "visible": True,
                       "info_key": label.info_key or label.key})
    return {"layers": layers, "labels": labels}
