# Prompt for Claude Fable: grab, pull and fold back tissue in a ray-marched volume (Unity)

Copy everything below the line into Claude Fable. Bring back every file it produces.

---

You are writing production code for a Unity 6 (6000.x) project using URP 17, Windows, DirectX 11/12, compute
shaders available, target GPU an NVIDIA RTX 2070 Max-Q. The app is an anatomy teaching table. Its body is a real
person rebuilt from colour photographs into a 3D texture and drawn by a ray-marching shader in a unit cube
(object space -0.5..0.5). Students cut with a scalpel (a 3D mask texture removes tissue; not your task). **Your
task: let the student grab tissue with a finger and pull it, and fold back the skin beside a cut like a flap,
so it stays open** — the way skin is retracted in a real dissection.

## How the volume is sampled (fixed; your code plugs into it)
The ray-marcher calls, at every step, a function that returns tissue at a texture coordinate:
```hlsl
// uvw in 0..1, x = patient's left, y = front-to-back, z = bottom-to-top (texture axes)
float4 SampleTissue(float3 uvw);   // rgb = photo colour, a = tissue density 0..1 (already includes cuts)
```
Deformation must be a **backward warp**: the shader will call `SampleTissue(WarpUVW(uvw))`, where `WarpUVW`
returns where the tissue now shown at `uvw` came from. Provide `WarpUVW`.

## Deliverables (complete files, no placeholders)
1. `Assets/DicomViewer/Shaders/AnatomyLab/TissueWarp.hlsl`: `float3 WarpUVW(float3 uvw)`, reading
   - a persistent displacement field `Texture3D<float4> _WarpField` (RGBA16F, xyz = backward displacement in uvw
     units, w unused), resolution about 128 on the longest axis, trilinear, covering the whole volume; and
   - up to 4 live grab handles as uniform arrays (`_GrabFrom[4]`, `_GrabTo[4]`, `_GrabRadius[4]`, `_GrabCount`),
     each a smooth, compactly supported displacement (e.g. Wendland or smoothstep falloff), applied on top.
   The warp must be fold-free (Jacobian determinant stays positive): clamp each handle's strength so the
   displacement's spatial gradient stays below about 0.8.
2. `Assets/DicomViewer/Resources/TissueWarp.compute` with kernels to:
   - `Clear`;
   - `BakeGrab`: add a released grab handle permanently into `_WarpField` (so a pulled flap stays where it was left);
   - `Flap`: given a cut as a polyline (up to 64 points, uvw) and a fold vector and amount 0..1, displace the tissue
     on **one side** of the cut, only down to a given depth under the skin, rotating it outwards about the cut line
     like a hinge (skin and fat lift, deeper tissue stays). A distance-to-surface texture is provided:
     `Texture3D<float> _SkinDepth` (millimetres below the body surface, 0 outside the body).
3. `Assets/DicomViewer/Scripts/AnatomyLab/TissueWarp.cs` (namespace `DicomViewer.AnatomyLab`): owns the field
   RenderTexture and the compute shader, and gives the app:
   - `void Setup(Vector3Int volumeDims, Vector3 voxelSizeMm, Texture skinDepth)`;
   - `int BeginGrab(Vector3 uvw, float radiusMm)`, `void UpdateGrab(int id, Vector3 uvwTarget)`,
     `void EndGrab(int id, bool keep)` (keep = bake into the field, else spring back over ~0.3 s);
   - `void FoldFlap(IReadOnlyList<Vector3> cutUvw, Vector3 foldDirUvw, float depthMm, float amount)`;
   - `void ResetAll()`; and `void Bind(Material m)` to set all shader properties on the volume material.
4. A short plain-English write-up: the maths of the backward warp, how fold-freedom is kept, every tunable
   parameter, and what you could not do or are unsure about.

## Constraints
- Unity 6 / URP 17 APIs only; no third-party packages; no per-frame managed allocations.
- Budget: `WarpUVW` must cost at most 1 texture fetch + the handle maths per ray step (the ray-marcher takes up to
  ~800 steps per pixel); compute kernels under 1 ms at 128^3.
- Units: uvw for positions; millimetres for radii and depths (convert with `voxelSizeMm` and `volumeDims`).
- Comments: short, saying why, not what.
