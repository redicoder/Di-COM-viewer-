# Names: what a touched structure is called (2026-11-25)

Research before the Model Lab named its structures (`backend/tools/anatomy_model/names.py`, `ModelPick`,
`ModelNames`, `ModelCard`). Marks as in the other reports: **O** read on our own data or code, **K** from general
knowledge (check before showing it to a student as fact).

## 1. What there is to name (O)

The model as built on 2026-11-24 has 539 meshes, each named in English by what made it:

| layer | meshes | named by |
|---|---|---|
| skin | 37 | us: skin, cloth, the mouth's linings, 20 nails, 10 kinds of hair |
| fat | 2 | the labels: subcutaneous, visceral |
| muscles | 159 | the SIO's labels (19), TotalSegmentator on his CT (38), the University of Denver's set (70), our drawing of the face's muscles (31), the unnamed mass |
| skeleton | 242 | BoneHub (141), the SIO's cartilages and discs (40), TotalSegmentator (3), the University of Denver's cartilages and ligaments (24), the teeth by their place in the row (16), the skull's bones after an atlas (18) |
| organs | 99 | the SIO's labels (67), TotalSegmentator (4), our drawing of the face's vessels and nerves and of the eyes (28) |

Stripped of their side and their number these are about 230 different terms. Series make up most of the rest:
24 ribs, 24 vertebrae, 20 discs, 14 costal cartilages, 10 metacarpals and 10 metatarsals, 20 sets of phalanges,
20 nails, 15 teeth.

One of the SIO's names does not say what it is: **"ampulla"**. Its label numbers (1598, 1599, 2601) follow the
duodenum's (1591 to 1597) and the stomach's (25xx) in the SIO's own sheet, so it is the duodenum's first part
(Ampulla duodeni, the duodenal cap), not the rectum's ampulla nor a duct's. (O, from the numbering; the SIO's
sheet has no hierarchy to confirm it.)

## 2. Where the terms come from, and how far they can be trusted (K)

The Latin follows Terminologia Anatomica as I know it, the Italian the usual terms of Italian anatomy texts.
**They were written from knowledge of the terminology, not copied from its tables, and nobody has checked them.**
The table says so (`"checked": false`). Terms I am least sure of:

- the group names that are not single structures: Musculi praevertebrales, Cartilago articularis ... (a joint
  surface's cartilage has no term of its own in the terminology; these are descriptions in Latin);
- the SIO's "jugular vein" (which one is not said: given as Vena jugularis), "clavicular cartilage" (given as
  the clavicle's joint cartilage), "seminal gland" (Glandula vesiculosa, the seminal vesicle);
- the metacarpals and metatarsals (Os metacarpi I; the newer edition has Os metacarpale I);
- central and lateral incisors (Dens incisivus medialis, lateralis: dentistry's usage, not the terminology's);
- the cloth and the mouth's back wall, which are not anatomy (Linteum; Paries cavitatis oris).

An anatomist or a teacher of the subject should read the table before the product is sold. Their corrections go
in `model_names_corrections.json` beside the table, which the app reads after it and a rebuild does not touch.

Terminologia Anatomica itself (FIPAT) is published under a licence that forbids derivatives of the document; a
term is not the document, and none of its tables is copied here.

## 3. Composed, not listed (O)

539 lines of three languages would be 1600 chances of a slip, and every new structure another three. The names
are composed: a table of the base terms with what the side's adjective agrees with, and rules for the series.

- Latin: dexter, dextra, dextrum by the noun's gender (Humerus dexter, Tibia dextra, Femur dextrum), their
  plurals (Musculi praevertebrales dextri, Cartilagines costales VI-IX dextrae), and the genitive where the side
  belongs to a noun in the genitive (Phalanges pollicis sinistri, Cartilago articularis patellae sinistrae).
- Italian the same with destro, destra, destri, destre.
- Where the side is not the last word the term says where it goes (Musculus biceps femoris sinister, caput
  longum).
- Numbers are Roman in Latin and in Italian's ribs and cartilages, as the existing table for the CT viewer has
  them (`backend/anatomy/anatomy_names.json`), whose forms for the vertebrae are kept (Atlas [C I], Axis [C II],
  Vertebra prominens [C VII]).

A structure no rule knows has no name, and the model's build stops and says which (`names.table`).

## 4. Read or drawn (O)

A student must be able to tell what is this body's own shape from what was drawn into it. Each builder already
records it (`Structure.info`); the table reduces that to five answers and three notes:

| answer | meshes | decided by |
|---|---|---|
| read from his photographs | 127 | no other source recorded: the SIO's labels, the skin, the fat |
| read from his CT | 226 | the source names BoneHub, TotalSegmentator or the CT |
| the University of Denver's models of this same body | 94 | the source names them |
| drawn | 91 | the builder marked it generated or drawn (face muscles, vessels, nerves, eyeballs, nails, the throat's lining), and all hair |
| not part of the body | 1 | the cloth |

Notes: 15 teeth are named by their place in the row, an estimate; the 18 bones of the skull are his skull, but
where one ends and the next begins follows an atlas fitted to it; 7 meshes are what their data does not name
further (the unnamed muscle mass, four pieces of bone, unclassified cartilage and veins).

## 5. Finding what was touched (O)

The model is 5.2 million triangles in 539 meshes, without colliders.

- **Colliders** (a physics ray): 539 mesh colliders would have to be cooked from 5 million triangles, and they
  would stand where the meshes are stored, not where they are drawn: a lid that is open and a jaw that is turned
  are moved in the vertex shader. Not done.
- **A ray against the triangles on the processor**: the same objection, and a fifth of a second for the skin.
- **Drawing once more, in numbers** (done: `ModelPick`, the shader's "Pick" pass): on a tap the meshes that
  can be touched are drawn again into five by five pixels round the touched one, each in its own number as a
  colour, by the same vertex program as the picture; the middle pixel is read. Both faces are drawn and the
  nearest wins. The spec's picking for the volume works the same way (2.5).

Hair is not offered to the pick: strands are no structure to name, and the skin under them is what was meant.
With the skin on, a tap anywhere on him therefore says skin (or a nail, a gum, the cloth); the student takes
layers away with the layer buttons to reach what is under it, as the spec's scenario has it.

## 6. Showing the name (O)

Everything else on the Model Lab's screen is drawn by Unity's immediate GUI, which is in no picture the snapshot
tool takes: the product owner judges by pictures, and a card that cannot be shown in one cannot be judged. So the
card is made of meshes that ride with the camera (a panel and lines of text a few centimetres before the lens,
laid out in screen pixels), and the camera draws it itself, on the screen and in the pictures alike.

The picked structure is marked in green: its own shading under a wash of one colour, lit as it is lit. A tint
alone was tried first and only darkened what is red already (a picked muscle was a dark stripe); blue was tried
next and is the colour the veins are drawn in. The skin is not marked when it is the one picked: it is all of
him.

The card: the name large in the language chosen (Italian first: the product is for Italian universities); the
other two under it; the layer; then where the shape comes from, in amber when it is drawn. With Latin names the
card's own words are Italian.

## 7. What stays open

- (Closed the same day.) Found with the new pick, by asking what is in front at a yellow speck on the chest: a
  spot of fat stood in front of the skin there. Asked of sixteen whole views, 2620 pixels were not skin: fat in
  three rings where photographs were passed over, and fingers' bones at six fingertips. The check on whole
  triangles now runs over all of him, and the same sixteen views show nothing but skin (ARCHITECTURE, Nothing
  shows through the skin).

- The names are unchecked (section 2).
- The spec's short descriptions (3.3, `anatomy_info.json`: two to four sentences per structure and language)
  are not written: the card names, it does not yet explain.
- A long press, a highlight that does not tint the whole structure, and the spec's UI Toolkit panels are not
  built. The layer and language buttons are still Unity's immediate GUI.
- The skin is one mesh: a tap on it cannot say "forearm" or "cheek". Regions of the skin are not named.
