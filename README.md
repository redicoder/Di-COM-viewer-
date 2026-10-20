# Dissection Table

Touch-screen anatomy dissection table built on a real whole-body CT, for Italian universities.
**For education only — not for diagnostic use.** (*Solo per uso didattico — non per uso diagnostico.*)

- Spec: [docs/DISSECTION_TABLE_SPEC.md](docs/DISSECTION_TABLE_SPEC.md) · decisions: [docs/SPEC_NOTES.md](docs/SPEC_NOTES.md)
- Structure: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · licences: [LICENSES.md](LICENSES.md)

## Setup (Windows)

Python 3.10, Unity 6 (6000.6.4f1) with Windows build support, an NVIDIA GPU for the AI organ labels.

```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q

# AI organ labels (separate environment: PyTorch + TotalSegmentator)
py -3.10 -m venv .venv-seg
.\.venv-seg\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu126
.\.venv-seg\Scripts\python.exe -m pip install "dipy==1.11.0" --only-binary dipy
.\.venv-seg\Scripts\python.exe -m pip install TotalSegmentator
```

Unity Hub → Add project → `unity/`. Open `Assets/Scenes/DicomViewer.unity`.

## Use

- **Convert a scan**: `Convert DICOM for Unity.bat` (window), or in the viewer **Open scan…**, or
  `backend\.venv\Scripts\python.exe backend\tools\convert_cli.py <zip|folder|.nrrd> --quality standard --organs`.
  Output goes to `backend/out/<name>/`, and `backend/out/latest.txt` tells the viewer what to load.
- **Run the viewer**: Play in Unity, or the built app `build/DICOM 3D Viewer.exe`
  (Unity menu **DICOM Viewer → Build Windows App**).

Scans, exported volumes and labels are never committed (see `.gitignore`).
