# Spec notes: agreed deviations and open checks

Review of `DISSECTION_TABLE_SPEC.md` before implementation. Each item is either a decision (applied) or a
check that must be done before the related step is closed.

## Decisions

| Spec | Decision | Why |
|---|---|---|
| §2.1 fork UVR into `Assets/ThirdParty/` | Kept as an **embedded package** in `unity/Packages/com.mlavik1.easyvolumerenderer/`, git-URL dependency removed from the manifest, changes logged in its `MODIFICATIONS.md` | Same effect (code in the repo, editable), but assembly definitions and asset GUIDs stay identical to upstream |
| §2.2 shader snippet (`sampler3D`, `tex3Dlod`) | Written in the URP shader's own style: `Texture3D` + `SamplerState` + `SampleLevel` | The URP DVR shader declares textures that way; mixing styles does not compile cleanly |
| §2.5 GPU picking first | First a **CPU copy of the mask**, updated by the same `MaskOp` list, used by the existing CPU ray-march picker behind `IVolumePicker`; GPU pick pass later if profiling asks for it | Picking must see cuts from day one; the CPU path is simpler and testable, and runs only on tap |
| §2.6 dig coalescing | A dig stroke is stored as **one op** (path of centres + radius), not one op per frame | Keeps the replay list short for undo/redo and lessons |
| §3.1 Visible Human **male** first | The **female** is the primary demo body: her fresh-cadaver CT (IDC study "Normal") is 1 mm from head to toe. The male's 1 mm CT is the *frozen* one: freezing brings fat and muscle within ~25 HU of each other (fat ≈ −50, muscle ≈ −25), so the HU tissue classes (§3.2 step 3) cannot separate them; his fresh CT is 3–5 mm. The male stays buildable (`--dataset vhp-male-frozen`, with his own `--fat` / `--muscle` ranges) | The layers (skin, fat, muscle) need real tissue contrast |
| §1 / §3.1 what the student sees (product owner, 2026-10-20) | The app gets two modes: **Scan viewer** (DICOM/NRRD → 3D, as built) and **Anatomy lab**, a body that looks and behaves like a real cadaver. After a side-by-side sample (game-style mesh vs photographs), the owner chose the **photographed body**: the Visible Human **male**'s colour cryosection photos (0.33 mm pixels, one per 1 mm slice), stacked into an RGBA volume (`tools/prepare_photo_volume.py`). His frozen CT has the same slice numbering and state, so CT labels (names, picking, layers) map onto the photos slice by slice. Touch physics (pinch, flaps, eyelids), blood (labelled as a simulation; a cadaver does not bleed) and organ removal are built on top, step by step | Solid real tissue in real colour wherever it is cut; meshes are hollow and invented inside. This supersedes "female first" (next row) for the Anatomy lab |
| URP renderer (PC_Renderer) | **Screen Space Ambient Occlusion switched off** | It forces a depth-normals prepass that ray-marched volumes (the scan viewer's and the photographed body) are not part of, so `_CameraDepthTexture` missed the body and liquid blood showed through it; the body shader does its own fold shading. With it off URP copies the real depth after opaques |
| Hard, self-contained graphics parts | Written by **Claude Fable** from the prompts in `docs/prompts/` (living eye, liquid blood, tissue pulling), reviewed and integrated here; each plugs in through a fixed interface (`LivingEye.Create`, `BloodDrops`, `WarpUVW`) | Owner's choice; the interfaces keep the parts swappable |
| §3.1 whole body ≈ 61 M voxels | The female's body box at 2 mm is ≈ 31 M voxels; regions at 1 mm, budget 40 M each | Measured on the data |
| §3.2 step 1 NRRD/NIfTI via SimpleITK or nibabel | Our own streaming NRRD reader (`app/nrrd_loader.py`, tested against DICOM); NIfTI not yet | No extra dependency in the main environment |
| §3.2 step 2 per export | TotalSegmentator runs **once per body** on a 1.5 mm whole-body grid (its native resolution); every export maps those labels by position in mm | Exports agree with each other, regions get whole-body context, one GPU run instead of five |
| §3.2 step 3 "other soft tissue: remainder" | Gas inside the body (sinuses, mouth, bowel gas outside labelled bowel) stays 0 = empty; fat and muscle are judged on a 1 mm Gaussian-smoothed copy of the CT; "other soft tissue" belongs to the **muscle** layer | Gas must not render as solid; noise would otherwise speckle fat/muscle; soft tissue must peel away before the organs show |
| §2.3 / §3.3 `labels.json` `name` = {la, en, it} | `name` stays a plain English string (the current viewer reads it with JsonUtility) and the three languages are in `names`; labels also carry `key`. The viewer moves to `names` with the language switch (step 5) | Each step leaves the app working |
| §3.3 `backend/data/anatomy_names.json` | `backend/anatomy/anatomy_names.json` (and later `anatomy_info.json`) | `backend/data/` is git-ignored: it holds scans |
| §4 legacy `Input` removed | The **Input Manager stays enabled** (Active Input Handling = Both) even after the tools move to the Input System | Sony's SR Display plugin reads the legacy Input Manager |

## Checks before the related step is closed

1. ~~**Visible Human licence** (§3.1)~~: done. NLM Terms and Conditions (May 21, 2019), credit line and
   notices recorded in `LICENSES.md`; the CT comes as DICOM from NCI Imaging Data Commons.
2. **TotalSegmentator `total` weights licence** (§7): confirm the licence of the released weights (the
   spec says CC BY 4.0). Record the citation required in the About screen.
3. **Sony ELF-SR2 with a second display** (§2.8): confirm in Sony's documentation that the SR plugin can
   run while Unity also drives a normal monitor (Display 0). The plugin may expect the app full-screen
   on the SR display; if so the touch monitor needs another design (e.g. a second app or window).
4. **Performance targets** (§5) are goals to measure on the RTX 2070 Max-Q laptop, not guarantees;
   presets get tuned from measurements.
5. **Dev fixtures**: `5 RibWB Standard.nrrd` (unknown origin) and `anonymized_20261019` (origin to be
   confirmed) are development data only and are never committed or shipped. Scans are git-ignored.
