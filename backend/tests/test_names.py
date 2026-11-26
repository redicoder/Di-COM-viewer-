"""The structures' names in Latin, English and Italian: composed by rule, the side's adjective agreeing with its
noun; and what a student is told about where a shape comes from.
Needs nothing but the standard library, but lives with the model's tools (backend/.venv-seg has their numpy)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("skimage")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from anatomy_model import elbows, names  # noqa: E402

TABLE = Path(__file__).resolve().parents[2] / "unity" / "Assets" / "StreamingAssets" / "anatomy" / "model_names.json"


@pytest.mark.parametrize("name, la, it", [
    ("left femur", "Femur sinistrum", "Femore sinistro"),                          # a neuter noun,
    ("right tibia", "Tibia dextra", "Tibia destra"),                               # a feminine one,
    ("right humerus", "Humerus dexter", "Omero destro"),                           # a masculine one
    ("left hip bone", "Os coxae sinistrum", "Osso dell'anca sinistro"),
    ("left rib 3", "Costa III sinistra", "III costa sinistra"),
    ("right costal cartilage 6-9", "Cartilagines costales VI–IX dextrae", "Cartilagini costali VI-IX destre"),     # plural
    ("thoracic vertebra T10", "Vertebra thoracica X [T X]", "Vertebra toracica T10"),
    ("cervical vertebra C1", "Atlas [C I]", "Atlante (C1)"),
    ("intervertebral disc T12/L1", "Discus intervertebralis T XII–L I", "Disco intervertebrale T12-L1"),
    ("left metacarpal 2", "Os metacarpi II sinistrum", "II osso metacarpale sinistro"),
    ("phalanges of the left thumb", "Phalanges pollicis sinistri", "Falangi del pollice sinistro"),                   # "of the left thumb": genitive
    ("nail of the right great toe", "Unguis hallucis dextri", "Unghia dell'alluce destro"),
    ("nail of the left second toe", "Unguis digiti secundi pedis sinistri", "Unghia del secondo dito del piede sinistro"),
    ("upper right first molar", "Dens molaris primus superior dexter", "Primo molare superiore destro"),
    ("left biceps femoris, long head", "Musculus biceps femoris sinister, caput longum", "Muscolo bicipite femorale sinistro, capo lungo"),
    ("right prevertebral muscles", "Musculi praevertebrales dextri", "Muscoli prevertebrali destri"),
    ("left cartilage of the patella", "Cartilago articularis patellae sinistrae", "Cartilagine articolare della rotula sinistra"),
    ("right facial nerve, buccal branch", "Nervus facialis dexter, rami buccales", "Nervo facciale destro, rami buccali"),
    ("muscles of the left arm", "Musculi membri superioris sinistri", "Muscoli dell'arto superiore sinistro"),
    ("bones of the right elbow", "Ossa cubiti dextri", "Ossa del gomito destro"),                                      # "of the right elbow": genitive
    ("bones of the left elbow", "Ossa cubiti sinistri", "Ossa del gomito sinistro"),
    ("left atrium", "Atrium sinistrum", "Atrio sinistro"),
    ("liver", "Hepar", "Fegato"),
])
def test_a_name_is_composed_with_its_side_agreeing(name, la, it):
    got = names.name_of(name)
    assert got["la"] == la and got["it"] == it
    assert got["en"][0].isupper()


def test_the_english_shown_is_the_meshs_name_unless_that_is_not_fit_to_show():
    assert names.name_of("left femur")["en"] == "Left femur"
    assert names.name_of("ampulla")["en"] == "Duodenal ampulla (duodenal cap)"      # the SIO's bare "ampulla": its labels follow the duodenum's
    assert names.name_of("bone (not named) 37")["en"] == "Bone (not separately named)"
    assert names.name_of("hair belly_line") == {"la": "Pili abdominis", "en": "Hair of the belly", "it": "Peli dell'addome"}


def test_what_no_rule_knows_has_no_name_and_the_table_says_which():
    assert names.name_of("left flux capacitor") is None
    assert names.name_of("thoracic vertebra T13") is None
    with pytest.raises(ValueError, match="flux capacitor"):
        names.table([SimpleNamespace(name="left flux capacitor", layer="organs", info={})])


@pytest.mark.parametrize("name, info, origin, drawn, note", [
    ("left femur", {"source": "BoneHub", "class": "bone"}, "ct", False, ""),
    ("liver", {"class": "organ"}, "photo", False, ""),
    ("left rectus femoris", {"source": "University of Denver, 3D Models of the Visible Human Male"}, "models", False, ""),
    ("right buccinator", {"generated": True, "source": "drawn from its origin and insertion"}, "drawn", True, ""),
    ("nail of the left thumb", {"class": "nail", "drawn": "its outline is not read from him"}, "drawn", True, ""),
    ("hair chest", {"hair": "chest"}, "drawn", True, ""),
    ("briefs", {}, "cloth", True, ""),
    ("upper left canine", {"source": "the frozen CT's bright voxels", "named": "by its place in the row: an estimate"}, "ct", False, "tooth"),
    ("frontal bone", {"source": "BoneHub's cranium; the bone's outline from BodyParts3D", "part_of": "cranium and maxilla"}, "ct", False, "atlas"),
    ("muscles", {"class": "muscle"}, "photo", False, "unnamed"),
    ("bone (not named) 3", {"class": "bone"}, "ct", False, "unnamed"),
    ("bones of the left elbow", {"source": elbows.SOURCE, "class": "bone"}, "photo", False, "elbow"),                  # a bone, but not the scanner's
])
def test_where_a_shape_comes_from(name, info, origin, drawn, note):
    assert names.origin_of(name, info) == (origin, drawn, note)


def test_the_table_the_app_reads_is_what_the_rules_give():
    if not TABLE.exists():
        pytest.skip("no names table (the model's build writes it)")
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    rows = table["structures"]
    assert len(rows) > 400 and len({r["key"] for r in rows}) == len(rows)
    assert table["checked"] is False                                    # until an anatomist has read it
    sources, notes, layers = ({t["key"] for t in table[k]} for k in ("sources", "notes", "layers"))
    for r in rows:
        assert names.name_of(r["key"]) == {"la": r["la"], "en": r["en"], "it": r["it"]}, r["key"]
        assert r["la"] and r["en"] and r["it"]
        assert r["from"] in sources and r["layer"] in layers and (r["note"] == "" or r["note"] in notes)
        assert r["drawn"] == (r["from"] in ("drawn", "cloth"))
    for t in table["sources"] + table["notes"] + table["layers"]:
        assert t["en"] and t["it"]
    drawn = {r["key"] for r in rows if r["drawn"]}
    assert {"right facial nerve", "left eyeball", "nail of the left thumb", "right frontalis", "briefs"} <= drawn
    assert not ({"skin", "liver", "left femur", "left rectus femoris", "mandible"} & drawn)
