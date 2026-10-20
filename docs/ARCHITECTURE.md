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
