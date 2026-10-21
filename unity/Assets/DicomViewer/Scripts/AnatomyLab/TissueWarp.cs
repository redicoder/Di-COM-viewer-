// TissueWarp — grab/pull and skin-flap deformation for the ray-marched body.
// Usage: one TissueWarp per volume. Setup() after the volume is loaded, Bind() on the volume material
// (and again if the material is replaced), then BeginGrab/UpdateGrab/EndGrab from the touch tools and
// FoldFlap after a scalpel cut. The volume shader includes TissueWarp.hlsl and samples at WarpUVW(uvw).
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    [DisallowMultipleComponent]
    public sealed class TissueWarp : MonoBehaviour
    {
        public const int MaxGrabs = 4;
        public const int MaxFlapPoints = 64;

        [Tooltip("Field voxels along the longest axis; other axes follow the physical aspect. 128 = 16 MB x 2. Use 192-256 for region volumes where flaps are only a few mm deep.")]
        [Range(32, 256)] public int fieldResolution = 128;
        [Tooltip("Seconds for a released, unkept grab to spring back.")]
        public float springBackSeconds = 0.3f;
        [Tooltip("Fold angle at amount = 1, degrees outward. 90 stands the flap up, 150-180 lays it back.")]
        [Range(10f, 180f)] public float maxFoldAngleDeg = 150f;
        [Tooltip("Distance from the cut to the flap's hinge, millimetres (the flap's width).")]
        public float flapWidthMm = 30f;
        [Tooltip("A grab may never grow past this fraction of the volume's longest side; beyond it the tissue slips.")]
        [Range(0.05f, 0.5f)] public float maxGrabRadiusFraction = 0.25f;

        // Fold-free bound: |pull| / radius <= maxGradient / max|w'|; max|w'| of the Wendland C2 kernel is 2.109 at t = 1/4.
        private const float kMaxGradient = 0.8f;
        private const float kWendlandMaxSlope = 2.109f;
        private const float kMaxPullOverRadius = kMaxGradient / kWendlandMaxSlope;   // 0.379

        public bool IsSetUp => m_Field != null;
        public RenderTexture Field => m_Field;
        public bool FieldHasContent => m_FieldOn;

        private struct Grab
        {
            public bool active, springing;
            public Vector3 from, to, releaseTo;
            public float baseRadiusMm, radiusMm, springT;
        }

        private readonly Grab[] m_Grabs = new Grab[MaxGrabs];
        private readonly Vector4[] m_FromArr = new Vector4[MaxGrabs];
        private readonly Vector4[] m_ToArr = new Vector4[MaxGrabs];
        private readonly float[] m_RadiusArr = new float[MaxGrabs];
        private readonly Vector4[] m_FlapPoints = new Vector4[MaxFlapPoints];
        private readonly int[] m_Int3A = new int[3];
        private readonly int[] m_Int3B = new int[3];

        private RenderTexture m_Field, m_FieldOld, m_FieldSaved;
        private bool m_SavedOn;
        private ComputeShader m_Compute;
        private int m_KClear, m_KBake, m_KFlap, m_KGape;
        private Vector3Int m_VolumeDims, m_FieldDims;
        private Vector3 m_VoxelMm, m_SizeMm;
        private Texture m_SkinDepth;
        private Material m_Material;
        private bool m_FieldOn, m_HandlesDirty;
        private int m_GrabCount;

        private static readonly int s_WarpField = Shader.PropertyToID("_WarpField");
        private static readonly int s_GrabFrom = Shader.PropertyToID("_GrabFrom");
        private static readonly int s_GrabTo = Shader.PropertyToID("_GrabTo");
        private static readonly int s_GrabRadius = Shader.PropertyToID("_GrabRadius");
        private static readonly int s_GrabCount = Shader.PropertyToID("_GrabCount");
        private static readonly int s_WarpSizeMm = Shader.PropertyToID("_WarpSizeMm");
        private static readonly int s_WarpFieldOn = Shader.PropertyToID("_WarpFieldOn");

        private static readonly int s_CField = Shader.PropertyToID("_Field");
        private static readonly int s_CFieldOld = Shader.PropertyToID("_FieldOld");
        private static readonly int s_CSkinDepth = Shader.PropertyToID("_SkinDepth");
        private static readonly int s_CDims = Shader.PropertyToID("_Dims");
        private static readonly int s_COrigin = Shader.PropertyToID("_Origin");
        private static readonly int s_CSizeMm = Shader.PropertyToID("_SizeMm");
        private static readonly int s_CSkinStepUvw = Shader.PropertyToID("_SkinStepUvw");
        private static readonly int s_CHandleFrom = Shader.PropertyToID("_HandleFrom");
        private static readonly int s_CHandleTo = Shader.PropertyToID("_HandleTo");
        private static readonly int s_CHandleRadiusMm = Shader.PropertyToID("_HandleRadiusMm");
        private static readonly int s_CFlapPoints = Shader.PropertyToID("_FlapPoints");
        private static readonly int s_CFlapCount = Shader.PropertyToID("_FlapCount");
        private static readonly int s_CFlapDir = Shader.PropertyToID("_FlapDir");
        private static readonly int s_CFlapWidthMm = Shader.PropertyToID("_FlapWidthMm");
        private static readonly int s_CFlapDepthMm = Shader.PropertyToID("_FlapDepthMm");
        private static readonly int s_CFlapAngle = Shader.PropertyToID("_FlapAngle");
        private static readonly int s_CCutPoints = Shader.PropertyToID("_CutPoints");
        private static readonly int s_CCutCount = Shader.PropertyToID("_CutCount");
        private static readonly int s_CGapeMm = Shader.PropertyToID("_GapeMm");
        private static readonly int s_CGapeReachMm = Shader.PropertyToID("_GapeReachMm");
        private static readonly int s_CGapeDepthMm = Shader.PropertyToID("_GapeDepthMm");

        // ------------------------------------------------------------------------------------------ API

        public void Setup(Vector3Int volumeDims, Vector3 voxelSizeMm, Texture skinDepth)
        {
            ReleaseField();
            m_VolumeDims = volumeDims;
            m_VoxelMm = voxelSizeMm;
            m_SizeMm = Vector3.Scale(volumeDims, voxelSizeMm);
            m_SkinDepth = skinDepth;

            if (m_Compute == null)
            {
                m_Compute = Resources.Load<ComputeShader>("TissueWarp");
                if (m_Compute == null) { Debug.LogError("TissueWarp: Resources/TissueWarp.compute not found."); return; }
                m_KClear = m_Compute.FindKernel("Clear");
                m_KBake = m_Compute.FindKernel("BakeGrab");
                m_KFlap = m_Compute.FindKernel("Flap");
                m_KGape = m_Compute.FindKernel("Gape");
            }

            // Isotropic field voxels in millimetres, longest axis = fieldResolution.
            float longest = Mathf.Max(m_SizeMm.x, m_SizeMm.y, m_SizeMm.z);
            m_FieldDims = new Vector3Int(
                Mathf.Max(8, Mathf.RoundToInt(fieldResolution * m_SizeMm.x / longest)),
                Mathf.Max(8, Mathf.RoundToInt(fieldResolution * m_SizeMm.y / longest)),
                Mathf.Max(8, Mathf.RoundToInt(fieldResolution * m_SizeMm.z / longest)));

            m_Field = CreateField("TissueWarp Field");
            m_FieldOld = CreateField("TissueWarp Field (old)");

            m_Int3A[0] = m_FieldDims.x; m_Int3A[1] = m_FieldDims.y; m_Int3A[2] = m_FieldDims.z;
            m_Compute.SetInts(s_CDims, m_Int3A);
            m_Compute.SetVector(s_CSizeMm, m_SizeMm);
            m_Compute.SetVector(s_CSkinStepUvw, new Vector3(1f / volumeDims.x, 1f / volumeDims.y, 1f / volumeDims.z));

            for (int i = 0; i < MaxGrabs; i++) m_Grabs[i] = default;
            m_GrabCount = 0;
            ClearField();
            m_HandlesDirty = true;
            if (m_Material != null) Bind(m_Material);
        }

        public void Bind(Material m)
        {
            m_Material = m;
            if (m == null) return;
            if (m_Field != null) m.SetTexture(s_WarpField, m_Field);
            m.SetVector(s_WarpSizeMm, m_SizeMm);
            m.SetFloat(s_WarpFieldOn, m_FieldOn ? 1f : 0f);
            PushHandles();
        }

        /// <summary>Starts a grab at uvw. Returns the handle id, or -1 when all four handles are in use.</summary>
        public int BeginGrab(Vector3 uvw, float radiusMm)
        {
            for (int i = 0; i < MaxGrabs; i++)
            {
                if (m_Grabs[i].active) continue;
                m_Grabs[i] = new Grab
                {
                    active = true, from = uvw, to = uvw,
                    baseRadiusMm = Mathf.Max(radiusMm, 1f), radiusMm = Mathf.Max(radiusMm, 1f),
                };
                m_GrabCount = Mathf.Max(m_GrabCount, i + 1);
                m_HandlesDirty = true;
                return i;
            }
            return -1;
        }

        public void UpdateGrab(int id, Vector3 uvwTarget)
        {
            if (!ValidGrab(id) || m_Grabs[id].springing) return;
            ref Grab g = ref m_Grabs[id];

            // Keep the warp fold-free: pulling further than 0.379 x radius widens the radius instead,
            // so more tissue comes along, as it does in a real pull; past the cap the tissue slips.
            Vector3 pullMm = Vector3.Scale(uvwTarget - g.from, m_SizeMm);
            float pull = pullMm.magnitude;
            float radiusCap = Mathf.Max(m_SizeMm.x, m_SizeMm.y, m_SizeMm.z) * maxGrabRadiusFraction;
            float radius = Mathf.Max(g.baseRadiusMm, pull / kMaxPullOverRadius);
            if (radius > radiusCap)
            {
                radius = radiusCap;
                float maxPull = radiusCap * kMaxPullOverRadius;
                if (pull > maxPull) pullMm *= maxPull / pull;
                uvwTarget = g.from + new Vector3(pullMm.x / m_SizeMm.x, pullMm.y / m_SizeMm.y, pullMm.z / m_SizeMm.z);
            }
            g.radiusMm = radius;
            g.to = uvwTarget;
            m_HandlesDirty = true;
        }

        /// <summary>keep = bake the pull into the field permanently; otherwise it springs back over springBackSeconds.</summary>
        public void EndGrab(int id, bool keep)
        {
            if (!ValidGrab(id)) return;
            ref Grab g = ref m_Grabs[id];
            if (keep)
            {
                BakeGrab(g);
                g = default;
                TrimGrabCount();
            }
            else
            {
                g.springing = true;
                g.releaseTo = g.to;
                g.springT = 0f;
            }
            m_HandlesDirty = true;
        }

        /// <summary>
        /// Lifts the skin on the foldDirUvw side of the cut polyline: tissue within flapWidthMm of the cut and
        /// depthMm below the surface rotates outward by amount * maxFoldAngleDeg about a hinge parallel to the
        /// cut. Applied once, permanently, on top of the current state (call with the final amount, not per frame).
        /// </summary>
        public void FoldFlap(IReadOnlyList<Vector3> cutUvw, Vector3 foldDirUvw, float depthMm, float amount)
        {
            if (m_Field == null || cutUvw == null || cutUvw.Count < 2) return;
            int count = Mathf.Min(cutUvw.Count, MaxFlapPoints);

            Vector3 minMm = new Vector3(float.MaxValue, float.MaxValue, float.MaxValue);
            Vector3 maxMm = new Vector3(float.MinValue, float.MinValue, float.MinValue);
            for (int i = 0; i < count; i++)
            {
                Vector3 p = Vector3.Scale(cutUvw[i], m_SizeMm);
                m_FlapPoints[i] = p;
                minMm = Vector3.Min(minMm, p);
                maxMm = Vector3.Max(maxMm, p);
            }
            for (int i = count; i < MaxFlapPoints; i++) m_FlapPoints[i] = Vector4.zero;

            Vector3 dirMm = Vector3.Scale(foldDirUvw, m_SizeMm);
            if (dirMm.sqrMagnitude < 1e-12f) return;
            dirMm.Normalize();

            m_Compute.SetVectorArray(s_CFlapPoints, m_FlapPoints);
            m_Compute.SetInt(s_CFlapCount, count);
            m_Compute.SetVector(s_CFlapDir, dirMm);
            m_Compute.SetFloat(s_CFlapWidthMm, Mathf.Max(flapWidthMm, 1f));
            m_Compute.SetFloat(s_CFlapDepthMm, Mathf.Max(depthMm, 0.5f));
            m_Compute.SetFloat(s_CFlapAngle, Mathf.Clamp01(amount) * maxFoldAngleDeg * Mathf.Deg2Rad);

            // The rotated flap can reach width + depth past the hinge in any direction of the fold plane.
            float reach = 2f * flapWidthMm + depthMm + 2f;
            Vector3 one = Vector3.one * reach;
            RunFieldKernel(m_KFlap, minMm - one, maxMm + one);
            SetFieldOn(true);
        }

        /// <summary>
        /// Opens an incision (polyline in texture coordinates): its edges draw apart by up to gapeMm each, most at the
        /// skin in the middle of the cut, fading to nothing at its ends, at depthMm and reachMm away from it.
        /// Applied once on top of the current field.
        /// </summary>
        public void Gape(IReadOnlyList<Vector3> cutUvw, float gapeMm, float reachMm, float depthMm)
        {
            if (m_Field == null || cutUvw == null || cutUvw.Count < 2 || gapeMm <= 0f) return;
            int count = Mathf.Min(cutUvw.Count, MaxFlapPoints);
            Vector3 minMm = new Vector3(float.MaxValue, float.MaxValue, float.MaxValue);
            Vector3 maxMm = new Vector3(float.MinValue, float.MinValue, float.MinValue);
            float along = 0f;
            for (int i = 0; i < count; i++)
            {
                int src = count == cutUvw.Count ? i : Mathf.RoundToInt(i * (cutUvw.Count - 1) / (float)(count - 1));
                Vector3 p = Vector3.Scale(cutUvw[src], m_SizeMm);
                if (i > 0) along += Vector3.Distance(p, (Vector3)m_FlapPoints[i - 1]);
                m_FlapPoints[i] = new Vector4(p.x, p.y, p.z, along);
                minMm = Vector3.Min(minMm, p);
                maxMm = Vector3.Max(maxMm, p);
            }
            for (int i = count; i < MaxFlapPoints; i++) m_FlapPoints[i] = Vector4.zero;
            reachMm = Mathf.Max(reachMm, gapeMm * kWendlandMaxSlope * 1.25f);   // keep it fold-free
            m_Compute.SetVectorArray(s_CCutPoints, m_FlapPoints);
            m_Compute.SetInt(s_CCutCount, count);
            m_Compute.SetFloat(s_CGapeMm, gapeMm);
            m_Compute.SetFloat(s_CGapeReachMm, reachMm);
            m_Compute.SetFloat(s_CGapeDepthMm, Mathf.Max(depthMm, 0.5f));
            Vector3 r = Vector3.one * (reachMm + 1f);
            RunFieldKernel(m_KGape, minMm - r, maxMm + r);
            SetFieldOn(true);
        }

        /// <summary>The field back to no deformation (grabs in progress are kept).</summary>
        public void ClearDeformation() => ClearField();

        /// <summary>Remembers the field as it is now (before a live flap drag: restore, then fold with the new amount).</summary>
        public void SaveState()
        {
            if (m_Field == null) return;
            if (m_FieldSaved == null) m_FieldSaved = CreateField("TissueWarp Field (saved)");
            Graphics.CopyTexture(m_Field, m_FieldSaved);
            m_SavedOn = m_FieldOn;
        }

        /// <summary>Back to the field SaveState remembered.</summary>
        public void RestoreState()
        {
            if (m_Field == null || m_FieldSaved == null) return;
            Graphics.CopyTexture(m_FieldSaved, m_Field);
            SetFieldOn(m_SavedOn);
        }

        public void ResetAll()
        {
            for (int i = 0; i < MaxGrabs; i++) m_Grabs[i] = default;
            m_GrabCount = 0;
            ClearField();
            m_HandlesDirty = true;
        }

        // -------------------------------------------------------------------------------------- update

        private void Update()
        {
            float dt = Time.deltaTime;
            for (int i = 0; i < MaxGrabs; i++)
            {
                ref Grab g = ref m_Grabs[i];
                if (!g.active || !g.springing) continue;
                g.springT += dt;
                float u = springBackSeconds > 0f ? Mathf.Clamp01(g.springT / springBackSeconds) : 1f;
                float k = 1f - u; k = 1f - k * k * k;                       // ease-out: fast at first, settles softly
                g.to = Vector3.LerpUnclamped(g.releaseTo, g.from, k);
                m_HandlesDirty = true;
                if (u >= 1f) { g = default; TrimGrabCount(); }
            }
            if (m_HandlesDirty) PushHandles();
        }

        private void PushHandles()
        {
            m_HandlesDirty = false;
            if (m_Material == null) return;
            for (int i = 0; i < MaxGrabs; i++)
            {
                ref Grab g = ref m_Grabs[i];
                bool on = g.active;
                m_FromArr[i] = on ? (Vector4)g.from : Vector4.zero;
                m_ToArr[i] = on ? (Vector4)g.to : Vector4.zero;
                m_RadiusArr[i] = on ? g.radiusMm : 0f;   // radius 0 = no influence (t is always >= 1)
            }
            m_Material.SetVectorArray(s_GrabFrom, m_FromArr);
            m_Material.SetVectorArray(s_GrabTo, m_ToArr);
            m_Material.SetFloatArray(s_GrabRadius, m_RadiusArr);
            m_Material.SetInt(s_GrabCount, m_GrabCount);
        }

        private bool ValidGrab(int id) => id >= 0 && id < MaxGrabs && m_Grabs[id].active;

        private void TrimGrabCount()
        {
            m_GrabCount = 0;
            for (int i = 0; i < MaxGrabs; i++) if (m_Grabs[i].active) m_GrabCount = i + 1;
        }

        // --------------------------------------------------------------------------------------- field

        private RenderTexture CreateField(string name)
        {
            var desc = new RenderTextureDescriptor(m_FieldDims.x, m_FieldDims.y, GraphicsFormat.R16G16B16A16_SFloat, 0)
            {
                dimension = TextureDimension.Tex3D,
                volumeDepth = m_FieldDims.z,
                enableRandomWrite = true,
                msaaSamples = 1,
                useMipMap = false,
            };
            var rt = new RenderTexture(desc)
            {
                name = name,
                filterMode = FilterMode.Trilinear,
                wrapMode = TextureWrapMode.Clamp,
                hideFlags = HideFlags.HideAndDontSave,
            };
            rt.Create();
            return rt;
        }

        private void ClearField()
        {
            if (m_Field == null) return;
            m_Int3B[0] = 0; m_Int3B[1] = 0; m_Int3B[2] = 0;
            m_Compute.SetInts(s_COrigin, m_Int3B);
            m_Compute.SetTexture(m_KClear, s_CField, m_Field);
            m_Compute.Dispatch(m_KClear, Groups(m_FieldDims.x), Groups(m_FieldDims.y), Groups(m_FieldDims.z));
            SetFieldOn(false);
        }

        private void BakeGrab(in Grab g)
        {
            if (m_Field == null) return;
            m_Compute.SetVector(s_CHandleFrom, g.from);
            m_Compute.SetVector(s_CHandleTo, g.to);
            m_Compute.SetFloat(s_CHandleRadiusMm, g.radiusMm);
            Vector3 centreMm = Vector3.Scale(g.to, m_SizeMm);
            Vector3 r = Vector3.one * (g.radiusMm + 1f);
            RunFieldKernel(m_KBake, centreMm - r, centreMm + r);
            SetFieldOn(true);
        }

        // Snapshot the field, then rewrite only the voxels inside the millimetre box.
        private void RunFieldKernel(int kernel, Vector3 minMm, Vector3 maxMm)
        {
            Graphics.CopyTexture(m_Field, m_FieldOld);

            Vector3Int lo = ToFieldVoxel(minMm, true), hi = ToFieldVoxel(maxMm, false);
            if (hi.x < lo.x || hi.y < lo.y || hi.z < lo.z) return;

            m_Int3B[0] = lo.x; m_Int3B[1] = lo.y; m_Int3B[2] = lo.z;
            m_Compute.SetInts(s_COrigin, m_Int3B);
            m_Compute.SetTexture(kernel, s_CField, m_Field);
            m_Compute.SetTexture(kernel, s_CFieldOld, m_FieldOld);
            if (m_SkinDepth != null) m_Compute.SetTexture(kernel, s_CSkinDepth, m_SkinDepth);
            m_Compute.Dispatch(kernel, Groups(hi.x - lo.x + 1), Groups(hi.y - lo.y + 1), Groups(hi.z - lo.z + 1));
        }

        private Vector3Int ToFieldVoxel(Vector3 mm, bool floor)
        {
            Vector3 f = new Vector3(mm.x / m_SizeMm.x * m_FieldDims.x, mm.y / m_SizeMm.y * m_FieldDims.y, mm.z / m_SizeMm.z * m_FieldDims.z);
            Vector3Int v = floor
                ? new Vector3Int(Mathf.FloorToInt(f.x), Mathf.FloorToInt(f.y), Mathf.FloorToInt(f.z))
                : new Vector3Int(Mathf.CeilToInt(f.x), Mathf.CeilToInt(f.y), Mathf.CeilToInt(f.z));
            return Vector3Int.Max(Vector3Int.zero, Vector3Int.Min(v, m_FieldDims - Vector3Int.one));
        }

        private static int Groups(int voxels) => (voxels + 3) / 4;

        private void SetFieldOn(bool on)
        {
            m_FieldOn = on;
            if (m_Material != null) m_Material.SetFloat(s_WarpFieldOn, on ? 1f : 0f);
        }

        private void ReleaseField()
        {
            Kill(ref m_Field);
            Kill(ref m_FieldOld);
            Kill(ref m_FieldSaved);
            m_FieldOn = false;
        }

        // Also used outside Play mode (editor snapshots), where Destroy is not allowed.
        private static void Kill(ref RenderTexture rt)
        {
            if (rt == null) return;
            rt.Release();
            if (Application.isPlaying) Destroy(rt);
            else DestroyImmediate(rt);
            rt = null;
        }

        private void OnDestroy() => ReleaseField();
    }
}
