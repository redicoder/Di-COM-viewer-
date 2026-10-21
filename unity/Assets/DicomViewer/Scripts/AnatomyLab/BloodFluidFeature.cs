// BloodFluidFeature — screen-space liquid rendering for BloodDrops (Unity 6, URP 17, Render Graph).
//
// README
// ------
// 1. Shaders: Assets/DicomViewer/Shaders/AnatomyLab/BloodFluidDrops.shader, BloodFluidBlur.shader,
//    BloodFluidComposite.shader (+ BloodFluidCommon.hlsl). Add the three shaders to
//    Edit > Project Settings > Graphics > Always Included Shaders, or run the demo menu once (it does it).
// 2. Add the feature: select the URP Renderer asset your pipeline uses (Project Settings > Graphics >
//    URP asset > Renderer List > click the renderer), press "Add Renderer Feature", choose "Blood Fluid Feature".
//    Menu "DICOM Viewer/Blood Fluid Demo Scene" also adds it to the default renderer if it is missing.
// 3. The feature draws only while BloodDrops.Buffer, BloodDrops.Capacity and BloodDrops.Body are set.
//    It runs after the skybox and before transparents, at Before Rendering Transparents.
// 4. Settings live on the feature (inspector). "Debug View" 1/2/3 shows depth / thickness / normals.
//
// Pass order per camera:
//   Blood Drops Depth   sphere imposters -> R32F "1/eyeDepth", BlendOp Max (nearest wins; 0 = none)
//   Blood Blur x/y      narrow-range bilateral, N iterations, converts to linear metres on the first pass
//   Blood Drops Thick.  sphere imposters -> R16F additive chord length (metres)
//   Blood Copy Color    camera colour -> copy (needed to read it while writing it)
//   Blood Composite     full-screen shade + SV_Depth into the camera colour/depth attachments
// Drops are tested against _CameraDepthTexture inside the imposter shader, so the first three passes can run
// at half resolution without a matching depth attachment.

using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;
using UnityEngine.Rendering.RenderGraphModule;
using UnityEngine.Rendering.RenderGraphModule.Util;
using UnityEngine.Rendering.Universal;

namespace DicomViewer.AnatomyLab
{
    public sealed class BloodFluidFeature : ScriptableRendererFeature
    {
        [System.Serializable]
        public sealed class Settings
        {
            [Header("Look")]
            [Tooltip("Transmission tint. Dark red: thin film shows the background tinted red, thick blood goes almost black.")]
            public Color bloodColor = new Color(0.55f, 0.02f, 0.02f, 1f);
            [Tooltip("Absorption per metre of blood (Beer-Lambert). 400 = a 2.5 mm pool transmits 37 %.")]
            [Range(50f, 2000f)] public float absorption = 450f;
            [Tooltip("In-scattered colour so deep pools stay dark red instead of black.")]
            [Range(0f, 1f)] public float scatter = 0.25f;
            [Tooltip("Main-light highlight strength.")]
            [Range(0f, 4f)] public float specularStrength = 1.0f;
            [Tooltip("Surface roughness of the wet film. Lower = sharper highlight.")]
            [Range(0.02f, 0.5f)] public float roughness = 0.06f;
            [Tooltip("Sky / default reflection probe contribution.")]
            [Range(0f, 2f)] public float reflectionStrength = 1.0f;
            [Tooltip("How far (in screen UV) the background is shifted under thick blood.")]
            [Range(0f, 0.05f)] public float refraction = 0.012f;
            [Tooltip("Blood thinner than this (metres) fades out, softening the film edge.")]
            [Range(0.0001f, 0.003f)] public float edgeThickness = 0.0006f;

            [Header("Surface smoothing")]
            [Tooltip("Smoothing radius in metres at the blood's depth. About 2x the drop radius merges touching drops.")]
            [Range(0.0005f, 0.01f)] public float smoothingRadius = 0.004f;
            [Tooltip("Cap on the radius in pixels (close-ups).")]
            [Range(1, 24)] public int maxSmoothingPixels = 12;
            [Tooltip("Separable blur iterations (each is a horizontal + vertical pass).")]
            [Range(1, 4)] public int smoothingIterations = 3;
            [Tooltip("Depth difference (metres) beyond which neighbours are treated as a different surface.")]
            [Range(0.0005f, 0.02f)] public float depthThreshold = 0.003f;

            [Header("Performance")]
            [Tooltip("Render depth/thickness/blur at half resolution. Composite is always full resolution.")]
            public bool halfResolution = false;
            [Tooltip("Billboard quad size relative to the sphere radius; 1.15 covers perspective bulge at normal distances.")]
            [Range(1f, 2f)] public float quadScale = 1.15f;
            [Tooltip("Metres a drop may sink below the opaque surface before the body hides it.")]
            [Range(0f, 0.005f)] public float depthBias = 0.0007f;

            [Header("Debug")]
            [Tooltip("0 = final, 1 = blood depth, 2 = thickness, 3 = normals.")]
            [Range(0, 3)] public int debugView = 0;
        }

        public Settings settings = new Settings();

        /// <summary>The frame this feature last queued its passes (BloodSim skips its simple drops when recent).</summary>
        public static int LastQueuedFrame = -100;

        private BloodFluidPass m_Pass;
        private Material m_DropsMaterial, m_BlurMaterial, m_CompositeMaterial;

        public override void Create()
        {
            m_DropsMaterial = Load("DicomViewer/BloodFluidDrops");
            m_BlurMaterial = Load("DicomViewer/BloodFluidBlur");
            m_CompositeMaterial = Load("DicomViewer/BloodFluidComposite");

            m_Pass = new BloodFluidPass
            {
                renderPassEvent = RenderPassEvent.BeforeRenderingTransparents,
                requiresIntermediateTexture = true,   // the composite reads the camera colour; a backbuffer cannot be read
            };
            m_Pass.ConfigureInput(ScriptableRenderPassInput.Depth);   // _CameraDepthTexture for the imposter depth test
        }

        private static Material Load(string shaderName)
        {
            Shader s = Shader.Find(shaderName);
            if (s == null)
            {
                Debug.LogError($"BloodFluidFeature: shader '{shaderName}' not found. Is it in Always Included Shaders?");
                return null;
            }
            return CoreUtils.CreateEngineMaterial(s);
        }

        public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
        {
            if (m_DropsMaterial == null || m_BlurMaterial == null || m_CompositeMaterial == null) return;
            ComputeBuffer buffer = BloodDrops.Buffer;
            if (buffer == null || !buffer.IsValid() || BloodDrops.Capacity <= 0 || BloodDrops.Body == null) return;

            m_Pass.Setup(settings, m_DropsMaterial, m_BlurMaterial, m_CompositeMaterial);
            renderer.EnqueuePass(m_Pass);
            LastQueuedFrame = Time.frameCount;
        }

        protected override void Dispose(bool disposing)
        {
            CoreUtils.Destroy(m_DropsMaterial);
            CoreUtils.Destroy(m_BlurMaterial);
            CoreUtils.Destroy(m_CompositeMaterial);
        }

        // ------------------------------------------------------------------------------------------------

        private sealed class BloodFluidPass : ScriptableRenderPass
        {
            private static readonly int s_BloodDrops = Shader.PropertyToID("_BloodDrops");
            private static readonly int s_BodyToWorld = Shader.PropertyToID("_BloodBodyToWorld");
            private static readonly int s_DropParams = Shader.PropertyToID("_BloodDropParams");
            private static readonly int s_TargetSize = Shader.PropertyToID("_BloodTargetSize");
            private static readonly int s_BlurDir = Shader.PropertyToID("_BloodBlurDir");
            private static readonly int s_BlurParams = Shader.PropertyToID("_BloodBlurParams");
            private static readonly int s_BlitTexture = Shader.PropertyToID("_BlitTexture");
            private static readonly int s_BlitScaleBias = Shader.PropertyToID("_BlitScaleBias");
            private static readonly int s_BloodDepth = Shader.PropertyToID("_BloodDepth");
            private static readonly int s_BloodThickness = Shader.PropertyToID("_BloodThickness");
            private static readonly int s_DepthTexelSize = Shader.PropertyToID("_BloodDepthTexelSize");
            private static readonly int s_BloodColor = Shader.PropertyToID("_BloodColor");
            private static readonly int s_Params = Shader.PropertyToID("_BloodParams");
            private static readonly int s_Params2 = Shader.PropertyToID("_BloodParams2");

            private static readonly Vector4 s_NoScaleBias = new Vector4(1f, 1f, 0f, 0f);
            private static readonly MaterialPropertyBlock s_Mpb = new MaterialPropertyBlock();

            private static readonly ProfilingSampler s_DepthSampler = new ProfilingSampler("Blood Drops Depth");
            private static readonly ProfilingSampler s_BlurSampler = new ProfilingSampler("Blood Blur");
            private static readonly ProfilingSampler s_ThicknessSampler = new ProfilingSampler("Blood Drops Thickness");
            private static readonly ProfilingSampler s_CompositeSampler = new ProfilingSampler("Blood Composite");

            private Settings m_Settings;
            private Material m_Drops, m_Blur, m_Composite;

            private sealed class DropsData
            {
                public Material material;
                public int pass;
                public ComputeBuffer buffer;
                public int instanceCount;
                public Matrix4x4 bodyToWorld;
                public Vector4 dropParams;
                public Vector4 targetSize;
            }

            private sealed class BlurData
            {
                public Material material;
                public TextureHandle source;
                public Vector4 dir;
                public Vector4 blurParams;
                public Vector4 targetSize;
            }

            private sealed class CompositeData
            {
                public Material material;
                public TextureHandle colorCopy, depth, thickness;
                public Vector4 depthTexelSize, color, p1, p2;
            }

            public void Setup(Settings settings, Material drops, Material blur, Material composite)
            {
                m_Settings = settings;
                m_Drops = drops;
                m_Blur = blur;
                m_Composite = composite;
            }

            public override void RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)
            {
                UniversalResourceData resources = frameData.Get<UniversalResourceData>();
                UniversalCameraData cameraData = frameData.Get<UniversalCameraData>();

                if (cameraData.cameraType == CameraType.Preview || cameraData.cameraType == CameraType.Reflection) return;
                if (resources.isActiveTargetBackBuffer || !resources.cameraDepthTexture.IsValid()) return;

                ComputeBuffer buffer = BloodDrops.Buffer;
                Transform body = BloodDrops.Body;
                if (buffer == null || !buffer.IsValid() || body == null) return;

                Settings s = m_Settings;
                int div = s.halfResolution ? 2 : 1;

                // Intermediate targets: single-sample, no depth, point filtered where they hold depth.
                RenderTextureDescriptor desc = cameraData.cameraTargetDescriptor;
                desc.msaaSamples = 1;
                desc.depthBufferBits = 0;
                desc.useMipMap = false;
                desc.autoGenerateMips = false;
                desc.enableRandomWrite = false;
                desc.bindMS = false;
                desc.width = Mathf.Max(1, desc.width / div);
                desc.height = Mathf.Max(1, desc.height / div);

                RenderTextureDescriptor depthDesc = desc;
                depthDesc.graphicsFormat = GraphicsFormat.R32_SFloat;
                RenderTextureDescriptor thickDesc = desc;
                thickDesc.graphicsFormat = GraphicsFormat.R16_SFloat;

                TextureHandle depthA = UniversalRenderer.CreateRenderGraphTexture(renderGraph, depthDesc, "_BloodDepthA", true, FilterMode.Point);
                TextureHandle depthB = UniversalRenderer.CreateRenderGraphTexture(renderGraph, depthDesc, "_BloodDepthB", true, FilterMode.Point);
                TextureHandle thickness = UniversalRenderer.CreateRenderGraphTexture(renderGraph, thickDesc, "_BloodThickness", true, FilterMode.Bilinear);

                TextureDesc copyDesc = renderGraph.GetTextureDesc(resources.activeColorTexture);
                copyDesc.name = "_BloodColorCopy";
                copyDesc.clearBuffer = false;
                TextureHandle colorCopy = renderGraph.CreateTexture(copyDesc);

                Vector4 targetSize = new Vector4(desc.width, desc.height, 1f / desc.width, 1f / desc.height);
                Vector3 ls = body.lossyScale;
                float bodyScale = Mathf.Max(Mathf.Abs(ls.x), Mathf.Abs(ls.y), Mathf.Abs(ls.z));
                Vector4 dropParams = new Vector4(bodyScale, s.quadScale, div, s.depthBias);

                // 1. nearest-surface depth of the drops
                AddDropsPass(renderGraph, resources, depthA, 0, s_DepthSampler, buffer, body.localToWorldMatrix, dropParams, targetSize);

                // 2. separable narrow-range smoothing (even number of passes: result ends in depthA)
                Vector4 blurParams = new Vector4(s.smoothingRadius, s.maxSmoothingPixels, s.depthThreshold, 1f);
                for (int it = 0; it < s.smoothingIterations; it++)
                {
                    AddBlurPass(renderGraph, depthA, depthB, new Vector4(1f, 0f, 0f, 0f), blurParams, targetSize);
                    blurParams.w = 0f;   // after the first pass the texture holds linear metres
                    AddBlurPass(renderGraph, depthB, depthA, new Vector4(0f, 1f, 0f, 0f), blurParams, targetSize);
                }

                // 3. accumulated thickness
                AddDropsPass(renderGraph, resources, thickness, 1, s_ThicknessSampler, buffer, body.localToWorldMatrix, dropParams, targetSize);

                // 4. the camera colour cannot be read and written by the same raster pass
                renderGraph.AddBlitPass(resources.activeColorTexture, colorCopy, Vector2.one, Vector2.zero, passName: "Blood Copy Color");

                // 5. shade and write depth
                using (IRasterRenderGraphBuilder builder = renderGraph.AddRasterRenderPass("Blood Composite", out CompositeData data, s_CompositeSampler))
                {
                    data.material = m_Composite;
                    data.colorCopy = colorCopy;
                    data.depth = depthA;
                    data.thickness = thickness;
                    data.depthTexelSize = new Vector4(targetSize.z, targetSize.w, targetSize.x, targetSize.y);
                    data.color = s.bloodColor;
                    data.p1 = new Vector4(s.absorption, s.specularStrength, s.refraction, s.edgeThickness);
                    data.p2 = new Vector4(s.roughness, s.reflectionStrength, s.scatter, s.debugView);

                    builder.UseTexture(colorCopy, AccessFlags.Read);
                    builder.UseTexture(depthA, AccessFlags.Read);
                    builder.UseTexture(thickness, AccessFlags.Read);
                    // ReadWrite: the pass only touches pixels that hold blood; everything else must survive.
                    builder.SetRenderAttachment(resources.activeColorTexture, 0, AccessFlags.ReadWrite);
                    builder.SetRenderAttachmentDepth(resources.activeDepthTexture, AccessFlags.ReadWrite);
                    builder.SetRenderFunc(static (CompositeData d, RasterGraphContext ctx) => ExecuteComposite(d, ctx));
                }
            }

            private void AddDropsPass(RenderGraph renderGraph, UniversalResourceData resources, TextureHandle target, int pass,
                ProfilingSampler sampler, ComputeBuffer buffer, Matrix4x4 bodyToWorld, Vector4 dropParams, Vector4 targetSize)
            {
                using (IRasterRenderGraphBuilder builder = renderGraph.AddRasterRenderPass(sampler.name, out DropsData data, sampler))
                {
                    data.material = m_Drops;
                    data.pass = pass;
                    data.buffer = buffer;
                    data.instanceCount = BloodDrops.Capacity;
                    data.bodyToWorld = bodyToWorld;
                    data.dropParams = dropParams;
                    data.targetSize = targetSize;

                    builder.UseTexture(resources.cameraDepthTexture, AccessFlags.Read);
                    builder.SetRenderAttachment(target, 0, AccessFlags.Write);
                    builder.SetRenderFunc(static (DropsData d, RasterGraphContext ctx) => ExecuteDrops(d, ctx));
                }
            }

            private void AddBlurPass(RenderGraph renderGraph, TextureHandle source, TextureHandle target,
                Vector4 dir, Vector4 blurParams, Vector4 targetSize)
            {
                using (IRasterRenderGraphBuilder builder = renderGraph.AddRasterRenderPass("Blood Blur", out BlurData data, s_BlurSampler))
                {
                    data.material = m_Blur;
                    data.source = source;
                    data.dir = dir;
                    data.blurParams = blurParams;
                    data.targetSize = targetSize;

                    builder.UseTexture(source, AccessFlags.Read);
                    builder.SetRenderAttachment(target, 0, AccessFlags.Write);
                    builder.SetRenderFunc(static (BlurData d, RasterGraphContext ctx) => ExecuteBlur(d, ctx));
                }
            }

            // The property block is copied into the command buffer by DrawProcedural, so one static block is safe to reuse.
            private static void ExecuteDrops(DropsData d, RasterGraphContext ctx)
            {
                s_Mpb.Clear();
                s_Mpb.SetBuffer(s_BloodDrops, d.buffer);
                s_Mpb.SetMatrix(s_BodyToWorld, d.bodyToWorld);
                s_Mpb.SetVector(s_DropParams, d.dropParams);
                s_Mpb.SetVector(s_TargetSize, d.targetSize);
                ctx.cmd.DrawProcedural(Matrix4x4.identity, d.material, d.pass, MeshTopology.Triangles, 6, d.instanceCount, s_Mpb);
            }

            private static void ExecuteBlur(BlurData d, RasterGraphContext ctx)
            {
                s_Mpb.Clear();
                s_Mpb.SetTexture(s_BlitTexture, d.source);
                s_Mpb.SetVector(s_BlitScaleBias, s_NoScaleBias);
                s_Mpb.SetVector(s_BlurDir, d.dir);
                s_Mpb.SetVector(s_BlurParams, d.blurParams);
                s_Mpb.SetVector(s_TargetSize, d.targetSize);
                ctx.cmd.DrawProcedural(Matrix4x4.identity, d.material, 0, MeshTopology.Triangles, 3, 1, s_Mpb);
            }

            private static void ExecuteComposite(CompositeData d, RasterGraphContext ctx)
            {
                s_Mpb.Clear();
                s_Mpb.SetTexture(s_BlitTexture, d.colorCopy);
                s_Mpb.SetVector(s_BlitScaleBias, s_NoScaleBias);
                s_Mpb.SetTexture(s_BloodDepth, d.depth);
                s_Mpb.SetTexture(s_BloodThickness, d.thickness);
                s_Mpb.SetVector(s_DepthTexelSize, d.depthTexelSize);
                s_Mpb.SetVector(s_BloodColor, d.color);
                s_Mpb.SetVector(s_Params, d.p1);
                s_Mpb.SetVector(s_Params2, d.p2);
                ctx.cmd.DrawProcedural(Matrix4x4.identity, d.material, 0, MeshTopology.Triangles, 3, 1, s_Mpb);
            }
        }
    }
}
