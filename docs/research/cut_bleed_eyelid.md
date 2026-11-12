# Cutting, bleeding, pinching, eyelids: what the body model must be built for

Research report, 2026-11-12. Education-only anatomy app. Blood is a labelled simulation: a cadaver does not bleed.

How to read the numbers. Every number carries a mark:

- **[V]** read in a source during this work (a paper saved under `build/research/` or a page fetched today)
- **[T]** standard textbook / review value written from memory, NOT re-read today (NCBI and StatPearls refused automated
  access, see section 6)
- **[E]** engineering estimate or a calculation made here; a starting value for a simulation, not a measurement

Sources saved by an earlier run and reused here: `build/research/epmc/*.txt` (open-access papers), `build/research/wiki/*.txt`
(vessel courses), `build/research/pdf/` (Ni Annaidh 2012), `build/research/cut_bleed_pinch/papers/` (Wu-Westermann-Dick
survey, GRIDiron, SkinFlaps readme, PBF, Kvick thesis, NVIDIA blood shader, Daenzer), `build/research/cut_bleed_pinch/data_hra/`
(HRA vasculature of the Visible Human Male).

---

## 0. What the repository already has (docs/ARCHITECTURE.md, docs/SPEC_NOTES.md)

The older volume-based Anatomy Lab already contains every requested behaviour in a first form:

| Existing part | How it works | What it needs from the body |
|---|---|---|
| `MaskVolume` + `LabScalpel` | drag carves a thin V incision into a mask on the photo grid (1.8 mm capsules, sinking to 5 mm over the first 3 mm), one undo step per stroke | a voxel grid in the body's frame |
| `TissueWarp.Gape` (compute) | a baked backward-displacement field draws the edges apart into a lens shape | a 3D displacement texture the body shader samples (`WarpUVW`) |
| `TissueSheet` + `TissueSheetJob` (Burst) | 64 x 64 two-layer XPBD sheet (skin surface, fat base), dermis ~1 MPa, fat ~3 kPa, shape matching, anisotropic fat-to-fascia junction (tears at 1.5 mm lift / 3 mm slide; fat at 4.5 mm shear), gravity, contact | skin-depth grid, colour under the surface |
| `BloodSim` + `BloodFluidFeature` | GPU drops fill the wound, spill, run along the skin under gravity, dry into a half-resolution 3D stain texture; drawn as liquid (sphere-imposter depth, narrow-range smoothing, thickness, Beer-Lambert) | body depth in `_CameraDepthTexture`, a surface to run on, "how red is this tissue" |
| Eyelids in `PhotoBody.shader` | opened geometrically in the ray-march (an almond fissure, lids slide into the orbit); `LivingEye` modelled eyeballs | eyelid map, eye centres |
| `SkinMesh` | 200-400k triangle skin over the volume; clips itself by the mask; "a mesh skin does not stretch" | volume coordinate per vertex |
| `BodyLabels`, layers, `OrganPiece` | label index per voxel, layer per object, Take out as a surface-nets piece | `labels.raw`, `labels.json` |

The new body (`anatomy.glb`, `backend/tools/build_model_meshes.py`): about 190 named structures, 1.4 M triangles, four
layer nodes, computed from the same labelled voxel volume. **The voxel volume and the meshes share one frame; that is the
property everything below relies on.** What the old lab did in a ray-marched volume must now work on meshes: a mesh skin
that cannot stretch, cannot gape and has no slit between the eyelids is the gap to close.

---

## 1. Anatomy numbers

### 1.1 Skin thickness (epidermis + dermis) by region

| Region | Epidermis mm | Dermis mm | Skin total to use | Mark and source |
|---|---|---|---|---|
| Eyelid | 0.04-0.05 | 0.3-0.5 | **0.5** (thinnest of the body, no fat under it) | [T]; "thinnest ... no subcutaneous fat" confirmed by StatPearls snippet [V], the number is not |
| Forehead | 0.116 | 1.72 | **1.8** | [V] Meng/Feng et al., HFUS map of 189 adults, PMC9838783 |
| Cheek | 0.116 | 1.80 | **1.9** | [V] same |
| Scalp | ~0.1 | 1.6 | **1.7** by ultrasound (plus dense fat 2-3 mm and the galea; whole scalp 5-6 mm) | [V] 1.71 mm, PMC12445948; scalp total [T] |
| Neck, front | ~0.1 | 1.0-1.5 | **1.5** | [T] |
| Neck, nape | ~0.12 | 2.5-3.5 | **3.0** | [T] |
| Chest | 0.115 | 1.82 | **1.9** | [V] PMC9838783 |
| Abdomen | 0.132 | 1.56 (2.09 in men incl. epidermis, Derraik) | **2.0** | [V] PMC9838783; [V] Derraik et al. 2014, PMC3897752 |
| Back | 0.128 | 2.84 | **3.0** (upper back to 4) | [V] PMC9838783; "thickest dermis: back" |
| Upper arm, inner (flexor) | 0.141 | 0.91 | **1.05** (thinnest dermis measured) | [V] same |
| Upper arm, outer | 0.137 | 1.34 | **1.5** | [V] same |
| Forearm, inner | 0.134 | 1.00 | **1.1** | [V] same |
| Forearm, outer | 0.135 | 1.21 | **1.35** | [V] same |
| Palm | 0.4-0.6 (thick horny layer) | 1.0-1.5 | **1.5-2.0** | [T] |
| Dorsum of hand | ~0.1 | 0.8-1.2 | **1.0** | [T] |
| Thigh, inner | 0.150 | 1.06 | **1.2** | [V] PMC9838783 |
| Thigh, outer | 0.141 | 1.32 (1.86 in men incl. epidermis, Derraik) | **1.5-1.9** | [V] both |
| Shin / calf (medial, lateral leg) | 0.139 / 0.147 | 1.18 / 1.23 | **1.3-1.4** | [V] PMC9838783 |
| Sole | 0.6-1.4 (heel up to 1.5) | 1.5-3 | **2.5-4** | [T] |

Notes. In PMC9838783 the epidermis column is headed "mm" but the values are micrometres (115 um, not 115 mm). Men's
dermis is thicker than women's at most sites (forehead 1.95 vs 1.54 mm, back 2.96 vs 2.77 mm) [V]. At 1.3 x 2 mm voxels
the dermis is one voxel or less everywhere: **skin thickness cannot be measured from the body's voxels and must come
from this table by region.**

### 1.2 Subcutaneous fat by region, 90 kg / 180 cm man (BMI 27.8, "overweight")

| Region | Fat thickness mm | Mark and source |
|---|---|---|
| Abdomen, beside the navel | **22 +/- 9.5** (superficial layer 8.6, deep layer 14.3, divided by Scarpa's membranous layer); 16.9-17.9 in Derraik's men (BMI 28) | [V] ultrasound, overweight men, n = 376, PMC11869708; [V] PMC3897752 |
| Chest (pectoral) | **10 +/- 6.5** | [V] overweight men, n = 303, PMC11869708 |
| Thigh, front / lateral | **9 +/- 3.5** (9.3-9.8 in Derraik) | [V] both |
| Flank / above the iliac crest | 15-25 | [T] skinfold literature |
| Back under the scapula | 8-12 | [T] |
| Buttock | 25-40 | [T] |
| Upper arm, back (triceps) | 6-10 | [T] |
| Upper arm, front (biceps) | 3-5 | [T] |
| Forearm | 2-4 | [T] |
| Calf, medial | 5-8 | [T] |
| Cheek | 8-15 (malar and buccal fat) | [T] |
| Neck, front | 3-6 (the platysma lies inside it) | [T] |
| Scalp | 2-3, dense, bound by fibrous septa | [T] |
| Palm | 2-4, fibro-fatty pads | [T] |
| Heel pad | 15-18; forefoot 10-12 under the metatarsal heads | [T] |

**Fat nearly absent (0-3 mm):** eyelids, ear, bridge of the nose, lips' red margin, penis and scrotum (dartos instead),
over the shin (antero-medial tibia), kneecap, elbow point, knuckles and dorsum of hand and foot, malleoli, clavicle,
sternum (3-8 mm), spinous processes, iliac crest, the linea alba line is thinner than beside it [T].

**Better than any table:** this body's own fat. The export already holds a skin-depth map and a layer per voxel; the
earlier run left two scripts that measure skin + fat thickness from them
(`build/research/cut_bleed_pinch/tools/layer_stats.py`, `front_thickness.py`: depth of the first muscle/bone voxel under
the skin, by height band). Fat thickness per skin vertex should be **measured from his voxels** (distance along the
inward normal from the skin to the deep fascia = first muscle, bone or organ voxel), and the table above used only as a
sanity check and for the dermis.

### 1.3 What a scalpel cut shows, layer by layer

| Layer | Thickness | Colour and texture on the cut wall | Living (simulated) | Cadaver |
|---|---|---|---|---|
| Epidermis | 0.05-0.15 mm (palm, sole 0.4-1.5) | a hair-thin translucent line, skin-coloured; never bleeds (no vessels) | dry | same; may slip off in sheets after days |
| Dermis | 1-3 mm | dense, pearl-white to pale pink, leathery, cuts with resistance, edge stays sharp and square | pin-point bleeding in a row along the edge, from the plexus under the papillae and the deep dermal plexus | white-grey, dry or a little dark seepage in dependent (livid) parts |
| Subcutaneous fat | 0-40 mm | bright yellow glistening lobules (1-3 mm in the superficial layer, flatter and larger, 5-10 mm, in the deep layer) between white fibrous septa (retinacula cutis); on the abdomen a thin white sheet (Scarpa) halves it | bulges out of the cut, oozes from septal vessels; cut superficial veins well up dark | deeper yellow to tan, firm and greasy when cold, embalmed: grey-yellow, crumbly |
| Deep fascia | 0.5-1 mm (fascia lata to 1.5-2) | white-silver, glistening, tough sheet with visible crossed fibres; the knife "catches" on it | hardly bleeds | same, duller |
| Muscle | to bone | fibres in bundles 1-3 mm with thin white partitions (perimysium), direction visible | beef red, twitches, bleeds freely | unembalmed dark red-brown; embalmed grey-brown to tan, dry |
| Periosteum / bone | 0.2-0.5 / - | white membrane; cortical bone ivory-yellow | bleeds from the bone surface | dry |

All [T] (gross anatomy and dissection-manual descriptions). The layer order on the abdomen, with the membranous layer,
is in the saved Camper / Scarpa texts (`wiki/Fascia_of_Scarpa.txt`) [V].

### 1.4 How much a wound gapes

- Skin is under tension even after death: Langer (1861) found his lines **on cadavers**, round stab holes became
  ellipses with the long axis along the fibres [V, `wiki/Langer's_lines.txt`]. So gaping needs no life; a fixed or frozen
  body gapes less (stiffened tissue) [T].
- Cut **along** the lines: the edges stay close. Cut **across**: the wound opens to a lens. An experiment on pigskin
  found edge retraction, modulus and closing tension all higher for wounds across the tension [V, search result,
  "Excisional wound biomechanics, skin tension lines and elastic contraction"].
- Skin's in-vivo pre-stretch is about 10-30 % and excised skin shrinks 10-30 %, more along the lines [T, Ridge & Wright
  1966, Jor et al. 2011; not re-read].
- Residual stress is what opens a cut in a simulator too: Wu, Buerger, Westermann, Dick 2012, "Interactive residual
  stress modeling for soft tissue simulation" [V, saved]. The existing `Gape` kernel is the cheap form of this.
- On the lower limb the least-tension direction is **longitudinal** (tensiometer study, 23 excisions: vertical closure
  had significantly lower closing tension than wrinkle-line closure) [V, Paul 2018, PMC5889464].

Working values for a 50 mm full-thickness skin incision, gape at the middle [E, to be tuned by eye against photographs]:

| Region | Across the lines | Along the lines | Why |
|---|---|---|---|
| Back, shoulder | 10-15 mm | 3-5 mm | thick skin, high tension |
| Chest, abdomen | 8-12 | 2-4 | abdomen opens further once Scarpa is through |
| Thigh, upper arm | 8-12 | 2-4 | |
| Forearm, leg | 5-8 | 2-3 | |
| Face, neck | 4-8 | 1-2 | thin, mobile, muscles insert into it |
| Eyelid | 2-4 (vertical cut) | 0.5-1 (horizontal) | orbicularis fibres run horizontally |
| Scalp | 1-2; 10+ once the galea is cut | - | skin bound to the galea |
| Palm, sole | 1-2 | 1-2 | bound down by septa |

Model: gape width = k x pre-tension(region) x length x sin^2(angle between the cut and the line) + a small isotropic
term; the lens shape is widest in the middle and zero at the ends; depth through the dermis only gives about a third of
the full gape, through the fat the rest [E].

### 1.5 Bleeding by vessel type (for the "living simulation" mode)

Blood as a fluid: density **1060 kg/m^3** [T]; viscosity **3.5-5.5 cP** (mPa s) at high shear, shear-thinning, rising to
tens of cP at very low shear [V, Nader et al. 2019, PMC6842957]; surface tension about 0.056 N/m [T]; volume about
70 ml/kg, **6.3 l** in a 90 kg man [T].

| | Capillary ooze | Venous flow | Arterial flow |
|---|---|---|---|
| Source | the whole cut dermal edge and fat septa | a cut vein cross-section | a cut artery cross-section |
| Driving pressure | 15-35 mmHg in the capillaries [T] | 5-15 mmHg lying down (a head of 7-20 cm of blood); up to ~90 mmHg at the foot standing [T] | 120/80 mmHg, mean ~93 (a head of ~1.3-1.6 m of blood) [T] |
| Look | bright to mid red beads that join into a film | dark red, steady, wells up and runs | bright red, spurts in time with the pulse (60-80 /min), arc up to 0.3-1 m from a large artery |
| Time course | stops by itself in 2-9 min (bleeding time) [T] | slows as the vein collapses; minutes | small arteries narrow in spasm within seconds to a minute; large ones do not stop |

Flow for cut vessels by bore. Method [E]: resting flow = cross-section x typical mean velocity; "cut" = 3-5 x resting,
because the downstream resistance is gone (as in reactive hyperaemia); the ceiling is the free jet at full pressure,
v = sqrt(2 dP / rho) = 5 m/s at 100 mmHg, which viscosity never lets a small vessel reach. Checked against measured
resting flows: brachial artery (4.4 mm) 50-150 ml/min, radial (2.5 mm) 20-50 ml/min [T].

| Bore | Area mm^2 | Artery at rest ml/min | **Artery cut, ml/min** | **Vein cut, lying, ml/min** | Jet ceiling ml/min |
|---|---|---|---|---|---|
| 0.5 mm | 0.20 | 0.6 (5 cm/s) | **2-5** | **0.2-0.5** | 59 |
| 1 mm | 0.79 | 4.7 (10 cm/s) | **15-40** | **1-4** | 236 |
| 2 mm | 3.14 | 28 (15 cm/s) | **80-200** | **10-30** | 940 |
| 4 mm | 12.6 | 150 (20 cm/s) | **400-800** | **50-150** | 3770 |

Capillary ooze: about **0.02-0.1 ml/min per cm of skin incision**, decaying to zero over 2-9 min [E, from the template
bleeding-time test]. Pulse shape for an emitter: v(t) = v_mean x (1 + 0.6 x pulse(t)), pulse = a sharp rise over 0.1 s
and a decay over 0.3 s, repeated at 1.1-1.3 Hz [E]; for the carotid, peak 115 and end-diastolic 32 cm/s in young men [V,
`wiki/Common_carotid_artery.txt`].

Clotting and drying: bleeding time 2-9 min; whole-blood clotting time 5-15 min in glass; the clot shrinks over 30-60
min [T]. A thin film skins over in 10-20 min and is dry in 1-2 h in room air; drops of 1-4 mm dry in 15-60 min [E].
Colour: arterial bright red, venous dark red; drying turns red-brown within hours (met-haemoglobin) and dark brown to
near black over days (hemichrome) [T, Bremmer et al. 2011, PLoS ONE, not re-read]. sRGB starting points [E]: arterial
(170, 12, 12), venous (115, 5, 12), dried 1 h (95, 15, 12), dried 1 day (60, 22, 15).

**In a cadaver (no pressure) [T, livor timing V from `wiki/Livor_mortis.txt`]:** the heart has stopped, so nothing
spurts and nothing oozes from capillaries. Blood sinks to the lowest parts (livor: starts in 20-30 min, visible at 2 h,
largest at 8-12 h, then fixed) [V]; arteries are almost empty, veins hold dark blood that is partly fluid, partly soft
clot. A cut through a filled vein in a dependent part lets dark blood **seep out slowly under gravity only** (a few
ml, no pulse, stops when the local vein is empty); a cut on the upper side stays dry. An embalmed body has fixed, grey
tissue and no flowing blood at all; the Visible Human Male was frozen. So the app's two modes are right: **dry
dissection (the truth for a cadaver)** and **bleeding as a labelled simulation of the living body**. A third,
"cadaver seep" (veins only, gravity only, dark, 0.5-5 ml per vein) is cheap and true.

### 1.6 Superficial veins and arteries as landmark paths (tubes under the skin)

Depth is measured from the skin surface to the vessel's centre. Superficial veins lie in the fat **on the deep fascia
side of the superficial layer**; where fat is thin they are 1-3 mm deep, under thick fat they stay within the outer
third to half [T]. At the elbow 89 % of visible veins were less than 3 mm deep and 91 % had an area of 2.5 mm^2 or more
(diameter >= 1.8 mm) [V, Nakatani group 2020, PMC7046143]. Flow in every vein is towards the heart.

| Vessel | Path as ordered landmarks | Diameter mm | Depth mm | Mark |
|---|---|---|---|---|
| Dorsal venous arch of foot | across the dorsum over the metatarsal shafts, 2-3 cm behind the toe webs, convex towards the toes; medial end -> great saphenous, lateral end -> small saphenous | 2-3 | 1-3 | course [V wiki], sizes [T] |
| Great saphenous v. | medial end of the arch -> **in front of the medial malleolus** -> medial border of the tibia up the leg -> **a hand's breadth behind the medial edge of the kneecap** (behind the medial femoral epicondyle) -> antero-medial thigh -> saphenous opening **3-4 cm below and lateral to the pubic tubercle** -> femoral vein | 2.5 leg, 3 knee and mid thigh, 3.7-4 upper thigh, 6.5-7.5 at the junction | 2-5 at the ankle, 5-15 leg, 10-30 thigh (on the deep fascia in its own sheath) | course [V wiki]; diameters [V, duplex studies via search]; depth [T/E] |
| Small saphenous v. | lateral end of the arch -> **behind the lateral malleolus** -> lateral edge of the Achilles tendon -> midline of the calf between the heads of gastrocnemius -> pierces the fascia in the lower popliteal fossa -> popliteal vein | 2-4 (4.6 mm is a cut-off for a diseased one) | 3-10; under the deep fascia in the upper half of the calf | course [V wiki]; cut-off [V]; rest [T] |
| Dorsal venous network of hand | 3 dorsal metacarpal veins between the knuckle rows, joined in an arch 2-3 cm proximal to the knuckles; radial end -> cephalic, ulnar end -> basilic | 1-3 | 1-2 | [T] |
| Cephalic v. | **anatomical snuffbox** -> round the radial border of the forearm to its front -> lateral to the biceps tendon at the elbow -> lateral edge of biceps -> **groove between deltoid and pectoralis major** -> dives under the clavicle (clavipectoral triangle) -> axillary vein | 2-3 forearm, 3-4 arm | 1-5 | course [V wiki]; sizes [T] |
| Basilic v. | ulnar side of the hand network -> back-medial forearm -> front of the elbow medial to the biceps tendon -> **pierces the deep fascia at mid-arm** in the medial bicipital groove -> beside the brachial artery -> axillary vein at the lower border of teres major | 3-5 (the largest arm vein) | 2-6, then deep | course [V wiki]; sizes [T] |
| Median cubital v. | from the cephalic **2.5 cm below the lateral epicondyle** obliquely up and medially over the bicipital aponeurosis to the basilic **2.5 cm above the medial epicondyle** | 3-5 | 1-3 | course [V wiki]; sizes [T] |
| External jugular v. | **angle of the mandible** (inside the parotid) -> straight down across sternocleidomastoid, on a line to **the middle of the clavicle**, under the platysma -> pierces the fascia 2-3 cm above the clavicle -> subclavian vein | 5-8 (very variable) | 2-5 | course [V wiki]; sizes [T] |
| Anterior jugular v. | from under the chin near the hyoid -> down about 1 cm from the midline -> just above the sternum turns laterally under sternocleidomastoid -> external jugular; the two joined by an arch above the sternum | 2-4 | 2-4 | course [V wiki]; sizes [T] |
| Superficial temporal a. (+ v.) | from behind the neck of the mandible -> **over the root of the zygomatic arch just in front of the tragus** -> 2-4 cm above the arch splits into a frontal branch (forwards, winding, towards the forehead) and a parietal branch (up and back) | artery 1.5-2.5; vein 2-3 | 2-4 (in the temporal fascia layer) | [T] |
| Facial a. (+ v.) | hooks round the **lower border of the mandible at the front edge of masseter** -> winding course to 1-1.5 cm beside the corner of the mouth -> along the side of the nose -> inner corner of the eye. The vein runs straighter and behind it, from the inner corner of the eye to the same point on the mandible | artery 2-3; vein 2.5-3.5 | 3-10 (under the facial muscles of expression in places) | [T]; vein course [V wiki] |
| Superficial epigastric a. (+ v.) | from the femoral artery **1 cm below the inguinal ligament** -> up over the ligament -> between the two layers of the abdominal fat **towards the navel**; the vein returns to the great saphenous at the saphenous opening | artery 1-1.5; vein 2-3 | half the fat thickness, 5-12 | course [V wiki]; sizes [T] |
| Thoraco-epigastric v. | from the superficial epigastric vein up the side of the trunk along the mid-axillary line to the lateral thoracic vein (axilla) | 1-3 | 3-10 | course [V wiki]; sizes [T] |

Deep named vessels (arteries flow away from the heart; each limb artery has one or two veins beside it):

| Vessel | Course by landmarks | Diameter mm | Mark and source |
|---|---|---|---|
| Common carotid a. | from behind the sternoclavicular joint up under the front edge of sternocleidomastoid to the **upper border of the thyroid cartilage**, where it divides | **6.5** men (6.1 women); length 13-14 cm | [V] Krejza et al. 2006 via HRA table; wiki |
| Internal jugular v. | from the jugular foramen down lateral to the carotid inside the same sheath to behind the inner end of the clavicle | **10-15** (CT mean 15.5 +/- 5.2; range 5-35) | [V] Tartiere et al. 2009 via HRA table; wiki |
| Subclavian a. | arches over the first rib behind scalenus anterior, to the outer border of the first rib | **9-10** (CT 9.5 +/- 1.7 men; "9-12 wide") ; left 9 cm, right 6 cm long | [V] HRA table; wiki |
| Axillary a. | outer border of the first rib -> behind pectoralis minor -> lower border of teres major | 6-8 | [T] |
| Brachial a. | medial side of the arm in the groove between biceps and triceps -> front of the elbow medial to the biceps tendon -> divides 1 cm below the elbow crease; length 23 cm | **4.4 +/- 0.9** | [V] Chami et al. 2009 (n = 682) via HRA table |
| Radial a. | from the elbow down the lateral forearm under brachioradialis -> at the wrist **lateral to the flexor carpi radialis tendon** (the pulse) -> across the snuffbox | 2.3-2.7 | [T] |
| Ulnar a. | deep under the flexor muscles to the medial forearm -> at the wrist lateral to the pisiform -> superficial palmar arch (about 1 cm distal to a line from the first web to the hook of hamate) | 2.3-2.8 | [T]; arch [V wiki] |
| Femoral a. | **mid-inguinal point** (halfway between the anterior superior iliac spine and the pubic symphysis) -> down the front-medial thigh under sartorius -> through the adductor hiatus a hand above the knee | **9.8** common (men; 8.2 women); upper reference 10.2 proximal, 7.7 distal; typical distal 5.2-6.4 | [V] Sandgren et al. 1999 via HRA table; [V] SHIP MR-angiography of 756 men, PMC6010244 |
| Femoral v. | medial to the artery at the groin | **11-17** (mean 14) | [V] cadaver study via HRA table |
| Popliteal a. | midline of the popliteal fossa, deepest structure, to the lower border of popliteus | **4.9-5.9** typical, 6.9 upper reference | [V] PMC6010244 |
| Anterior tibial a. | through the interosseous membrane -> front of the leg on the membrane, lateral to the tibia -> midway between the malleoli -> dorsalis pedis (2-3 mm, lateral to the big-toe extensor tendon) | **3.1-3.5**, 4.2 upper reference | [V] PMC6010244; dorsalis pedis [T] |
| Posterior tibial a. | deep back of the leg -> **behind the medial malleolus**, halfway to the heel | **~3**, 3.8 upper reference | [V] PMC6010244 |
| Fibular a. | deep back of the leg along the fibula | **~3.3**, 4.0 upper reference | [V] PMC6010244 |

Ready-made vessels for this very body: the **HRA "3D Reference Organ for Blood Vasculature, Male"** (HuBMAP, built on the
Visible Human Male; Browne & Schlehlein 2022) was downloaded by the earlier run
(`build/research/cut_bleed_pinch/data_hra/*.glb`, 106 named meshes, 416k triangles) with a table of vessel diameters and
their sources (`blood-vasculature-geometry_v2.0.csv`). Its meshes are the **central vessels of trunk and head** (aorta
and branches, carotid, subclavian, iliac, mesenteric, renal, hepatic, portal, coronary, pulmonary, ophthalmic). It has
**no limb vessels and no superficial veins** (judged from the saved list of its 106 mesh names): those must be laid
from the paths above. The SIO labels already name the torso's large vessels in his own voxels. The HRA objects are
CC BY 4.0 (section 6); their frame is not ours, so they would need registering to the export.

### 1.7 The eyelid, for "pinch to open"

Layers, front to back [T]:
- over the tarsal plate (the lower 10 mm of the upper lid): skin 0.5 mm -> orbicularis muscle (pretarsal, ~1 mm) ->
  tarsal plate 1 mm (the levator's tendon sheet inserts on its front) -> conjunctiva, bound to the plate.
  Total about **2.5-3 mm** at the margin; the margin itself is 2 mm thick front to back and about 30 mm long.
- above the plate: skin -> orbicularis (preseptal) -> orbital septum -> a fat pad -> levator tendon sheet ->
  Mueller's muscle -> conjunctiva. This part is **loose and folds**; it makes the lid crease.

| Quantity | Value | Mark |
|---|---|---|
| Tarsal plate, upper | 10 mm high (10-12 in the centre), 25-29 mm long, 1 mm thick | [V] 10 mm (wiki / Gray); 10-12 and 29 mm (StatPearls snippets) |
| Tarsal plate, lower | 4 mm (3.5-5) high | [V] "up to 4 mm" / "5 mm" in two sources |
| Palpebral fissure (open, living) | **30 mm wide, 10 mm high** (8-11) | [V] wiki and StatPearls snippet |
| Outer corner | about 2 mm higher than the inner corner | [T] |
| Upper lid margin, eye open | covers the top 1-2 mm of the cornea; lower margin at the cornea's lower edge | [T] |
| Upper lid crease | 8-10 mm above the margin (men 7-8) | [T] |
| Upper lid travel (levator) | **12-15 mm** from looking down to looking up; Mueller's muscle adds ~2 mm | 2 mm [V StatPearls snippet]; 12-15 [T] |
| Lower lid travel | 3-5 mm on looking down | [T] |
| Lower lid pulled off the globe | 6-8 mm at most in a normal lid | [T] |
| Inner corner tendon | from the inner ends of both plates to the bone crests around the tear sac (front and back limb) | [T] |
| Outer corner tendon | from the outer ends of the plates to a bony bump just inside the outer orbital rim, ~10 mm below the suture line of the brow | [T] |
| Lashes | **upper 90-160 in 5-6 rows, lower 75-80 in 3-4 rows**; upper 8-12 mm long curving up, lower 6-8 mm curving down | counts [V] Aumond & Bitton 2018, PMC6147748; lengths [T] |
| Oil glands in the plate | 30-40 upper, 20-30 lower (yellow vertical streaks seen through the inner surface) | [T] |
| Eyeball | **24 mm** front to back (23-25), 24 wide, 23.5 high; sclera radius 12 mm | [T] |
| Cornea | **11.5-11.7 mm** wide, 10.6-11 high, radius of curvature 7.8 mm, 0.52-0.55 mm thick in the centre, stands 2.5-3 mm proud of the sclera sphere | [T] |
| Iris | 12 mm across; seen through the cornea 11.7 mm | [T] |
| Pupil | 2-4 mm in light, 4-8 mm in the dark | [T] |

What "pinch to open" must do mechanically: the **plate is stiff and keeps its curved shape** (a 10 x 27 x 1 mm shell
that fits the globe); the skin over it is bound to it; the skin above it is thin, loose and folds into the crease.
Lifting the upper lid in a dead person slides the plate **up and back over the globe** (radius 12 mm + ~1 mm) about the
two corner tendons as hinge points, until the margin reaches the upper orbital rim (10-12 mm of travel exposes the
whole cornea and 1-2 mm of sclera above it). There is no muscle tone: a lifted lid stays roughly where it is left or
sinks back slowly under its own weight and the friction of a drying surface [T]. The lower lid pulls down 3-5 mm and
6-8 mm away from the globe. The inner surface (conjunctiva) is pale pink-white in a cadaver, wet-red in the living.

The eye of a dead person when the lid is lifted [timing: StatPearls "Postmortem changes" as returned by search, V; the
rest T]:
- pressure inside the eye falls to nothing in about 2 h (disputed; other notes say 4-8 h) [V]: the globe is soft, the
  cornea can dimple under a finger;
- the cornea loses its shine within minutes if the lids were open, turns hazy in about 2-3 h with open lids and only
  after about a day with closed lids, and is milky-opaque by 2-3 days [V for 2-3 h and "closed lids delay it"; T rest];
- **tache noire**: with lids left open, a yellowish then brown-black triangle or band on the exposed sclera either side
  of the cornea, from 3-4 h (other sources 6-12 h) [V, sources disagree];
- pupil: mid-wide, typically 4-6 mm, round or slightly irregular, does not react; size is not reliable [T; sources
  found today conflict, see section 6];
- the Visible Human Male was frozen and the app's body has his real closed eyes; for a lifted lid the modelled eyeball
  should be the **post-mortem** one by default (dull, hazy cornea, 5 mm fixed pupil, sunken 1-2 mm), with the existing
  `LivingEye` as the "living" option.

### 1.8 Mechanical properties

| Tissue | Small-strain stiffness | Large-strain / failure | Anisotropy | Mark and source |
|---|---|---|---|---|
| Skin (dermis) | in vivo 0.1-2 MPa (toe region, the first 20-30 % of stretch; suction and torsion tests); initial slope 1.18 +/- 0.88 MPa on excised back skin | linear-region modulus **83 +/- 35 MPa**; strength **21.6 +/- 8.4 MPa**; failure strain **54 +/- 17 %** (stretch ~1.5) | stiffer and stronger along Langer lines (orientation significant for strength, modulus and failure stretch); roughly 2 : 1 | [V] Ni Annaidh et al. 2012, excised human back skin (`pdf/niannaidh2012.txt`); in vivo range [T] |
| Subcutaneous fat | **~1-2 kPa** (human 1.6 kPa initial) | 11.7 kPa at 30 % strain; lobules shear and tear along septa at 30-50 % | nearly isotropic; septa stiffen it across the layer | [V] Comley & Fleck 2010 and others via search |
| Muscle, passive | 10-50 kPa across the fibres; 50-150 kPa along them (relaxed, fresh) | fails at 30-60 % stretch; indentation values rise steeply with load (62 kPa at 5 N to 440 kPa at 30 N in one cadaver table) | 2-5 x stiffer along the fibres; rigor or fixation stiffen it several-fold | [T]; indentation [V via search, methods unverified] |
| Deep fascia | 100-400 MPa along the main fibres (fascia lata), 30-70 MPa across | fails at 10-25 % strain | strong, two or three crossed fibre layers | [T] Butler 1984, Stecco / Pancheri 2014, not re-read |

The existing sheet's values (dermis ~1 MPa, fat ~3 kPa) are the right small-strain numbers. What it lacks is the
**strain-stiffening** (skin locks at 20-30 % stretch across the lines and 10-15 % along them): in XPBD this is a
strain limit, not a stiffer spring.

How far skin can be pinched up or stretched [E from clinical pinch and turgor tests, T]:

| Region | Lift between two fingers | Stretch before it locks | Slides over the deep layer |
|---|---|---|---|
| Eyelid | 5-10 mm (skin alone) | 30-50 % | freely |
| Cheek, neck | 15-30 mm | 25-40 % | 10-20 mm |
| Back of hand | 10-20 mm | 20-30 % | 5-10 mm |
| Abdomen, flank, inner arm | 20-40 mm as a fold with its fat | 20-40 % | 10-30 mm |
| Chest, thigh, forearm | 10-20 mm | 15-30 % | 5-15 mm |
| Back | 5-10 mm | 10-20 % | 5-10 mm |
| Shin | 3-8 mm | 10-15 % | 3-5 mm |
| Scalp | 2-5 mm (slides 10 mm as one layer over the skull) | < 10 % | as a whole, on the loose layer under the galea |
| Palm, sole | 1-2 mm | < 10 % | almost none |

SkinFlaps' own "known issues" list says the same from the surgical side: one stretch limit for all flaps is wrong,
"cheek and eyelid skin stretches much more than scalp and forehead" [V, `papers/skinflaps_readme.md`].

---

## 2. Techniques for real time

### 2.1 Cutting: the families (after Wu, Westermann, Dick, "A Survey of Physically Based Simulation of Cuts in Deformable Bodies", CGF 2015; preprint saved)

The survey sorts methods by (a) how the cut is put into the geometry, (b) which discretisation computes the
deformation, (c) how the visible surface is rebuilt. Its families, plus the game and voxel approaches it leaves out:

| # | Method | How the cut enters | Cut walls / layers visible | Cost and robustness | Who uses it | Fit for this project |
|---|---|---|---|---|---|---|
| 1 | Surface mesh cutting with re-triangulation | triangles crossed by the blade are split, vertices duplicated | **no**: the body is hollow unless a cap is built separately | cheap; slivers; no volume physics | MAGES SDK (section 3); most "mesh slicer" assets | no: a dissection is about the wall of the cut |
| 2 | Tetrahedral mesh: element removal / splitting / snapping | tets deleted, subdivided along the blade, or nodes snapped to it | yes (tet faces), needs interior colour | ill-shaped elements, time step collapses; needs a whole-body tet mesh | early surgery simulators (Bielser, Steinemann, Nienhuys) | no |
| 3 | Virtual node algorithm (Molino 2004, Sifakis 2007) | elements are **duplicated**, each copy owns part of the material; the fine surface is embedded | yes, from the embedded cut surface | robust; elements stay well shaped; bookkeeping heavy | film VFX; plastic-surgery research | ideas only |
| 4 | XFEM / enriched elements | discontinuous basis functions | yes, embedded | elegant, complex; stiffness changes | research (Jerabkova & Kuhlen 2009) | no |
| 5 | Hexahedral lattice / octree + composite elements, surface by dual contouring (Dick, Wu, Westermann 2011) | links between voxels are cut; the surface is re-contoured from the lattice | **yes, and the interior comes from the volume data** | interactive on CPU for 10^4-10^5 elements with multigrid | the survey authors' own simulators; **GRIDiron** (Mitchell, Cutting, Sifakis 2015: "a Cartesian grid-based embedded discretization ... hybridizing with an explicit hexahedral mesh" for thin incisions) | **closest to our data: we already have the voxels** |
| 6 | Projective dynamics / XPBD on tets or prisms with constraint removal | constraints crossed by the blade are deleted, vertices split | yes if the layer mesh has thickness | fast, stable, mobile-friendly; stiffness depends on iterations | **SkinFlaps** (open source, projective dynamics, 620k tets reduced to 17k by multiresolution, AVX + MKL on CPU); Berndt et al. 2017; Pan et al. 2015; our `TissueSheet` | **yes, locally (a patch), as today** |
| 7 | Particles / meshfree (shape matching, point-based, MPM, Flex) | neighbour links broken | needs a surface rebuilt every frame | robust; surface reconstruction is the cost | NVIDIA Flex demos; research | no (surface quality) |
| 8 | Voxel / SDF carving + displacement field | material removed from a mask; edges moved apart by a warp | **yes: the wall is the volume itself** | trivially robust, undoable; no physics; limited by voxel size | **our old lab** (`MaskVolume`, `Gape`); Anatomage-style tables | **yes: the truth layer** |
| 9 | Texture-space wounds: mask + displacement / parallax + wound meshes | a damage mask in UV or object space hides skin and shows a pre-built layer beneath | layers are **pre-built nested meshes** revealed by the mask | very cheap, looks excellent, no new geometry | games (Left 4 Dead 2 wounds, Vlachos GDC 2010, from memory; Dead Island 2's procedural "FLESH" gore system, whose internals are not published in anything found, section 6) | **yes: the look layer**; we already have nested layer meshes |

Reading it against what we hold: methods 2-4 need a whole-body tetrahedral mesh and give nothing that the voxel volume
does not already give. The combination that matches our data is **8 for the truth (carve the labelled volume), 9 for
the look (nested layer meshes clipped by the mask, cut walls contoured from the volume), 6 for the physics (a local
XPBD patch), 5 as the way to build that patch (a small lattice cut out of the voxels on demand)**.

### 2.2 Bleeding

| Technique | What it gives | Cost | Notes |
|---|---|---|---|
| SPH (Mueller et al. 2004, "Interactive blood simulation for virtual surgery") / **PBF** (Macklin & Mueller 2013, saved) | pooling, spilling, spurting, real volume | 10-50k particles on GPU; needs neighbour grid | PBF is unconditionally stable with large steps; the existing `BloodSim` drops are this family |
| Screen-space fluid rendering (van der Laan, Green, Sainz 2009; narrow-range filter, Truong & Yuksel 2018) | particles drawn as one liquid surface with thickness | 3-4 full-screen passes | **already built** (`BloodFluidFeature`) |
| Flow on the surface in texture space ("gravity map": NVIDIA HLSL Blood Shader white paper 2004, saved; Kvick 2011 thesis, GPU liquids for surgical simulation, saved) | thin films and trails that run downhill over the skin, wetness, drying | one or two render-to-texture passes over a UV atlas | needs a **UV atlas of the skin with low distortion** and a per-texel gravity direction (tangent-space projection of gravity) |
| Flow per vertex along mesh edges (Daenzer et al. 2006, in the SPRING simulator, saved) | blood trails follow the steepest edge downhill | trivial | coarse; depends on mesh density |
| Stain in a 3D texture (our lab) | dried blood that survives remeshing and cuts | a half-resolution volume | no UVs needed; resolution 1.3-2.6 mm, too coarse for fine trails |
| Emitters at cut vessel cross-sections | the anatomy decides where it bleeds | negligible | needs the **vessel graph**; see below |

Sources: when a stroke carves the mask, intersect the blade's swept capsule with (a) the vessel centre lines (a segment
tree) and (b) the layer ids along the wall. Each crossed vessel becomes an emitter at the crossing point, with the
vessel's direction, radius and type: artery = pulsed velocity (table 1.5), vein = steady low velocity, both scaled by
r^2; the dermal edge becomes a line emitter of small beads (capillary ooze) whose rate decays over minutes. Clotting =
the emitter's rate falls exponentially (time constant 2-4 min for ooze and small vessels, none for arteries of 2 mm or
more) and the fluid's viscosity rises; drying = a per-texel (or per-voxel) age that darkens the colour (1.5), lowers
gloss and stops flow. Cadaver seep = vein emitters only, driven by gravity head, finite volume.

### 2.3 Skin pinching and stretching

- **A shell over a volume, sliding on the fascia.** Skin behaves as a thin stiff membrane (dermis) on a very soft layer
  (fat) that lets it slide over the deep fascia. The research formulation is Li, Sueda, Neog, Pai, "Thin skin
  elastodynamics" (SIGGRAPH 2013): skin simulated as a 2D membrane that slides over the body surface. The cheap game
  form is "skin sliding": move the vertices, then project them back onto the base surface.
- **XPBD** (Macklin, Mueller, Chentanez 2016): distance / area / bending constraints with compliance from real moduli,
  plus attachment constraints to the bed that slide and break. This is what `TissueSheet` already does; projective
  dynamics (SkinFlaps) is the same idea with a global solve and scales to more elements on a desktop CPU.
- **Anisotropy by Langer lines**: give each edge a compliance and a strain limit that depend on the angle between the
  edge and the tension direction at that vertex (orthotropic strain limiting; Mueller et al. 2014, "Strain based
  dynamics"); the same field sets the pre-tension that opens a cut (1.4).
- **Layer model**: SkinFlaps builds its solid from a textured skin surface plus a deep bed, i.e. the skin surface
  extruded to the fascia. The same is available to us for free: each skin vertex has a fat thickness, so the patch is a
  layer of prisms (three tets each) between the skin vertex and its point on the fascia.

### 2.4 Engines and Unity options

| Option | What it is | Verdict here |
|---|---|---|
| Custom Burst XPBD (as `TissueSheetJob`) | our own, CPU, any platform | **keep and generalise**: it is the only option that already knows the tissue's moduli, the fascia junction and the mask |
| Compute shaders (as `BloodSim`, `TissueWarp`) | our own, GPU | **keep**; needs Vulkan / Metal / GLES 3.1 on mobile |
| Obi (Cloth, Softbody, Fluid; Virtual Method) | paid Unity assets, particle XPBD on CPU and GPU; Obi Fluid $60 per seat, Obi Physics Suite $179 per seat (version 7.2, 25 Aug 2026), standard Unity Asset Store EULA [V, Asset Store listings via search]. The Softbody listing states: "Does not support topological changes in the meshes such as cutting/tearing." [V] | not for cutting; possible for fluid only, but it adds a second particle world beside ours |
| NVIDIA Flex | unified particles | the Unity plugin was discontinued; Windows / DX11 only |
| PhysX 5 FEM soft bodies / PBD | GPU (CUDA) only; not exposed by Unity's built-in physics | no |
| SOFA | open-source (LGPL) research framework with cutting plugins; C++; Unity bridge is a separate third-party product | too heavy, desktop only; good as a reference implementation |
| SkinFlaps | open source C++, projective dynamics, facial flaps | reference for the layer model and the scalpel / undermine / suture tools; not a Unity library |
| MAGES SDK | see section 3 | do not adopt |

### 2.5 Recommendation for this project

**Voxels are the truth, meshes are the look, a local patch is the physics.**

1. **Cut = carve the labelled volume**, as today (`MaskVolume`, one stroke = one undo step). Nothing about the cut is
   stored in the meshes.
2. **Layer meshes clip themselves** against the mask per pixel (sample the mask at the fragment's volume coordinate), as
   `SkinMesh` already does. No remeshing of the 1.4 M triangle body, ever.
3. **Cut walls are meshed locally from the volume**: around a stroke, contour the carved region with surface nets
   (`FieldMesh` already does this for organ pieces) on a fine local grid (0.3-0.5 mm, a brick of ~64^3 per 3 cm of
   cut), and colour each wall vertex **from the layer and structure id of the voxel behind it** plus depth under the
   skin: epidermis line, white dermis band of the region's thickness, yellow lobules, white fascia line, red fibres
   along the muscle's direction. Procedural triplanar detail, no UVs.
4. **Gape = the existing displacement field, driven by a tension field**: direction and pre-tension per skin vertex
   (Langer), lens profile, and applied to the meshes in the vertex shader and to the wall mesh, so layers and walls move
   together.
5. **Pinch and stretch = a local XPBD patch cut out of the skin mesh** (not a 64 x 64 height field): the skin triangles
   within ~6 cm of the hand, each vertex paired with its fascia point (fat thickness along the normal), prisms between
   them, anisotropic strain limits, the fascia junction that slides and tears, collision with the fascia SDF; outside
   the patch the vertices are pinned and blended. The patch is drawn in place of the hidden region of the static skin,
   exactly as `TissueSheets` hides the body's copy today.
6. **Bleeding = emitters from the vessel graph and the layer ids** feeding the existing drops and screen-space fluid;
   thin films and drying in a skin UV atlas (new), stains in the existing 3D texture where there are no UVs.
7. **Eyelids = a marked region with a real slit**: lid vertices, the margin curve, the two corner points and the globe
   are data in the model; pinching makes a small patch whose plate part is a stiff shape-matched cluster constrained to
   slide on the globe's sphere about the corner tendons.
8. **No whole-body tetrahedra, no third-party cutting SDK**; everything runs in Burst jobs and compute shaders that
   already exist in the repository, so mobile stays possible.

---

## 3. MAGES SDK (ORamaVR)

### 3.1 What its soft-body and cutting features are

Three papers by the same group (University of Crete / FORTH / ORamaVR) and the SDK manual:

- **Kamarianakis & Papagiannakis, "An All-In-One Geometric Algorithm for Cutting, Tearing, and Drilling Deformable
  Models"**, Advances in Applied Clifford Algebras 2021, arXiv 2102.07499. Skinning is rewritten in conformal geometric
  algebra (rotations, translations and dilations as multivectors, vertices moved by a sandwich product). A **cut** is a
  plane: edges crossed by it get intersection points, crossed faces are re-triangulated, faces are sorted into two
  meshes. A **tear** is a partial cut along the scalpel's sampled positions: intersection points are duplicated and
  "moved parallel to the direction of the normal of the plane" to open it. A **drill** is a point-in-cylinder test and
  re-triangulation. New vertices get skinning weights from the edge ends or barycentric coordinates (top four bone
  weights, renormalised), so the cut model can still be animated. The paper states: "Our algorithm does not require
  tetrahedral meshed models and requires minimum to none pre-processing." It is **surface only**: no cap faces, no
  interior. Timings are from single-threaded Python: cutting an arm of 3,069 vertices / 5,037 faces took 4.5 s; the
  authors say real time needs C++ or C#.
- **"Deep Cut"** (arXiv 2108.05281): the same operations for mobile VR on top of a custom soft-body deformation.
- **Kamarianakis, Protopsaltis, Angelis, Tamiolakis, Papagiannakis, "Progressive tearing and cutting of soft-bodies in
  high-performance virtual reality"**, ICAT-EGVE 2022, arXiv 2209.08531, implemented in MAGES on Unity. The soft body
  is a **particle system on top of linear-blend skinning**: mesh vertices are sampled by Poisson disks, each sample
  anchors a spherical particle on a spring; nearby particles are linked; vertices follow a weighted sum of particle
  displacements; forces and collisions are left to Unity's physics (sphere colliders with rigid bodies), "a typical
  spring mass approach". Cutting and tearing use **Euclidean** predicates here (the geometric algebra is no longer the
  working tool). A tear removes "a box-like section of mesh" along the scalpel path; with soft bodies "the particle
  connections intersecting the tear box will be broken". Measured on a desktop PC (Ryzen 7 5800H, RTX 3060, CPU only,
  single thread), per tear segment: sphere 515 vertices 3.25 ms; bunny 2,527 vertices / 4,968 faces 11.19 ms; **heart
  9,747 vertices / 18,336 faces 18.65 ms** (most of it bone-weight calculation); planar cut of the bunny 17.29 ms. The
  abstract's "10 ms" is exceeded by its own tables. VR test on a tethered headset. Stated limit: "the described
  particle system still misses to model the absolute physical behavior of human tissue."
- **Manual** (docs.oramavr.com): components `Cuttable Mesh` + `Cutter` (planar cut, `Cut(Plane, out Mesh positiveSide,
  out Mesh negativeSide, ...)`, `UndoCut()`), `Tearable Mesh` + `Tearer` (`Tear(pointA, pointB, direction, width,
  height)`), `Drill`, `SpringMassSoftbody`. The cut page says its `seperationDistance` is "Used mainly to make the cut
  visible by leaving a gap in the cut section"; both pages warn the feature is beta / experimental and "can create
  artifacts on the newly created meshes."

Summary: **mesh-based, surface-only re-triangulation of a rigged mesh, with a spring-mass particle layer for softness.
No volumetric cut, no layered cut faces (skin / fat / muscle), no bleeding or fluid of any kind** (none in the papers,
none in the documentation index).

### 3.2 What it requires from a model

- A triangulated mesh with a Renderer and a collider; for the published algorithms a **rigged, skinned** mesh
  (.fbx / .dae). No tetrahedra. UVs and normals are interpolated at new points if present.
- Soft bodies: clean manifold topology (no n-gons, no non-manifold edges), import with compression off, Read/Write on,
  mesh optimisation off; particles are generated once in the editor (Particle Distance, Particle Connection Distance,
  Skinning Distance) and saved as a prefab. "The number of vertices is really important in our soft body system"; the
  tutorial's example organ has 5,700 vertices.
- Real-time sizes shown: **0.5k to 10k vertices** per object. Our skin alone is 200-400k triangles and the body 1.4 M;
  the tear search has a per-stroke selection sphere (`editFragmentScaleFactor`) but the published cost per segment at
  18k faces is already a full frame.

### 3.3 Licence, price, source, versions

- Unity Asset Store listing: https://assetstore.unity.com/packages/tools/game-toolkits/mages-sdk-277259 . Fetched today
  it shows only: "This asset has been deprecated from the Unity Asset Store." / "It is no longer available for purchase
  and will no longer be supported by the publisher." / "If you've already purchased this asset, you will still be able
  to use it in new and existing projects."
- The listing text as indexed by the search engine (older copy; two independent snippets agree): the asset "is governed
  by the custom EULA"; "The free version of MAGES SDK provides 20 actions per med-XR training for non-commercial
  simulations"; the paid tier is "MAGES SDK - PRO", unlocked through ORamaVR's pricing page; "designed for any Unity
  LTS version above 2022.3.53"; "URP is the only pipeline supported due to mobile VR compatibility"; contact
  info-sdk@oramavr.com. The documentation front page still says "Download the latest version of MAGES 5 (NXT) from the
  Unity Asset Store" while its release notes end at 4.3.1.
- https://oramavr.com/pricing/ today lists no SDK tiers at all, only the company's own products ("Virtual Training
  Center", "SIM Library": "License only the titles you need").
- **Source**: not open. No public SDK repository or Unity scoped registry was found; GitHub holds the documentation
  source only (`MAGES_SDK_docs`). Distribution was the Asset Store package.
- **The EULA text itself and any price could not be retrieved** (section 6).
- Scope: MAGES is a whole VR training framework (action scenegraph, analytics, multiplayer, no-code authoring), built
  for headsets; desktop and tablet builds exist in its docs (a desktop 3D controller, an iOS build tutorial), but the
  cutting components are a small beta part of it.

### 3.4 Verdict

Do not adopt. (1) It cuts **surfaces**; a dissection table must show the wall of the cut, layer by layer, and MAGES has
no interior. (2) No bleeding. (3) It expects small rigged meshes (5-20k faces); ours are unrigged, static and a hundred
times larger. (4) The free tier is non-commercial and capped at 20 actions, the commercial terms are a custom EULA we
could not read, and the Asset Store package is marked deprecated and unsupported: a dependency risk for a product.
(5) Unity 6 / URP 17 would probably work (URP-only, LTS above 2022.3.53), but nothing is gained. **Borrow the published
ideas only**, all of which are a few dozen lines each: interpolating vertex attributes at new cut vertices; opening a
tear by duplicating the intersection points and moving them along the cut plane's normal (the mesh form of our `Gape`);
restricting the search to a sphere / mesh sections around the blade; Poisson-disk particles as handles for a soft
region.

URLs: https://arxiv.org/abs/2102.07499 , https://arxiv.org/abs/2108.05281 , https://arxiv.org/abs/2209.08531 ,
https://docs.oramavr.com/ , https://docs.oramavr.com/en/latest/unity/manual/ctd/cut.html ,
https://docs.oramavr.com/en/latest/unity/manual/ctd/tear.html ,
https://docs.oramavr.com/en/latest/unity/tutorials/soft_bodies/index.html ,
https://assetstore.unity.com/packages/tools/game-toolkits/mages-sdk-277259 , https://oramavr.com/pricing/

---

## 4. Checklist: what the body model must provide

**NOW** = must be made in the build (expensive or impossible to add afterwards, or it fixes the mesh topology).
**LATER** = can be derived at load or in a later build step from things marked NOW.

| # | Item | When | Why / how |
|---|---|---|---|
| 1 | **One frame**: every mesh in the volume's frame, with the affine (metres <-> voxel uvw) written in the model's metadata; mesh surfaces within 0.5 mm of the label boundaries they came from | NOW | cut walls are contoured from voxels and must meet the layer meshes; smoothing and decimation must not drift (check the Hausdorff distance in the build's tests) |
| 2 | The **labelled volume ships with the meshes**: structure id and layer per voxel, depth under the skin; mesh node index = label index, one to one | NOW | truth for cuts, wall colour, picking, "how red"; already exists (`labels.raw`, `depth.raw`) |
| 3 | **Skin as a closed, manifold surface** with a triangle size fit for simulation: edges 2-3 mm on the body, 0.7-1 mm on eyelids, lips, nose, ears; no slivers; a coarser LOD for drawing | NOW | a local XPBD patch is cut out of this mesh; decimation slivers break it |
| 4 | **Region id per skin vertex** (about 40 regions: lids x4, face parts, scalp, neck front/nape, chest, abdomen, flank, back, buttock, arm/forearm inner and outer, palm, dorsum of hand, thigh, knee, shin, calf, sole, dorsum of foot, genital) painted once in voxel space | NOW | drives dermis thickness, tension, pinch limits, hair, vein depth; everything in section 1 is "by region" |
| 5 | **Skin (dermis) thickness per vertex** from the region table (1.1) | NOW (a table lookup, but the attribute channel and the inner skin surface depend on it) | cannot be measured at 1.3 mm voxels |
| 6 | **Fat thickness per vertex, measured**: distance along the inward normal from the skin to the first muscle / bone / organ voxel, with the matching point on the deep surface | NOW | the prism layer for pinch physics, vein depth, wall colour bands |
| 7 | **Fat layer as its own closed mesh** (outer face = base of the dermis, inner face = deep fascia) | NOW | the "fat" layer of the model; shows when skin is reflected |
| 8 | **Deep fascia surface** = envelope of muscles and bones under the fat, as a mesh and as a signed distance field | NOW (mesh), LATER (SDF) | the surface skin slides on and collides with; the white sheet seen in a cut |
| 9 | **Eyelids**: the skin mesh has a **real slit** along the closed lid line (two free edge loops from corner to corner, per eye), lid vertices marked upper / lower with a weight (1 on the plate, falling to 0 at the orbital rim), the lid margin as a curve, the two corner points, an inner (conjunctival) face giving the lid 2.5-3 mm of thickness | NOW | at 0.66 mm voxels the closed lids are fused into one surface; a slit cannot be added later without remeshing the face |
| 10 | **Eyeballs as separate meshes** per eye: sclera sphere (radius 12 mm), cornea (11.5 mm wide, radius 7.8 mm), iris, pupil; centre, forward axis and radius in the metadata; taken from the head export's eye voxels for position | NOW | what is seen when the lid lifts; the sphere the lid slides on |
| 11 | **Landmark table** (about 60 bony and surface points, left and right: medial / lateral malleolus, tibial border, femoral epicondyles, kneecap, pubic tubercle, anterior superior iliac spine, mid-inguinal point, navel, epicondyles of the humerus, styloids, snuffbox, pisiform, deltopectoral groove, mid-clavicle, sternal notch, angle of mandible, tragus, zygomatic arch root, corner of the mouth, inner / outer eye corners) | NOW | all vessel paths in 1.6 are written against these; picked once on the bone and skin meshes |
| 12 | **Vessel graph**: centre lines as polylines with radius per node, name, type (artery / vein), parent-child order (= flow direction), which layer they run in. Torso: skeletonised from the SIO vessel labels (and the HRA meshes if the licence allows). Limbs, neck, face, superficial veins: laid from the landmark paths at the depths of 1.6, snapped into the fat layer / along the bones | NOW for the graph format and the labelled torso vessels; superficial paths can follow in the next build | bleeding sources, visible veins under thin skin, vessels seen in a cut |
| 13 | **Vessel tube meshes** generated from the graph (so mesh and graph always agree), and stamped into the label volume as structures | NOW with the graph | a cut must show the vessel's cross-section in the wall |
| 14 | **UV atlas for the skin only**, low distortion, texel about 0.5 mm, seams along body midlines and away from face and hands | NOW | texture-space blood films, wetness, drying, bruising, skin detail; a UV layout cannot be changed later without redoing everything baked in it |
| 15 | UVs for muscles, bones, organs | not needed | walls and surfaces are coloured by volume coordinate and triplanar detail |
| 16 | **Skin tension (Langer) direction and pre-tension per vertex** | LATER (reserve the vertex tangent channel NOW) | derived from region id + limb / trunk axes from the skeleton: transverse on trunk, neck and forehead, horizontal on the lids, radial round the mouth, longitudinal on the leg (1.4), then hand-corrected |
| 17 | **Per-vertex volume coordinate** | LATER | follows from item 1 for static meshes (position x affine); only pieces that are moved (patches, organs taken out) need it stored, and they are created at run time |
| 18 | **Tetrahedral meshes** | not in the build | local prism / lattice patches are built on demand from items 3, 6 and the voxels |
| 19 | **Signed distance fields** (skin, fascia, bone) at 2-4 mm | LATER | a distance transform of the label volume takes seconds; the skin-depth grid already is one |
| 20 | Muscle fibre direction per muscle | LATER | principal axis of each muscle's voxels, or origin to insertion; for the look of cut muscle |
| 21 | Capillary density / "how red" per layer, clot and drying constants | LATER | tables (1.5) |
| 22 | Lashes, brows, hair roots | LATER | lash roots from the margin curve (150 upper, 75 lower per eye) |
| 23 | Adjacency of structures (what touches what, attachment areas) | LATER | from the label volume |
| 24 | Vertex attribute budget, fixed now: colour = occlusion / thickness / curvature (exists); uv0 = atlas; uv1 = region id, dermis thickness; uv2 = fat thickness, lid weight; tangent = tension direction, w = pre-tension | NOW | changing vertex layouts later touches every shader |

The three items that would hurt most if left out now: **9 (the slit between the lids), 14 (the skin's UV atlas) and
12 (the vessel graph format with flow direction)**, followed by **6 (measured fat thickness with the matching fascia
point)**.

---

## 5. Recommended architecture in eight lines

1. Truth: the labelled voxel volume plus the dissection mask; a scalpel stroke carves the mask (one undo step), nothing else.
2. Look: the nested layer meshes clip themselves per pixel against the mask; the body is never remeshed.
3. Walls: the carved region is contoured locally (surface nets, 0.3-0.5 mm) and coloured from the layer / structure id behind each point: epidermis line, dermis band, fat lobules, fascia, muscle fibres.
4. Gape: the existing displacement field, driven by a per-vertex Langer direction and pre-tension, applied to meshes and walls alike.
5. Pinch / stretch: a local XPBD patch cut from the skin mesh (skin vertex + its fascia point = prisms), anisotropic strain limits, sliding and tearing junction to the fascia; the rest of the body stays static.
6. Blood: emitters where the stroke crosses the vessel graph (artery pulsed, vein steady) and along the dermal edge (ooze), into the existing GPU drops and screen-space fluid; films and drying in the skin's UV atlas; "cadaver" = dry or gravity seep from veins.
7. Eyelids: a marked region with a real slit, a stiff plate cluster sliding on the globe sphere about the two corner tendons; a separate post-mortem eyeball (living eye optional).
8. All in Burst jobs and compute shaders already in the repository; no whole-body tetrahedra, no third-party cutting SDK.

---

## 6. What could not be verified

- **StatPearls / NCBI Bookshelf pages** (eyelid anatomy, post-mortem changes, skin) refused automated reading today
  (CAPTCHA, HTTP 403). Eyelid measurements other than tarsal heights, fissure size, Mueller's 2 mm and lash counts are
  from memory [T]: skin 0.5 mm, lid thickness, crease height, levator travel 12-15 mm, tendon attachments, globe and
  cornea sizes.
- **Post-mortem eye timeline**: sources found disagree (pressure nil at 2 h vs 4-8 h; tache noire 3-4 h vs 6-12 h);
  **no source for the dead pupil's size** was found, and two sources contradict each other on wide vs narrow.
- **Skin thickness** of eyelid, scalp total, neck, palm, sole, dorsum of hand: no measured source read today.
- **Fat thickness** outside abdomen, chest and thigh: skinfold-literature values from memory.
- **Wound gape in millimetres** by region and direction: no measured table exists that I could find; the values in 1.4
  are estimates to tune by eye. Skin pre-stretch and shrinkage percentages (Ridge & Wright; Jor) not re-read.
- **Bleeding rates in ml/min**: computed here (velocity x area, x 3-5 when cut), not measured values; clotting and
  drying times and the drying colours are textbook / estimate.
- **Superficial vein diameters and depths** except the great saphenous diameters and the elbow depth finding; all
  artery diameters marked [T] (radial, ulnar, axillary, facial, superficial temporal, dorsalis pedis).
- **Muscle and fascia moduli**; pinch heights and stretch limits by region.
- **MAGES**: the EULA text, any price, and whether the SDK is still sold anywhere (the Asset Store package is
  deprecated; the pricing page no longer mentions it); whether a cut ever generates a cap face (the papers and manual
  describe none); the owner of the `MAGES_SDK_docs` GitHub repository; behaviour on Unity 6 / URP 17.
- **Licence of the HRA vasculature models**: the CCF 3D Reference Object Library page states "All CCF 3D reference
  objects are released under Attribution 4.0 International (CC BY 4.0)" [V, via search]; the vasculature object's own
  entry was not opened. If any of it ships, credit it and update LICENSES.md.
- **Games references**: Dead Island 2's "FLESH" (Fully Locational Evisceration System for Humanoids, Dambuster
  Studios) is confirmed only as procedural, progressive, weapon-dependent damage to skin and bone; **its internal
  layered-mesh design was not found in any source** and is my reading, not a fact. Left 4 Dead 2's wound system, Li et
  al. 2013, Berndt 2017, Pan 2015, Mueller 2004 / 2014, Truong & Yuksel 2018 are cited from memory. The
  Wu-Westermann-Dick survey, GRIDiron, SkinFlaps, PBF, the NVIDIA blood shader, Kvick and Daenzer were read from the
  saved copies (the survey only in part). **The state of SOFA's Unity bridge was not checked.**
- This body's own skin + fat thickness by region was not computed in this task (no repository changes, no runs); the
  scripts to do it are in `build/research/cut_bleed_pinch/tools/`.
