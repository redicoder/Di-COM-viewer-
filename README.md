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
- **Build the demo body** (Visible Human female, credit: *Courtesy of the U.S. National Library of Medicine*):
  download the CT parts from NCI Imaging Data Commons (see `backend/tools/prepare_visible_human.py`), then
  ```powershell
  .\.venv\Scripts\python.exe tools\prepare_visible_human.py data\vhp_female_normal data\visible_human_female.nrrd
  .\.venv\Scripts\python.exe tools\build_body.py data\visible_human_female.nrrd --dataset vhp-female
  ```
  This gives `out/visible_human_female/` with the whole body (2 mm) and head, thorax, abdomen and pelvis (~1 mm),
  each with layered labels (names in Latin, English and Italian). The viewer loads the whole body; **N** cycles
  through the regions.
- **Build the Anatomy Lab body** (Visible Human male, colour photographs; same credit):
  ```powershell
  .\.venv-seg\Scripts\python.exe tools\download_visible_human.py photos data\vhp_male_head_photos --first 1001 --last 1225
  .\.venv-seg\Scripts\python.exe tools\prepare_photo_volume.py data\vhp_male_head_photos out\photo_head --first 1001 --last 1225 --unity --eye-slice 1095
  ```
  The whole body (all 1,878 photos, ~14 GB) at 1.3 x 2 mm (460 MB of texture), for the lab's **Body: whole** button:
  ```powershell
  .\.venv-seg\Scripts\python.exe tools\download_visible_human.py photos data\vhp_male_photos --first 1001 --last 2878
  .\.venv-seg\Scripts\python.exe tools\prepare_photo_volume.py data\vhp_male_photos out\photo_body --first 1001 --last 2878 --factor 4 --every 2 --unity
  ```
  The skin as a mesh over each export (the lab draws it when present):
  ```powershell
  .\.venv-seg\Scripts\python.exe tools\extract_skin_mesh.py out\photo_head --triangles 200000
  .\.venv-seg\Scripts\python.exe tools\extract_skin_mesh.py out\photo_body --triangles 400000 --smooth 1.5
  # Organ labels for the whole body: the SIO (CC BY 4.0) from https://zenodo.org/records/15882019, unpacked
  # into data\sio\ (the zip's folder plus 'SIO Object Labels.xlsx' beside it); registered slice by slice
  .\.venv\Scripts\python.exe tools\import_sio_labels.py data\sio\VOXEL-MAN_segmented-internal-organs data\vhp_male_photos out\photo_body
  # Tissue classes (skin, fat, muscle, bone) for the rest of him and for the head export, learnt from the labelled torso's colours
  .\.venv\Scripts\python.exe tools\classify_tissue.py out\photo_body
  .\.venv\Scripts\python.exe tools\classify_tissue.py out\photo_head --from out\photo_body
  # Bone from his frozen CT (data\vhp_male_frozen, same slice numbers), registered slice by slice: the skull, the arm and leg bones
  .\.venv\Scripts\python.exe tools\import_ct_bone.py data\vhp_male_frozen out\photo_body
  .\.venv\Scripts\python.exe tools\import_ct_bone.py data\vhp_male_frozen out\photo_head
  ```
  In the app choose **Anatomy lab** on the start screen.
- **The modelled body** (the new body built step by step from generated reference pictures: body, skeleton,
  muscles, each organ as a GLB made by an image-to-3D tool from Gemini pictures): put the files in
  `unity/Assets/Models/` (`body.glb`, `skeleton.glb`, `muscles.glb`, `heart.glb`, ...). The glTF importer
  (`com.unity.cloud.gltfast`) turns each into a model. Unity menu **DICOM Viewer → Build Model Lab Scene** lays him
  on the table at 1.78 m in `Assets/Scenes/ModelLab.unity` (open it, Play, drag to walk round him, wheel to come
  closer, right-drag to slide); **DICOM Viewer → Model Body Snapshots** renders `build/snapshots/model_*.png`:
  ```powershell
  & "C:\Program Files\Unity\Hub\Editor\6000.6.4f1\Editor\Unity.exe" -batchmode -projectPath unity -executeMethod ModelSnapshot.Run -logFile build\model_snapshot.log -quit
  ```
- **Run the viewer**: Play in Unity, or the built app `build/DICOM 3D Viewer.exe`
  (Unity menu **DICOM Viewer → Build Windows App**).

Scans, exported volumes and labels are never committed (see `.gitignore`).
