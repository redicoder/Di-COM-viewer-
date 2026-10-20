# Dissection Table — engineering specification for the coding agent

Target: a touch-screen anatomy dissection table for Italian universities, built on a real whole-body CT,
with the Sony ELF-SR2 glasses-free 3D display as a second screen once the hardware arrives.
**Intended use: education only. Not for diagnosis, surgical planning or any clinical decision.**

This document is the brief. Read it fully before changing code. Where it says MUST, do not deviate
without raising it first.

> Agreed deviations and review notes: see `docs/SPEC_NOTES.md`.

---

## 0. Ground rules for the agent

1. **UnityVolumeRendering 1.8.0 ("Easy Volume Renderer") is the renderer.** Its API is small and has
   changed between versions. Never invent methods: read the source under the package (or under
   `Assets/ThirdParty/UnityVolumeRendering` once forked, see §2.1) before calling anything.
   Known API this project relies on: `VolumeDataset` (fields `data`, `dimX/Y/Z`, `scale` in metres,
   `rotation`), `VolumeObjectFactory.CreateObjectAsync`, `VolumeRenderedObject.SetTransferFunction /
   AddSegmentation / SetSegmentationRenderMode / SetLightingEnabled / SetSamplingRateMultiplier`,
   `TransferFunction` with `TFColourControlPoint` / `TFAlphaControlPoint`, `CrossSectionPlane`,
   `CutoutSphere`, `ShaderFactory`.
2. **Axis convention is fixed and tested**: texture x = patient left (+), y = superior (+),
   z = posterior (+). The backend writes voxels in this order; `VolumeDataset.rotation` is identity.
   Never use `RawDatasetImporter` (it applies a 90° X rotation for z-up raw files).
3. **Transfer-function positions are normalised by the dataset's actual min/max**:
   `t = (HU - value_min) / (value_max - value_min)`. Always go through a `T(hu)` helper; never
   hard-code normalised positions.
4. **No keyboard-only features.** Every function must be reachable by touch. Keyboard shortcuts are
   optional extras.
5. **One source of truth.** The git repository is the only copy of the code. No parallel copies of
   scripts in other folders.
6. **Tests are not optional** (§9). A change to geometry, axis mapping, mask maths or picking ships
   with a test.
7. **Licences are part of the build** (§7). Do not add a dataset, model or atlas without adding it to
   `LICENSES.md` with its terms.
8. Work in small PR-sized steps, each leaving the app runnable. Update `docs/ARCHITECTURE.md` when
   structure changes.

---

## 1. What the student must be able to do (acceptance scenario)

On a touch screen, with no keyboard:

1. Open the demo body. It appears whole, skin on, lit, correct left/right (liver on the viewer's left
   when the body faces the viewer). FPS counter ≥ 55.
2. Rotate with one finger, pan/zoom/twist with two. Double-tap empty space to reset the view.
3. Drag the **Peel** slider: skin → subcutaneous fat → muscle → skeleton → organs disappear in order,
   smoothly. Any layer can also be toggled individually from the **Layers** panel.
4. Pick **Scalpel**, draw a stroke on the body: tissue along the stroke is removed to a chosen depth.
   Draw several strokes; no "too many cuts" message, ever.
5. Pick **Dig**, touch and hold on the chest: a hole deepens under the finger until the heart is visible.
6. Pick **Plane**: a clipping plane with its own slider, axial/coronal/sagittal, flip side.
7. Tap the heart: it highlights and a card shows *Cor / Heart / Cuore* plus a short description.
   Tap again or tap empty space: card closes.
8. **Undo** the last three operations. **Redo** one.
9. **Reset body**: everything back to step 1 in under one second.
10. Save the current dissection as a lesson; load it on another PC.
11. The 2D slice panel still works and follows the plane position.
12. (Later, hardware-dependent) The same body renders on the Sony display in 3D while the touch
    monitor shows controls + a 2D preview that is used for all touch interaction.

---

## 2. Architecture

### 2.1 Fork UnityVolumeRendering into the repository
Move the package from the git-URL dependency to `Assets/ThirdParty/UnityVolumeRendering/`
(same version, 1.8.0). Reason: the mask volume (§2.2) and the realistic shading (§2.4) require
shader changes. Keep the fork minimal and document every change in
`Assets/ThirdParty/UnityVolumeRendering/MODIFICATIONS.md`. Keep its MIT licence file.

### 2.2 Mask volume — the dissection engine (MUST, build first)
Replace cross-section objects as the cutting mechanism. UVR caps cross sections at 8; a dissection
needs unlimited cuts, undo and reset.

**Data**
- `_MaskTex`: a 3D `RenderTexture`, `GraphicsFormat.R8_UNorm`, `enableRandomWrite = true`,
  same grid as `_DataTex`. Value 1 = tissue present, 0 = removed. Trilinear sampling.
- Memory: 1 byte/voxel (33 MB at 320³, 61 MB for a 2 mm whole body).

**Shader change** (in the forked DVR shader, both Built-in and URP variants if both are kept):
```hlsl
sampler3D _MaskTex;
float _MaskEnabled;
// inside the ray-march loop, after the sample position `pos` (0..1 texture space) is known:
float keep = _MaskEnabled > 0.5 ? tex3Dlod(_MaskTex, float4(pos, 0)).r : 1.0;
if (keep < 0.01) continue;      // removed: skip sampling, lighting and compositing
...
src.a *= keep;                  // trilinear edge = smooth cut surface
```
Removed voxels must also be ignored by the picking pass (§2.5) and by any 2D slice view that is meant
to show the dissected state (the slice panel may offer a toggle "show removed tissue").

**Edits** — one compute shader `MaskOps.compute` with kernels:
- `Fill(value)` — whole volume (reset = Fill(1)).
- `CutSphere(centreMm, radiusMm, value)`.
- `CutCapsule(aMm, bMm, radiusMm, value)` — a scalpel stroke is a polyline; each segment is a capsule.
- `CutHalfSpace(normalMm, dMm, value)` — knife through the whole depth (replaces the current knife).
- `RestoreLabel(labelId)` — optional, puts one organ back.
All distances are computed in **millimetres** using `spacing_mm` per axis, never in voxel indices,
because voxels are anisotropic before resampling. Voxel centre (mm) = `(id + 0.5) * spacing`.
Dispatch only over the axis-aligned bounding box of the affected region (pass a group offset), so a
scalpel stroke costs microseconds, not a full-volume pass.

**World → texture mapping** (C#): `local = volumeContainer.InverseTransformPoint(world)`
(container cube spans −0.5..0.5) → `tex = local + 0.5` → `mm = tex * size_mm`. One helper class
`VolumeSpace` owns these conversions and is unit-tested (§9).

**Undo / redo**: keep an ordered `List<MaskOp>` (a plain struct per edit). Undo pops to a redo stack
and **replays all remaining ops from Fill(1)** on the GPU. Replay of a few hundred ops is
sub-millisecond; this avoids storing mask snapshots. The op list is also the serialised dissection
state (§2.7).

### 2.3 Tissue layers (label volume + layer map)
The segmentation overlay already loads `labels.raw` / `labels.json`. Extend it:

- Every label belongs to exactly one **Layer**: `Skin`, `Fat`, `Muscle`, `Skeleton`, `Organs`,
  `Vessels`, `Nervous` (brain, spinal cord). Layers have a **peel order** (outside → inside) and a
  **base colour**. Schema in `labels.json`:
  ```json
  { "layers": [ {"id":"skin","order":0,"name":{"la":"Cutis","en":"Skin","it":"Cute"},"color":[0.87,0.67,0.55]}, ... ],
    "labels": [ {"id":12,"key":"liver","layer":"organs","name":{"la":"Hepar","en":"Liver","it":"Fegato"},
                 "color":[0.55,0.22,0.16],"opacity":1.0,"visible":true,"info_key":"liver"} ] }
  ```
- **Peel slider** `p ∈ [0, layerCount]`: layer with order `k` has visibility
  `clamp(p - k, 0, 1)` inverted — i.e. fully visible while `p < k`, fading out as `p` passes it.
  This gives a continuous peel instead of pops. Individual toggles override.
- Label visibility is applied as a per-label alpha multiplier in the segmentation lookup texture
  (UVR already has per-label alpha; expose and drive it). Hidden ≠ removed: hidden layers come back
  with the slider; removed voxels (mask) come back only with Undo/Reset.

Where the layers come from is the pipeline's job (§3). The Unity side only consumes the two files.

### 2.4 Realistic look
Target: a body that reads as a body, not coloured blobs.
- The **label** decides colour (albedo) and visibility; the **HU value** decides opacity curve and
  fine shading within a layer (bone trabeculae, liver texture).
  `colour = labelAlbedo * shade(gradientLighting) ; alpha = labelAlpha * tfAlpha(hu)`.
- Lighting on (gradient-based, already in UVR). Add a cheap darkening by gradient magnitude at
  cut surfaces so the inside of a cut looks "wet/dense", not flat.
- Starter palette (sRGB): skin 0.87/0.67/0.55 · fat 0.95/0.85/0.45 · muscle 0.60/0.20/0.18 ·
  bone 0.93/0.90/0.82 · liver 0.55/0.22/0.16 · lungs 0.90/0.60/0.60 · kidneys 0.50/0.15/0.15 ·
  heart 0.70/0.20/0.20 · arteries 0.85/0.10/0.10 · veins 0.20/0.25/0.70 · brain 0.85/0.75/0.70.
  Palette lives in `labels.json`, not in code.
- Two quality presets: **Interactive** (lower sampling rate while a finger is down or the camera
  moves) and **Idle** (full quality, cubic interpolation). Switch automatically.

### 2.5 Picking (tap → structure) — GPU
Replace CPU ray marching for picking with a GPU pick pass:
- A shader variant (keyword `VOLUME_PICK`) that marches the same ray as the DVR shader, respects the
  mask and layer visibility, accumulates alpha, and at the first sample where accumulated alpha
  exceeds `pickThreshold` (default 0.35) writes `(labelId, depth)` and stops.
- On tap only: render the volume with that variant into a small `RenderTexture` (e.g. 64×64 around
  the tap, via a pick camera with an off-centre projection) and read back with `AsyncGPUReadback`.
- Result: `PickResult { labelId, worldPoint }`. `labelId = 0` = unlabelled tissue (report the layer
  from HU instead: fat/muscle/bone), `-1` = empty space.
Keep the old CPU `RaycastVisible` behind an interface `IVolumePicker` until the GPU path is proven.

### 2.6 Dig tool rework
Dig becomes repeated `CutSphere` ops under the finger: on touch-begin, pick the surface point; every
frame while held, push the centre inward along the view ray by `digSpeed` mm/s and apply
`CutSphere`. Radius and depth rate in the tool's panel (sliders, not Ctrl/Shift+wheel).
Each stroke of the finger = one undo step (coalesce the per-frame spheres into one `MaskOp` group).

### 2.7 Lessons: save / load dissection state
`lesson.json`: body id, mask op list, layer visibility, peel value, camera/body transform, open
info card, teacher notes (markdown), language. Deterministic replay. Store under
`%USERPROFILE%/Documents/DissectionTable/Lessons/`. Loading a lesson for a different body id must
refuse with a clear message.

### 2.8 Two-screen design (prepare now, hardware later)
- **Display 0 — touch monitor**: UI + a 2D "preview camera" of the body. All touch picking and tool
  geometry uses the preview camera. This is the camera the current code calls `Camera.main`.
- **Display 1 — Sony ELF-SR2**: body only, no UI. Until the hardware arrives this is a plain second
  `Camera` with `targetDisplay = 1` (activated with `Display.displays[1].Activate()` when present).
  When the SR plugin is installed, this camera is replaced by Sony's `SRDisplayManager` prefab; the
  preview camera keeps the same pose as the SR view so touch and 3D agree.
- Consequence for today's code: nothing may depend on being the only camera. Remove the
  `cam.rect` shrink in `SliceViewPanel`; the slice panel becomes a UI element. All OnGUI overlays
  are to be replaced by UI Toolkit on display 0 (§4).
- Quality budget on the SR display: two eye renders per frame at 4K. Expect to run the
  **Interactive** preset there until measured otherwise.

---

## 3. Data pipeline (Python, `backend/`)

### 3.1 Demo body
- **Primary: NLM Visible Human (male first)** — public domain since 2019, acknowledgement of the
  U.S. National Library of Medicine required. Download the CT (also available as DICOM from NCI
  Imaging Data Commons). Add the acknowledgement to the app's About screen.
- **Any other dataset only if its licence is in `LICENSES.md`.** The `RibWB.nrrd` of unknown origin
  is a development fixture only and must not ship in a build.
- Resolution plan for a whole body (CT ≈ 512×512×~1800 at ~1 mm = ~470 M voxels, does not fit one
  texture): export **whole body at 2 mm** (≈ 61 M voxels) plus **region exports at native/1 mm**
  (head, thorax, abdomen, pelvis, each ≤ 40 M voxels). The app lists them as "Whole body" and
  "Regions". A multi-resolution renderer is out of scope for now.

### 3.2 `build_body.py` (new, replaces ad-hoc steps)
Inputs: DICOM series folder or NRRD/NIfTI. Steps, each cached on disk:
1. Load + reorient to the project axis convention (reuse `dicom_loader.py`; add NRRD/NIfTI via
   `SimpleITK` or `nibabel`), resample to the requested isotropic spacing, optional ROI crop
   (`--roi x0,y0,z0,x1,y1,z1` in mm).
2. Run **TotalSegmentator `total`** (free, Apache 2.0 code / CC BY weights) → organ, bone and vessel
   labels. Do **not** call `tissue_types`, `appendicular_bones`, `face` or `heartchambers_highres`
   unless a commercial licence has been purchased and recorded in `LICENSES.md`.
3. **Tissue classes from HU** (no licensed model):
   - body mask: HU > −500, largest connected component, holes filled;
   - skin: body mask minus 3 mm erosion (shell);
   - fat: −190 ≤ HU ≤ −30 inside body, not lung, not labelled;
   - muscle: 30 ≤ HU ≤ 100 inside body, not labelled by step 2;
   - bone: HU > 200 inside body, not labelled;
   - other soft tissue: remainder.
4. Merge: step-2 labels win; tissue classes fill unlabelled voxels. Remap ids to a stable table
   (`backend/app/label_table.py`) so ids never change between exports. Assert < 255 labels (uint8).
5. Write `volume.raw/json`, `labels.raw/json` (with layers, names, colours from
   `backend/data/anatomy_names.json`), and `provenance.json` (source, licence, spacing, tool versions,
   git commit). Update `out/latest.txt`.
6. Tests: tissue classes on the phantom; label id stability; orientation markers (existing).

### 3.3 Names and info cards
`backend/data/anatomy_names.json`: TotalSegmentator label key → `{ "la": ..., "en": ..., "it": ... }`
using **Terminologia Anatomica** Latin. Start with the ~120 `total` labels plus the tissue classes.
`backend/data/anatomy_info.json`: `info_key` → short description per language (2–4 sentences),
editable by teachers without rebuilding (the app reads these JSON files at start-up).

---

## 4. Touch UI (Unity, display 0)

- **UI Toolkit** (UXML + USS), `PanelSettings` scale mode "Scale With Screen Size", reference
  1920×1080. Minimum touch target 56×56 px at reference scale; 12 px spacing.
- **Input System package** with `EnhancedTouch` for gestures; legacy `Input` removed from tools.
  Gesture rules: 1 finger = rotate (or tool action when a tool is armed), 2 fingers = pan / pinch /
  twist, tap = identify, double-tap on empty = reset view, long-press = context (info card without
  highlighting).
- Layout: left rail = tools (Rotate, Scalpel, Dig, Plane, Peel, Layers, Identify) with the active tool
  highlighted; bottom = contextual sliders for the active tool; right = Layers panel / info card;
  top-right = Undo, Redo, Reset body, Language, Lesson menu. The 2D slice view is a resizable panel.
- Every destructive action has Undo; Reset body asks "Reset the body?" with a 1-tap confirm.
- Languages: IT / EN / LA switch at runtime (Unity Localization package or the JSON tables above).
- Permanent footer line in small type: *Solo per uso didattico — non per uso diagnostico* /
  *For education only — not for diagnostic use*.

---

## 5. Performance targets

| Scenario | Volume | Target |
|---|---|---|
| Touch monitor, 1080p, lighting on, Idle preset | 320³ region | ≥ 60 FPS (RTX 2070) |
| Touch monitor, Interactive preset, while cutting | 2 mm whole body (~256×256×936) | ≥ 45 FPS |
| Sony ELF-SR2, two eyes, Interactive preset | 256³ equivalent | ≥ 60 FPS (measure, then decide) |
| Mask op (scalpel segment / dig sphere) | any | < 0.5 ms GPU |
| Pick | any | < 1 frame to readback (async) |
| Reset body | any | < 1 s |

GPU memory estimate per volume: data (RHalf) 2 B + labels 1 B + mask 1 B + gradient 4 B ≈ 8 B/voxel
→ ~0.5 GB for the 2 mm whole body. Fine on 8 GB.

---

## 6. Build order (one developer + agent; each step leaves the app working)

1. **Repo hygiene**: git, `.gitignore`, `CLAUDE.md` (§10), CI running `pytest`. Fork UVR into
   `Assets/ThirdParty`. Second-camera / display-0-1 split with a plain camera (§2.8).
2. **Mask engine** (§2.2): shader change, `MaskOps.compute`, `VolumeSpace`, undo/redo via replay,
   Reset. Port Scalpel (capsule strokes), Dig (§2.6) and Knife (half-space) onto it. Delete the
   cross-section-based tools. Tests.
3. **Pipeline** (§3.2): `build_body.py`, tissue classes, stable ids, names JSON. Visible Human
   downloaded, inspected, exported as whole body 2 mm + 4 regions.
4. **Layers + peel + realistic shading** (§2.3, §2.4). Palette in JSON.
5. **GPU picking + info cards + languages** (§2.5, §3.3).
6. **UI Toolkit port** (§4) replacing all OnGUI; slice panel as a UI element.
7. **Lessons save/load** (§2.7).
8. **Sony integration** when the display arrives: swap the display-1 camera for the SRDisplayManager
   prefab; measure FPS; tune presets. Nothing else should need to change.
9. Only after a university pilot is agreed: blood-flow and nerve-impulse illustrations (clearly
   labelled as illustrations), atlas layer, quiz mode.

---

## 7. Licences and compliance (`LICENSES.md`, kept current)

| Item | Terms | Status |
|---|---|---|
| UnityVolumeRendering 1.8.0 | MIT | forked; keep LICENSE |
| Visible Human Project CT | public domain, acknowledge NLM | demo body |
| TotalSegmentator code | Apache 2.0 | used (`total` task only) |
| TotalSegmentator `total` weights | CC BY 4.0 | cite in About |
| TotalSegmentator `tissue_types`, `appendicular_bones`, `face`, `heartchambers_highres` | non-commercial free / paid commercial | **not used** until purchased |
| BodyParts3D / Z-Anatomy atlas | CC BY-SA (share-alike) | not in core; legal review first |
| Any TCIA collection | per collection (CC BY 3.0/4.0 typical) | dev/testing only unless listed |

Regulatory: intended use is education. Do not add "surgical planning", "pre-operative" or
"diagnostic" language anywhere (UI, docs, marketing) — that changes the product's classification
under EU MDR. Data protection: no patient data from hospitals; only licensed/public bodies.

---

## 8. Known UVR 1.8.0 facts the agent must respect

- `VolumeDataset.data` is `float[]` (4 B/voxel CPU). The GPU texture is RHalf, normalised to
  min..max of the data.
- `VolumeDataset.scale` is in **metres** (mm / 1000). The container mesh is Unity's unit cube.
- `NormaliseScale` runs only if a PlayerPrefs flag is set; we set `localScale` ourselves.
- Texture3D max dimension 2048 per axis.
- Segmentation overlay: `AddSegmentation(dataset, labels)`, `SetSegmentationRenderMode(...)`.
- Cross sections share one limit of 8 objects — to be made irrelevant by the mask engine.
- URP shaders live under `Runtime/Shaders/URP`; the factory picks them by detecting the URP asset.

---

## 9. Tests

Python (`pytest`): orientation markers; tissue-class thresholds on a synthetic phantom; label-id
stability; `build_body.py` end-to-end on the phantom; `inspect_series.py` recommendations.
Unity EditMode: `VolumeSpace` world↔texture↔mm round trips, including non-uniform spacing and a
rotated/scaled body. Unity PlayMode: `CutSphere` on a 64³ mask → readback → voxel count within 2 %
of analytic volume; undo/redo replay equals direct state; GPU pick of a known labelled voxel returns
its id; peel slider ordering. A manual QA checklist for the acceptance scenario in §1.

---

## 10. `CLAUDE.md` content (put at repo root)

```
Project: Dissection Table (education-only anatomy app). Unity 6 URP + UnityVolumeRendering 1.8.0
(forked under Assets/ThirdParty) + Python/FastAPI backend.
Read docs/DISSECTION_TABLE_SPEC.md before any task. Do not invent UnityVolumeRendering API — read
the source. Axis convention: texture x = patient left, y = superior, z = posterior; never use
RawDatasetImporter. TF positions via T(hu) = (hu - min)/(max - min). Every function must work by touch.
Keep LICENSES.md current. Run pytest and Unity tests before declaring a task done. Never add
diagnostic/surgical-planning language.
```
