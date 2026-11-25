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
  .\.venv-seg\Scripts\python.exe tools\download_visible_human.py photos data\vhp_male_photos --first 1001 --last 2878
  # FIRST line the photographs up with each other (about 20 minutes, once): they come in runs that are shifted sideways against each
  # other by 2 to 4 mm, six times between the hips and the head. Writes registration.json into both folders; every tool below reads
  # the photographs through it. Without it the body has a step round it at each of those places (prepare_photo_volume.py warns).
  .\.venv-seg\Scripts\python.exe tools\register_photos.py data\vhp_male_photos --also data\vhp_male_head_photos
  .\.venv-seg\Scripts\python.exe tools\prepare_photo_volume.py data\vhp_male_head_photos out\photo_head --first 1001 --last 1225 --unity --eye-slice 1095
  # (NOTE: the head export this project's model is built on was made on 2026-10-22 with the tool as it was at commit 65ce774, before it
  #  learnt to equalise each photograph's exposure. Made with the tool as it is now, the head comes out a little other in its colours and the
  #  eyes are measured elsewhere (docs/SPEC_NOTES.md). The export on disk was therefore kept and only moved to its place among the lined-up
  #  photographs:  .\.venv-seg\Scripts\python.exe tools\register_photos.py data\vhp_male_photos --export out\photo_head )
  ```
  The whole body (all 1,878 photos, ~14 GB) at 1.3 x 2 mm (460 MB of texture), for the lab's **Body: whole** button:
  ```powershell
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
  # The eyes found on the head export, and the head as a finer region of the whole body
  .\.venv-seg\Scripts\python.exe tools\transfer_eyes.py out\photo_head out\photo_body
  ```
  In the app choose **Anatomy lab** on the start screen.
- **The anatomy model** (the Model Lab's body: every labelled structure as its own mesh, layers that fit inside one another), built from the labelled export and then laid on the table by the menu below:
  ```powershell
  # the first time (and after a new export): read the fine skin outline from every photograph, about 12 minutes
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb --photos data\vhp_male_photos
  # the named bones (BoneHub, CC BY 4.0: the eleven .seg.nrrd files of 01_Male into data\bonehub), once, about 4 minutes
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb --bones data\bonehub --layers skeleton
  # the head and neck's named structures (TotalSegmentator's open head tasks on his frozen CT; GPU, once, about 15 minutes)
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb --head-ct data\vhp_male_frozen --layers fat,muscles,skeleton,organs
  # the hips' and legs' named muscles, knee ligaments and joint cartilage (University of Denver's STL models in data\du_visible_human, see LICENSES.md; once, a minute)
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb --legs data\du_visible_human\Final_3D_STL_Models --layers muscles,skeleton
  # the muscles' own surfaces from the photographs (reads them all again, about 6 minutes; kept in out\photo_body\model\muscle_fine.npy):
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb --skin-reuse --muscle-photos data\vhp_male_photos --layers muscles
  # the skull as its named bones (BodyParts3D 4.0 from the LSDB Archive in data\bodyparts3d, see LICENSES.md; once, half a minute)
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb --atlas data\bodyparts3d --layers skeleton
  # (the feet's outline alone can be read again in two minutes: anatomy_model.fine_skin.extract(body, photos, only=(0, 215)), then build without --skin-reuse)
  # afterwards; --layers skin rebuilds one layer, --preview <folder> renders pictures without Unity
  # (the mouth is measured on every run, about a minute: it needs out\photo_head, the head CT's labels and the skin of an earlier build;
  #  with --head-ct its teeth come from the CT's own 0.5 mm pixels, kept afterwards in out\photo_body\model\ct_mouth.npz)
  .\.venv-seg\Scripts\python.exe tools\build_model_meshes.py out\photo_body ..\unity\Assets\Models\anatomy.glb
  ```
- **Names in the modelled body**: in Play, tap a structure: it is marked and a card names it in Italian, English and Latin (the **IT / EN / LA** button, top right, picks which is large) and says whether its shape is read from this body or drawn. Tap it again, or beside the body, to put the card away; the layer buttons take layers off to reach what lies under the skin. The names are in `unity/Assets/StreamingAssets/anatomy/model_names.json`, written whenever the model is built (do not edit it: put corrections in `model_names_corrections.json` beside it, same shape, only the `key` and the names to change). **The Latin and Italian terms have not yet been checked by an anatomist.** To write the table again without rebuilding the model, and to take pictures of taps (`build/snapshots/names_*.png`):
  ```powershell
  cd backend\tools; ..\.venv-seg\Scripts\python.exe -m anatomy_model.names ..\out\photo_body ..\..\unity\Assets\StreamingAssets\anatomy\model_names.json
  & "C:\Program Files\Unity\Hub\Editor\6000.6.4f1\Editor\Unity.exe" -batchmode -projectPath unity -executeMethod ModelSnapshot.RunNames -logFile build\model_names.log -quit
  ```
- **The modelled body, prototype** (the new body built step by step from generated reference pictures: body, skeleton,
  muscles, each organ as a GLB made by an image-to-3D tool from Gemini pictures): put the files in
  `unity/Assets/Models/` (`body.glb`, `skeleton.glb`, `muscles.glb`, `heart.glb`, ...). The glTF importer
  (`com.unity.cloud.gltfast`) turns each into a model. Unity menu **DICOM Viewer → Build Model Lab Scene** lays him
  on the table at 1.78 m in `Assets/Scenes/ModelLab.unity` (open it, Play, drag to walk round him, wheel to come
  closer, right-drag to slide; the Skin / Muscles / Skeleton buttons pick the layer to see); **DICOM Viewer → Model Body Snapshots** renders `build/snapshots/model_*.png`:
  ```powershell
  & "C:\Program Files\Unity\Hub\Editor\6000.6.4f1\Editor\Unity.exe" -batchmode -projectPath unity -executeMethod ModelSnapshot.Run -logFile build\model_snapshot.log -quit
  ```
- **Run the viewer**: Play in Unity, or the built app `build/DICOM 3D Viewer.exe`
  (Unity menu **DICOM Viewer → Build Windows App**).

Scans, exported volumes and labels are never committed (see `.gitignore`).
