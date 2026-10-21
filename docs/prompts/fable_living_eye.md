# Prompt for Claude Fable: a living human eye for Unity URP

Copy everything below the line into Claude Fable. Bring back every file it produces.

---

You are writing production code for a Unity 6 (6000.x) project using the Universal Render Pipeline (URP 17,
Render Graph on), Windows, DirectX 11/12, target GPU an NVIDIA RTX 2070 Max-Q laptop driving a 32" 1080p touch
screen. The app is an anatomy teaching table. Its body is a real person rebuilt from colour photographs and
drawn by a ray-marched volume shader that writes SV_Depth. When the student opens the eyelids (done elsewhere, not
your task) a **modelled living eye** must sit behind them. Make that eye.

## Goal
An eyeball that reads as alive and healthy at close range on a large screen: wet, bright, with depth in the iris
seen through a clear cornea. It must survive close-ups (the eye can fill a third of the screen).

## Deliverables (complete files, no placeholders, no "TODO")
1. `Assets/DicomViewer/Scripts/AnatomyLab/LivingEye.cs`, namespace `DicomViewer.AnatomyLab`, a MonoBehaviour:
   - `public static LivingEye Create(Transform parent, Vector3 localCentre, float radius, Vector3 localForward)`:
     builds the eye as a child of `parent`. `localCentre` and `radius` are in the parent's local space, in metres
     (a typical radius is 0.012). `localForward` is the direction the eye looks, in the parent's local space.
   - Public fields/properties: `Color irisColor` (default a natural brown), `float pupil` (0 = pin-point,
     1 = fully dilated; default 0.35), `float wetness` (0..1, default 1), `bool autoSaccades` (small natural eye
     movements, default true).
   - `public void LookAt(Vector3 worldTarget)` turns the eye smoothly (limit 30 degrees from `localForward`).
   - Pupil reacts slowly to the brightness of the main light (optional but nice).
   - Builds its own meshes procedurally in code: sclera (sphere), cornea (a separate transparent cap with a
     radius of curvature ~7.8 mm on a 12 mm eye, scaled with `radius`, bulging ~2.5 mm in front of the sclera),
     iris (a slightly cone-shaped disc ~2.5 mm behind the cornea apex), pupil as part of the iris. No imported models.
   - Any textures are generated at runtime (`Texture2D` filled in code) or computed in the shader. No asset files
     other than the shaders below.
2. Shaders in `Assets/DicomViewer/Shaders/AnatomyLab/` (hand-written HLSL for URP, not Shader Graph), SRP Batcher
   compatible, working with URP's main directional light, additional lights optional, ambient from spherical
   harmonics, and reflections from the reflection probe / sky:
   - Sclera: off-white with a faint blue-grey and pink near the corners, fine procedural veins thickening towards
     the edges, soft wrap / subsurface-like lighting, a wet specular layer.
   - Iris: procedural stroma (radial fibres, crypts, a collarette ring, darker limbal ring at the edge), driven by
     `irisColor`, with the pupil radius driven by `pupil`. Seen **through the cornea with refraction** (parallax or
     proper refraction through the cornea's curved surface) so the iris looks set back under a clear dome.
   - Cornea: transparent, sharp specular highlights and environment reflection with Fresnel, no visible colour.
   - Opaque parts write depth; the transparent cornea is drawn after opaques and depth-tests against them.
3. `Assets/DicomViewer/Editor/LivingEyeDemo.cs`: a menu item `DICOM Viewer/Living Eye Demo Scene` that creates a
   new scene with a camera, one directional light, a dark background and two eyes 64 mm apart looking at the
   camera, with `LookAt` following the mouse, for a quick visual check.

## Conventions you must follow
- Units: metres. In the body's local space X = patient's left, Y = up, Z = towards the back of the head; the face
  looks towards -Z. (So a typical call is `Create(head, new Vector3(0.033f, 0.05f, -0.07f), 0.012f, Vector3.back)`.)
- Use only `UnityEngine` / URP APIs available in Unity 6 with URP 17. No third-party packages, no Asset Store code.
- Input, if any, uses the legacy `UnityEngine.Input` API (the project has Active Input Handling = Both).
- Shader names: `DicomViewer/LivingEyeSclera`, `DicomViewer/LivingEyeIris`, `DicomViewer/LivingEyeCornea`. Load
  them with `Shader.Find` (the build includes them in Always Included Shaders).
- Budget: under 0.5 ms per eye at 1080p on the RTX 2070 Max-Q. No per-frame allocations.
- Comments: short, saying why, not what.

## Write-up
After the code, list in plain English: how the iris refraction works, every tunable parameter and its range, and
anything you could not do or are unsure about.
