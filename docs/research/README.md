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
| `muscle_surface.md` | (2026-11-17) Colours of muscle and fat in the photographs; runs of photographs with darker fat; photographs that are not whole; **the photographs are not registered to each other** (six sideways jumps of 2 to 4.6 mm, measured) | the muscles' surfaces (`fine_muscle.py`); the registration still to be done |
| `throat.md` | (2026-11-16) What the photographs and the CT hold behind the mouth: soft palate, uvula, tonsils, back wall, with measurements; what cannot be read; why the jaw's axis lies under its joints | the throat (`throat.py`), the jaw's axis, the mouth's bag |

The pictures and working files of the research (crops of the photographs, downloaded reference images) stay in
`build/research/`, which is not committed: the photographs are data, and the reference images are other people's.
