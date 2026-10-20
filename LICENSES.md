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
| numpy, scipy | backend | BSD-3-Clause | confirmed |
| pydicom | backend | MIT | confirmed |
| fastapi / uvicorn / httpx | backend (optional HTTP service, tests) | MIT / BSD-3 / BSD-3 | confirmed |
| pylibjpeg, pylibjpeg-openjpeg | backend (compressed DICOM) | MIT | verify |
| **pylibjpeg-libjpeg** | backend (JPEG lossless DICOM) | **GPL-3.0** (to verify) | **do not ship** in a commercial build until resolved (replace or confirm) |
| PyTorch | backend/.venv-seg | BSD-3-Clause | verify |
| nnU-Net v2 | backend/.venv-seg (used by TotalSegmentator) | Apache-2.0 | verify |
| nibabel, SimpleITK, dipy | backend/.venv-seg | MIT / Apache-2.0 / BSD-3 | verify |
| Weasis (separate desktop app, not bundled) | used next to the viewer for 2D reading | EPL-2.0 / Apache-2.0 | external |

## AI models

| Item | Terms | Status |
|---|---|---|
| TotalSegmentator code | Apache-2.0 | used |
| TotalSegmentator `total` task weights | CC BY 4.0 per spec — **verify**; cite in About | used |
| TotalSegmentator `tissue_types`, `appendicular_bones`, `face`, `heartchambers_highres` and other restricted tasks | free non-commercial / paid commercial | **not used** until a licence is bought and recorded here |

TotalSegmentator usage statistics are disabled (`%USERPROFILE%\.totalsegmentator\config.json`,
`send_usage_stats: false`).

## Data

| Item | Terms | Status |
|---|---|---|
| NLM Visible Human Project CT | public domain since 2019, acknowledge the U.S. National Library of Medicine (per spec) — **verify wording** | planned demo body |
| TCIA collections used in development (C4KC-KiTS, LIDC-IDRI, FDG-PET-CT-Lesions) | per collection page (CC BY 3.0/4.0 typical) — verify | development/testing only, not shipped |
| `5 RibWB Standard.nrrd` | unknown origin | development fixture only, never committed or shipped |
| `anonymized_20261019` | origin to be confirmed | development only, never committed or shipped |
| BodyParts3D / Z-Anatomy atlas | CC BY-SA (share-alike) | not used; legal review first |

Scans and derived volumes are git-ignored (`backend/data/`, `backend/out/`, `*.nrrd`, `*.dcm`, `*.raw`).
