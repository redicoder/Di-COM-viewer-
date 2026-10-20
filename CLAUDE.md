Project: Dissection Table (education-only anatomy app). Unity 6 URP + UnityVolumeRendering 1.8.0
(embedded fork in unity/Packages/com.mlavik1.easyvolumerenderer, changes logged in its MODIFICATIONS.md)
+ Python backend (backend/: DICOM/NRRD conversion, TotalSegmentator organ labels).

Read docs/DISSECTION_TABLE_SPEC.md and docs/SPEC_NOTES.md before any task. Do not invent
UnityVolumeRendering API — read the source in the embedded package. Axis convention: texture x = patient
left, y = superior, z = posterior; never use RawDatasetImporter. TF positions via T(hu) = (hu - min)/(max - min).
Every function must work by touch. Keep LICENSES.md current. Run pytest (backend) and Unity tests before
declaring a task done. Never add diagnostic/surgical-planning language.

Repository layout and how to run things: README.md. Structure: docs/ARCHITECTURE.md.
Python: backend/.venv (converter, tests) and backend/.venv-seg (TotalSegmentator + CUDA PyTorch, separate on
purpose). Scans, volumes and labels (backend/data, backend/out) are never committed.
Git remote: personal GitHub only. Never push to the company GitLab.
