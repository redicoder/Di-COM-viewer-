# Architecture (current state)

Updated whenever the structure changes. Target design: `DISSECTION_TABLE_SPEC.md`; deviations: `SPEC_NOTES.md`.

```
<repo>/
├── backend/                     Python: scan -> volume for the viewer
│   ├── app/                     library
│   │   ├── dicom_loader.py      DICOM folder -> Volume (sorted by geometry, HU, LPS axes)
│   │   ├── nrrd_loader.py       .nrrd/.nhdr -> Volume (streamed, any axis order/space reoriented)
│   │   ├── volume.py            isotropic resampling; pack into Unity texture order
│   │   ├── body.py              body mask, crop to patient, scanner-table removal
│   │   ├── lungs.py             lungs-only export
│   │   ├── export.py            CLI + write_export(): volume.raw / volume.json
│   │   ├── label_table.py       stable label ids, layers, colours (dissection bodies)
│   │   ├── tissue.py            skin / fat / muscle / bone / soft-tissue classes from HU
│   │   ├── segmentation.py      grids in mm, resampling between grids, label smoothing
│   │   └── main.py              optional FastAPI service
│   ├── anatomy/                 anatomy_names.json: la / en / it names per label (teachers may edit)
│   ├── tools/
│   │   ├── inspect_series.py    what is in a folder, recommended spacing
│   │   ├── dicom_converter_app.py   converter window (tkinter) = the pipeline used by everything
│   │   ├── convert_cli.py       same pipeline from the command line (used by the viewer's "Open scan")
│   │   ├── segment_organs.py    TotalSegmentator -> labels.raw / labels.json (runs in .venv-seg)
│   │   ├── build_body.py        dissection body: whole body + regions with layered labels
│   │   ├── prepare_visible_human.py   stitch the Visible Human CT parts into one NRRD
│   │   ├── download_visible_human.py  Visible Human CT series / colour photo slices from NCI IDC (.venv-seg)
│   │   ├── prepare_photo_volume.py    colour cryosection photos -> RGBA "photographed body" volume
│   │   └── make_test_series.py  synthetic phantom with orientation markers (tests)
│   ├── tests/                   pytest: pipeline, orientation, NRRD, body pipeline, label-id snapshot
│   ├── .venv/  .venv-seg/       Python environments (not in git)
│   ├── data/                    source scans (not in git)
│   └── out/                     exported volumes + out/latest.txt (not in git)
├── unity/                       Unity 6 URP project
│   ├── Assets/DicomViewer/Scripts   viewer components (all on the `volumeroot` object)
│   ├── Assets/DicomViewer/Editor    menu "DICOM Viewer": Set Up Scene, Build Windows App
│   ├── Assets/Scenes/DicomViewer.unity
│   └── Packages/com.mlavik1.easyvolumerenderer   embedded UnityVolumeRendering 1.8.0
├── build/                       built Windows app (not in git); finds ../backend/out/latest.txt
└── docs/
```

## Data flow

1. A scan (DICOM zip/folder or NRRD) goes through `dicom_converter_app.convert()` (window, CLI or the
   viewer's Open scan): load -> crop to patient -> resample (voxel budget per quality level) -> remove
   table -> `out/<name>/volume.raw + volume.json` -> optional TotalSegmentator `labels.raw + labels.json`
   -> optional lungs-only copy -> `out/latest.txt` lists the result folders.
2. The viewer's `VolumeLoader` reads `latest.txt` (found relative to the project or the build), builds a
   UnityVolumeRendering `VolumeDataset` with identity rotation (texture x = patient left, y = superior,
   z = posterior), adds organ labels as a segmentation, applies the transfer-function preset.

## Dissection bodies (`tools/build_body.py`)

1. `prepare_visible_human.py` turns the downloaded CT parts into one NRRD: slices ordered by the Visible
   Human slice number (`SliceLocation`), every slice resampled by its own pixel size and position onto one
   0.94 mm grid (the head was reconstructed with a smaller field of view), parts shifted to line up at the joins.
2. `build_body.py` finds the body, runs TotalSegmentator `total` **once** on a 1.5 mm whole-body grid
   (cached in `out/<body>/_cache/seg`), then builds each export: whole body at 2 mm and head, thorax,
   abdomen, pelvis at about 1 mm (≤ 40 M voxels). Region heights come from landmarks (C4, lungs and
   clavicles, L5 to liver/spleen, hip bones); width and depth from the body inside them.
3. Per export: CT resampled onto the export grid (all grids are boxes in mm in the scan's frame, so they line
   up); the patient = connected pieces overlapping the whole-body mask; TotalSegmentator labels cleaned of
   stray pieces (< 0.5 % of a structure), mapped by position and smoothed; tissue classes from HU (`app/tissue.py`) fill the rest; ids from
   `app/label_table.py`, which never renumbers (`tests/label_ids.json` is the snapshot).
4. `labels.json` = `layers` (peel order, names, colour) + `labels` (id, key, layer, `name` in English for the
   current viewer, `names` {la, en, it}, colour, opacity, info_key). `provenance.json` = dataset, licence,
   credit, source hash, grid, thresholds, tool versions, git commit.

## Photographed body (`tools/prepare_photo_volume.py`)

The Visible Human male was frozen, cut into 1 mm slices and every slice photographed (2048 × 1216 RGB, 0.33 mm
pixels, body in blue gelatin). Each photo's `SliceLocation` is the same slice number as his frozen CT. The tool
flips the rows to the CT's layout (front to back), crops to the body, averages down (factor 2 = 0.66 mm), keeps
tissue (redder than blue) as the body's 3D pieces (every piece at least 2 % of the largest, connectivity judged across the
joints between the specimen's blocks; a piece that does not change from photo to photo is the label card beside him,
not tissue) with holes filled, repairs the sliver and blank photos at the block joints from their neighbours (a sliver lacks a rim of the body that both its neighbours have), matches each block's exposure to the next across its joint on the skin (12 cm either side, then an exact ramp at the joint), leaves gelatin-filled air spaces empty, gives the
outermost voxel of tissue the colour beneath it (it was skin averaged with the gelatin) and bleeds tissue colour into
the gelatin, equalises each photo's exposure to its neighbours' (on all its tissue, over nine photos), makes the outer surface a 1.5 mm smoothing of the
filled outline (the inside stays sharp), and writes `photo.raw` (RGBA, x = patient left, rows front to back, slices bottom
to top) + `photo.json`; `--web` writes JPEG colour + PNG alpha atlases for the browser sample. The renderer finds
the first tissue sample along each ray: on a cut face it shows the photo itself; on the skin it shades the
surface and reads the colour 0.7 mm below it, blended over neighbouring slices. `--every 2 --factor 4` exports the
whole body at 1.3 x 2 mm (`out/photo_body`, 436 x 282 x 939 voxels, 460 MB RGBA; `LargeVolumeTests` checks a volume
that size reaches the GPU whole); the head at 0.66 mm is `out/photo_head`. Three tools work on an export afterwards: `extract_skin_mesh.py` (the skin as a mesh), `transfer_eyes.py` (the head's eyes and its box into the whole body) `import_sio_labels.py` (the SIO organ labels, registered slice by slice; unlabelled tissue inside the labelled torso takes the nearest label, so a layer taken away leaves no specks) and `classify_tissue.py` (tissue classes for the rest of him and for the head export: a table indexed by smoothed colour, depth under the skin and local unevenness, filled from the labelled torso's twenty million voxels and scored on held-out slices; the classes go in as five more objects, "skin (by colour)" to "organ (by colour)", so the layers work on the head and legs too) and `import_ct_bone.py` (bone from his frozen CT, over 250 HU with marrow filled, each slice placed on its photograph by outline as the SIO was: "bone (from CT)" wherever the SIO has no name, because at 1.3 mm the photographs show bone as marrow and the colour table misses most of it).

## Anatomy Lab (`unity/Assets/DicomViewer/Scripts/AnatomyLab`)

The app opens on a start screen (`AppMode`): **Scan viewer** (everything below) or **Anatomy lab**. Each mode is its
own object and only the chosen one is active; the lab's objects are built in code (`AnatomyLab.CreateRig`), so the
scene is unchanged. `-mode lab` / `-mode viewer` on the command line skips the menu.

| Component | Role |
|---|---|
| `PhotoBody` | loads `backend/out/<body>/body.raw + body.json` (`prepare_photo_volume.py --unity`; `photo_head` or `photo_body`, the toolbar's **Body** button swaps them) into an sRGB RGBA 3D texture, an eyelid map and an empty-space map (one cell per 8^3 voxels); CPU picking that respects cuts. Its transform is the body's (metres, x left, y up, z back); the child cube is scaled to the body, so cube-local = VolumeSpace's convention |
| `Shaders/AnatomyLab/PhotoBody.shader` + `LabSkin.hlsl` (+ `LabBody.hlsl`) | first-hit ray march with empty-space skipping; cut walls show the photo itself, skin takes its colour from 0.7 mm under the surface (the epidermis, blended over neighbouring slices) and its normal over 1.2 mm (cut walls keep the fine one); the eyes open geometrically (an almond fissure whose lids slide into the orbit, continuous with the skin round it, no mask edge), the real eyeballs can be swapped for modelled ones; blood stains, soft occlusion in folds; writes SV_Depth so meshes and drops mix in. `LabSkin.hlsl` is the lighting shared with lifted skin: key light with subsurface wrap and a blood-warm terminator, fill and rim set against the camera, hemisphere ambient, GGX specular over a procedural micro-relief, wet where cut or bloody, a soft shoulder on highlights, and a mild colour grade (`LabSkinGrade`) that lifts the blue bath's cast off the frozen skin |
| `MaskVolume` (shared with the viewer) | the dissection mask on the photo grid: undo / redo / heal |
| `LabScalpel` | drag to cut: a thin V incision (1.8 mm mask capsules, sinking to 5 mm over the first 3 mm) per stroke, one undo step; behind the blade the skin's tension draws the edges apart into a lens-shaped wound (`TissueWarp.Gape`, rebuilt on undo / redo / heal); tells BloodSim how red the tissue is |
| `LabPull` | Pull tool: pinch beside a scalpel cut and the skin is taken in hand (`TissueSheets`); pinch lifted or loose tissue to take hold of it again; pinch intact skin to stretch it, and it springs back (`TissueWarp` grabs) |
| `TissueWarp` + `Resources/TissueWarp.compute` (by Claude Fable; `Gape` kernel added) | live grabs evaluated in the shader, and a baked backward-displacement field (incision gapes) |
| `TissueSheet` + `TissueSheetJob` (Burst) | the physics of skin taken in hand: a 64 x 64 two-layer particle sheet (skin surface, fat's base) over the body, XPBD distance constraints from the tissues' moduli (dermis ~1 MPa, fat ~3 kPa), shape matching so freed tissue bends like skin rather than folding like cloth, an anisotropic junction to the fascia (slides a few mm, tears when lifted 1.5 mm or slid 3 mm, and the fat tears sheared 4.5 mm), real gravity, contacts with the body's wound bed and the tray with Coulomb friction. Cut edges carry no force, so one cut lets its edge lift, a U cut makes a flap that hangs about its base, a closed cut frees a piece that falls. Units mm, g, s |
| `TissueSheets` | owns up to four sheets: makes one when the hand pinches beside a cut, draws each as a mesh coloured from the photos (`TissueSheet.shader`: skin on top, fat beneath, wet cut walls, blood carried along), hides the body's own copy of that tissue (`_SheetMaps` in `PhotoBody.shader`), the steel tray under the neck, picking on lifted tissue, the scalpel cutting through it |
| `LabRoom` + `LabTable.shader` | the dissection room in body millimetres under the volume: the steel table (top, rim, legs) under the table plane and the floor 90 cm below; the table's shader marches the photo volume towards the light for the body's soft shadow and along the table's normal for the dark seam where he lies on it |
| `SkinMesh` + `LabSkinMesh.shader` + `LabBody.hlsl` | the skin as a mesh over the volume (`skin.mesh`, from `tools/extract_skin_mesh.py`: marching cubes on the skin-depth map, Taubin smoothing, decimation to 200-400k triangles): lit and shadowed like a game character. By default (`_SkinMode` 1, the toolbar's **Skin: clean**) it is one even skin tone over his real shape with the slow unevenness living skin has, a flush where the skin is thin, and briefs between the hip bones and the thighs (`AnatomyLab.Briefs`, from the labels); **Skin: photos** reads the colour from the photographs under the surface instead, graded to a living tone. It cuts itself away where the mask, a lifted sheet or the eyes' opening say so, and the volume beneath (told `_SkinByMesh`) draws only what is opened, lifted or deeper, so cutting still reveals the real tissue. `LabBody.hlsl` holds what the two shaders share. A mesh skin does not stretch (the Pull tool's stretch is off with it) |
| `LabRegion` | regions at full detail: where the whole body's export names a finer export inside it (`regions` in body.json, written by `tools/transfer_eyes.py`: the head at 0.66 mm), that export is loaded as a body of its own with its skin mesh, at its place inside the whole body; the whole body's volume and mesh leave the box to it (`_RegionOn/_RegionMin/_RegionMax`), and the tools look away from it (to dissect the face, show the head on its own) |
| `SkinBake` | what a game bakes into a character's skin, taken from the body itself at load (Burst job, under a second): per vertex of the skin mesh, ambient occlusion (rays over the surface stopped by his own tissue in the skin-depth grid), thickness (light through ears, nostrils, the webs of the fingers) and curvature; and the pre-integrated scattering lookup (d'Eon & Luebke's skin profile integrated over curvature, Penner 2011) that `LabSkin.hlsl` uses for the skin mesh's diffuse. The skin mesh casts and receives the main light's soft shadow (the arm on the belly); the volume's cut tissue receives it too |
| `BodyLabels` | names for his voxels: `labels.raw` (an object index per voxel, his own grid) and `labels.json` (the objects), from `tools/import_sio_labels.py`, which registers the Segmented Internal Organs of the Visible Human Male (SIO, CC BY 4.0: 202 structures of the torso at 1 mm, made from the same photographs) onto the export slice by slice. The lab names what is under the cursor with any tool (`AnatomyLab.UnderCursor`, shown by the toolbar) and the body shader lifts that structure's voxels where a cut shows them (`_LabelTex`, `_HighlightIndex`). Each object has a **layer** (skin, fat, muscle, bone, organ; from its name, in the importer): the toolbar's layer buttons take a layer away over the labelled part of him (`_LayersOn`, `_LabelHideTex`: the volume and the skin mesh skip those voxels, the tools treat them as gone), so the muscles, then the organs, show in place in his own photographs. The **Take out** tool takes a single named structure out of the body (a tap on it; `BodyLabels.HideObject`), **Put back** returns them all; the table's shadow (`LabTable.shader`) ignores what is hidden too |
| `OrganPiece` + `FieldMesh` + `LabOrganPiece.shader` | a structure taken out as a **piece**: its voxels (one label index) blurred and contoured by surface nets (`FieldMesh`, the glove's method) into a mesh in the body's metres, each vertex keeping its volume coordinate so the shader colours the piece from the photographs where it came from, lit as wet tissue with shadows; large objects on a coarser grid (under a second). The Take out tool puts it in the hand (follows the pointer on a plane facing the camera, lifted clear) and, let go, it glides to the next spot on the table beside him or the tray beside a head and settles lying flat. Put back destroys the pieces |
| `SkinDepthGrid` | the skin-depth map in native memory for the physics job (PhotoBody keeps it beside its texture) |
| `LabInstruments` + `LabInstrument.shader` + `HandMesh` | the instruments, built in code at real size: a No. 3 handle with a No. 10 blade at the cursor while cutting (belly pressed into the wound, rolled to show its side) and a gloved hand pinching what Pull holds (open and hovering under a mouse; `HandMesh` is one smooth signed-distance surface, fingers, thumb, palm and wrist in a soft union, meshed with surface nets on a 1.5 mm grid); soft shadows and contact darkening on the body (capsules in `PhotoBody.shader`); the cursor hides while one stands in for it |
| `BloodSim` + `Resources/BloodSim.compute` | GPU drops that fill the wound, spill at leak points and run along the skin by real gravity (turn the head, the blood follows), drying into a half-resolution 3D stain texture. `showBlood` off = dry dissection (hidden, paused, cuts do not bleed) |
| `BloodFluidFeature` (URP renderer feature, by Claude Fable) | draws `BloodDrops.Buffer` as liquid: sphere-imposter depth, narrow-range smoothing, thickness, Beer-Lambert shading; `BloodDrop.shader` is the simple fallback |
| `AnatomyLab` | the coordinator: body placement (a head stands facing the viewer on a tray with the world's gravity; a whole body lies on his back on the dissection table, head to the left, and down is towards the table however he is turned), orbit target, living eyes (`LivingEye`, by Claude Fable: sclera, refracting iris under a clear cornea, pupil and gaze; they look at the viewer when open), eyelid tool, blood on / off, heal |
| `LabToolbar` | Turn / Scalpel / Pull / Eyelids, open / close eyes, undo / redo / heal, living or real eyes, blood on / off, front view, credit; wraps onto a second row on touch screens |
| `Editor/LabSnapshot.cs` | renders the lab to `build/snapshots/*.png` without Play mode (batch-mode check of the shader) |
| `ModelLab` + `ModelOrbit` + `Editor/ModelSnapshot.cs` | the **modelled body**: GLB models in `Assets/Models/` (the body, then the skeleton, the muscles and each organ, generated from reference pictures by an image-to-3D tool; imported by `com.unity.cloud.gltfast`) in a plain world frame (up +y, the table top y = 0, he lies along x with his head at -x, face up). `ModelLab.Lay` scales a model to real height and lays it on its back; `ModelLab.Room` builds the steel table and the floor as lit meshes (URP Lit) that receive his shadow; the generator's material is corrected (it exports skin as full metal). `ModelOrbit` walks the camera round the table (drag, pinch or wheel, two fingers or right-drag to slide; the room stays put). `ModelBody` holds the layers (skin `body.glb`, `muscles.glb`, `skeleton.glb`, outermost first) laid at the same place; the generated models do not nest exactly, so only the outermost layer that is on is drawn, and buttons at the top of the screen pick the layer to see. `ModelSnapshot` builds the scene, saves it as `Assets/Scenes/ModelLab.unity` and renders `build/snapshots/model_*.png` |

Parts written by Claude Fable from the prompts in `docs/prompts/` (living eye, liquid blood, tissue pulling) plug in
through fixed interfaces: `LivingEye.Create(...)`, `BloodDrops`, `WarpUVW(uvw)`.

## Viewer components (`unity/Assets/DicomViewer/Scripts`)

Scripts compile into the `DicomViewer.Runtime` assembly; the editor menu into `DicomViewer.Editor`; tests into
`DicomViewer.Tests.EditMode` (`Assets/DicomViewer/Tests/EditMode`, run from Window > General > Test Runner).

| Component | Role |
|---|---|
| `VolumeLoader` | load volume + labels, transfer-function presets (Body, Lungs, Organs), quality switching, CPU picking (`RaycastVisible`, respects the mask), organ visibility, selection (ghost / isolate), organ statistics |
| `VolumeOrbitController` | rotate / move / zoom with mouse and touch (pinch, two-finger pan, twist); rotation pivot and Focus animation |
| `MaskVolume` | **dissection engine**: op history (undo / redo / reset / lessons), GPU mask via `MaskGpu`, CPU copy via `MaskModel` on a background thread |
| `MaskGpu` / `MaskModel` / `VolumeSpace` | GPU mask texture + `Resources/MaskOps.compute`; CPU mask + op replay; world / texture / mm conversions |
| `ScalpelTool`, `CutTool` (Dig), `KnifeTool` | cutting tools on the mask: trench strokes, hold-to-deepen holes, half-space knife |
| `ClippingPlaneController` | one non-destructive cutting plane (UVR `CrossSectionPlane`) |
| `InspectPanel` | tap a structure: select, ghost/isolate the rest, card with volume / size / mean HU, Focus |
| `OrganPanel` | organ list (show/hide, select), hover names |
| `MarkerCheck` | bones-only view |
| `SliceViewPanel` | 2D slice view next to the 3D (shrinks the main camera viewport) |
| `ViewerToolbar` | buttons for every function, tool selection, undo/redo/reset, tool sliders, Open scan + conversion, help, background |
| `ViewerUi`, `FpsOverlay` | shared UI state and helpers (armed tool, pointer-over-UI, scale, tap detection); FPS |

## Dissection mask

`_MaskTex` (R8, same grid as the CT, 1 = tissue) is bound to the forked volume shader (see the package's
`MODIFICATIONS.md`). Every edit is a `MaskOp` in millimetres: capsules (scalpel, dig; a stroke is one op) or a
half-space (knife). The main thread applies each op on the GPU immediately; the CPU copy follows on a background
lane with cloned ops. Undo/redo/reset replay the op list from a full body on both sides; both use the same voxel
ranges (`MaskModel.CapsuleRange`), and `MaskGpuTests` checks they agree.

UI is IMGUI (`OnGUI`) for now; the spec moves it to UI Toolkit (step 6).
