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
│   │   └── main.py              optional FastAPI service
│   ├── tools/
│   │   ├── inspect_series.py    what is in a folder, recommended spacing
│   │   ├── dicom_converter_app.py   converter window (tkinter) = the pipeline used by everything
│   │   ├── convert_cli.py       same pipeline from the command line (used by the viewer's "Open scan")
│   │   ├── segment_organs.py    TotalSegmentator -> labels.raw / labels.json (runs in .venv-seg)
│   │   └── make_test_series.py  synthetic phantom with orientation markers (tests)
│   ├── tests/                   pytest: pipeline, orientation, NRRD reorientation
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

## Viewer components (`unity/Assets/DicomViewer/Scripts`)

| Component | Role |
|---|---|
| `VolumeLoader` | load volume + labels, transfer-function presets (Body, Lungs, Organs), quality switching, CPU picking (`RaycastVisible`), organ visibility |
| `VolumeOrbitController` | rotate / move / zoom with mouse and touch (pinch, two-finger pan, twist) |
| `ClippingPlaneController` | one cutting plane (UVR `CrossSectionPlane`) |
| `KnifeTool`, `CutTool` | knife (half-space) and dig (sphere) cuts; UVR cross sections, max 8 in total |
| `OrganPanel` | organ list, tap-to-isolate, hover names |
| `MarkerCheck` | bones-only view |
| `SliceViewPanel` | 2D slice view next to the 3D (shrinks the main camera viewport) |
| `ViewerToolbar` | buttons for every function, Open scan + conversion, help, background |
| `ViewerUi`, `FpsOverlay` | shared UI helpers (pointer-over-UI, scale, tap detection); FPS |

UI is IMGUI (`OnGUI`) for now; the spec moves it to UI Toolkit (step 6). Cutting moves from cross
sections to the mask engine (step 2).
