# Face and head: assets, fitting, repair, detail (research, 2026-11-12)

STATUS: final (draft 3). Marks: [V] read at the source today, [S] search summary only, [M] from memory / reasoning. Nothing larger than 3 MB was downloaded; no repository file other than this report was changed.

## 0. Summary

Recommended route in one line: wrap the MIT-licensed ICT-FaceKit head (separate lids, eyeballs, tear line, mouth bag, gums, tongue, 32 teeth, lashes, UVs) onto our scanned Visible Human head, keep the scan as the source of shape detail (displacement/normal) and colour, place eyeballs and teeth from the internal data (labels, CT), add CC0/CC BY micro detail.

| Asset | What it has | Licence (quote) | Verdict |
|---|---|---|---|
| ICT-FaceKit "Face Model Light" (USC ICT) | 26,719 v / 26,384 faces (25,836 quads) with UVs: face, back head, mouth socket, eye sockets, gums+tongue, 32 teeth, eyeballs (sclera+iris), lacrimal fluid, eye blend, eye occlusion, eyelashes; 53 expression shapes, 100 identity modes; 68 landmark indices; no textures | "ICT-FaceKit is released under the MIT license." / "MIT License, Copyright (c) 2020 USC Institute for Creative Technologies" [V] | YES, first choice |
| MakeHuman / MPFB2 assets | body base mesh, eyes, teeth, tongue, eyebrows, eyelashes, skins | "These assets have been released under CC0 1.0 Universal." [V] | YES (assets); MPFB code GPLv3 = tool only |
| Anny (NAVER 2025) | Python model on MakeHuman topology | code Apache-2.0, data "CC0 1.0 Universal" [V] | YES, optional |
| Blender Human Base Meshes v1.4.1 | 17 quad meshes with UVs: realistic + stylised bodies, heads, jaws, eyeballs | "available free under a Creative Commons CC0 licence" [V at cgchannel; blender.org blocked] | YES, parts donor |
| FLAME 2023 Open | 5,023 v head, eyeballs; no teeth/tongue/mouth bag [M] | "right to share and adapt the model for any purpose, including commercial use" (CC BY 4.0), "applies ONLY to the FLAME 2023 Open model" [V] | usable, but inferior to ICT |
| Lee Perry-Smith "Infinite" head | scan mesh, colour, spec, 4096 displacement, tangent normal | "licensed under a Creative Commons Attribution 3.0 Unported License" [V] | YES, detail maps / reference, credit required |
| Sketchfab "Human Materials 1" | 4 seamless 2K skin materials (colour, AO, roughness, normal, displacement) | description "CC0 free to use however you want, no attribution needed"; licence field CC BY 4.0 [V] | YES (credit to be safe) |
| FLAME 2017/2019/2020/2023 standard | | "for the sole purpose of performing non-commercial scientific research" [V] | NO |
| Basel Face Model 2019 | face PCA | "internal, non-commercial research, evaluation or testing purposes only" [V] | NO |
| FaceScape | faces + bilinear model | "only released for non-commercial research use" [V] | NO |
| Universal Head Model (UHM) | head PCA with eyes, teeth variants | "non-commercial research and education purposes only" [V] | NO |
| FaceWarehouse | 150 subjects | terms not found (research request) | NO, unverified |
| 3D Scan Store / Ten24 free heads | scans + retopo | "any private or non commercial project" [V] | NO |
| Digital Emily 2 (Wikihuman) | head + EXR maps | free "only for non-commercial use" [S] | NO |
| Triplegangers free samples | scans | licence not found | NO, unverified |
| MetaHuman | AAA head | "now obeys the standard Unreal Engine EULA", other engines allowed [V secondary] | LEGAL REVIEW; proprietary, outside our licence rule |
| Reallusion Character Creator | AAA base | proprietary paid EULA [S] | outside the rule |
| Ready Player Me | stylised avatars | CC non-commercial for website avatars [S]; docs host no longer resolves [V] | NO |
| Unity Digital Human package | eye / tearline / skin tech, HDRP | "Unity Companion License for Unity-dependent projects" [V] | technique reference only |

## 1. Template heads

### 1.1 ICT-FaceKit (recommended)
- URL: https://github.com/USC-ICT/ICT-FaceKit ; repository about 228 MB (GitHub API "size": 227693 KB) [V]. We need only `FaceXModel/generic_neutral_mesh.obj` (2.56 MB [V]) plus a few expression OBJs (eyeBlink_L/R, mouthClose, jawOpen), each about the same size: https://raw.githubusercontent.com/USC-ICT/ICT-FaceKit/master/FaceXModel/generic_neutral_mesh.obj
- Licence [V] https://raw.githubusercontent.com/USC-ICT/ICT-FaceKit/master/LICENSE : "MIT License / Copyright (c) 2020 USC Institute for Creative Technologies / Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software ... The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software." README: "ICT-FaceKit is released under the MIT license."
- Measured from the OBJ today [V]: 26,719 vertices, 28,911 UV coordinates, 26,384 faces (25,836 quads, 548 triangles); material groups M_Face, M_BackHead, M_GumsTongue, M_Teeth, M_ScleraLeft, M_IrisLeft, M_ScleraRight, M_IrisRight, M_LacrimalFluid, M_EyeBlend, M_EyeOcclusion, M_EyeLashes.
- Sub-meshes (README) [V]: face 9,409 v; head and neck 1,839 v; mouth socket 2,046 v; eye sockets 384 v each; gums and tongue 2,977 v; teeth 4,412 v (32 individual teeth); eyeballs 1,570 v each; lacrimal fluid 204 v each; eye blend 24 v each; eye occlusion 152 v each; eyelashes 684 v each. 53 expression shapes (ARKit-style: eyeBlink_L/R, eyeLookDown, jawOpen, mouthClose, PupilDilate ...) and 100 identity modes.
- Landmarks [V]: the README gives 68 "Multi-PIE 68 point facial landmarks indices" (0-indexed vertex ids: 1225, 1888, 1052, 367, ... 5517, 5966): the template side of the landmark pairs is already defined.
- Limits [V]: no skin textures in the repo (only UV layout figures); "The full model will be released under a different USC specific license": only the Light model is MIT. Face vertex spacing is about 2 to 3 mm, so scan detail must go into maps (section 2.3 step 6).

### 1.2 MakeHuman / MPFB2 / Anny
- https://static.makehumancommunity.org/about/license.html [V]: "All core assets are shared under Creative Commons, CC0." "you are free to do as you see fit with the asset or derivates of the assets."
- MPFB2 LICENSE.md [V] https://github.com/makehumancommunity/mpfb2/blob/master/LICENSE.md : assets = "The base mesh and proxies / Targets and modifiers / Textures / Clothes / Rigs, poses and expressions / JSON data ... These assets have been released under CC0 1.0 Universal." Code: "The MPFB source ... is released under GPLv3." Output: "no output from MPFB contains any trace of program logic". Repo about 90 MB.
- Asset packs [V] https://static.makehumancommunity.org/assets/assetpacks.html : "System assets, shared under CC0" (proxies, eyes, teeth ...); Skins 01/02/03 "Material assets, shared under CC0"; Eyebrows 01, Eyelashes 01 "Mesh assets shared under CC0"; Hair 02/03 "Mesh assets shared under CC-BY". Sizes not listed.
- Contents [M]: hm08 base mesh about 13.4k body vertices, mouth cavity in the base, separate eyes (low/high poly) with iris textures in several colours, teeth sets, tongue, eyebrow and eyelash cards, 1K to 2K skins. Fewer loops around lids and lips than ICT; advantage: whole body in one topology.
- Anny https://github.com/naver/anny [V]: "The code of Anny ... is licensed under the Apache License, Version 2.0"; "MakeHuman assets adapted from MPFB2 that are licensed under the CC0 1.0 Universal License"; warning: its optional "smplx" topology "can be downloaded for non-commercial use only": do not fetch that file.

### 1.3 Blender Human Base Meshes
- https://www.blender.org/download/demo-files/ (asset bundles; blender.org returned 403 / Cloudflare to curl and to the fetcher, so not read directly). Search summary: "Human Base Meshes v1.4.1, 49 MB, CC0", updated 2025-01-20 [S]. CG Channel article read [V] https://www.cgchannel.com/2023/06/download-blender-studios-free-human-base-meshes : 17 meshes, "closed volumes with clean quad topology", "come with UV maps", realistic and stylised figures, heads, jaws, eyeballs, hands, feet; "The Human Base Meshes bundle is available free under a Creative Commons CC0 licence." Use: jaw/teeth and eyeball as parts, realistic head as an alternative template (no mouth bag/lash meshes as far as known [M]).

### 1.4 FLAME
- https://flame.is.tue.mpg.de/modellicense.html [V]. Open licence (CC BY 4.0) "applies ONLY to the FLAME 2023 Open model; all other models are covered by the non-commercial license above"; grants "the right to share and adapt the model for any purpose, including commercial use" (plus: no pornographic use, no fake/defamatory content). Others: "for the sole purpose of performing non-commercial scientific research ... Any other use, in particular any use for commercial, pornographic, military, or surveillance, purposes is prohibited." Download needs an account.
- Contents [M]: 5,023 v, two eyeball spheres, no mouth bag, teeth or tongue, single-sheet lids. Verdict: FLAME 2023 Open is legally fine but gives less than ICT.

### 1.5 Research models: flagged, not usable
- Basel Face Model 2019 https://faces.dmi.unibas.ch/bfm/bfm2019.html [V]: "NON-COMMERCIAL USE: The license granted is for internal, non-commercial research, evaluation or testing purposes only. Any use of the DATA or its contents to manufacture or sell products or technologies ..." (BFM 2017 has the same agreement [S]).
- FaceScape https://github.com/zhuhao-nju/facescape [V README]: "The datasets are only released for non-commercial research use."
- Universal Head Model https://github.com/steliosploumpis/Universal_Head_3DMM [V README]: "freely available for research and education purposes ... 1. The models are used for non-commercial research and education purposes only. 2. You agree not copy, sell, trade, or exploit the model for any commercial purposes." Signed agreement by academic staff required.
- FaceWarehouse (kunzhou.net): terms not found; distributed on request to researchers. Treat as NO.

### 1.6 Scans
- Lee Perry-Smith "Infinite" head [V] https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/LeePerrySmith/LeePerrySmith_License.txt : "Infinite, 3D Head Scan by Lee Perry-Smith is licensed under a Creative Commons Attribution 3.0 Unported License. Based on a work at www.triplegangers.com. Permissions beyond the scope of this license may be available at http://www.ir-ltd.net/ Please remember: Do what you want with the files, but always mention where you got them from..."
  Files at https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf/LeePerrySmith [V, sizes from GitHub API]: LeePerrySmith.glb 405 KB (decimated mesh), Map-COL.jpg 148 KB (colour), Map-SPEC.jpg 682 KB (specular), Infinite-Level_02_Disp_NoSmoothUV-4096.jpg 752 KB (4096 px displacement, 8-bit JPEG), Infinite-Level_02_Tangent_SmoothUV.jpg 147 KB (tangent normal). Higher quality copy (OBJ, lambertian.jpg, 16-bit bump.png converted from the original .tif) is in the McGuire Computer Graphics Archive, https://casual-effects.com/data/ [S; the entry itself could not be read, the page is script-built]. The original 2010 release (ir-ltd.net) was a ZBrush-level scan with displacement .tif and colour map; the original page is reported offline [S].
  It is a living bald male, eyes closed: no eyeballs, mouth interior or teeth. Use: pore and fine-wrinkle displacement/normal source and a shading test head. Credit line required.
- 3D Scan Store (Ten24) free head / multi-expression base mesh [V] https://www.3dscanstore.com/blog/multi-expression-basemesh : "may be used for any private or non commercial project under the terms of the "Personal single user license". If you wish to use it for a commercial project or application please contact us". NO.
- Triplegangers free samples https://www.triplegangers.com : licence text not found. NO until read.
- Digital Emily 2 (Wikihuman / USC ICT) [S, awn.com]: free "only for non-commercial use". NO.
- Sketchfab CC0 / CC BY heads: search found no CC0 or CC BY retopologised male head with eyes and teeth; scans of living people also raise a likeness question. Not recommended.

### 1.7 Commercial character systems
- MetaHuman [V secondary, https://digitalproduction.com/2025/06/05/metahumans-graduate-ready-for-unity-godot-and-the-fab-cash-register/]: "The toolkit now obeys the standard Unreal Engine EULA"; characters count as "non-engine products" and can ship in Unity or Godot; "no 5 % revenue cut applies when you export characters to other engines"; "bigger studios need an $1,850 per-seat annual licence" above 1 M USD; "feeding MetaHumans back into training data is off-limits". The EULA itself (metahuman.com/license, login wall) was not read. Proprietary EULA, not PD/CC/MIT: outside our rule; LEGAL REVIEW if the owner ever wants it. A fictional MetaHuman face would also replace the real man's face, which is against the idea of the product.
- Reallusion Character Creator [S]: paid, proprietary; forum/EULA texts say exports may be used in products but not resold as assets. Outside the rule.
- Ready Player Me (Wolf3D) [S]: avatars made on the website under a Creative Commons non-commercial licence, commercial use for registered partners only; one source reports the platform closed 2026-01-31; docs.readyplayer.me does not resolve today [V]. NO.

## 2. Fitting a template to the scanned head (Python)

### 2.1 Landmarks
- One head only: a hand-picked landmark file (30 to 70 points, clicked once in Blender or MeshLab, stored as JSON) is the most reliable route and costs about an hour. The template side exists already (ICT's 68 Multi-PIE indices). Detectors are only a convenience. [M]
- Internal anatomy gives exact landmarks that the swollen surface cannot [M]: eyeball centres and radii (eye labels / dark globe in the photographs), dental arch and incisor edges from CT (enamel threshold), nasion, nasal aperture, external acoustic meatus, mandible angle from the skull label. Use them to place eyeballs, teeth and jaw, and as soft constraints for the lids and lips.
- MediaPipe Face Landmarker (478 points): repository Apache-2.0 [V, GitHub API]; Face Mesh V2 model card "LICENSED UNDER Apache License, Version 2.0" [S]. Trained on photographs of living faces. On an untextured grey render of a closed-eye, swollen face: the detector usually finds a frontal face, contour/nose points are fair, eyelid and inner-lip points are unreliable [M; NOT TESTED today]. If used: render frontal and two 30 degree views with the per-vertex skin colour and soft lighting, unproject the 2D points by depth buffer, average across views, then check by eye.
- Deep-MVLM https://github.com/RasmusRPaulsen/Deep-MVLM [V]: "Deep-MVLM is released under the MIT license"; "A tool for accurately placing 3D landmarks on 3D facial scans"; render modes "geometry", "depth", "geometry+depth" recommended for surfaces with no texture; 73 landmarks (DTU3D) or 84 (BU-3DFE); needs VTK and PyTorch. Built for exactly this case; weights were trained on research datasets, but we use only its output offline and ship nothing of it.
- dlib 68-point predictor: the stock model file was trained on iBUG 300-W, which excludes commercial use [M]: avoid.

### 2.2 Libraries (offline tools; none is shipped in the app)
| Library | Use | Licence |
|---|---|---|
| trimesh | I/O, `registration.procrustes`, `registration.icp`, `registration.nricp_amberg`, `registration.nricp_sumner`, `smoothing.filter_taubin`, ray queries | MIT [V] |
| Open3D | rigid ICP, `deform_as_rigid_as_possible`, Taubin, `t.geometry.RaycastingScene` | MIT [V] |
| pycpd | Coherent Point Drift (rigid, affine, deformable) for coarse alignment | MIT [V, API] |
| PyTorch3D | gradient fitting with chamfer + Laplacian + normal-consistency + edge losses | BSD [V] |
| charlienash/nricp (MATLAB), rafcy/nonrigid_icp (Python) | reference optimal-step N-ICP (Amberg 2007) | MIT [V API] / MIT stated in README [S] |
| libigl (`igl`) | ARAP, harmonic/biharmonic deformation, cotangent Laplacian | MPL-2.0 core [M]; GitHub API labels the repo GPL-3.0 because of optional modules [V] |
| scipy | `RBFInterpolator` for warping interior parts | BSD [M] |
| Blender `bpy` | shrinkwrap modifier, multires, normal/displacement bake | GPL, tool only (output not affected) |
| Wrap / Wrap4D (R3DS, now Faceform) | the industry standard for this job | commercial, paid: not needed |

### 2.3 Recipe
1. Template pose: load ICT neutral; add eyeBlink_L/R at weight 1 and mouthClose so that lids are closed and lips together like the cadaver. Keep the vertex ranges / material groups.
2. Scan preparation: crop head and neck; fill holes; light Taubin smoothing for the wrapping target only (raw scan is kept for step 6).
3. Rigid + uniform scale: `trimesh.registration.procrustes` on landmark pairs, then rigid ICP on the face area.
4. Skin wrap: `trimesh.registration.nricp_amberg(template_skin, scan, source_landmarks=..., target_positions=..., steps=[[stiffness, landmark_w, normal_w, iterations], ...], distance_threshold=..., )` with stiffness going down in 6 to 8 stages (for example 50, 20, 8, 3, 1, 0.5), landmark weight going down, normal-compatibility rejection (45 to 60 degrees) and a distance threshold of 5 to 10 mm. Only skin sub-meshes are sources. Excluded from correspondence (regularised only): lid margins and everything behind them, inner lip loops, nostril interiors, ear canal, neck border.
5. Interior parts are not wrapped; they follow: eyeballs rigidly to the measured globe centres and diameter; eye sockets, lacrimal fluid, eye blend, eye occlusion and lashes by an RBF/biharmonic warp driven by the face displacement, then snapped to the lid margin loops; teeth and gums by rigid + anisotropic scale to the CT dental arch (or replaced by the real CT tooth surface); tongue and mouth bag by the same RBF warp, followed by an intersection check.
6. Detail transfer (what studios do after wrapping): subdivide the wrapped head 2 to 3 levels (about 0.3 mm on the face), cast a ray from each vertex along +/- normal onto the RAW scan (`open3d.t.geometry.RaycastingScene`), clamp to +/- 3 mm, store the signed distance as a 16-bit displacement map in the template UVs, derive the tangent normal map from it (or bake both in Blender: multires "bake displacement" + selected-to-active normal bake). Ship low-poly + normal map; keep displacement for close-ups / tessellation.
7. Colour: project the cryosection per-vertex colours into the same UVs (closest surface point), 4K head albedo; region masks (lips, lids, ears, scalp) as a second texture.
8. Acceptance checks (pytest): mean and 95th percentile distance scan to wrapped surface on the face (target < 0.3 mm after displacement, report larger areas), no flipped faces, no self-intersection between lids and eyeballs, lid and lip loops closed, teeth inside the mouth bag.

### 2.4 What goes wrong
- Ears: thin folded sheets and concavities; closest-point matches jump between front and back of the helix, and the 1 mm scan has fused the folds. Use 6 to 8 landmarks per ear, high stiffness there, the normal test, and accept the template's ear form scaled to the scan (no detail projection on the ear).
- Closed eyes: the scan has no slit, so the lid loops slide. Pin the lid line with landmarks (both canthi + 3 points along the lash line, visible in the photographs as the lash colour). Frozen lids are swollen; put the globe where the internal data says, not where the surface suggests, and let the lids drape over it.
- Lips: pressed lips are a single crease; if the inner lip loops take part in correspondence the mouth bag folds through the face. Take the vermilion border from colour, not geometry.
- Nostrils: shallow pits in the scan; mask the template's nostril interior.
- Neck border and hairline: seam to the body skin; snap the template border loop to a cut loop on the body mesh and blend displacement over about 2 cm; scalp hair roots must be re-sampled on the new surface.
- Stiffness schedule too fast: sheared or folded triangles (cheeks, under the chin); finish with a Laplacian-regularised pass.
- The table-flattened occiput and the swelling are real shape and will be reproduced; decide deliberately whether to keep them.

## 3. Keeping our own mesh and only repairing it
- Eyelid slit: draw the lid line canthus to canthus, split the mesh along it, extrude both edges 1.5 to 2 mm inward as lid margins, build the inner lid (conjunctiva) as an offset shell of the globe (radius + 0.3 mm) up to the fornix (about 10 mm above the upper margin, 6 to 8 mm below the lower). Possible in code, but on an irregular marching-cubes mesh there are no edge loops, so the pinch deformation and the scalpel will look ragged. [M]
- Eyeball dimensions: globe about 24.2 mm transverse x 23.7 mm sagittal x 22.0 to 24.8 mm axial [S, review]; corneal diameter about 12 mm horizontal, 11 mm vertical (white-to-white 11.95 +/- 0.39 mm) [S]; anterior corneal radius 7.80 mm (7.00 to 8.65) [S]; anterior chamber depth about 3.0 to 3.7 mm [S]. From memory [M]: scleral radius about 12 mm, so the cornea stands about 2.5 mm proud; iris about 12 mm; pupil 2 to 4 mm in life, mid-dilated 4 to 6 mm after death; limbus transition 0.5 to 1 mm; palpebral fissure about 28 to 30 mm wide, 9 to 11 mm high when open; interpupillary distance about 63 mm.
- Mouth interior: bag from the lip line to the oropharynx; real teeth from the CT (enamel is the brightest tissue); tongue from segmentation if available, otherwise template tongue.
- Sharper ears and lips: re-extract those regions from the photographs at full 0.33 mm in-plane resolution; slice spacing stays 1 mm, so folds that run along the body axis stay coarse. Colour edges (vermilion border, lid margin) can sharpen the look through albedo and normal map.
- Denoising while keeping folds: Taubin lambda/mu smoothing removes slice staircase without shrinkage (`trimesh.smoothing.filter_taubin`, Open3D `filter_smooth_taubin`); edge-preserving: bilateral mesh denoising (Fleishman 2003), bilateral normal filtering (Zheng 2011), guided normal filtering; implementations in pymeshlab (GPL, tool only) and libigl. A 1 mm scan holds nothing real below about 2 mm, so "wrinkles" here means nasolabial fold, lid crease, philtrum.
- Pore detail: tileable micro normal (features 0.1 to 0.2 mm, tile every 1 to 2 cm) blended as detail normal, with region masks (strong on nose and cheeks, separate tiles for lips and lids) and a cavity term in specular. Standard in every AAA skin shader. [M]
- Recommendation: the HYBRID route of section 2 (template topology, scan shape and colour). Reasons: (1) pinch-open lids, scalpel cuts and peelable layers need clean loops, UVs and a stable vertex order; (2) lids, eyeballs, tear line, mouth bag, gums, tongue, teeth and lashes come as fitted, separate meshes; (3) the face stays the real man's because shape detail and colour are projected from the scan; (4) all parts are MIT / CC0 / CC BY; (5) UV maps remove the 1 mm vertex limit. Pure repair is the fallback for regions where the template cannot be made to fit.

## 4. Face detail at game quality
- Budget of a current AAA hero head [M]: about 20k to 40k vertices at LOD0; forms larger than about 2 mm in geometry, everything finer in maps. Maps: albedo 4K (8K source), tangent normal 4K, detail normal tile 512 to 1K, roughness/specular 2K to 4K, cavity/AO 2K, thickness/scatter 1K to 2K, 16-bit displacement 4K for close-ups. MetaHuman delivers 2K/4K/8K textures; its animated wrinkle maps default to 1K normal and 512 colour deltas [S, Epic docs summary]. A cadaver has one expression: wrinkle-map blending is unnecessary.
- Eyes [M]: sclera+iris mesh with a clear cornea bulge (or one mesh with cornea refraction and iris parallax in the shader), limbus darkening, sclera veins and subsurface; "eye occlusion" mesh (soft dark contact shadow under the lids); "lacrimal fluid / tear line" mesh (wet meniscus with a sharp highlight on the lid margin); caruncle; lashes as alpha cards in games (ICT ships them) or strands (we already have strand hair: 150 to 250 per upper lid, 6 to 12 mm; 75 to 100 lower, 4 to 8 mm). Unity's Digital Human package shows the tearline and occlusion technique, but it is HDRP and under the Unity Companion License [V]; for URP re-implement in HLSL/Shader Graph.
- Teeth and tongue [M]: teeth with slight subsurface and translucent incisal edge, darker toward the gum, AO from the lips; tongue with papillae detail normal and high gloss. Behind nearly closed lips they are mostly dark, so cost is small.
- Ears [M]: transmission through thin cartilage (thickness map). Weak in a cadaver (no blood glow).
- Lips [M]: vertical crease normal detail, vermilion colour border, wet line on the inner mucosa. After death: dry, matte, pale.
- Free detail assets:
  - Lee Perry-Smith displacement 4096, tangent normal, specular (CC BY 3.0) [V], section 1.6.
  - Sketchfab "Human Materials 1 (CC0)" by britdawgmasterfunk [V] https://sketchfab.com/3d-models/human-materials-1-cc0-be48a7526b304914b7c9f45c289b2ecf : four seamless 2K skin materials (colour, AO, roughness, normal, displacement); description "CC0 free to use however you want, no attribution needed", licence field "Creative Commons Attribution" (CC BY 4.0): both allowed; credit to be safe. Pore quality not inspected.
  - MakeHuman eyes (iris textures), teeth, tongue, eyelashes, eyebrows: CC0 [V]; eye pack mirrored at https://opengameart.org/content/makehuman-system-assets-eyes (CC0) [S].
  - ICT-FaceKit teeth, gums, tongue, eyeballs, lashes, tear line, occlusion meshes: MIT [V].
  - Blender Human Base Meshes eyeball and jaw: CC0 [V secondary].
  - Our own data (NLM Visible Human, public domain [M]): real iris and lip colour, real teeth from CT.
  - Not usable: texturing.xyz, 3D Scan Store, CGAxis (paid or non-commercial); AI texture sites saying only "free for commercial use" without a redistribution licence.
  - No verified CC0 photographic iris texture set was found beyond MakeHuman's; an iris can also be generated procedurally (radial fibres + collarette + limbus ring).

## 5. A dead face that is realistic but not gruesome
- Changes after death [S forensic lecture notes; M]: pallor within 15 to 30 minutes (lips, ears and nail beds lose red; skin waxy grey-yellow); lividity only in dependent parts (for a supine body the back of head and neck, not the face); loss of muscle tone, so the jaw drops and the mouth opens slightly unless supported, then rigor starts in lids and jaw at 1 to 2 hours; lids commonly rest half open; cornea turns hazy within hours; eye pressure falls to zero in 4 to 8 hours, so the globe softens and sinks; pupils fixed, mid-dilated; exposed sclera dries to a brown band (tache noire, 6 to 12 hours); lips and nose tip dry and darken; soft tissue sags toward the table (cheeks fall back, nose looks sharper).
- Prepared teaching donors [M]: eyes closed, mouth closed or slightly parted, firm grey-tan skin, head often shaved. The Visible Human Male was frozen unembalmed.
- Recommended look [M]: eyes closed with relaxed lids and a slight hollow, lips parted 0 to 2 mm, even pallor with desaturated lips, no tache noire, no fluids, no skin slip, no expression. When a lid is pinched open: dull, slightly hazy cornea, mid-dilated pupil, pale conjunctiva, no tear film sparkle. Neutral wording in the UI.
- Commercial tables [S]: Anatomage says its bodies are "digitized from real human cadavers", from "non-chemically treated frozen cadavers", with "photorealistic detail down to 0.2 mm"; a separate high-resolution female head from Ajou University exists in Table EDU 11. The face shown is the frozen section-photo surface (eyes closed, no modelled mouth interior or separate lids) [M, from product images, not verified]. Sectra-type tables show CT/MR volume renderings of clinical cases (uncoloured skin surface) [M]. No source found for any table offering lid interaction or a game-quality face.

## 6. Could not verify
- blender.org demo-files page and the bundle zip (403 Cloudflare): version, 49 MB size and CC0 come from search and CG Channel, not from blender.org; exact contents (mouth bag? teeth separate?) unread.
- McGuire archive entry for the Lee Perry-Smith head (page built by script): triangle count, map resolution and zip size of the full version not read; the original ir-ltd.net release page is reported offline.
- MediaPipe (and Deep-MVLM) on our untextured closed-eye head: not run; behaviour stated from experience only.
- MetaHuman / Unreal EULA text, Reallusion EULA, Ready Player Me terms: only secondary sources or search summaries.
- FaceWarehouse and Triplegangers free-sample licence texts: not found.
- FLAME 2023 Open contents (5,023 v, no mouth interior) and MakeHuman base mesh counts: from memory.
- libigl licence (MPL-2.0 core) from memory; GitHub API reports GPL-3.0 for the repository.
- Iris diameter, palpebral fissure size, pupil size after death, AAA budgets, eye-shading components: from memory.
- What Anatomage/Sectra tables show for the face in detail: product-level statements only.
