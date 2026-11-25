"""The structures' names in Latin, English and Italian, and what a student is told about where each shape comes from.

Every mesh of the model is named in English by what made it (the SIO's labels, BoneHub, TotalSegmentator, the
University of Denver's set, our own drawing). This module gives each of those names its Latin (after Terminologia
Anatomica) and its Italian, and says of each structure whether its shape was READ from this body or DRAWN.

The Latin and the Italian are composed, not listed 539 times: a table of the base terms with their gender, and
rules for what comes in series (a side, a number, a digit, a tooth's place). So "left rib 3" is Costa III sinistra
and "right femur" Femur dextrum, the adjective agreeing with its noun.

THE TERMS WERE WRITTEN FROM KNOWLEDGE OF THE TERMINOLOGY, NOT COPIED FROM ITS TABLES, AND HAVE NOT BEEN CHECKED BY
AN ANATOMIST: the table says so ("checked": false), and a teacher's corrections go in a file of their own beside
it (model_names_corrections.json), which the app reads after this one and which a rebuild does not touch.

    names.name_of("left rib 3")                       # {"la": "Costa III sinistra", "en": "Left rib 3", "it": "III costa sinistra"}
    names.write(path, structures)                     # the table the app reads (StreamingAssets/anatomy/model_names.json)
    python -m anatomy_model.names <export> <out.json> # the same, from the layers as last built
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# The side's adjective by what it agrees with: nominative m / f / n, their plurals, and the genitive singular
# ("of the left thumb": pollicis sinistri).
LA_SIDE = {"m": ("dexter", "sinister"), "f": ("dextra", "sinistra"), "n": ("dextrum", "sinistrum"),
           "mp": ("dextri", "sinistri"), "fp": ("dextrae", "sinistrae"), "np": ("dextra", "sinistra"),
           "gm": ("dextri", "sinistri"), "gf": ("dextrae", "sinistrae"), "gn": ("dextri", "sinistri")}
IT_SIDE = {"m": ("destro", "sinistro"), "f": ("destra", "sinistra"), "mp": ("destri", "sinistri"), "fp": ("destre", "sinistre")}
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

# What comes with a side: English base -> (Latin, what its side agrees with, Italian, the same). "{s}" marks where
# the side goes when it is not the last word.
SIDED = {
    # muscles of the trunk and the neck
    "external oblique": ("Musculus obliquus externus abdominis", "m", "Muscolo obliquo esterno dell'addome", "m"),
    "internal oblique": ("Musculus obliquus internus abdominis", "m", "Muscolo obliquo interno dell'addome", "m"),
    "transversus abdominis": ("Musculus transversus abdominis", "m", "Muscolo trasverso dell'addome", "m"),
    "rectus abdominis": ("Musculus rectus abdominis", "m", "Muscolo retto dell'addome", "m"),
    "iliacus": ("Musculus iliacus", "m", "Muscolo iliaco", "m"),
    "psoas": ("Musculus psoas major", "m", "Muscolo grande psoas", "m"),
    "obturator internus": ("Musculus obturatorius internus", "m", "Muscolo otturatore interno", "m"),
    "masseter": ("Musculus masseter", "m", "Muscolo massetere", "m"),
    "temporalis": ("Musculus temporalis", "m", "Muscolo temporale", "m"),
    "lateral pterygoid": ("Musculus pterygoideus lateralis", "m", "Muscolo pterigoideo laterale", "m"),
    "medial pterygoid": ("Musculus pterygoideus medialis", "m", "Muscolo pterigoideo mediale", "m"),
    "digastric": ("Musculus digastricus", "m", "Muscolo digastrico", "m"),
    "sternocleidomastoid": ("Musculus sternocleidomastoideus", "m", "Muscolo sternocleidomastoideo", "m"),
    "trapezius": ("Musculus trapezius", "m", "Muscolo trapezio", "m"),
    "levator scapulae": ("Musculus levator scapulae", "m", "Muscolo elevatore della scapola", "m"),
    "anterior scalene": ("Musculus scalenus anterior", "m", "Muscolo scaleno anteriore", "m"),
    "middle scalene": ("Musculus scalenus medius", "m", "Muscolo scaleno medio", "m"),
    "posterior scalene": ("Musculus scalenus posterior", "m", "Muscolo scaleno posteriore", "m"),
    "platysma": ("Platysma", "n", "Platisma", "m"),
    "sternothyroid": ("Musculus sternothyroideus", "m", "Muscolo sternotiroideo", "m"),
    "thyrohyoid": ("Musculus thyrohyoideus", "m", "Muscolo tiroioideo", "m"),
    "prevertebral muscles": ("Musculi praevertebrales", "mp", "Muscoli prevertebrali", "mp"),
    # the eye's muscles
    "lateral rectus": ("Musculus rectus lateralis", "m", "Muscolo retto laterale", "m"),
    "medial rectus": ("Musculus rectus medialis", "m", "Muscolo retto mediale", "m"),
    "superior rectus": ("Musculus rectus superior", "m", "Muscolo retto superiore", "m"),
    "inferior rectus": ("Musculus rectus inferior", "m", "Muscolo retto inferiore", "m"),
    "superior oblique": ("Musculus obliquus superior", "m", "Muscolo obliquo superiore", "m"),
    "inferior oblique": ("Musculus obliquus inferior", "m", "Muscolo obliquo inferiore", "m"),
    "levator palpebrae superioris": ("Musculus levator palpebrae superioris", "m", "Muscolo elevatore della palpebra superiore", "m"),
    # muscles of the hip and the leg
    "adductor brevis": ("Musculus adductor brevis", "m", "Muscolo adduttore breve", "m"),
    "adductor longus": ("Musculus adductor longus", "m", "Muscolo adduttore lungo", "m"),
    "adductor magnus": ("Musculus adductor magnus", "m", "Muscolo grande adduttore", "m"),
    "biceps femoris, long head": ("Musculus biceps femoris {s}, caput longum", "m", "Muscolo bicipite femorale {s}, capo lungo", "m"),
    "biceps femoris, short head": ("Musculus biceps femoris {s}, caput breve", "m", "Muscolo bicipite femorale {s}, capo breve", "m"),
    "extensor digitorum longus": ("Musculus extensor digitorum longus", "m", "Muscolo estensore lungo delle dita", "m"),
    "extensor hallucis longus": ("Musculus extensor hallucis longus", "m", "Muscolo estensore lungo dell'alluce", "m"),
    "flexor digitorum longus": ("Musculus flexor digitorum longus", "m", "Muscolo flessore lungo delle dita", "m"),
    "flexor hallucis longus": ("Musculus flexor hallucis longus", "m", "Muscolo flessore lungo dell'alluce", "m"),
    "gastrocnemius, lateral head": ("Musculus gastrocnemius {s}, caput laterale", "m", "Muscolo gastrocnemio {s}, capo laterale", "m"),
    "gastrocnemius, medial head": ("Musculus gastrocnemius {s}, caput mediale", "m", "Muscolo gastrocnemio {s}, capo mediale", "m"),
    "gluteus maximus": ("Musculus gluteus maximus", "m", "Muscolo grande gluteo", "m"),
    "gluteus medius": ("Musculus gluteus medius", "m", "Muscolo medio gluteo", "m"),
    "gluteus minimus": ("Musculus gluteus minimus", "m", "Muscolo piccolo gluteo", "m"),
    "gracilis": ("Musculus gracilis", "m", "Muscolo gracile", "m"),
    "inferior gemellus": ("Musculus gemellus inferior", "m", "Muscolo gemello inferiore", "m"),
    "superior gemellus": ("Musculus gemellus superior", "m", "Muscolo gemello superiore", "m"),
    "obturator externus": ("Musculus obturatorius externus", "m", "Muscolo otturatore esterno", "m"),
    "pectineus": ("Musculus pectineus", "m", "Muscolo pettineo", "m"),
    "fibularis (peroneus) longus": ("Musculus fibularis longus", "m", "Muscolo peroneo lungo", "m"),
    "piriformis": ("Musculus piriformis", "m", "Muscolo piriforme", "m"),
    "plantaris": ("Musculus plantaris", "m", "Muscolo plantare", "m"),
    "popliteus": ("Musculus popliteus", "m", "Muscolo popliteo", "m"),
    "quadratus femoris": ("Musculus quadratus femoris", "m", "Muscolo quadrato del femore", "m"),
    "rectus femoris": ("Musculus rectus femoris", "m", "Muscolo retto del femore", "m"),
    "sartorius": ("Musculus sartorius", "m", "Muscolo sartorio", "m"),
    "semimembranosus": ("Musculus semimembranosus", "m", "Muscolo semimembranoso", "m"),
    "semitendinosus": ("Musculus semitendinosus", "m", "Muscolo semitendinoso", "m"),
    "soleus": ("Musculus soleus", "m", "Muscolo soleo", "m"),
    "tensor fasciae latae": ("Musculus tensor fasciae latae", "m", "Muscolo tensore della fascia lata", "m"),
    "tibialis anterior": ("Musculus tibialis anterior", "m", "Muscolo tibiale anteriore", "m"),
    "tibialis posterior": ("Musculus tibialis posterior", "m", "Muscolo tibiale posteriore", "m"),
    "vastus intermedius": ("Musculus vastus intermedius", "m", "Muscolo vasto intermedio", "m"),
    "vastus lateralis": ("Musculus vastus lateralis", "m", "Muscolo vasto laterale", "m"),
    "vastus medialis": ("Musculus vastus medialis", "m", "Muscolo vasto mediale", "m"),
    # muscles of the face
    "frontalis": ("Venter frontalis musculi occipitofrontalis", "m", "Ventre frontale del muscolo occipitofrontale", "m"),
    "orbicularis oculi": ("Musculus orbicularis oculi", "m", "Muscolo orbicolare dell'occhio", "m"),
    "corrugator supercilii": ("Musculus corrugator supercilii", "m", "Muscolo corrugatore del sopracciglio", "m"),
    "nasalis": ("Musculus nasalis", "m", "Muscolo nasale", "m"),
    "levator labii superioris alaeque nasi": ("Musculus levator labii superioris alaeque nasi", "m", "Muscolo elevatore del labbro superiore e dell'ala del naso", "m"),
    "levator labii superioris": ("Musculus levator labii superioris", "m", "Muscolo elevatore del labbro superiore", "m"),
    "zygomaticus minor": ("Musculus zygomaticus minor", "m", "Muscolo zigomatico minore", "m"),
    "zygomaticus major": ("Musculus zygomaticus major", "m", "Muscolo zigomatico maggiore", "m"),
    "levator anguli oris": ("Musculus levator anguli oris", "m", "Muscolo elevatore dell'angolo della bocca", "m"),
    "buccinator": ("Musculus buccinator", "m", "Muscolo buccinatore", "m"),
    "risorius": ("Musculus risorius", "m", "Muscolo risorio", "m"),
    "depressor anguli oris": ("Musculus depressor anguli oris", "m", "Muscolo depressore dell'angolo della bocca", "m"),
    "depressor labii inferioris": ("Musculus depressor labii inferioris", "m", "Muscolo depressore del labbro inferiore", "m"),
    "mentalis": ("Musculus mentalis", "m", "Muscolo mentale", "m"),
    # bones
    "radius": ("Radius", "m", "Radio", "m"),
    "humerus": ("Humerus", "m", "Omero", "m"),
    "scapula": ("Scapula", "f", "Scapola", "f"),
    "ulna": ("Ulna", "f", "Ulna", "f"),
    "clavicle": ("Clavicula", "f", "Clavicola", "f"),
    "hip bone": ("Os coxae", "n", "Osso dell'anca", "m"),
    "femur": ("Femur", "n", "Femore", "m"),
    "fibula": ("Fibula", "f", "Fibula (perone)", "f"),
    "patella": ("Patella", "f", "Rotula (patella)", "f"),
    "tibia": ("Tibia", "f", "Tibia", "f"),
    "scaphoid": ("Os scaphoideum", "n", "Osso scafoide", "m"),
    "lunate": ("Os lunatum", "n", "Osso semilunare", "m"),
    "triquetrum": ("Os triquetrum", "n", "Osso piramidale", "m"),
    "pisiform": ("Os pisiforme", "n", "Osso pisiforme", "m"),
    "trapezium": ("Os trapezium", "n", "Osso trapezio", "m"),
    "trapezoid": ("Os trapezoideum", "n", "Osso trapezoide", "m"),
    "capitate": ("Os capitatum", "n", "Osso capitato", "m"),
    "hamate": ("Os hamatum", "n", "Osso uncinato", "m"),
    "talus": ("Talus", "m", "Astragalo (talo)", "m"),
    "calcaneus": ("Calcaneus", "m", "Calcagno", "m"),
    "navicular": ("Os naviculare", "n", "Osso navicolare", "m"),
    "cuboid": ("Os cuboideum", "n", "Osso cuboide", "m"),
    "medial cuneiform": ("Os cuneiforme mediale", "n", "Osso cuneiforme mediale", "m"),
    "intermediate cuneiform": ("Os cuneiforme intermedium", "n", "Osso cuneiforme intermedio", "m"),
    "lateral cuneiform": ("Os cuneiforme laterale", "n", "Osso cuneiforme laterale", "m"),
    "parietal bone": ("Os parietale", "n", "Osso parietale", "m"),
    "temporal bone": ("Os temporale", "n", "Osso temporale", "m"),
    "maxilla": ("Maxilla", "f", "Osso mascellare", "m"),
    "zygomatic bone": ("Os zygomaticum", "n", "Osso zigomatico", "m"),
    "nasal bone": ("Os nasale", "n", "Osso nasale", "m"),
    "lacrimal bone": ("Os lacrimale", "n", "Osso lacrimale", "m"),
    "palatine bone": ("Os palatinum", "n", "Osso palatino", "m"),
    "inferior nasal concha": ("Concha nasalis inferior", "f", "Cornetto nasale inferiore", "m"),
    # cartilage and ligaments
    "clavicular cartilage": ("Cartilago articularis claviculae {s}", "gf", "Cartilagine articolare della clavicola {s}", "f"),
    "cartilage of the femur at the knee": ("Cartilago articularis condylorum femoris {s}", "gn", "Cartilagine articolare del femore {s} al ginocchio", "m"),
    "cartilage of the femur's head": ("Cartilago articularis capitis femoris {s}", "gn", "Cartilagine articolare della testa del femore {s}", "m"),
    "cartilage of the patella": ("Cartilago articularis patellae {s}", "gf", "Cartilagine articolare della rotula {s}", "f"),
    "cartilage of the hip socket": ("Cartilago articularis acetabuli {s}", "gn", "Cartilagine articolare dell'acetabolo {s}", "m"),
    "cartilage of the talus": ("Cartilago articularis tali {s}", "gm", "Cartilagine articolare dell'astragalo {s}", "m"),
    "cartilage of the tibia at the ankle": ("Cartilago articularis tibiae {s} (facies articularis inferior)", "gf", "Cartilagine articolare della tibia {s} alla caviglia", "f"),
    "lateral cartilage of the tibia at the knee": ("Cartilago articularis condyli lateralis tibiae {s}", "gf", "Cartilagine articolare del condilo laterale della tibia {s}", "f"),
    "medial cartilage of the tibia at the knee": ("Cartilago articularis condyli medialis tibiae {s}", "gf", "Cartilagine articolare del condilo mediale della tibia {s}", "f"),
    "anterior cruciate ligament": ("Ligamentum cruciatum anterius", "n", "Legamento crociato anteriore", "m"),
    "posterior cruciate ligament": ("Ligamentum cruciatum posterius", "n", "Legamento crociato posteriore", "m"),
    "lateral collateral ligament of the knee": ("Ligamentum collaterale fibulare", "n", "Legamento collaterale fibulare (laterale)", "m"),
    "medial collateral ligament of the knee": ("Ligamentum collaterale tibiale", "n", "Legamento collaterale tibiale (mediale)", "m"),
    # organs, vessels, nerves
    "kidney": ("Ren", "m", "Rene", "m"),
    "renal medulla": ("Medulla renalis", "f", "Midollare renale", "f"),
    "renal vein": ("Vena renalis", "f", "Vena renale", "f"),
    "lung": ("Pulmo", "m", "Polmone", "m"),
    "atrium": ("Atrium", "n", "Atrio", "m"),
    "ventricle": ("Ventriculus", "m", "Ventricolo", "m"),
    "colic flexure": ("Flexura coli", "f", "Flessura colica", "f"),
    "jugular vein": ("Vena jugularis", "f", "Vena giugulare", "f"),
    "internal jugular vein": ("Vena jugularis interna", "f", "Vena giugulare interna", "f"),
    "subclavian vein": ("Vena subclavia", "f", "Vena succlavia", "f"),
    "internal carotid artery": ("Arteria carotis interna", "f", "Arteria carotide interna", "f"),
    "parotid gland": ("Glandula parotidea", "f", "Ghiandola parotide", "f"),
    "submandibular gland": ("Glandula submandibularis", "f", "Ghiandola sottomandibolare", "f"),
    "optic nerve": ("Nervus opticus", "m", "Nervo ottico", "m"),
    "facial artery": ("Arteria facialis", "f", "Arteria facciale", "f"),
    "facial vein": ("Vena facialis", "f", "Vena facciale", "f"),
    "superficial temporal artery": ("Arteria temporalis superficialis", "f", "Arteria temporale superficiale", "f"),
    "facial nerve": ("Nervus facialis", "m", "Nervo facciale", "m"),
    "supraorbital nerve": ("Nervus supraorbitalis", "m", "Nervo sopraorbitario", "m"),
    "infraorbital nerve": ("Nervus infraorbitalis", "m", "Nervo infraorbitario", "m"),
    "mental nerve": ("Nervus mentalis", "m", "Nervo mentale", "m"),
    "eyeball": ("Bulbus oculi", "m", "Bulbo oculare", "m"),
    "conjunctiva": ("Tunica conjunctiva", "f", "Congiuntiva", "f"),
}

# What has no side: English -> (Latin, Italian[, the English shown, where the mesh's name is not fit to show]).
PLAIN = {
    "skin": ("Cutis", "Cute"),
    "briefs": ("Linteum", "Telo sui fianchi (non fa parte del corpo)", "Cloth over the hips (not part of the body)"),
    "lining of the mouth": ("Tunica mucosa oris", "Mucosa della bocca"),
    "upper gum": ("Gingiva superior", "Gengiva superiore"),
    "lower gum": ("Gingiva inferior", "Gengiva inferiore"),
    "lining of the throat": ("Tunica mucosa pharyngis", "Mucosa della faringe"),
    "wall of the mouth": ("Paries cavitatis oris", "Parete della cavità orale"),
    "subcutaneous fat": ("Panniculus adiposus", "Tessuto adiposo sottocutaneo"),
    "visceral fat": ("Textus adiposus visceralis", "Tessuto adiposo viscerale"),
    "diaphragm": ("Diaphragma", "Diaframma"),
    "ischiocavernosus": ("Musculus ischiocavernosus", "Muscolo ischiocavernoso"),
    "pelvic diaphragm": ("Diaphragma pelvis", "Diaframma pelvico"),
    "rectus sheath": ("Vagina musculi recti abdominis", "Guaina del muscolo retto dell'addome"),
    "muscles": ("Musculi", "Muscoli (non distinti per nome)", "Muscles (not separately named)"),
    "superior pharyngeal constrictor": ("Musculus constrictor pharyngis superior", "Muscolo costrittore superiore della faringe"),
    "middle pharyngeal constrictor": ("Musculus constrictor pharyngis medius", "Muscolo costrittore medio della faringe"),
    "inferior pharyngeal constrictor": ("Musculus constrictor pharyngis inferior", "Muscolo costrittore inferiore della faringe"),
    "procerus": ("Musculus procerus", "Muscolo procero"),
    "orbicularis oris, upper lip": ("Musculus orbicularis oris (labium superius)", "Muscolo orbicolare della bocca (labbro superiore)"),
    "orbicularis oris, lower lip": ("Musculus orbicularis oris (labium inferius)", "Muscolo orbicolare della bocca (labbro inferiore)"),
    "mandible": ("Mandibula", "Mandibola"),
    "cranium and maxilla": ("Cranium", "Cranio"),
    "sacrum": ("Os sacrum", "Osso sacro"),
    "coccyx": ("Os coccygis", "Coccige"),
    "sternum": ("Sternum", "Sterno"),
    "unclassified cartilage": ("Cartilago", "Cartilagine (non classificata)"),
    "thyroid cartilage": ("Cartilago thyroidea", "Cartilagine tiroidea"),
    "cricoid cartilage": ("Cartilago cricoidea", "Cartilagine cricoidea"),
    "hyoid bone": ("Os hyoideum", "Osso ioide"),
    "upper teeth": ("Dentes superiores", "Denti superiori"),
    "lower teeth": ("Dentes inferiores", "Denti inferiori"),
    "frontal bone": ("Os frontale", "Osso frontale"),
    "occipital bone": ("Os occipitale", "Osso occipitale"),
    "sphenoid bone": ("Os sphenoidale", "Osso sfenoide"),
    "ethmoid bone": ("Os ethmoidale", "Osso etmoide"),
    "vomer": ("Vomer", "Vomere"),
    "abdominal aorta": ("Aorta abdominalis", "Aorta addominale"),
    "ampulla": ("Ampulla duodeni", "Ampolla (bulbo) del duodeno", "Duodenal ampulla (duodenal cap)"),
    "arch of aorta": ("Arcus aortae", "Arco aortico"),
    "ascending aorta": ("Aorta ascendens", "Aorta ascendente"),
    "ascending colon": ("Colon ascendens", "Colon ascendente"),
    "azygos vein": ("Vena azygos", "Vena azygos"),
    "body of stomach": ("Corpus gastricum", "Corpo dello stomaco"),
    "brachiocephalic vein": ("Vena brachiocephalica", "Vena brachiocefalica"),
    "bronchi": ("Bronchi", "Bronchi"),
    "caecum": ("Caecum", "Intestino cieco"),
    "cardia": ("Cardia", "Cardias"),
    "cystic duct": ("Ductus cysticus", "Dotto cistico"),
    "descending aorta": ("Aorta descendens", "Aorta discendente"),
    "descending colon": ("Colon descendens", "Colon discendente"),
    "duodenum (retroperitoneal part)": ("Duodenum (pars retroperitonealis)", "Duodeno (porzione retroperitoneale)"),
    "fundus of stomach": ("Fundus gastricus", "Fondo dello stomaco"),
    "gallbladder": ("Vesica biliaris", "Colecisti"),
    "greater curvature": ("Curvatura major", "Grande curvatura dello stomaco", "Greater curvature of the stomach"),
    "lesser curvature": ("Curvatura minor", "Piccola curvatura dello stomaco", "Lesser curvature of the stomach"),
    "grey matter": ("Substantia grisea", "Sostanza grigia"),
    "white matter": ("Substantia alba", "Sostanza bianca"),
    "hepatic veins": ("Venae hepaticae", "Vene epatiche"),
    "inferior mesenteric vein": ("Vena mesenterica inferior", "Vena mesenterica inferiore"),
    "superior mesenteric vein": ("Vena mesenterica superior", "Vena mesenterica superiore"),
    "inferior vena cava": ("Vena cava inferior", "Vena cava inferiore"),
    "superior vena cava": ("Vena cava superior", "Vena cava superiore"),
    "larynx": ("Larynx", "Laringe"),
    "liver": ("Hepar", "Fegato"),
    "myocardium": ("Myocardium", "Miocardio"),
    "pancreas": ("Pancreas", "Pancreas"),
    "pericardium": ("Pericardium", "Pericardio"),
    "portal vein": ("Vena portae hepatis", "Vena porta"),
    "prostate": ("Prostata", "Prostata"),
    "pulmonary arteries": ("Arteriae pulmonales", "Arterie polmonari"),
    "pulmonary trunk": ("Truncus pulmonalis", "Tronco polmonare"),
    "pulmonary veins": ("Venae pulmonales", "Vene polmonari"),
    "rectum": ("Rectum", "Retto"),
    "seminal gland": ("Glandula vesiculosa", "Vescichetta seminale", "Seminal gland (seminal vesicle)"),
    "sigmoid colon": ("Colon sigmoideum", "Colon sigmoideo (sigma)"),
    "small intestine": ("Intestinum tenue", "Intestino tenue"),
    "spleen": ("Splen", "Milza"),
    "splenic vein": ("Vena splenica", "Vena splenica (lienale)"),
    "stomach": ("Gaster", "Stomaco"),
    "testis": ("Testis", "Testicolo"),
    "thyroid gland": ("Glandula thyroidea", "Tiroide"),
    "trachea": ("Trachea", "Trachea"),
    "transverse colon": ("Colon transversum", "Colon trasverso"),
    "unclassified veins": ("Venae", "Vene (non classificate)"),
    "urinary bladder": ("Vesica urinaria", "Vescica urinaria"),
    "tongue": ("Lingua", "Lingua"),
    "soft palate": ("Palatum molle", "Palato molle"),
}

# A digit's name in the genitive ("of the thumb"), Latin and Italian.
DIGITS = {
    "thumb": ("pollicis", "del pollice"), "index finger": ("indicis", "dell'indice"), "middle finger": ("digiti medii", "del dito medio"),
    "ring finger": ("digiti anularis", "dell'anulare"), "little finger": ("digiti minimi", "del mignolo"),
    "great toe": ("hallucis", "dell'alluce"), "second toe": ("digiti secundi pedis", "del secondo dito del piede"),
    "third toe": ("digiti tertii pedis", "del terzo dito del piede"), "fourth toe": ("digiti quarti pedis", "del quarto dito del piede"),
    "little toe": ("digiti minimi pedis", "del quinto dito del piede"),
}
TEETH = {
    "central incisor": ("Dens incisivus medialis", "Incisivo centrale"), "lateral incisor": ("Dens incisivus lateralis", "Incisivo laterale"),
    "canine": ("Dens caninus", "Canino"), "first premolar": ("Dens premolaris primus", "Primo premolare"),
    "second premolar": ("Dens premolaris secundus", "Secondo premolare"), "first molar": ("Dens molaris primus", "Primo molare"),
    "second molar": ("Dens molaris secundus", "Secondo molare"), "third molar": ("Dens molaris tertius", "Terzo molare"),
}
VERTEBRAE = {"cervical": ("cervicalis", "cervicale", "C"), "thoracic": ("thoracica", "toracica", "T"), "lumbar": ("lumbalis", "lombare", "L")}
NERVE_BRANCHES = {
    "temporal": ("rami temporales", "rami temporali"), "zygomatic": ("rami zygomatici", "rami zigomatici"), "buccal": ("rami buccales", "rami buccali"),
    "marginal mandibular": ("ramus marginalis mandibularis", "ramo marginale della mandibola"), "cervical": ("ramus colli", "ramo cervicale"),
}
HAIR = {
    "scalp": ("Capilli", "Hair of the scalp", "Capelli"), "beard": ("Barba", "Beard", "Barba"), "brow": ("Supercilia", "Eyebrows", "Sopracciglia"),
    "lashes": ("Cilia", "Eyelashes", "Ciglia"), "chest": ("Pili pectoris", "Hair of the chest", "Peli del torace"),
    "belly_line": ("Pili abdominis", "Hair of the belly", "Peli dell'addome"), "forearm": ("Pili antebrachii", "Hair of the forearm", "Peli dell'avambraccio"),
    "upper_arm": ("Pili brachii", "Hair of the upper arm", "Peli del braccio"), "thigh": ("Pili femoris", "Hair of the thigh", "Peli della coscia"),
    "shin": ("Pili cruris", "Hair of the lower leg", "Peli della gamba"),
}
LAYERS = {
    "skin": ("Cutis", "Skin", "Cute"), "fat": ("Textus adiposus", "Fat", "Grasso"), "muscles": ("Musculi", "Muscles", "Muscoli"),
    "skeleton": ("Skeleton", "Skeleton", "Scheletro"), "organs": ("Viscera", "Organs", "Organi"),
}
# Where a shape comes from, as a student is told it (the card's small line): key -> (English, Italian).
SOURCES = {
    "photo": ("Shape read from this body's own photographs.", "Forma rilevata dalle fotografie di questo stesso corpo."),
    "ct": ("Shape read from this body's own CT.", "Forma rilevata dalla TC di questo stesso corpo."),
    "models": ("Shape from the University of Denver's models of this same body.", "Forma tratta dai modelli dell'Università di Denver di questo stesso corpo."),
    "drawn": ("Drawn: not read from this body. It shows where the structure lies in a body of this shape.",
              "Disegnato: non rilevato da questo corpo. Mostra dove si trova la struttura in un corpo di questa forma."),
    "cloth": ("Not part of the body.", "Non fa parte del corpo."),
}
NOTES = {
    "tooth": ("Named by its place in the row: an estimate.", "Denominato in base alla posizione nell'arcata: una stima."),
    "atlas": ("Where this bone ends and the next begins follows an atlas fitted to this skull.",
              "I confini tra questo osso e i vicini seguono un atlante adattato a questo cranio."),
    "unnamed": ("The data this comes from does not name it further.", "I dati di origine non lo distinguono ulteriormente."),
}


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _with_side(text: str, word: str) -> str:
    return text.replace("{s}", word) if "{s}" in text else f"{text} {word}"


def _digit(side: str, digit: str):
    """("of the left thumb" in Latin, in Italian) or None."""
    if digit not in DIGITS:
        return None
    k = 0 if side == "right" else 1
    la, it = DIGITS[digit]
    return f"{la} {LA_SIDE['gm'][k]}", f"{it} {IT_SIDE['m'][k]}"


def name_of(name: str) -> dict | None:
    """A structure's name in Latin, English and Italian ({"la", "en", "it"}), from the mesh's English name; None
    where no rule and no entry knows it."""
    en = _capital(name)
    if name in PLAIN:
        entry = PLAIN[name]
        return {"la": entry[0], "en": entry[2] if len(entry) > 2 else en, "it": entry[1]}
    m = re.fullmatch(r"hair (\w+)", name)
    if m and m.group(1) in HAIR:
        la, english, it = HAIR[m.group(1)]
        return {"la": la, "en": english, "it": it}
    if re.fullmatch(r"bone \(not named\) \d+", name):
        return {"la": "Os", "en": "Bone (not separately named)", "it": "Osso (senza nome proprio)"}
    m = re.fullmatch(r"(cervical|thoracic|lumbar) vertebra ([CTL])(\d+)", name)
    if m:
        la, it, letter = VERTEBRAE[m.group(1)]
        n = int(m.group(3))
        if not 1 <= n <= 12:
            return None
        if letter == "C" and n == 1:
            return {"la": "Atlas [C I]", "en": "Atlas (C1)", "it": "Atlante (C1)"}
        if letter == "C" and n == 2:
            return {"la": "Axis [C II]", "en": "Axis (C2)", "it": "Epistrofeo (C2)"}
        if letter == "C" and n == 7:
            return {"la": "Vertebra prominens [C VII]", "en": "Cervical vertebra C7 (vertebra prominens)", "it": "Vertebra cervicale C7 (prominente)"}
        return {"la": f"Vertebra {la} {ROMAN[n]} [{letter} {ROMAN[n]}]", "en": en, "it": f"Vertebra {it} {letter}{n}"}
    m = re.fullmatch(r"intervertebral disc ([CTLS])(\d+)/([CTLS])(\d+)", name)
    if m:
        a, i, b, j = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if not (1 <= i <= 12 and 1 <= j <= 12):
            return None
        return {"la": f"Discus intervertebralis {a} {ROMAN[i]}–{b} {ROMAN[j]}", "en": en, "it": f"Disco intervertebrale {a}{i}-{b}{j}"}
    m = re.fullmatch(r"(upper|lower) (left|right) (.+)", name)
    if m and m.group(3) in TEETH:
        la, it = TEETH[m.group(3)]
        k = 0 if m.group(2) == "right" else 1
        upper = m.group(1) == "upper"
        return {"la": f"{la} {'superior' if upper else 'inferior'} {LA_SIDE['m'][k]}", "en": en,
                "it": f"{it} {'superiore' if upper else 'inferiore'} {IT_SIDE['m'][k]}"}
    m = re.fullmatch(r"(phalanges|nail) of the (left|right) (.+)", name)
    if m:
        got = _digit(m.group(2), m.group(3))
        if got is None:
            return None
        la, it = got
        return ({"la": f"Phalanges {la}", "en": en, "it": f"Falangi {it}"} if m.group(1) == "phalanges"
                else {"la": f"Unguis {la}", "en": en, "it": f"Unghia {it}"})
    m = re.fullmatch(r"muscles of the (left|right) arm", name)
    if m:
        k = 0 if m.group(1) == "right" else 1
        return {"la": f"Musculi membri superioris {LA_SIDE['gn'][k]}", "en": en, "it": f"Muscoli dell'arto superiore {IT_SIDE['m'][k]}"}
    m = re.fullmatch(r"(left|right) (.+)", name)
    if not m:
        return None
    k = 0 if m.group(1) == "right" else 1
    rest = m.group(2)
    n = re.fullmatch(r"rib (\d+)", rest)
    if n and 1 <= int(n.group(1)) <= 12:
        r = ROMAN[int(n.group(1))]
        return {"la": f"Costa {r} {LA_SIDE['f'][k]}", "en": en, "it": f"{r} costa {IT_SIDE['f'][k]}"}
    n = re.fullmatch(r"costal cartilage (\d+)(?:-(\d+))?", rest)
    if n and 1 <= int(n.group(1)) <= 12 and (n.group(2) is None or 1 <= int(n.group(2)) <= 12):
        a = ROMAN[int(n.group(1))]
        if n.group(2) is None:
            return {"la": f"Cartilago costalis {a} {LA_SIDE['f'][k]}", "en": en, "it": f"{a} cartilagine costale {IT_SIDE['f'][k]}"}
        b = ROMAN[int(n.group(2))]
        return {"la": f"Cartilagines costales {a}–{b} {LA_SIDE['fp'][k]}", "en": en, "it": f"Cartilagini costali {a}-{b} {IT_SIDE['fp'][k]}"}
    n = re.fullmatch(r"(metacarpal|metatarsal) (\d)", rest)
    if n and 1 <= int(n.group(2)) <= 5:
        r = ROMAN[int(n.group(2))]
        hand = n.group(1) == "metacarpal"
        return {"la": f"Os {'metacarpi' if hand else 'metatarsi'} {r} {LA_SIDE['n'][k]}", "en": en,
                "it": f"{r} osso {'metacarpale' if hand else 'metatarsale'} {IT_SIDE['m'][k]}"}
    n = re.fullmatch(r"facial nerve, (.+) branch", rest)
    if n and n.group(1) in NERVE_BRANCHES:
        la, it = NERVE_BRANCHES[n.group(1)]
        return {"la": f"Nervus facialis {LA_SIDE['m'][k]}, {la}", "en": en, "it": f"Nervo facciale {IT_SIDE['m'][k]}, {it}"}
    if rest in SIDED:
        la, la_gender, it, it_gender = SIDED[rest]
        return {"la": _with_side(la, LA_SIDE[la_gender][k]), "en": en, "it": _with_side(it, IT_SIDE[it_gender][k])}
    return None


def origin_of(name: str, info: dict) -> tuple[str, bool, str]:
    """Where a structure's shape comes from: (a key of SOURCES, whether it is drawn and not read from him, a key of
    NOTES or ""), from its name and what its builder recorded about it (Structure.info)."""
    source = str(info.get("source", ""))
    if name == "briefs":
        return "cloth", True, ""
    if name.startswith("hair ") or info.get("generated") or info.get("drawn"):
        return "drawn", True, ""
    note = "tooth" if info.get("named") else "atlas" if info.get("part_of") else ""
    if "(not named)" in name or name.startswith("unclassified") or name == "muscles":
        note = "unnamed"
    if "University of Denver" in source:
        return "models", False, note
    if "BoneHub" in source or "TotalSegmentator" in source or "CT" in source or "(not named)" in name or name == "lining of the mouth":
        return "ct", False, note
    return "photo", False, note


def table(structures) -> dict:
    """The table the app reads: every structure's key (its mesh's name), layer, three names, origin; and the texts
    the card shows. `structures`: objects with .name, .layer and .info. Raises for a structure without a name."""
    rows, nameless = [], []
    for s in structures:
        names = name_of(s.name)
        if names is None:
            nameless.append(s.name)
            continue
        origin, drawn, note = origin_of(s.name, s.info or {})
        rows.append({"key": s.name, "layer": s.layer, "la": names["la"], "en": names["en"], "it": names["it"], "from": origin, "drawn": bool(drawn), "note": note})
    if nameless:
        raise ValueError(f"no name for {len(nameless)} structure(s): {nameless[:12]} (add them to anatomy_model/names.py)")
    return {
        "_about": "Names of the Model Lab's structures, keyed by mesh name: la = Latin after Terminologia Anatomica, en = English, it = Italian. "
                  "Made by backend/tools/anatomy_model/names.py when the model is built: do not edit this file, a rebuild writes it again. "
                  "A teacher's corrections go in model_names_corrections.json beside it (same shape; only 'structures' with 'key' and the names to change), "
                  "which the app reads after this file.",
        "checked": False,
        "checked_note": "The Latin and the Italian were composed from knowledge of the terminology and have not yet been checked by an anatomist.",
        "layers": [{"key": k, "la": la, "en": en, "it": it} for k, (la, en, it) in LAYERS.items()],
        "sources": [{"key": k, "la": it, "en": en, "it": it} for k, (en, it) in SOURCES.items()],
        "notes": [{"key": k, "la": it, "en": en, "it": it} for k, (en, it) in NOTES.items()],
        "structures": rows,
    }


def write(path: Path, structures, log=print) -> dict:
    """Writes the table (table) as JSON; returns it."""
    got = table(structures)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    drawn = sum(1 for r in got["structures"] if r["drawn"])
    log(f"names: {len(got['structures'])} structures named in Latin, English and Italian ({drawn} of them marked as drawn), {path}")
    return got


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    from .common import LAYERS as MODEL_LAYERS, load_structures
    export, out = Path(sys.argv[1]), Path(sys.argv[2])
    structures = []
    for layer in MODEL_LAYERS:
        structures += load_structures(export / "model" / f"{layer}.npz")
    write(out, structures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
