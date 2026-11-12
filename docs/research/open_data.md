# Open data for the gaps of the Visible Human Male cadaver

Research report, 2026-11-12. Status: FINAL (web research only, no repository files changed, no file over 30 MB downloaded).

Licence rule applied: only public domain, CC0, CC BY or the NLM Visible Human terms count as usable. CC BY-SA, CC BY-NC, CC BY-ND and unclear licences are reported and flagged, never recommended.

"Verified" below means I opened the licence statement on the authoritative page (or its official metadata/API) myself in this session. Anything taken from a search summary or a secondary source is marked "not verified".

## 1. Summary table

| # | Source | What it holds | Same body as ours? | Licence (verified?) | Fills gap | Verdict |
|---|---|---|---|---|---|---|
| A | BoneHub "Visible Human Full-Skeleton 3D Bone Models" (Hugging Face) | 142 individually labelled bones of the Visible Human Male, label volumes + STL | YES (Visible Human Male CT, aligned to the cryosections) | CC BY 4.0 (verified, dataset card + HF API) | 4 (bone names, whole body) | usable: yes |
| B | University of Denver "3D Models of the Visible Human Male" (Andreassen 2023) | 38 named muscles per leg (76), 28 bones, 16 cartilages, 8 ligaments, 2 fat volumes, pelvis to ankle; label volumes + STL | YES (segmented on the Visible Human Male cryosections) | CC BY 4.0 (verified on the page saved by the previous researcher and in the paper) | 1 (leg and hip muscles) | usable: yes |
| C | BodyParts3D 4.0, LSDB Archive (DBCLS Japan) | 2,235 element meshes, 2,905 named FMA concepts: limb muscles individually, 684 artery names, 318 vein names incl. superficial veins (cephalic, basilic, great and small saphenous), bones; nerves only in the orbit | NO (generic Japanese adult male model) | CC BY 4.0 since the archive licence page of 2025/02/27 (verified, quoted) | 1 (arms), 2 (limb and superficial vessels), partly 4 | usable: yes (needs non-rigid fitting to our body) |
| D | TotalSegmentator, open tasks (total, headneck_muscles, head_muscles, headneck_bones_vessels, craniofacial_structures...) | A tool, not data: names bones, some muscles, big vessels on OUR CT | YES (runs on our own CT) | "Openly available for any usage (Apache-2.0 license)" (verified, README) | 1 (head and neck muscles), 2 (neck vessels, weak), 4 (partly) | usable: yes (quality on a frozen non-contrast cadaver CT not tested) |
| E | HuBMAP HRA blood vasculature, male v1.3 | 106 vessel meshes, torso + eyes only (aorta and branches, venae cavae, iliac, renal, mesenteric, hepatic, portal, coronary, pulmonary, ophthalmic) | Derived from the Visible Human Male but re-modelled; own frame | CC BY 4.0 (verified, official metadata) | 2 only inside the torso (we mostly have this from SIO) | usable: yes, low value |
| F | HuBMAP HRA skin, male v1.4 | One skin mesh, 414,594 vertices, no UV, no texture, arms abducted (re-posed) | Derived, re-posed, NOT in Visible Human coordinates | CC BY 4.0 (verified, official metadata) | none (no texture, wrong pose) | usable: yes, no value for us |
| G | HuBMAP HRA united male v1.10 | 850 named nodes: organs, brain regions, spinal cord segments, vertebrae, pelvis, femur, tibia, knee, one generic lymph node. No limb muscles, no nerves, no arm bones | Derived, re-modelled | CC BY 4.0 (verified, official metadata) | none of our gaps | usable: yes, no value for us |
| H | MakeHuman core assets and asset packs | Base body mesh, skin textures (packs CC0), hair (Hair 01 CC0; Hair 02, Hair 03 CC BY) | NO (generic) | CC0 for core assets (verified); packs CC0 / CC BY (verified on the asset pack page) | 5 (hair, skin texture reference) | usable: yes (assets only, never the AGPL code) |
| I | Blender Studio "Human Base Meshes" | 17 base meshes incl. realistic male, heads, hands | NO | CC0 according to CG Channel / 80.lv; blender.org page blocked (HTTP 403) - NOT verified | 5 (minor) | needs verification |
| J | SPARC "3D human whole-body model ... for mapping nerves" (models.cellml.org/e/b03) | Whole-body scaffold with nerve centrelines (nerve_centerlines.exf, about 125 KB), built from BodyParts3D | NO | No licence statement on the page | 3 (nerve paths as lines) | needs legal review |
| K | Z-Anatomy | Blender atlas derived from BodyParts3D with muscles, vessels and nerves | NO | CC BY-SA 4.0 (verified, quoted) - SHARE-ALIKE | 1, 2, 3 | usable: NO (flagged) |
| L | Open Anatomy / SPL atlases (head and neck, abdomen, knee, brain) | CT/MR atlases with label maps and models | NO | "3D Slicer License section B", not a CC licence (as stated on the atlas page) | 1, 2 (head and neck only) | needs legal review |
| M | AustinMan (UT Austin) | Voxel model of the Visible Human Male with tissue classes incl. blood vessel and nerve | YES | CC BY-NC-ND 3.0 (verified, quoted) | 2, 3 (as unnamed classes) | usable: NO (flagged) |
| N | NEVA VHP-Female 2.2 / 5.0, VHP-Male 2.0 | CAD surface models | Female: no. Male: not checked | "free of charge for academic research and non-commercial purposes only" (verified for 2.2) | - | usable: NO (flagged) |
| O | IT'IS Virtual Population (ViP) | Whole-body models with vessels and nerves (v3 "Eddie" is Visible-Human based) | Partly | Individual licence agreements, non-transferable; v3 needs a Sim4Life licence (search summary; licence page not readable) | 1, 2, 3 | usable: NO |
| P | AnatomyTOOL Open3DModel (median nerve, lower limb) | Labelled 3D models | NO | CC BY-SA (search summary, not opened) | 3 | usable: NO (flagged) |
| Q | Sketchfab university collections (IU Ruth Lilly, Groningen, Dundee) | Scans and models | NO | IU: CC BY-NC-SA 4.0; Groningen: BY-NC-SA / BY-NC-ND; Dundee: per model, not checked (search summary) | - | usable: NO / not verified |
| R | Zenodo 20228135 "Hand muscles", 20194622 "Right shoulder muscles" | Muscle models, 81-89 MB | NO | CC BY-NC-SA 4.0 (Zenodo API) | 1 | usable: NO (flagged) |
| S | Zenodo 5500740 / 3942741, Korean Visible Human vector reconstructions (neck nerves; atlas) | 3D vector reconstructions, 3-5 MB | NO (Korean cadaver) | CC BY 4.0 (Zenodo API listing; record not opened) | 3 (ventral neck only) | needs a look; small scope |
| T | NIH 3D | Mixed user uploads | NO | Per entry; page needs JavaScript, not verified | - | not verified |

Bottom line by gap:

1. Limb, head and neck muscles: legs and hips are solved on the same body by B. Head and neck muscles can be named on our own CT with D (open tasks). Arms have no same-body source; C is the only open source and must be fitted.
2. Vessels outside the torso and superficial veins: only C has them under a usable licence, and it is a different body, so it must be warped onto ours. E adds nothing outside the torso.
3. Nerves: NO usable open source with limb nerves as meshes was found. J has centrelines but no licence statement. K and P have them but are share-alike. M has a nerve tissue class on our body but is NC-ND.
4. Bone names outside the torso: solved on the same body by A.
5. Hair and skin texture: H (CC0 / CC BY assets). The skin colour itself is best taken from the Visible Human cryosection photographs we already have.

## 2. Details and evidence

### 2.1 HuBMAP / Human Reference Atlas 3D Reference Object Library, male

Evidence is the official metadata published at lod.humanatlas.io (local copies in build/research/hra/meta_*.json) and the GLB files the previous researcher downloaded (build/research/hra/dl/), which I inspected with build/research/_scripts/glb_info.py. The portal page https://humanatlas.io/3d-reference-library is a JavaScript application and returned no text.

Licence, verbatim from https://lod.humanatlas.io/ref-organ/blood-vasculature-male/v1.3 metadata:

> "license": "Creative Commons Attribution 4.0 International ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))"

Origin, verbatim from the same metadata:

> "This reference organ ... was created using data from the Visible Human Dataset, provided by the National Library of Medicine (Spitzer and Whitlock 2002)."

Credit lines given in the metadata:

- Vasculature: Browne, Kristen, and Heidi Schlehlein. 2024. "3D Reference Organ for Blood Vasculature, Male v1.3." https://doi.org/10.48539/HBM473.XTPP.725
- Skin: Browne, Kristen. 2024. "3D Reference Organ for Skin, Male v1.4." https://doi.org/10.48539/HBM953.DCMN.563
- United: Browne, Kristen, and Heidi Schlehlein. 2026. "3D Reference Organ Set for Male, v1.10." https://doi.org/10.48539/HBM833.WZWN.425
- Library as a whole: Browne, Kristen, Heidi Schlehlein, Bruce W. Herr II, Ellen Quardokus, Andreas Bueckle, and Katy Börner. 2024. "HuBMAP CCF 3D Reference Object Library." https://humanatlas.io/3d-reference-library

| Object | Download URL | Size | Content measured |
|---|---|---|---|
| Blood vasculature male v1.3 | https://cdn.humanatlas.io/digital-objects/ref-organ/blood-vasculature-male/v1.3/assets/3d-vh-m-blood-vasculature.glb | 18,050,040 bytes | 155 nodes, 106 mesh nodes, 122 named rows in crosswalk.csv, 442,064 vertices, 416,538 triangles, 9 materials, no textures |
| Skin male v1.4 | https://cdn.humanatlas.io/digital-objects/ref-organ/skin-male/v1.4/assets/3d-vh-m-skin.glb | 19,901,928 bytes | 1 node, 1 mesh, 414,594 vertices, 829,184 triangles, attributes POSITION and NORMAL only (no UV), no texture |
| United male v1.10 | https://cdn.humanatlas.io/digital-objects/ref-organ/united-male/v1.10/assets/3d-vh-m-united.glb | 241,633,636 bytes (header only, not downloaded) | 850 named rows in crosswalk.csv |
| United male, older, zipped | https://raw.githubusercontent.com/hubmapconsortium/ccf-releases/main/v2.0/models/3d-vh-m-united.glb.zip | 85,967,961 bytes (not downloaded) | - |

Name lists: https://cdn.humanatlas.io/digital-objects/ref-organ/blood-vasculature-male/v1.3/assets/crosswalk.csv (local copy build/research/hra/dl/bv_crosswalk.csv) and build/research/hra/dl/united_crosswalk.csv.

What the vasculature really covers: the bounding box is x -0.112..0.124, y -0.043..0.829, z -0.091..0.097 metres, that is 0.24 m wide and 0.87 m tall. It is the trunk, the root of the neck and the eye vessels. Named vessels: aorta (ascending, arch, descending), brachiocephalic artery, left common carotid, left subclavian, coronary arteries and cardiac veins, pulmonary trunk, arteries and veins, venae cavae, brachiocephalic veins, celiac trunk, hepatic, splenic, cystic, mesenteric, colic, sigmoid, renal vessels, portal vein, common / external / internal iliac veins, rectal and pudendal veins, ophthalmic and retinal vessels. There are NO limb vessels, NO jugular veins, NO superficial veins.

There is no male reference organ for muscles, for nerves or for the skeleton as a whole. The list of reference organs (build/research/hra/lod_reforgan.json) has only: adipose, blood vasculature, brain, eye, heart, intervertebral disk, kidney, knee, large intestine, larynx, liver, lung, lymph node, main bronchus, mouth, omentum, palatine tonsil, pancreas, pelvis, prostate, renal pelvis, skin, small intestine, spinal cord, spleen, thymus, trachea, ureter, urinary bladder, united. "Lymph" is one generic lymph node model ("Yao lymph node"), not a lymphatic system.

Coordinate frame and units (measured on the GLBs, not documented by HRA on a page I could read): glTF 2.0 exported from Autodesk Maya 2023; units are metres (the skin is 1.824 m tall); +Y is superior; +X is the patient's left (the left ophthalmic vein sits at x = +0.02); +Z is anterior (the eyes sit at z = +0.04..+0.10). Compared with our convention (x = left, y = superior, z = posterior) the z axis is flipped. The origin is near the middle of the body (the skin spans y -0.913..+0.911).

Same coordinates as the Visible Human Male? No. The skin is 1.043 m wide with the arms held away from the body and the palms forward (see build/research/hra/skin_male_views.png), while the cadaver lies with the arms at the sides inside a 0.68 m wide photograph. The HRA procedure says the modellers build the objects "from Visible Human or other data ... using ... Autodesk Maya, ZBrush, and Blender" (search summary of the HRA SOP, not opened). So the HRA body is a cleaned, re-posed artist model of the same man. A similarity transform will bring the trunk close, but a non-rigid fit must be expected, and the limbs do not match at all. I did not measure the residual; this can be tested locally by fitting the HRA aorta or vertebrae to our SIO meshes.

Verdict: licence is fine, but E, F and G do not fill any of our five gaps.

### 2.2 TotalSegmentator

Source: README of https://github.com/wasserth/TotalSegmentator (copy in build/research/totalseg/README.md).

Licence, verbatim:

> "Openly available for any usage (Apache-2.0 license): total: default task containing 117 main classes ..."

> "Available with a license (free licenses available for non-commercial usage here. For a commercial license contact jakob.wasserthal@usb.ch): heartchambers_highres ... appendicular_bones ... tissue_types ... tissue_4_types ... brain_structures ... face ... thigh_shoulder_muscles ... coronary_arteries ... aortic_sinuses ... brain_aneurysm (CC BY-NC 4.0 license, no commercial license available)"

The open "total" task names exactly these bones, muscles and vessels:

- Bones: skull; vertebrae C1-C7, T1-T12, L1-L5, S1; sacrum; rib_left_1..12, rib_right_1..12; sternum; costal_cartilages; humerus_left/right; scapula_left/right; clavicula_left/right; femur_left/right; hip_left/right.
- Muscles: gluteus_maximus, gluteus_medius, gluteus_minimus, autochthon, iliopsoas (each left and right).
- Vessels: aorta; pulmonary_vein; brachiocephalic_trunk; subclavian_artery_right/left; common_carotid_artery_right/left; brachiocephalic_vein_left/right; superior_vena_cava; inferior_vena_cava; portal_vein_and_splenic_vein; iliac_artery_left/right; iliac_vena_left/right (plus heart and atrial_appendage_left).

Other open (Apache-2.0) tasks that matter for us:

- headneck_muscles: sternocleidomastoid, trapezius, platysma, levator_scapulae, anterior / middle / posterior scalene, sterno_thyroid, thyrohyoid, prevertebral (each left and right), superior / middle / inferior pharyngeal constrictor.
- head_muscles: masseter, temporalis, lateral and medial pterygoid, digastric (left and right), tongue.
- headneck_bones_vessels: internal_carotid_artery left/right, internal_jugular_vein left/right, hyoid, thyroid_cartilage, cricoid_cartilage, zygomatic_arch, styloid_process, larynx_air.
- craniofacial_structures (mandible, skull, teeth, sinuses), head_glands_cavities (eyes, optic nerves, parotid and submandibular glands...), oculomotor_muscles, teeth, abdominal_muscles (T4-L4 only), body (skin, body_extremities).

Restricted tasks (licence key needed, commercial licence by contact): appendicular_bones (patella, tibia, fibula, tarsal, metatarsal, phalanges_feet, ulna, radius, carpal, metacarpal, phalanges_hand), tissue_types, tissue_4_types, thigh_shoulder_muscles and the others quoted above.

Can the open classes name our limb bones and neck vessels on the Visible Human frozen CT?

- Limb bones: only humerus, femur, scapula, clavicle, hip and skull. Radius, ulna, tibia, fibula, hands and feet are in the restricted task. Source A already gives all of these on our body, so TotalSegmentator is not needed for bones.
- Neck vessels: common carotid, subclavian, brachiocephalic (total) and internal carotid, internal jugular (headneck_bones_vessels) are open. The models were trained on clinical CT, much of it with contrast. Our CT is a non-contrast scan of a frozen cadaver with collapsed vessels, so vessel results are likely weak. NOT tested by me.
- The output is a segmentation of our own CT; the Apache-2.0 statement covers "any usage", so there is no licence obstacle to shipping meshes made from it.

### 2.3 Source A: BoneHub Visible Human Full-Skeleton 3D Bone Models

- Page: https://huggingface.co/datasets/BoneHub/visible-human-3d-models (DOI 10.57967/hf/10464). Dataset card saved in build/research/bonehub/README.md.
- Licence, verbatim from the card: "This dataset is released under CC BY 4.0, consistent with the source dataset's license. If you use this dataset, please cite both: 1. The original Visible Human 3D geometry paper (Andreassen et al., 2023) ... 2. This dataset". The Hugging Face API reports license cc-by-4.0, last modified 2026-11-06.
- Content: "142 (male) and 143 (female) individually labeled bones". Every vertebra, rib, carpal, metacarpal, tarsal and metatarsal is its own label. Limits stated by the authors: elbow region truncated in the source CT, phalanges are one label per finger or toe, the skull is only SKULL_CRANIAL_MAXILLA and SKULL_MANDIBLE, sacrum includes the coccyx, sternum undivided, no hyoid, no costal cartilage, no sesamoids except the patella.
- Format and frame: 3D Slicer .seg.nrrd on a 520 x 552 x 1873 grid, spacing 0.9375 x 0.9375 x 1.0 mm, space left-posterior-superior, origin 0 (build/research/bonehub/seg_stats_1.txt). It is the University of Denver "Aligned CT", which is aligned to the cryosections. STL meshes per bone as well.
- Sizes (HF API): male segmentations 10.6 MB in total (11 .seg.nrrd files of 0.6 to 1.3 MB); male STL meshes 142 files, 242.1 MB; male NURBS 1,986.5 MB (not needed); CT volume 01_Male.nii.gz 418.6 MB.
- Download pattern: https://huggingface.co/datasets/BoneHub/visible-human-3d-models/resolve/main/visible_human_3d_models/CT/Segmentation/01_Male/<NAME>.seg.nrrd with NAME in SKULL, SPINAL_COLUMN, THORAX, UPPER_EXTREMITY_LEFT, UPPER_EXTREMITY_RIGHT, LOWER_EXTREMITY_LEFT, LOWER_EXTREMITY_RIGHT, HAND_LEFT, HAND_RIGHT, FOOT_LEFT, FOOT_RIGHT.
- Note: the labels were made with the nnInteractive tool and checked by two annotators. The dataset itself is what is licensed CC BY 4.0.
- Verdict: usable: yes. Fills gap 4 on the same body. Needs only a rigid/affine check against our CT volume.

### 2.4 Source B: University of Denver, 3D Models of the Visible Human Male

- Page: https://digitalcommons.du.edu/visiblehuman/2 (saved copy build/research/du_vh/male_page.html). Paper: Andreassen et al., Scientific Data 10, 34 (2023), https://doi.org/10.1038/s41597-022-01905-2 (full text read through Europe PMC, PMC9849470).
- Licence, verbatim from the page: "This work is licensed under a Creative Commons Attribution 4.0 International License."
- Content, verbatim from the paper: "In total 260 geometries from the Visible Human Female and Male were extracted from the cryosections consisting of 76 muscles, 28 bones, 16 cartilages, 8 ligaments, and 2 fat geometries per subject". "Muscle, bone, cartilage, ligament, and fat from the pelvis to the ankle".
- The 38 muscles per side (Table 3, partly read): adductor brevis, longus, magnus; biceps femoris long and short; extensor digitorum longus; extensor hallucis longus; flexor digitorum longus; gluteus minimus (and the other gluteals); gracilis; iliacus; inferior and superior gemellus; obturator externus and internus; pectineus; peroneus longus; rectus femoris; sartorius; semimembranosus; semitendinosus; soleus; tensor fasciae latae; tibialis ... (the rest of the table was cut off in my extract). No vessels, no nerves.
- Frame: segmented on the Visible Human cryosections ("reduced in size for manageability", "cropped to the sternum", slice offsets corrected). Remeshed edge lengths: muscle 1.5 mm, bone 1.0 mm, cartilage and ligament 0.75 mm. Final models have no overlaps (0.05 mm gap). The exact voxel size and origin were not read; check the MetaData.zip.
- Downloads for the male (checked with HTTP HEAD):
  - Final 3D STL models: https://digitalcommons.du.edu/cgi/viewcontent.cgi?filename=10&article=1000&context=visiblehuman&type=additional , 139,572,345 bytes, file "Final 3D STL Models-stl.zip"
  - Smoothed 3D STL models: same URL with filename=9, 255,818,978 bytes
  - MetaData: same URL with filename=11, 59,379 bytes
  - Other folders listed on the page: aligned cryosection DICOM 607 MB, aligned CT DICOM 291 MB, final segmentation masks with aligned scans (3D Slicer) 2,773 MB, original STL 1,296.5 MB.
- Verdict: usable: yes. Fills gap 1 for hips, thighs and lower legs on the same body. Arms, feet, head and neck are not covered.

### 2.5 Source C: BodyParts3D 4.0 (LSDB Archive)

- Licence page: https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html , "Last updated : 2025/02/27". Verbatim:

> "The license for this database is specified in the Creative Commons Attribution 4.0 International. If you use data from this database, please be sure attribute this database as follows: "BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International"."

> "you are licensed to: freely access part or whole of this database, and acquire data; freely redistribute part or whole of the data from this database; and freely create and distribute database and other derivative works ..."

- IMPORTANT licence history: the older BodyParts3D site and everything derived from the older release (Z-Anatomy, and many copies on the web) carry "CC Attribution-Share Alike 2.1 Japan". Only the copy downloaded from the LSDB Archive under the page above is CC BY 4.0. Download from the archive, keep a dated copy of the licence page, and never take the meshes from Z-Anatomy or the old site.
- Downloads: https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_BP3D_4.0_obj_99.zip (142,903,898 bytes, not downloaded) and https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/partof_BP3D_4.0_obj_99.zip (62 MB). Name tables: .../LATEST/isa_parts_list_e.txt (126 KB, downloaded and counted), .../LATEST/isa_element_parts.txt.
- Format: one Wavefront OBJ per element, "polygon reduction rate of 99%" (meaning of 99 % not checked: it may be the lightest or the fullest version).
- Content counted from the name tables: 2,905 named concepts with FMA ids, 2,235 distinct element meshes. Names containing "artery": 684. "vein": 318, including cephalic, basilic, great saphenous, small saphenous. Also radial artery, dorsalis pedis artery and many others in the limbs. Limb muscles are individual (biceps, triceps, deltoid, sartorius, gastrocnemius, tibialis anterior, fibularis longus / brevis / tertius ...). Names containing "nerve": 55, all cranial / orbital (optic, trochlear, ophthalmic, lacrimal, frontal, nasociliary, ciliary ...). No brachial plexus, no median / ulnar / radial / sciatic / femoral nerve. No lymphatics.
- Body: "a three-dimensional whole-body model for an adult human male" built by DBCLS. NOT the Visible Human. Units and axes not checked.
- Verdict: usable: yes. It is the only open source found for limb arteries, limb veins and superficial veins, and for arm muscles. It must be warped onto our body (landmarks: the bones of source A and our skin), so the vessels will be anatomically typical, not this man's own vessels. For teaching and for "bleeding from a cut vessel" this is sound; it must be described as a typical course, not as the cadaver's own.

### 2.6 Hair and skin (gap 5)

- MakeHuman, https://static.makehumancommunity.org/about/license.html : "All core assets are shared under Creative Commons, CC0." and "the source code of MakeHuman is shared under AGPL." Use assets only, never the code.
- MakeHuman asset packs, https://static.makehumancommunity.org/assets/assetpacks.html : Hair 01 under "Mesh assets shared under CC0"; Hair 02 ("mostly high-poly hair by Elvaerwyn") and Hair 03 under "Mesh assets shared under CC-BY"; skin packs under "Material assets, shared under CC0". Pack sizes and direct URLs were not read. Single user-contributed assets carry their own licence and must be checked one by one.
- Blender Studio Human Base Meshes: reported as CC0 by CG Channel and 80.lv; https://www.blender.org/download/demo-files/ returned HTTP 403 to my client, so NOT verified.
- HRA skin (F) has no UV and no texture, so it gives nothing here.
- NLM Visible Human terms, https://www.nlm.nih.gov/databases/download/terms_and_conditions.html : credit "Courtesy of the U.S. National Library of Medicine", do not imply NLM endorsement, state if the data is not the most current. The page does not name the Visible Human Project specifically.

### 2.7 Flagged or rejected

- Z-Anatomy, https://github.com/Z-Anatomy/Models-of-human-anatomy : "All the code and content shared by 'Z-Anatomy' is under Creative Commons Attribution-ShareAlike 4.0 International License." It also lists "BodyParts3D - The Database Center for Life Science - CC-BY-SA 2.1 Japan" and Wikipedia text under CC BY-SA 3.0, and some models under CC BY-NC-SA. Share-alike: any adapted material we distribute would have to be CC BY-SA too. Not usable.
- AustinMan, https://web.corral.tacc.utexas.edu/AustinManEMVoxels/AustinMan/conditions_of_use/index.html : "is licensed under a Creative Commons Attribution-NonCommercial-NoDerivs 3.0 Unported License". Password needed. Not usable, although it is the same body.
- NEVA VHP-Female 2.2, https://www.nevaelectromagnetics.com/vhp-female-2-2 : "available to interested researchers, professors, and students free of charge for academic research and non-commercial purposes only". Not usable. The full models are sold.
- IT'IS Virtual Population: licence page could not be read (redirect loop). Search summary of the IT'IS FAQ and fact sheet: separate academic and commercial licence agreements, "non-exclusive, non-transferable" licence, v3.x only with a Sim4Life licence from ZMT. Not usable for redistribution.
- Open Anatomy / SPL head and neck atlas, https://www.openanatomy.org/atlas-pages/atlas-spl-head-and-neck.html : licence given as "3D Slicer License section B". Download https://www.openanatomy.org/atlases/nac/head-neck-2016-09.zip . Not a CC licence; the text of section B was not read. Needs legal review. Different body.
- SPARC whole-body model with nerves, https://models.cellml.org/e/b03 : "The muscles and bones data are obtained from Anatomography (BodyParts3D V4.3i; DOI: 10.1093/nar/gkn613)". Files nerve_centerlines.exf and whole-body.exf (Cmgui / Argon format). The page shows no licence. Needs legal review; ask the authors (Auckland Bioengineering Institute, SPARC).
- AnatomyTOOL Open3DModel, Sketchfab university collections, the two Zenodo muscle records: share-alike or non-commercial as listed in the table. Not usable.

### 2.8 A lead worth an e-mail

The FAQ of the VOXEL-MAN "Segmented Inner Organs" data we already use says (search summary of https://www.virtual-body.org/segmented-internal-organs/faq/): thin arteries, nerves and lymph nodes that are not visible on the cross-sections "were modeled with a tube editor and represented as polygonal surface meshes. They are not part of this model." So nerve and small-artery meshes for exactly our body exist at the VOXEL-MAN group but were not released. Asking them to release these under CC BY 4.0 as well is the only path I found to nerves on the same body.

## 3. Top 3 recommendations

1. Bone names for the whole body (gap 4), same body. BoneHub, CC BY 4.0. Download the 11 files https://huggingface.co/datasets/BoneHub/visible-human-3d-models/resolve/main/visible_human_3d_models/CT/Segmentation/01_Male/<NAME>.seg.nrrd (10.6 MB in total).
   Credit: "Bone labels: Alavi S.H., Asseln M., Visible-Human-3d-Models, Hugging Face, 2026, doi:10.57967/hf/10464, CC BY 4.0; based on Andreassen T.E. et al., Three Dimensional Lower Extremity Musculoskeletal Geometry of the Visible Human Female and Male, Sci Data 10, 34 (2023), doi:10.1038/s41597-022-01905-2, CC BY 4.0. Changes were made."
2. Named leg and hip muscles (gap 1), same body. University of Denver, CC BY 4.0. Download https://digitalcommons.du.edu/cgi/viewcontent.cgi?filename=10&article=1000&context=visiblehuman&type=additional (Final 3D STL Models-stl.zip, 139,572,345 bytes; over the 30 MB limit of this task, so not downloaded) and the MetaData zip (filename=11, 59 KB).
   Credit: "Leg muscles: Andreassen T.E., Hume D.R., Hamilton L.D., Walker K.E., Higinbotham S.E., Shelburne K.B., Three Dimensional Lower Extremity Musculoskeletal Geometry of the Visible Human Female and Male, Sci Data 10, 34 (2023), doi:10.1038/s41597-022-01905-2; data: University of Denver, https://digitalcommons.du.edu/visiblehuman/2 , CC BY 4.0. Changes were made. Source images courtesy of the U.S. National Library of Medicine."
3. Limb vessels, superficial veins and arm muscles (gaps 2 and 1), different body, to be fitted. BodyParts3D 4.0 from the LSDB Archive, CC BY 4.0. Download https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_BP3D_4.0_obj_99.zip (142,903,898 bytes, not downloaded) with https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_parts_list_e.txt and isa_element_parts.txt.
   Credit (wording required by the licensor): "BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International". Add "adapted (fitted to the Visible Human Male)".

Runner-up for head and neck: run the open TotalSegmentator tasks headneck_muscles, head_muscles and headneck_bones_vessels on our CT (Apache-2.0; cite Wasserthal et al., Radiology: Artificial Intelligence 2023, doi:10.1148/ryai.230024).

For LICENSES.md, when any of these is taken into the project: add the source, the licence, the credit line above and the date of download.

## 4. What I could not verify

- HRA: the portal page text (JavaScript only). Units and axes are measured from the GLB files, not quoted from HRA documentation. How well the HRA trunk fits our body after a similarity transform was not measured. The united GLB (241 MB) was not opened; its content is judged from the 850-row crosswalk.
- TotalSegmentator: no run on the Visible Human frozen CT; the quality of head / neck muscle and vessel output on it is unknown. I did not find a separate licence file for the weights; the README sentence "Openly available for any usage (Apache-2.0 license)" is the only statement read.
- University of Denver: the full list of 38 muscles (the table was cut in my extract), the voxel size and origin of the label volumes, and whether the feet muscles are included ("pelvis to the ankle" suggests not).
- BodyParts3D: the zip was not opened (142 MB). Units, axes, polygon counts and the meaning of "reduction rate 99%" are unchecked. The count of names includes group concepts, so the number of distinct vessel meshes is lower than 684 + 318. Whether the CC BY 4.0 change also covers the data on the old lifesciencedb.jp site is not stated; use only the archive copy.
- BoneHub: label volumes were not compared with our CT (the previous researcher's statistics look plausible: femur 484 mm, tibia 409 mm).
- MakeHuman: sizes and direct URLs of hair and skin packs; licences of single community assets.
- Blender Human Base Meshes: licence on blender.org (HTTP 403).
- IT'IS licence text, 3D Slicer licence section B text, NIH 3D terms, the licence of the SPARC whole-body nerve model, Sketchfab Dundee model licences, AnatomyTOOL item licences, the Korean Visible Human Zenodo records: not opened or not readable.
- NEVA VHP-Male 2.0 terms were not read (only VHP-Female 2.2).
- No usable open source for peripheral nerves as meshes was found. This gap stays open.
