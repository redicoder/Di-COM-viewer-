# Research behind the anatomy model

The reports the Model Lab's body was built from (2026-11-12). Each was written by a research pass before the
part it covers was built; the decisions taken from them are in `docs/SPEC_NOTES.md`. In every report a number or
claim is marked as read at its source, taken from a search summary, or from memory: check a from-memory number
before showing it to a student as fact. Licences were quoted from the sources' own pages on that date; read them
again before shipping anything new.

| Report | What it covers | Used for |
|---|---|---|
| `realtime_skin_hair.md` | How games render skin and hair; hair as strands; a ranked plan for our shaders; free assets with licences | the skin shading, the hair strands and `LabHair.shader` |
| `skin_features_hair_maps.md` | Hair density, length, thickness and growth direction by body region; sizes of lips, eyes, brows, nipples, navel, nails; colour zones | `tools/anatomy_model/zones.py`, `hair.py` |
| `palette.md`, `palette.csv` | Tissue colours measured from photographs, and feature colours as ratios against skin | the skin zones and `palette.py` |
| `open_data.md` | Open anatomy data and their licences: named bones and leg muscles of the same body, limb vessels from a generic atlas, what is not usable | the skeleton (BoneHub); the leg muscles and vessels still to come |
| `cut_bleed_eyelid.md` | Skin and fat thickness, vessels, bleeding, the eyelid; how real-time cutting is done; what the body must carry; the MAGES SDK verdict | the plan for the scalpel, bleeding and the eyelid |
| `face_head_assets.md` | Template heads and their licences (ICT-FaceKit, MIT), how to fit one to a scanned head, face detail assets | step 2 of the head (separate lids, eyeballs, mouth) |
| `head_anatomy_data.md` | Data for the head's layers: what exists for skull bones, facial muscles, eyes, teeth, vessels, nerves, brain; numbers for what must be generated | step 3 of the head |
| `head_data.md` | What our own photographs and CT hold for the head at full resolution, with measurements | step 1 of the head (done) |
| `muscle_surface.md` | (2026-11-17) Colours of muscle and fat in the photographs; runs of photographs with darker fat; photographs that are not whole; **the photographs were not registered to each other** (six sideways jumps of 1.7 to 4.3 mm, measured, and confirmed by the SIO's own crop) | the muscles' surfaces (`fine_muscle.py`); the photographs' registration (`tools/register_photos.py`) and the rebuild of the body on it |
| `nails.md` | (2026-11-23) What the photographs hold of the nails (not readable by a rule), the sizes used, what was measured on his toes, how a nail's place is found and what failed, why the fingers wait | the toes' nails (`nails.py`) |
| `head_outline.md` | (2026-11-24) How far the head's old outline stood off his skin (1.65 mm at the face, 4 to 16 mm over the crown); why the crown is worst (the camera sees the scalp further down through the gelatin); what the tissue rule gives at the nostrils, cavities, lids and ears; what was fitted to the old skin and what showed through the new one | the head's skin (`fine_skin.head_outline`), `head_layers.faces_under_skin` |
| `names.md` | (2026-11-25) The 539 meshes and who named them; why the Latin and Italian are composed by rule; what is least sure in them (unchecked); read or drawn, in five answers; three ways to find what was touched and why the meshes are drawn again in numbers; why the card is made of meshes | the names (`anatomy_model/names.py`, `ModelPick`, `ModelNames`, `ModelCard`) |
| `under_layers.md` | (2026-11-25) What each layer under the skin looked like (fat, muscles, skeleton, organs) and the order of work; the fat: its surface from the skin's outline, and the five things found on the way (the outline is not the skin as drawn; the windows in the face ran together; what lies under the fat; no fat under the red of the lips; it must go with the jaw as the skin over it goes); what stays open; the muscles: why the arms looked like lace (each was in the model twice), how near the skin a muscle may begin, thin sheets, the rectus sheath, the lips' muscle; the organs: the windpipe's label is its wall only, the "torn lungs" were the heart's sac | the fat (`fat_shell.py`), `head_layers.under_skin_everywhere(under_fat)`, `mouth.on_the_skin`, `ModelSnapshot.RunThrough` (through the fat; the mouth open); the muscles (`fine_muscle.under_limit`, `thin_parts`, `SHEETS`); the organs (`thin_organs.py`: the windpipe and the bronchi as tubes, the heart's sac opened) |
| `throat.md` | (2026-11-16) What the photographs and the CT hold behind the mouth: soft palate, uvula, tonsils, back wall, with measurements; what cannot be read; why the jaw's axis lies under its joints | the throat (`throat.py`), the jaw's axis, the mouth's bag |

The pictures and working files of the research (crops of the photographs, downloaded reference images) stay in
`build/research/`, which is not committed: the photographs are data, and the reference images are other people's.
