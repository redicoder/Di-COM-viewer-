# Licences

Everything the product uses or ships, with its terms. Add an entry **before** adding a dataset, model,
atlas or library. "Verify" = the terms were not yet confirmed at the source; the item must not ship until
the row says "confirmed".

## Code and libraries

| Item | Where | Terms | Status |
|---|---|---|---|
| UnityVolumeRendering 1.8.0 | `unity/Packages/com.mlavik1.easyvolumerenderer` (embedded fork) | MIT (`LICENSE.md` kept) | confirmed |
| openDicom (bundled inside UnityVolumeRendering, `ThirdParty/openDicom`) | **LGPL** | **unused by us** (the backend reads DICOM); remove from the fork before a commercial build, or confirm LGPL compliance |
| Nifti.NET (bundled inside UnityVolumeRendering, `ThirdParty/Nifti.NET`) | verify | unused by us; remove with openDicom |
| Unity 6 editor / player, URP | build tool and runtime | Unity terms; Unity Personal only below Unity's revenue/funding threshold | check plan before sale |
| Unity Burst, Collections, Mathematics packages | skin physics job (`TissueSheetJob`) | Unity Companion License (ship with Unity) | confirmed |
| Unity glTFast (`com.unity.cloud.gltfast` 6.20.0) | imports the modelled body's GLB files (`unity/Assets/Models/`) | Apache-2.0 (Unity package) | confirmed |
| The modelled body's GLB files (`unity/Assets/Models/*.glb`) | made by the product owner: reference pictures generated with Gemini, meshed by an image-to-3D service (Tripo) | the service's terms for generated output; **record the plan and its commercial-use terms here before sale** | verify |
| numpy, scipy | backend | BSD-3-Clause | confirmed |
| pydicom | backend | MIT | confirmed |
| fastapi / uvicorn / httpx | backend (optional HTTP service, tests) | MIT / BSD-3 / BSD-3 | confirmed |
| pylibjpeg, pylibjpeg-openjpeg | backend (compressed DICOM) | MIT | verify |
| **pylibjpeg-libjpeg** | backend (JPEG lossless DICOM) | **GPL-3.0** (to verify) | **do not ship** in a commercial build until resolved (replace or confirm) |
| scikit-image | backend/.venv-seg (skin mesh extraction, `tools/extract_skin_mesh.py`) | BSD-3-Clause | confirmed |
| fast-simplification | backend/.venv-seg (mesh decimation) | MIT | confirmed |
| tifffile | backend/.venv (reads the SIO label TIFFs) | BSD-3-Clause | confirmed |
| pyfqmr | backend/.venv-seg (mesh decimation by region with kept borders, `tools/anatomy_model`; a build tool, not shipped) | MIT | confirmed |
| PyTorch | backend/.venv-seg | BSD-3-Clause | verify |
| nnU-Net v2 | backend/.venv-seg (used by TotalSegmentator) | Apache-2.0 | verify |
| nibabel, SimpleITK, dipy | backend/.venv-seg | MIT / Apache-2.0 / BSD-3 | verify |
| Weasis (separate desktop app, not bundled) | used next to the viewer for 2D reading | EPL-2.0 / Apache-2.0 | external |

## AI models

| Item | Terms | Status |
|---|---|---|
| TotalSegmentator code | Apache-2.0 | used |
| TotalSegmentator `total` task weights | CC BY 4.0 per spec — **verify**; cite in About | used |
| TotalSegmentator head and neck tasks: `head_muscles`, `headneck_muscles`, `head_glands_cavities`, `headneck_bones_vessels`, `craniofacial_structures`, `oculomotor_muscles` (run on the Visible Human Male's frozen CT by `tools/anatomy_model/head_layers.py`; their labels become the named head and neck structures of the anatomy model, and say where the teeth, the tongue, the mandible and the skull are for its mouth, `mouth.py`) | open tasks: not in the tool's own list of licensed tasks (`commercial_models` in `map_to_binary.py`, read 2026-11-13); README: "Openly available for any usage (Apache-2.0 license)". Cite Wasserthal et al., Radiology: AI 2023, doi:10.1148/ryai.230024 | used; **read the weights' licence file before sale** (the README sentence is what was read) |
| TotalSegmentator task `teeth` (every tooth by FDI number) | the tool's README lists it as open (Apache-2.0) and "based on the ToothFairy3 dataset"; the ToothFairy3 page (https://ditto.ing.unimore.it/toothfairy3/, read 2026-11-16) carries "CC BY-NC-SA" (Creative Commons Attribution-NonCommercial-ShareAlike 4.0) | **NOT used** (non-commercial, share-alike training data). Tried once on 2026-11-16 and stopped before any label was written; its weights and partial output were deleted. The teeth are named by our own method (`tools/anatomy_model/teeth.py`) |
| TotalSegmentator `tissue_types`, `appendicular_bones`, `face`, `heartchambers_highres` and other restricted tasks | free non-commercial / paid commercial | **not used** until a licence is bought and recorded here |

TotalSegmentator usage statistics are disabled (`%USERPROFILE%\.totalsegmentator\config.json`,
`send_usage_stats: false`).

## Data

| Item | Terms | Status |
|---|---|---|
| NLM Visible Human Project: male colour cryosection photographs (the photographed body, `tools/prepare_photo_volume.py`), male frozen CT, female fresh CT | "National Library of Medicine Terms and Conditions; May 21, 2019" (licence listed by NCI Imaging Data Commons, collection `nlm_visible_human_project`, DOI 10.5281/zenodo.12690049). Free use; credit line **"Courtesy of the U.S. National Library of Medicine"** on the About screen; no suggestion that NLM endorses the product; state that the data may not reflect the most current or accurate data available from NLM. `tools/build_body.py` writes all of this into each export's `provenance.json` | confirmed; demo body |
| Segmented Internal Organs of the Visible Human Male (SIO), VOXEL-MAN group, University Medical Center Hamburg-Eppendorf: Höhne K.H., Pflesser B., Pommert A., Riemer M., Schiemann T., Schubert R., Tiede U., Schumacher U. — a 1 mm voxel model of the torso with 202 labelled structures, made from the NLM photographs (`tools/import_sio_labels.py` registers it onto the photographed body; `labels.raw` / `labels.json` in the export) | **CC BY 4.0**, Zenodo, DOI 10.5281/zenodo.15882018 (v1 10.5281/zenodo.15882019). Credit the authors, title, source and licence (the lab's toolbar and the About screen); cite the DOI; mark changes (resampled onto the photographs' grid, objects re-indexed) | confirmed |
| BoneHub "Visible-Human-3d-Models" (Alavi S.H., Asseln M., Hugging Face 2026): 142 individually labelled bones of the Visible Human Male on his CT (`backend/data/bonehub`, not committed; `tools/anatomy_model/bonehub.py` meshes and fits them: the skeleton layer of the anatomy model) | **CC BY 4.0**, doi:10.57967/hf/10464; based on Andreassen T.E. et al., "Three Dimensional Lower Extremity Musculoskeletal Geometry of the Visible Human Female and Male", Sci Data 10, 34 (2023), doi:10.1038/s41597-022-01905-2 (CC BY 4.0). Credit both and say changes were made (meshed, smoothed, decimated, moved into the body's frame); the Model Lab shows the line | confirmed (licence read at the source by the research of 2026-11-12) |
| University of Denver, Center for Orthopaedic Biomechanics, "3D Models of the Visible Human Male": `Final 3D STL Models-stl.zip` (139,572,345 bytes) from https://digitalcommons.du.edu/visiblehuman/2 , doi:10.56902/COB.vh.2022.0 (`backend/data/du_visible_human`, not committed). Used by `tools/anatomy_model/leg_muscles.py`: 70 muscles of the hips and legs, 16 joint cartilages and 8 knee ligaments, placed in the body and decimated (in the model `anatomy.glb`, which is not committed); its bones are used only to place them | the page (copy kept 2026-11-16, `backend/data/du_visible_human/male_page_2026-11-16.html`) and the set's own README: "This work is licensed under a Creative Commons Attribution 4.0 International License"; "free to use under the Creative Commons Attribution 4.0 license ... we ask that you cite the original papers". Credit (shown in the Model Lab's credits): Andreassen T.E., Hume D.R., Hamilton L.D., Walker K.E., Higinbotham S.E., Shelburne K.B., Three Dimensional Lower Extremity Musculoskeletal Geometry of the Visible Human Female and Male, Sci Data 10, 34 (2023), doi:10.1038/s41597-022-01905-2; and Andreassen et al., arXiv:2209.06948. Changes were made (placed, decimated) | confirmed (CC BY 4.0, same body); used |
| BodyParts3D 4.0 (The Database Center for Life Science, Japan), the LSDB Archive's copy: `isa_BP3D_4.0_obj_99.zip` and `isa_element_parts.txt` from https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/ (`backend/data/bodyparts3d`, not committed; a generic adult male, not the Visible Human). Used by `tools/anatomy_model/skull_bones.py` only to say which part of HIS skull is which bone: its 21 skull bones are fitted to BoneHub's cranium and each triangle of his skull takes the nearest atlas bone's name. No vertex of the atlas is in the model or the repository; the fitted points are kept in `backend/out/photo_body/model/skull_bones.npz` (not committed) | Licence page https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html , "Last updated : 2025/02/27", read and a copy kept 2026-11-13 (`backend/data/bodyparts3d/lic_2026-11-13.html`): "The license for this database is specified in the Creative Commons Attribution 4.0 International." Credit as the licensor words it: "BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International" (shown in the Model Lab's credits). **But** the comment at the head of every `.obj` inside the archive (files of 2013) still reads "Creative Commons Attribution-Share Alike 2.1 Japan" and points to that same licence page | used for the outlines of the skull's bones; **flagged: confirm with DBCLS in writing before sale** that the archive's files are under CC BY 4.0 as its licence page says (the stale header says Share-Alike, which this product does not use). Until then the step can be left out: without `model/skull_bones.npz` the skull is built whole, as before. Never take BodyParts3D from the old site, Anatomography or Z-Anatomy (Share-Alike) |
| The muscles of expression of the anatomy model (`tools/anatomy_model/face_muscles.py`): generated by our own code on his skull and skin; where each arises and ends and how big it is are anatomical facts as the textbooks give them (collected in `docs/research/head_anatomy_data.md` 5.5; no figure, mesh or table of another work is copied) | our own work | used; say in the product that these muscles are drawn, not scanned |
| The face's vessels and nerves of the anatomy model (`tools/anatomy_model/face_vessels.py`): generated by our own code along their textbook courses between landmarks of his own skull, jaw and face (the courses collected in `docs/research/head_anatomy_data.md` 5.8; no figure, mesh or table of another work is copied) | our own work | used; say in the product that these are drawn, not scanned |
| The anatomy model (`unity/Assets/Models/anatomy.glb`, built by `backend/tools/build_model_meshes.py`, not committed): the surfaces of the labelled structures of the photographed body as meshes, shapes only, no photographs | derived from the SIO labels (**CC BY 4.0**, credit and DOI as the row above; changes: resampled, meshed, smoothed, decimated) and the NLM Visible Human data (credit line as above); the frozen CT for bone outside the torso | confirmed; the credits must show wherever the model does |
| TCIA collections used in development (C4KC-KiTS, LIDC-IDRI, FDG-PET-CT-Lesions) | per collection page (CC BY 3.0/4.0 typical) — verify | development/testing only, not shipped |
| `5 RibWB Standard.nrrd` | unknown origin | development fixture only, never committed or shipped |
| `anonymized_20261019` | origin to be confirmed | development only, never committed or shipped |
| BodyParts3D / Z-Anatomy atlas | CC BY-SA (share-alike) | not used; legal review first |

Scans and derived volumes are git-ignored (`backend/data/`, `backend/out/`, `*.nrrd`, `*.dcm`, `*.raw`).
