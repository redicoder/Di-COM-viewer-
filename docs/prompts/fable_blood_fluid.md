# Prompt for Claude Fable: liquid blood rendering (screen-space fluid) for Unity URP

Copy everything below the line into Claude Fable. Bring back every file it produces.

---

You are writing production code for a Unity 6 (6000.x) project using the Universal Render Pipeline (URP 17 with
the **Render Graph** API; compatibility mode is off), Windows, DirectX 11/12, target GPU an NVIDIA RTX 2070 Max-Q,
1080p. The app is an anatomy teaching table: a real body rebuilt from colour photographs, drawn by a ray-marched
volume shader that writes SV_Depth into the camera depth buffer. When the student cuts, a GPU simulation (already
written, not your task) moves thousands of blood drops over the body's surface. **Your task is to draw those drops
as liquid blood**, not as dots: drops that touch merge into one smooth, glossy, dark-red film and rivulets.

## Input you get (do not change it)
```csharp
namespace DicomViewer.AnatomyLab {
    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    public struct BloodDrop {          // 32 bytes, matches the HLSL struct below
        public UnityEngine.Vector3 position;   // metres, in the body's local space
        public float radius;                   // metres, typically 0.0008 - 0.0015
        public UnityEngine.Vector3 normal;     // outward surface normal under the drop (body local); zero if falling
        public uint alive;                     // 0 = unused slot, 1 = alive
    }
    public static class BloodDrops {
        public static UnityEngine.ComputeBuffer Buffer;      // StructuredBuffer<BloodDrop>, capacity slots
        public static int Capacity;                          // number of slots (draw all; skip alive == 0)
        public static UnityEngine.Transform Body;            // body transform: localToWorldMatrix converts positions
    }
}
```
```hlsl
struct BloodDrop { float3 position; float radius; float3 normal; uint alive; };
```
`BloodDrops.Buffer` may be null (no blood yet); then draw nothing.

## Deliverables (complete files, no placeholders)
1. `Assets/DicomViewer/Scripts/AnatomyLab/BloodFluidFeature.cs`: a `ScriptableRendererFeature` (namespace
   `DicomViewer.AnatomyLab`) implemented with the **Render Graph** API (`RecordRenderGraph`), running after opaques
   and before transparents:
   - pass 1: draw each alive drop as a sphere imposter (procedural instanced quads, `DrawProcedural`) into a
     linear-depth target, depth-tested against the camera depth (so blood is hidden behind the body);
   - pass 2: smooth that depth with a bilateral / narrow-range filter (separable, a few iterations, radius in
     pixels scaled by distance) so neighbouring drops merge into one surface;
   - pass 3: additive thickness pass (how much blood the view ray crosses);
   - pass 4: composite onto the camera colour: normals from the smoothed depth, Beer-Lambert absorption (thin film
     = bright red, thick pool = almost black red), a sharp wet specular from the main light, Fresnel environment
     reflection, slight refraction of what is behind, and write the blood's depth so later transparents sort.
   - Settings exposed on the feature: blood colour / absorption, smoothing radius and iterations, specular strength,
     a downscale option (full / half resolution) for performance.
2. Shaders in `Assets/DicomViewer/Shaders/AnatomyLab/` (hand-written HLSL), names starting `DicomViewer/BloodFluid`,
   loaded with `Shader.Find` (the build includes them in Always Included Shaders).
3. A short `README` section at the top of the C# file: how to add the feature to the URP Renderer asset.
4. `Assets/DicomViewer/Editor/BloodFluidDemo.cs`: menu `DICOM Viewer/Blood Fluid Demo Scene` that makes a scene with
   a sphere and a small script filling `BloodDrops.Buffer` with ~3000 animated drops running down the sphere
   (simple CPU animation is fine), so the look can be checked without the rest of the app.

## Constraints
- Unity 6 + URP 17 APIs only (`RenderGraph`, `RTHandle`, `TextureHandle`, `ContextContainer`, `UniversalResourceData`).
  No obsolete `Execute` / `OnCameraSetup` path. No third-party packages.
- Budget: under 1.5 ms at 1080p for 10,000 drops on the RTX 2070 Max-Q (half-resolution option for more).
- No per-frame managed allocations.
- Comments: short, saying why, not what.

## Write-up
After the code, explain in plain English the pass order, every setting and its sensible range, how depth is
handled against the body, and anything you could not do or are unsure about.
