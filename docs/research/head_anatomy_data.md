# Head and neck anatomy data for the Visible Human Male cadaver

Research report, 2026-11-12. Status: FINAL. Web research only; no repository files changed; no file over 30 MB downloaded. Working files (name tables, metadata, three small GLB files) are in build/research/head_data/.

Marks: [V] read at the source today (page, official metadata, or the file itself), [S] search summary only, [M] from memory (not checked today; confirm before it is used as a hard fact).

Licence rule: usable = public domain, CC0, CC BY, NLM Visible Human terms, permissive code licences. CC BY-SA, non-commercial, no-derivatives and research-only are reported and flagged, never recommended.

## 1. Summary table

| # | Source | What it holds for the head | Same body? | Licence | Verdict |
|---|---|---|---|---|---|
| 1 | VOXEL-MAN head and neck of the Visible Human | Exists at the group (gallery shows head and neck muscles, white matter, optic nerves) but NOT released. FAQ: "We are working on the head and neck section, please check back later." [V] | YES | Torso is CC BY 4.0 [V]; head: nothing published | not available yet; ask / watch |
| 2 | VOXEL-MAN "Brain and Skull" navigator | Interactive atlas of another head | NO [M] | CC BY-NC-ND [S] | NO (flagged) |
| 3 | BoneHub SKULL.seg.nrrd | Only 2 labels: SKULL_CRANIAL_MAXILLA, SKULL_MANDIBLE. Teeth not separate, no hyoid [V, previous report] | YES | CC BY 4.0 [V] | yes, but coarse |
| 4 | HuBMAP HRA Eye, male, left/right v1.3 | 23 parts per eye: sclera, cornea, iris, pupil, lens, zonule, ciliary body/muscle/processes, trabecular meshwork, Schlemm's canal, aqueous, vitreous, choroid, retina, ora serrata, macula, fovea, optic disc, bulbar and palpebral conjunctiva. 27.5 MB GLB [V, measured] | Modelled from the Visible Human Male, own frame | CC BY 4.0 [V] | YES - best eye source |
| 5 | HRA Mouth, male v1.0 | 32 names: parotid, submandibular, sublingual glands L/R, tongue (parts, papillae), gingiva, hard and soft palate, buccal mucosa, frenula, mouth floor, upper teeth, lower teeth (as rows), mandible. 53.5 MB GLB (not downloaded) [V metadata] | Modelled from VHM | CC BY 4.0 [V] | yes |
| 6 | HRA Larynx, male v1.1 | thyroid, cricoid, epiglottic, arytenoid L/R, corniculate L/R cartilages. 0.34 MB [V, measured] | Modelled from VHM | CC BY 4.0 [V] | yes |
| 7 | HRA Brain, male v1.4 | 283 meshes (141 Allen structures mirrored), 12 MB [V, measured]. NOT his brain: Allen atlas "resized to fit the Visible Human Male" | NO (fitted) | CC BY 4.0 [V] | yes (generic) |
| 8 | HRA United male v1.10 | Adds extraocular muscles (4 recti, 2 obliques per eye), optic nerve/chiasm/tract/radiation, central retinal vessels, palatine tonsils, laryngeal muscles. 241 MB [V crosswalk] | Modelled from VHM | CC BY 4.0 [V] | yes |
| 9 | Allen Human Reference Atlas 3D, 2020 | Label volume, 141 brain structures, drawn on MNI ICBM 2009b symmetric template [V] | NO | "provided under the Attribution International 4.0 (CC BY 4.0) license as of Sept. 1, 2022" [V] | YES - best brain naming source (warp onto our grey/white) |
| 10 | TotalSegmentator open tasks (run on our CT) | See section 3. head_muscles, headneck_muscles, headneck_bones_vessels, head_glands_cavities, craniofacial_structures, teeth, oculomotor_muscles, ventricle_parts, total | YES (our CT) | "Openly available for any usage (Apache-2.0 license)" [V] | yes; quality on frozen non-contrast CT untested |
| 11 | TotalSegmentator brain_structures, face | lobes, thalamus, caudate, ventricle, cerebellum, brainstem... | YES (our CT) | "Available with a license (free licenses available for non-commercial usage ...). For a commercial license contact ..." [V] | NO unless a commercial licence is bought |
| 12 | BodyParts3D 4.0 | Skull bones separately (22 bones), 28 single teeth, hyoid, tongue + genioglossus/hyoglossus, palate, pharynx and larynx muscles, eye parts, tarsal plates, 14 extraocular muscles, external ear, nasal cartilages, lip, eyebrow, orbital nerves, optic nerve, ICA, IJV, cerebral arteries. NO mimic muscles, NO masseter/temporalis/pterygoids, NO facial/superficial temporal artery, NO facial nerve [V, name tables resolved] | NO | CC BY 4.0 (archive copy) [V, previous report] | yes, must be fitted |
| 13 | NLM "Additional Head Images" | NOT the Visible Human Male: "the head of a 72 year old male donor", formalin, vessels filled with araldite, cryosections at 0.147 mm, CT 0.489 x 0.5 mm, MRI. No labels [V] | NO | NLM: "public-domain library"; "As of 2019, a license is no longer required" [V] | yes as reference images (vessels are visible); no labels |
| 14 | Open Anatomy / SPL head and neck atlas 2016 | CT 256x256 (OsiriX MANIX): skull, mandible, neck muscles, cartilage, vessels, glands; no facial muscles or nerves named on the page [V] | NO | "3D Slicer License section B" [V]: covers "data, if any", royalty-free, "designed for research purposes only", commercialization "at the sole risk", full licence text must travel with copies; source CT has its own unclear terms | legal review |
| 15 | MIDA (IT'IS / FDA) | 115-153 head and neck structures incl. muscles, vessels, cranial nerves | NO | "non-exclusive, non-transferable"; "shall not be distributed to any third party whatsoever" [S] | NO |
| 16 | MNI Colin27 2008 | 0.5 mm head, 11 tissue classes (CSF, grey, white, fat, muscle, skin, skull, dura, marrow, vessels), no named structures | NO | "Permission to use, copy, modify, and distribute this software and its documentation for any purpose and without fee" (Collins / McGill) [V] | usable, little value |
| 17 | Harvard-Oxford atlas (FSL) | cortical and subcortical probability labels | NO | CC BY-SA 4.0 on the current FSL licence page; older releases non-commercial [S] | NO (flagged share-alike) |
| 18 | AAL / AAL3 | 116-170 brain regions | NO | not verified | not verified |
| 19 | Mendeley "3D models of human jaw with teeth, ligaments, and bone" (Diaz 2024; xjsx7nfhj8 and 97c3pf8h2h) | Lower jaw only: 14 teeth, 14 periodontal ligaments, cortical and cancellous bone; STL + IGES | NO | CC BY 4.0 (licence field: "give appropriate credit, provide a link to the CC BY license") [V, API] | yes, small value (lower jaw only) |
| 20 | Z-Anatomy | Has mimic muscles, vessels, nerves of the head | NO | CC BY-SA 4.0 [V, previous report] | NO (flagged) |
| 21 | AustinMan | VHM voxel model with tissue classes | YES | CC BY-NC-ND 3.0 [V, previous report] | NO (flagged) |
| 22 | Korean Visible Human brain, Zenodo 3956014 | 3D vector brain, 3 MB | NO | CC BY 4.0 (Zenodo API) [V listing only] | low value |

Headline: no usable open data set contains the muscles of facial expression, the external carotid branches (facial, superficial temporal, maxillary), the facial vein or the facial and trigeminal nerves as meshes. These must be generated on our own skull and skin from anatomical rules (section 5), or obtained from VOXEL-MAN when their head section is released.

## 2. Segmentations of the Visible Human Male head (same body)

### 2.1 VOXEL-MAN

- FAQ https://www.virtual-body.org/segmented-internal-organs/faq/ : "We are working on the head and neck section, please check back later." [V]. Licence of the published torso: "available free of charge via Zenodo under a Creative Commons Attribution 4.0 license (CC BY 4.0)", DOI 10.5281/zenodo.15882018 [V].
- Gallery https://www.virtual-body.org/gallery/visible-human/head/ : pictures titled "Head dissection", "Brain dissection (virtual)", "Head and neck muscles", "Brain white matter, basal view", "Skull base and optic nerves". No download, no licence on the page [V]. So a Visible Human head model with muscles exists there but is unpublished.
- Zenodo API search today for "visible human" AND (head OR skull OR brain): 5 records, none a Visible Human Male head segmentation [V].
- "Brain and Skull" navigator: CC BY-NC-ND [S]; not usable.
- Action: write to the group (same request as for the nerve and small-artery meshes in the previous report). This is the only path to a real, same-body head atlas with facial muscles.

### 2.2 BoneHub skull

SKULL.seg.nrrd, https://huggingface.co/datasets/BoneHub/visible-human-3d-models/resolve/main/visible_human_3d_models/CT/Segmentation/01_Male/SKULL.seg.nrrd (about 1 MB). Labels SKULL_CRANIAL_MAXILLA and SKULL_MANDIBLE only; no separate cranial bones, teeth are inside the bone labels, no hyoid [V, dataset card, previous report]. CC BY 4.0.

### 2.3 HuBMAP HRA head organs (male)

All read from the official metadata, e.g. https://cdn.humanatlas.io/digital-objects/ref-organ/eye-male-left/v1.3/metadata.json . Licence line, verbatim: "Creative Commons Attribution 4.0 International ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))" [V].

| Object | URL | Bytes | Measured / listed |
|---|---|---|---|
| Eye, male, left v1.3 | https://cdn.humanatlas.io/digital-objects/ref-organ/eye-male-left/v1.3/assets/3d-vh-m-eye-l.glb | 27,462,616 | 23 mesh nodes, 737,140 vertices, 346,630 triangles, no textures; bounding box 24.5 x 24.4 x 25.7 mm; centre x +0.036, y 0.810, z +0.084 m |
| Eye, male, right | .../ref-organ/eye-male-right/ (version not opened) | - | mirror set |
| Mouth, male v1.0 | https://cdn.humanatlas.io/digital-objects/ref-organ/mouth-male/v1.0/assets/3d-vh-m-mouth.glb | 53,487,620 | 32 names (crosswalk.csv); not downloaded |
| Larynx, male v1.1 | https://cdn.humanatlas.io/digital-objects/ref-organ/larynx-male/v1.1/assets/3d-vh-m-larynx.glb | 335,576 | 7 meshes, 6,772 vertices; 54 x 73 x 39 mm |
| Brain, male v1.4 | https://cdn.humanatlas.io/digital-objects/ref-organ/brain-male/v1.4/assets/3d-allen-m-brain.glb | 11,982,812 | 283 meshes, 324,855 vertices; 136 x 146 x 167 mm |

Descriptions, verbatim [V]:

- Eye: "was created using data from the Visible Human Male ... In version v1.3, the long posterior ciliary artery was added, as well as a more detailed iris. The position of the optic nerve also moved, and was made twice as thick. The muscle thickness was decreased and the position of the muscles was shifted. The levator palpebrae superioris muscle was removed ..."
- Mouth: "created using data from the Visible Human Male dataset ... features anatomically segmented oral structures including the gingiva, lingual mucosa, palate, vestibular tissues, teeth, and salivary structures."
- Brain: "created using data from the Allen brain reference atlas (Ding et al. 2016). The 141 anatomical structures were mirrored ... and resized to fit the Visible Human Male and Female bodies ... In version v1.3, an update in licensing occurred; this brain model is now licensed under Creative Commons Attribution 4.0 International (CC BY 4.0)."

Credits: Browne K., Schlehlein H. 2024, "3D Reference Organ for Eye, Male, Left v1.3", https://doi.org/10.48539/HBM769.RWTZ.963 ; Larynx v1.1 https://doi.org/10.48539/HBM362.HNZB.247 ; Brain v1.4 https://doi.org/10.48539/HBM538.NKCT.649 ; Mouth v1.0 https://doi.org/10.48539/HBM568.RFGM.978 (the male metadata prints the title "mouth, Female v1.0"; an error on their side).

Caveats: these are artist models (Maya) built over the Visible Human, in the HRA frame (metres, +Y up, +X patient left, +Z anterior; our z is flipped), not voxel-exact segmentations. They need a similarity fit to our orbit / mouth / larynx. The eye meshes have no UVs. The teeth are two rows, not single teeth.

### 2.4 NLM itself

- https://www.nlm.nih.gov/research/visible/visible_human.html [V]: "As of 2019, a license is no longer required to access the VHP datasets."; "the VHP provides a public-domain library of cross-sectional cryosection, CT, and MRI images". Head MRI: "Axial MRI images of the head and neck ... were obtained at 4mm intervals." No segmented data, AnatLine or Insight Toolkit labels are mentioned on the page.
- https://data.lhncbc.nlm.nih.gov/public/Visible-Human/Additional-Head-Images/ [V README]: "Data is the head of a 72 year old male donor. The donor was preserved in formalin and the blood vessels were filled with araldite-F. ... cryo sectioned at 0.147mm intervals ... 1056 x 1528 pixels" (Ratiu et al., "Visible Human 2.0", MMVR 11, 2003). CT 0.489 mm pixels, 0.5 mm slices; MRI PD/T1/T2 at 0.94 mm, 3 mm slices and T2 at 0.47 mm, 1 mm slices; 1,477 cryosections. It is another person. Good reference for small head vessels and for texture, no labels.
- Other groups: a NA-MIC 2019 project week page on the Visible Human notes incomplete head segmentation [S]. No other released Visible Human Male head label set with a usable licence was found. AnatLine: retired [M].

## 3. TotalSegmentator: what the open tasks give for the head and neck

Source: README (local copy build/research/totalseg/README.md, read today) [V]. Everything listed under "Openly available for any usage (Apache-2.0 license)":

- total (head and neck part) [M for the exact class list]: skull, brain, vertebrae_C1..C7, spinal_cord, trachea, esophagus, thyroid_gland, common_carotid_artery_left/right, subclavian arteries, brachiocephalic trunk and veins, clavicula.
- head_muscles: masseter_right/left, temporalis_right/left, lateral_pterygoid_right/left, medial_pterygoid_right/left, tongue, digastric_right/left.
- headneck_muscles: sternocleidomastoid R/L, superior / middle / inferior_pharyngeal_constrictor, trapezius R/L, platysma R/L, levator_scapulae R/L, anterior / middle / posterior_scalene R/L, sterno_thyroid R/L, thyrohyoid R/L, prevertebral R/L.
- headneck_bones_vessels: larynx_air, thyroid_cartilage, hyoid, cricoid_cartilage, zygomatic_arch R/L, styloid_process R/L, internal_carotid_artery R/L, internal_jugular_vein R/L.
- head_glands_cavities: eye L/R, eye_lens L/R, optic_nerve L/R, parotid_gland L/R, submandibular_gland L/R, nasopharynx, oropharynx, hypopharynx, nasal_cavity R/L, auditory_canal R/L, soft_palate, hard_palate.
- craniofacial_structures: mandible, teeth_lower, skull, head, sinus_maxillary, sinus_frontal, teeth_upper.
- teeth: lower_jawbone, upper_jawbone, inferior alveolar canals L/R, maxillary sinuses L/R, pharynx, bridge, crown, implant, all 32 teeth by FDI number (11-18, 21-28, 31-38, 41-48), mandibular incisive canals, lingual canal, and the pulp of each tooth ("based on the ToothFairy3 dataset", which is cone-beam CT).
- oculomotor_muscles: skull, eyeball R/L, lateral / medial / superior / inferior rectus R/L, superior / inferior oblique R/L, levator_palpebrae_superioris R/L, optic_nerve R/L. Marked with "*": "These models are not trained on the full totalsegmentator dataset but on some small other datasets. Therefore, expect them to work less robustly."
- ventricle_parts: frontal / occipital / temporal horn, body, trigone of each lateral ventricle, third_ventricle, fourth_ventricle.
- body: body, body_trunc, body_extremities, skin.

Restricted ("Available with a license (free licenses available for non-commercial usage ... For a commercial license contact jakob.wasserthal@usb.ch)") [V]: brain_structures (brainstem, subarachnoid_space, venous_sinuses, septum_pellucidum, cerebellum, caudate_nucleus, lentiform_nucleus, insular_cortex, internal_capsule, ventricle, central_sulcus, frontal / parietal / occipital / temporal lobe, thalamus), face (face_region), tissue_types.

Not offered by any task: mimic muscles, single skull bones, external carotid branches, facial vein, cranial nerves other than the optic nerve, sublingual gland, ear cartilage.

On a non-contrast frozen cadaver CT: no published test found [S]. The head and neck models come from Walter et al., Cancers 2024, 16, 415: 71 structures on 104 radiotherapy planning CT scans of living patients [S]. Expectation (my judgement, not tested): bone, teeth, air spaces and sinuses should work well; muscles, glands and the tongue moderately (frozen tissue has lower CT numbers than living tissue, which is outside the training range [M]; a trial with a soft-tissue HU offset is cheap); internal carotid and jugular poorly (no contrast, collapsed). The teeth task was trained on cone-beam CT at finer voxels than our 0.94 mm, so single-tooth labels may merge. The Visible Human Male also has a "fresh" CT of the head made before freezing [M]; if we have it, run the tasks on it too and compare. Every result must be checked against the 0.33 mm cryosection photographs.

## 4. Generic head atlases

### 4.1 BodyParts3D 4.0: exact head content

From isa_parts_list_e.txt, partof_parts_list_e.txt and isa_element_parts.txt (downloaded today, 3,433 distinct names, 2,234 element meshes) [V]:

- Mimic muscles: NONE. The concept "muscle of face" resolves to 14 elements, all extraocular: superior / inferior / medial / lateral rectus, superior / inferior oblique, levator palpebrae superioris (left and right). No orbicularis oculi or oris, zygomaticus, levator labii, buccinator, frontalis, mentalis, depressor, risorius, procerus, corrugator, nasalis. No masseter, temporalis or pterygoids. Platysma L/R is present.
- Neck and floor of mouth (54 elements): digastric, geniohyoid, mylohyoid, omohyoid, sternohyoid, sternothyroid, thyrohyoid, stylohyoid, sternocleidomastoid, scalenus anterior / medius / posterior, platysma, pharyngeal constrictors (3), palatopharyngeus, salpingopharyngeus, stylopharyngeus, laryngeal muscles (lateral and posterior crico-arytenoid, oblique and transverse arytenoid, thyro-arytenoid, vocalis, cricothyroid), plus longus colli / capitis, rectus capitis, splenius, semispinalis.
- Tongue and palate: tongue (1 mesh), genioglossus, hyoglossus, levator and tensor veli palatini, uvular muscle.
- Skull bones as separate meshes: frontal, occipital, sphenoid, ethmoid, vomer, mandible, and left/right parietal, temporal, maxilla, zygomatic, nasal, lacrimal, palatine, inferior nasal concha; hyoid. No ear ossicles found.
- Teeth: 28 single permanent teeth (central and lateral incisor, canine, first and second premolar, first and second molar x 4 quadrants). No third molars.
- Eye: cornea, sclera, iris, lens, vitreous body, anterior chamber, retina, vascular layer, suspensory ligament of lens, check ligaments, tarsal plates of the 4 eyelids, lacrimal gland.
- Other: external ear (1 mesh), eyebrow / facial hairs, lip, external nose with lateral, major alar and septal cartilages, thyroid / cricoid / arytenoid / corniculate / cuneiform cartilages, epiglottis, submandibular and sublingual glands (no parotid found).
- Vessels: common carotid, internal carotid (with cerebral part), internal jugular vein, vertebral, basilar, anterior / middle / posterior cerebral arteries with many named branches, cerebellar arteries, ophthalmic artery. NOT present: external carotid, facial, lingual, maxillary, superficial temporal, occipital (scalp) arteries; facial, retromandibular, external jugular veins.
- Nerves: optic nerve, chiasm, tract; oculomotor (superior and inferior branch), trochlear, ophthalmic, frontal, supra-orbital, supratrochlear, lacrimal, nasociliary, infratrochlear, anterior and posterior ethmoidal, long and short ciliary nerves, ciliary ganglion. NOT present: facial nerve, maxillary and mandibular divisions, vagus, hypoglossal, accessory.
- Brain: lobes, many gyri, cerebellum, caudate, hippocampus, hypothalamus, corpus callosum, ventricles and more (59 elements under "brain").

Licence, download and credit as in the previous report (CC BY 4.0, archive copy only).

### 4.2 Brain atlases

- Allen Human Reference Atlas 3D, 2020. README https://download.alleninstitute.org/informatics-archive/allen_human_reference_atlas_3d_2020/version_1/README.pdf [V]: "a parcellation of the adult human brain in 3D, labeling every voxel with a brain structure spanning 141 structures"; drawn on "ICBM 2009b Nonlinear Symmetric"; "TERMS OF USE: These materials are now provided under the Attribution International 4.0 (CC BY 4.0) license as of Sept. 1, 2022". Citation: Ding S-L, Royall JJ, Sunkin SM, Facer BAC, Lesnar P, Bernard A, Ng L, Lein ES (2020), "Allen Human Reference Atlas - 3D, 2020", RRID:SCR_017764, version 1.0.0; "© 2019 Allen Institute for Brain Science". Download folder: http://download.alleninstitute.org/informatics-archive/allen_human_reference_atlas_3d_2020/version_1/ (file names and sizes not read). The template itself comes from the MNI under its own permissive notice. Verdict: usable.
- MNI Colin27 2008, https://nist.mni.mcgill.ca/colin-27-average-brain-2008/ [V]: "Permission to use, copy, modify, and distribute this software and its documentation for any purpose and without fee" (Copyright Louis Collins, McConnell Brain Imaging Centre, 1993-2009; keep the notice). 0.5 mm; 11 tissue classes. Downloads 222-291 MB (not downloaded). Usable; little value because nothing is named.
- Harvard-Oxford: current FSL licence page says CC BY-SA 4.0; older FSL releases said non-commercial [S]. Flagged, not usable.
- AAL / AAL3: licence not verified.
- TotalSegmentator brain_structures: restricted (section 3).

### 4.3 Others

- Open Anatomy SPL head and neck atlas: see table row 14. 3D Slicer licence Part B, https://raw.githubusercontent.com/Slicer/Slicer/main/License.txt [V]: grants "with right to sublicense, with respect to Brigham's rights in the software, and data, if any" a "royalty-free, non-exclusive" licence; "The Software has been designed for research purposes only"; "Any commercialization of the Software is at the sole risk of the party or parties engaged in such commercialization"; copies must carry the licence; names of Brigham may not be used "to endorse or promote products". Not CC. Legal review; low priority because it has no facial muscles either.
- MIDA: licence PDF https://itis.swiss/assets/Downloads/VirtualPopulation/License_Agreements/LicenseAgreementMIDA.pdf : "non-exclusive, non-transferable"; data "must not be distributed or redistributed in the original form or in any modified or updated form" [S]. Not usable.
- Dental: no CC BY / CC0 full-dentition set of single anatomical teeth found (Zenodo API searches returned 0). Mendeley Diaz 2024 (lower jaw, 14 teeth, CC BY 4.0 [V]) is a finite-element model set. For teeth, our own CT + cryosections, TotalSegmentator "teeth", and BodyParts3D's 28 teeth are the practical sources.
- Eye with internal anatomy: HRA eye (row 4) is the answer. No other CC BY / CC0 eye found (Zenodo search 0 hits).

## 5. Numbers for what no data gives

All values in this section are [M] (standard textbook values recalled from Gray's Anatomy, Wolff's Anatomy of the Eye and Orbit, Wheeler's Dental Anatomy, Freilinger 1987 / Happak 1997, Rhine and Moore 1984, Stephan and Simpson 2008) unless marked otherwise. I could not open these sources today. Use them to build, and confirm any number that will be shown to a student as a fact.

### 5.1 Eye and orbit

| Item | Value |
|---|---|
| Globe | axial 24 mm (23.5-24.5), transverse 24.2, vertical 23.7; volume 6.5 ml. HRA model measures 24.5 x 24.4 x 25.7 mm incl. conjunctiva [V] |
| Sclera | radius about 12 mm; thickness 1.0 mm at the back, 0.5-0.6 at the equator, 0.3 under the rectus insertions, 0.8 at the limbus |
| Cornea | diameter 11.7 mm horizontal, 10.6-11 vertical; front radius 7.8 mm, back radius 6.5 mm; thickness 0.52-0.55 mm centre, 0.7-1.0 edge |
| Anterior chamber | depth 3.0 mm (2.5-3.5); volume 0.25 ml |
| Iris | diameter 12 mm, thickness 0.5 mm; pupil 2-4 mm in light, up to 8 mm in dark; after death usually mid-wide, 4-6 mm |
| Lens | equatorial diameter 9-10 mm, thickness 4.0-4.5 mm at age 40; front radius 10 mm, back radius 6 mm |
| Vitreous | 4 ml |
| Optic disc, macula | disc 1.5 x 1.75 mm, centre 3-4 mm nasal to the fovea and slightly above it; macula 5.5 mm; fovea 1.5 mm |
| Optic nerve | total 45-50 mm: in the globe 1 mm, in the orbit 25-30 mm (S-shaped slack; straight distance globe to canal 18-20 mm), in the canal 5-9 mm, intracranial 10 mm to the chiasm. Diameter 1.5 mm at the disc, 3-4 mm behind the globe, 4-5 mm with its sheath |
| Orbit | entrance 40 mm wide x 35 mm high, depth 40-45 mm, volume 30 ml; medial walls parallel and 25 mm apart; lateral wall at 45 degrees to the medial wall; orbital axis 23 degrees outward from the sagittal plane |
| Position | interpupillary distance, adult male, 64 mm (54-74); corneal apex 16-17 mm in front of the lateral orbital rim (12-21) |

Extraocular muscles (origin: common tendinous ring at the orbital apex, unless noted):

| Muscle | Length | Tendon length | Insertion width | Insertion from limbus |
|---|---|---|---|---|
| Medial rectus | 40 mm | 3.7 mm | 10.3 mm | 5.5 mm |
| Inferior rectus | 40 mm | 5.5 mm | 9.8 mm | 6.5 mm |
| Lateral rectus | 40 mm | 8.8 mm | 9.2 mm | 6.9 mm |
| Superior rectus | 42 mm | 5.8 mm | 10.6 mm | 7.7 mm |
| Superior oblique | 32 mm belly + 26 mm tendon | via the trochlea (upper medial orbital rim, 4 mm behind it) | 10.8 mm | upper outer back quadrant, under the superior rectus; tendon makes 51-54 degrees with the visual axis |
| Inferior oblique | 37 mm | 1 mm | 9.4 mm | origin: orbital floor just lateral to the lacrimal fossa; inserts lower outer back quadrant near the macula; 51 degrees |
| Levator palpebrae | 40 mm belly + 15-20 mm aponeurosis | - | whole width of the upper lid | origin: lesser wing of the sphenoid above the ring |

Belly thickness 3-5 mm, belly width 8-10 mm.

### 5.2 Eyelids

- Palpebral fissure 28-30 mm long, 9-11 mm high when open; lateral canthus 2 mm higher than the medial. Upper lid covers the top 1-2 mm of the cornea; lower lid lies at the limbus.
- Tarsal plates: upper 25-29 mm long, 10 mm high in the middle, 1 mm thick; lower 4-5 mm high, 1 mm thick (local note: build/research/wiki/Tarsus_(eyelids).txt).
- Lid skin 0.5 mm (thinnest of the body). Orbicularis oculi about 1 mm thick: pretarsal and preseptal parts in the lid; orbital part reaches the eyebrow above, about 30 mm lateral to the lateral canthus, and 10-20 mm below the lower orbital rim.
- Medial canthal tendon to the anterior lacrimal crest; lateral canthal tendon to Whitnall's tubercle, 2-3 mm inside the lateral rim, about 10 mm below the frontozygomatic suture.
- Lashes: upper lid 100-150, lower 50-75. Meibomian glands 25-40 upper, 20-30 lower.

### 5.3 Teeth (Wheeler's averages, mm)

| Tooth | Crown height | Mesiodistal | Labio/buccolingual | Root length |
|---|---|---|---|---|
| Upper central incisor | 10.5 | 8.5 | 7.0 | 13.0 |
| Upper lateral incisor | 9.0 | 6.5 | 6.0 | 13.0 |
| Upper canine | 10.0 | 7.5 | 8.0 | 17.0 |
| Upper first premolar | 8.5 | 7.0 | 9.0 | 14.0 |
| Upper second premolar | 8.5 | 7.0 | 9.0 | 14.0 |
| Upper first molar | 7.5 | 10.0 | 11.0 | 12-13 |
| Upper second molar | 7.0 | 9.0 | 11.0 | 11-12 |
| Upper third molar | 6.5 | 8.5 | 10.0 | 11.0 |
| Lower central incisor | 9.0 | 5.0 | 6.0 | 12.5 |
| Lower lateral incisor | 9.5 | 5.5 | 6.5 | 14.0 |
| Lower canine | 11.0 | 7.0 | 7.5 | 16.0 |
| Lower first premolar | 8.5 | 7.0 | 7.5 | 14.0 |
| Lower second premolar | 8.0 | 7.0 | 8.0 | 14.5 |
| Lower first molar | 7.5 | 11.0 | 10.5 | 14.0 |
| Lower second molar | 7.0 | 10.5 | 10.0 | 13.0 |
| Lower third molar | 7.0 | 10.0 | 9.5 | 11.0 |

Arch: sum of the 14 crown widths, upper 111 mm, lower 106 mm (computed from the table). Width between canine tips: upper 34-35 mm, lower 26-27 mm. Width between first molars (mesiobuccal cusps): upper 52-54 mm, lower 46-48 mm. Arch depth, incisors to the back of the first molars: upper 28-30 mm, lower 25-26 mm; to the second molars about 43-45 mm. Shape: a parabola or catenary through these points. Upper incisors overlap the lower by 2-3 mm vertically and stand 2-3 mm in front. Curve of Spee 1.5-2 mm deep. Enamel up to 2-2.5 mm on cusps.

### 5.4 Tongue, ear, glands

- Tongue: 9-10 cm from tip to the vallecula (front two-thirds 6-7 cm), 5 cm wide, 1.5-2 cm thick at mid-body above the floor muscles; volume 70-80 cm3 and mass 60-70 g in men.
- Auricle: 63 mm high (55-70) and 35 mm wide in men; lobule 18-20 mm; long axis tilted back 15-20 degrees; helix stands 15-20 mm off the mastoid (angle 20-30 degrees); top level with the eyebrow, bottom with the base of the nose. Elastic cartilage 1-1.5 mm thick; none in the lobule. Ear canal 25 mm long, 7-9 mm wide, outer third cartilage, inner two-thirds bone; eardrum 9-10 mm.
- Parotid 58 x 34 mm, 15-30 g; its duct 50 mm long, 3 mm wide, on the line from the tragus to the middle of the upper lip, about 15 mm below the zygomatic arch, piercing the buccinator opposite the upper second molar. Submandibular 7-15 g, 30-40 mm. Sublingual 3-4 g, 30-40 mm long.

### 5.5 Facial muscles as bands (origin, insertion, size)

Sizes as length x width x thickness in mm. Zygomaticus major is from Freilinger 1987 as I recall it; the others are approximate.

| Muscle | Origin | Insertion | Size |
|---|---|---|---|
| Frontalis (frontal belly) | galea aponeurotica near the coronal suture; no bone | skin of the eyebrow and root of nose, blending with orbicularis oculi, procerus, corrugator | 60-70 x 50-60 x 1-2 per side |
| Occipital belly | lateral two-thirds of the superior nuchal line, mastoid | galea | 30-40 x 50-60 x 1-2 |
| Orbicularis oculi, orbital part | medial orbital margin: nasal part of frontal bone, frontal process of maxilla, medial palpebral ligament | loops round the orbit back to the origin | outer ring 60-70 wide x 50-60 high; ring band 15-20; 1 thick |
| Orbicularis oculi, palpebral part | medial palpebral ligament | lateral palpebral raphe | over both lids; 1 thick |
| Corrugator supercilii | medial end of the superciliary arch | skin of the middle of the eyebrow | 30-40 x 8-10 x 2 |
| Procerus | nasal bone, upper lateral cartilage | skin between the eyebrows | 15-20 x 10 x 1 |
| Nasalis | maxilla beside the nasal notch (transverse part); maxilla above the lateral incisor (alar part) | aponeurosis over the nasal bridge; alar cartilage | 20-25 x 8-10 x 1 |
| Levator labii superioris alaeque nasi | frontal process of maxilla | alar cartilage and upper lip | 50-60 x 5 x 1.5 |
| Levator labii superioris | infraorbital margin above the infraorbital foramen, 20-25 wide | skin and orbicularis of the lateral upper lip | 34 x 25 x 1.8 |
| Zygomaticus minor | zygomatic bone behind the zygomaticomaxillary suture | lateral upper lip | 50 x 5 x 1 |
| Zygomaticus major | zygomatic bone in front of the zygomaticotemporal suture | modiolus (angle of mouth) | 70 x 8 x 2 |
| Levator anguli oris | canine fossa below the infraorbital foramen | modiolus | 38 x 14 x 1.7 |
| Risorius (often absent) | parotid and masseteric fascia | modiolus | 38 x 12 x 1 |
| Buccinator | alveolar processes of maxilla and mandible beside the three molars; pterygomandibular raphe | modiolus and orbicularis oris | 55-60 x 40-45 x 2-3 |
| Orbicularis oris | no bone; modiolus to modiolus | skin and mucosa of the lips | mouth width 50-55; from the nasal base to the chin-lip fold; 3-4 thick |
| Depressor anguli oris | oblique line of the mandible, canine to first molar, base 30-35 | modiolus | 40-48 long, triangular, 1.5 thick |
| Depressor labii inferioris | oblique line between symphysis and mental foramen | skin of the lower lip | 29 x 13-20 x 2-2.5 |
| Mentalis | incisive fossa of the mandible | skin of the chin | 20-25 x 10, cone |
| Platysma | fascia over pectoralis major and deltoid, to the 2nd rib | lower border of the mandible, skin of the lower face, modiolus | 180-200 x 60-90 x 1-1.5 |
| Masseter | superficial: zygomatic process of maxilla, front two-thirds of the arch; deep: back third and inner face of the arch | angle and lateral face of the ramus; coronoid | 45-50 x 30-40 x 12-15; volume 25-30 cm3 |
| Temporalis | temporal fossa up to the inferior temporal line, deep temporal fascia | coronoid process, front of the ramus down to behind the last molar | fan 100-120 x 70-90, 10-15 thick above the arch |
| Medial pterygoid | medial face of the lateral pterygoid plate, maxillary tuberosity | medial face of the angle | 40-45 x 25 x 12 |
| Lateral pterygoid | upper head: greater wing; lower head: lateral face of the lateral pterygoid plate | pterygoid fovea of the condylar neck, joint disc | 30-35 long; lower head 25 x 15 |
| Auricular muscles | galea (superior, anterior); mastoid (posterior) | auricle | superior fan 40; posterior 15-20 |
| Digastric | mastoid notch | digastric fossa of the mandible, via the tendon at the hyoid | posterior belly 70, anterior 40 x 8-10 |

Happak et al. 1997 (Anat Rec 249:276): ten facial muscles of 11 cadavers measured 29 to 65 mm in length [S, abstract]; the per-muscle table was not readable.

### 5.6 Soft tissue thickness at forensic landmarks (mm)

Rhine and Moore 1984, American white males, as I recall the table [M]; the search could not confirm any value today.

| Landmark | Slender | Normal | Obese |
|---|---|---|---|
| Supraglabella | 2.25 | 4.25 | 5.50 |
| Glabella | 2.50 | 5.25 | 7.50 |
| Nasion | 4.25 | 6.50 | 7.50 |
| End of nasal bones (rhinion) | 2.50 | 3.00 | 3.50 |
| Mid-philtrum | 6.25 | 10.00 | 11.00 |
| Upper lip margin | 9.75 | 9.75 | 11.00 |
| Lower lip margin | 9.50 | 11.00 | 12.75 |
| Chin-lip fold | 8.75 | 10.75 | 12.25 |
| Mental eminence (pogonion) | 7.00 | 11.25 | 14.00 |
| Beneath chin (menton) | 4.50 | 7.25 | 10.75 |
| Frontal eminence | 3.00 | 4.25 | 5.50 |
| Supraorbital | 6.25 | 8.25 | 10.25 |
| Suborbital | 2.75 | 5.75 | 8.25 |
| Inferior malar | 8.50 | 13.25 | 15.25 |
| Lateral orbit | 5.00 | 10.00 | 13.75 |
| Zygomatic arch, midway | 3.00 | 7.25 | 11.75 |
| Supraglenoid | 4.25 | 8.50 | 11.25 |
| Gonion | 4.50 | 11.50 | 17.50 |
| Above upper second molar | 12.00 | 19.50 | 25.00 |
| Occlusal line | 12.00 | 18.25 | 23.50 |
| Below lower second molar | 10.00 | 16.00 | 19.75 |

Modern pooled means (Stephan and Simpson 2008 T-table, adults, as I recall [M]): vertex 5, opisthocranion 6.5, glabella 5.5, nasion 6.5, rhinion 3, subnasale 13, mid-philtrum 11.5, upper lip 12, lower lip 13, chin-lip fold 11, pogonion 11, menton 7, mid-supraorbital 6, mid-infraorbital 7, zygion 6, gonion 10, mid-ramus 17.5, above upper M2 26, below lower M2 19.5. The 2018 table is Stephan, Forensic Sci Int 280:113-123, doi:10.1016/j.forsciint.2017.09.016; a 2023 update raises infra-M2 by 3 mm, gonion by 2.5, mid-ramus by 2, zygion by 1.5 against 2008 [S].

Rule of thumb [M]: midline points over thin bone (glabella, nasion, rhinion) change little with body weight; cheek and jaw points change most. The Visible Human Male was 5 ft 11 in and 199 lb [S], BMI about 27.8 (computed), so he sits between the "normal" and "obese" columns. We do not need the tables for him: his real thickness can be measured at every landmark directly from our skull and skin meshes. The tables matter only for a different body build.

### 5.7 Scalp and skull

Scalp layers (S-C-A-L-P): skin 3 mm at the vertex up to 6-8 mm at the occiput; dense connective tissue with the vessels; aponeurosis (galea) 1-2 mm; loose areolar tissue 1-3 mm; pericranium under 1 mm. Total about 5-6.5 mm. Vault bone 6-7 mm on average (temporal squama 2-4, occipital 7-10).

### 5.8 Landmarks for vessels and nerves to be generated

- Facial artery: 2.5-3 mm wide; crosses the lower border of the mandible at the front edge of the masseter; winds to a point about 15 mm lateral to the angle of the mouth, then beside the nose to the medial canthus (angular artery). Facial vein: behind the artery, straighter.
- Superficial temporal artery: 2-2.7 mm; crosses the zygomatic arch 10-15 mm in front of the tragus; splits 30-40 mm above the arch into frontal and parietal branches.
- Common carotid 6-7 mm, internal jugular 10-15 mm.
- Facial nerve: trunk 2-3 mm, leaves the stylomastoid foramen, runs 15-20 mm, divides inside the parotid into temporal, zygomatic, buccal, marginal mandibular and cervical branches.
- Supraorbital notch, infraorbital foramen and mental foramen lie on one vertical line 25-27 mm from the midline: infraorbital foramen 6-10 mm below the orbital rim; mental foramen below the second premolar, 13-15 mm above the lower border.

## 6. The Visible Human Male's own face

- No paper was found that describes his face, his dental state or a reconstruction of his living appearance [S; two searches]. The NLM page gives no such detail [V].
- Known facts: Joseph Paul Jernigan, executed by lethal injection on 5 August 1993, age 39, 5 ft 11 in, 199 lb [S]. One testicle, appendix removed [S]. A missing tooth (number 14 in US numbering, upper left first molar) is in my memory of the NLM fact sheet [M]; the search could not confirm it. Check it on our own CT.
- The technical report (Spitzer et al., JAMIA 1996;3:118-130, PMC116294) is a scanned article; Europe PMC returned no machine-readable full text, so I could not read what it says about the head.
- His real face, head measurements and teeth are best taken from our own data: the skin and skull meshes and the 0.33 mm photographs.

## 7. Recommended source for each head layer

| Layer | First choice | Fallback / addition |
|---|---|---|
| Skull parts | BoneHub cranium + mandible (same body, CC BY 4.0); split the cranium into named bones by fitting BodyParts3D's 22 separate skull bones (CC BY 4.0) to it and carrying the names across | TotalSegmentator: zygomatic_arch, styloid_process, hyoid, sinuses (open) |
| Larynx, hyoid | HRA larynx (CC BY 4.0, modelled on him) + TotalSegmentator thyroid_cartilage, cricoid_cartilage, hyoid on our CT | BodyParts3D cartilages |
| Chewing muscles, tongue, neck muscles | TotalSegmentator head_muscles and headneck_muscles on our CT (Apache-2.0), checked against the photographs | BodyParts3D neck and floor-of-mouth muscles, fitted |
| Muscles of facial expression | No data. Generate as bands on our skull and skin from the table in 5.5, then correct against the 0.33 mm photographs | Ask VOXEL-MAN for their head model |
| Eyes | HRA eye male left / right v1.3 (CC BY 4.0), fitted to our orbits | Extraocular muscles and optic nerve: HRA united, TotalSegmentator oculomotor_muscles, or BodyParts3D; tarsal plates: BodyParts3D; eyelids: numbers in 5.2 |
| Teeth | Our own CT and photographs, labelled with TotalSegmentator "teeth" (FDI numbers) or craniofacial_structures (upper / lower) | BodyParts3D 28 single teeth as shape templates; sizes in 5.3 |
| Tongue, palate, glands | TotalSegmentator tongue, soft_palate, hard_palate, parotid, submandibular on our CT | HRA mouth (tongue parts, gingiva, all three gland pairs, CC BY 4.0); BodyParts3D genioglossus, hyoglossus |
| Vessels | Internal carotid, internal jugular, common carotid: TotalSegmentator on our CT, expected weak; BodyParts3D for ICA, IJV, vertebral, basilar, cerebral arteries, ophthalmic, fitted | Facial, superficial temporal, maxillary, lingual arteries and facial vein: no data; generate as tubes from 5.8. The NLM "Additional Head Images" head (public domain) shows filled vessels for reference |
| Nerves | Optic nerve, chiasm, tract: HRA united or BodyParts3D; orbital nerves: BodyParts3D | Facial and trigeminal branches: no data; generate from foramina (5.8); ask VOXEL-MAN |
| Brain | Our own grey and white matter, named by warping the Allen Human Reference Atlas 3D 2020 label volume (141 structures, CC BY 4.0) onto it | HRA brain GLB (283 meshes, already scaled to him, CC BY 4.0); TotalSegmentator ventricle_parts (open) |

Credit lines to add to LICENSES.md when a source is taken in: the HRA DOIs in 2.3; "Allen Human Reference Atlas - 3D, 2020, RRID:SCR_017764, © 2019 Allen Institute for Brain Science, CC BY 4.0"; TotalSegmentator (Wasserthal et al. 2023, doi:10.1148/ryai.230024; head and neck tasks also Walter et al., Cancers 2024, 16, 415); BodyParts3D and BoneHub as in the previous report; "Courtesy of the U.S. National Library of Medicine".

## 8. What I could not verify

- Whether and when VOXEL-MAN will release the head and neck section, and under which licence. The "Brain and Skull" CC BY-NC-ND statement is from a search summary.
- TotalSegmentator on our frozen non-contrast CT: not run; no published cadaver test found. The class list of the "total" task for the head is from memory. No separate licence file for the model weights was read; the README sentence is the only statement.
- HRA: the mouth GLB (53 MB) and the united GLB (241 MB) were not opened; the right eye version was not opened; the fit of the HRA eye, mouth and larynx to our volume was not measured.
- Allen atlas: file names, voxel size and sizes in the download folder. The MNI ICBM 2009b template licence text (only the Colin27 notice was read).
- BodyParts3D: meshes not opened; content judged from the name tables. Parotid gland and ear ossicles were not found in the tables by my searches.
- All numbers in section 5 are from memory, including the Rhine and Moore and Stephan tables and the muscle sizes; the Happak and Freilinger tables and the Stephan T-tables could not be opened (craniofacialidentification.com returned 404).
- The Visible Human Male's missing tooth and any paper on his face: nothing found; the 1996 technical report was not readable.
- MIDA and Harvard-Oxford licence wording: search summaries only. AAL: not checked. The 3D Slicer licence was read through a summarising fetch with short quotes, not as full text. The terms of the OsiriX MANIX CT behind the SPL head and neck atlas were not read.
- NLM AnatLine and Insight Toolkit Visible Human head data: not found on the current NLM page; not researched further.
