using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// What a game bakes into a character's skin before it is drawn, taken here from the body itself: per vertex
    /// of the skin mesh (SkinMesh.cs), how open the space above the skin is (ambient occlusion: rays into the
    /// hemisphere over the surface, stopped by the body's own tissue in the skin-depth grid), how much tissue lies
    /// behind the surface (thickness, for light through ears, nostrils and the webs of the fingers), and how
    /// curved the surface is (for the pre-integrated scattering of light under the skin, Penner 2011). The three
    /// go into the mesh's vertex colour (r occlusion, g thickness / ThickMaxMm, b curvature / CurvMax, 1/mm).
    /// The scattering lookup (PreintegratedLut) is the skin's diffusion profile (d'Eon and Luebke 2007, in
    /// millimetres) integrated over a ring of the given curvature: the warm, soft terminator of lit skin.
    /// </summary>
    public static class SkinBake
    {
        public const float ReachMm = 50f;       // occlusion: how far a ray looks for tissue
        public const float ThickMaxMm = 60f;    // thickness saturates here (nothing shines through)
        public const float CurvMax = 0.25f;     // 1/mm: a 4 mm radius; sharper than that is stored as this
        private const int Rays = 16;

        /// <summary>Bakes the three into vertex colours. Without a depth grid, the skin is open and thick.</summary>
        public static Color32[] Bake(Vector3[] verts, Vector3[] norms, int[] tris, SkinDepthGrid grid)
        {
            int nv = verts.Length;
            float[] curv = Curvature(verts, norms, tris);
            var result = new NativeArray<float2>(nv, Allocator.TempJob);
            var pos = new NativeArray<Vector3>(verts, Allocator.TempJob);
            var nrm = new NativeArray<Vector3>(norms, Allocator.TempJob);
            bool grown = grid != null && grid.IsCreated;
            try
            {
                if (grown)
                {
                    var job = new SkinBakeJob
                    {
                        Pos = pos.Reinterpret<float3>(), Nrm = nrm.Reinterpret<float3>(), Depth = grid.Data,
                        Dims = new int3(grid.Dims.x, grid.Dims.y, grid.Dims.z), Spacing = grid.SpacingMm, Result = result,
                    };
                    job.Schedule(nv, 256).Complete();
                }
                var colours = new Color32[nv];
                for (int i = 0; i < nv; i++)
                {
                    float ao = grown ? result[i].x : 1f, thick = grown ? result[i].y : ThickMaxMm;
                    colours[i] = new Color32((byte)Mathf.RoundToInt(Mathf.Clamp01(ao) * 255f),
                                             (byte)Mathf.RoundToInt(Mathf.Clamp01(thick / ThickMaxMm) * 255f),
                                             (byte)Mathf.RoundToInt(Mathf.Clamp01(curv[i] / CurvMax) * 255f), 255);
                }
                return colours;
            }
            finally
            {
                result.Dispose();
                pos.Dispose();
                nrm.Dispose();
            }
        }

        /// <summary>Mean curvature per vertex (1/mm): how fast the normal turns along the edges that meet there.</summary>
        public static float[] Curvature(Vector3[] verts, Vector3[] norms, int[] tris)
        {
            int nv = verts.Length;
            var sum = new float[nv];
            var count = new int[nv];
            for (int t = 0; t + 2 < tris.Length; t += 3)
            {
                for (int e = 0; e < 3; e++)
                {
                    int a = tris[t + e], b = tris[t + (e + 1) % 3];
                    float len = Mathf.Max((verts[a] - verts[b]).magnitude, 1e-3f);
                    float c = (norms[a] - norms[b]).magnitude / len;
                    sum[a] += c; sum[b] += c;
                    count[a]++; count[b]++;
                }
            }
            var curv = new float[nv];
            for (int i = 0; i < nv; i++) curv[i] = count[i] > 0 ? sum[i] / count[i] : 0f;
            return curv;
        }

        private static Texture2D lut;

        /// <summary>
        /// Diffuse light on skin by the cosine of the light's angle (u, -1..1) and the surface's curvature
        /// (v, 0..CurvMax per mm): the skin's scattering profile integrated round a ring of that curvature.
        /// </summary>
        public static Texture2D PreintegratedLut()
        {
            if (lut != null) return lut;
            const int W = 64, H = 64, S = 256;
            // d'Eon and Luebke 2007: six Gaussians (variance mm^2) with their weights per channel.
            float[] variance = { 0.0064f, 0.0484f, 0.187f, 0.567f, 1.99f, 7.41f };
            Vector3[] weight =
            {
                new Vector3(0.233f, 0.455f, 0.649f), new Vector3(0.100f, 0.336f, 0.344f), new Vector3(0.118f, 0.198f, 0.000f),
                new Vector3(0.113f, 0.007f, 0.007f), new Vector3(0.358f, 0.004f, 0.000f), new Vector3(0.078f, 0.000f, 0.000f),
            };
            var px = new Color32[W * H];
            for (int y = 0; y < H; y++)
            {
                float curv = (y + 0.5f) / H * CurvMax;
                float r = 1f / Mathf.Max(curv, 1f / 256f);                     // mm
                for (int x = 0; x < W; x++)
                {
                    float ndl = (x + 0.5f) / W * 2f - 1f;
                    float theta = Mathf.Acos(Mathf.Clamp(ndl, -1f, 1f));
                    Vector3 num = Vector3.zero, den = Vector3.zero;
                    for (int s = 0; s < S; s++)
                    {
                        float a = (s + 0.5f) / S * 2f * Mathf.PI - Mathf.PI;
                        float d = 2f * r * Mathf.Sin(Mathf.Abs(a) * 0.5f);     // chord between the two points on the ring
                        Vector3 R = Vector3.zero;
                        for (int g = 0; g < 6; g++)
                            R += weight[g] * (Mathf.Exp(-d * d / (2f * variance[g])) / variance[g]);
                        float lit = Mathf.Max(Mathf.Cos(theta + a), 0f);
                        num += R * lit;
                        den += R;
                    }
                    Vector3 c = new Vector3(num.x / Mathf.Max(den.x, 1e-6f), num.y / Mathf.Max(den.y, 1e-6f), num.z / Mathf.Max(den.z, 1e-6f));
                    px[y * W + x] = new Color32((byte)Mathf.RoundToInt(Mathf.Clamp01(c.x) * 255f), (byte)Mathf.RoundToInt(Mathf.Clamp01(c.y) * 255f),
                                                (byte)Mathf.RoundToInt(Mathf.Clamp01(c.z) * 255f), 255);
                }
            }
            lut = new Texture2D(W, H, TextureFormat.RGB24, false, true)
            {
                name = "Skin scattering LUT", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, hideFlags = HideFlags.DontSave,
            };
            lut.SetPixels32(px);
            lut.Apply(false, true);
            return lut;
        }

        [BurstCompile(CompileSynchronously = true)]
        private struct SkinBakeJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<float3> Pos, Nrm;
            [ReadOnly] public NativeArray<ushort> Depth;
            public int3 Dims;
            public float3 Spacing;
            [WriteOnly] public NativeArray<float2> Result;

            public void Execute(int i)
            {
                float3 p = Pos[i], n = math.normalize(Nrm[i]);
                float3 t = math.normalize(math.cross(n, math.abs(n.y) < 0.9f ? new float3(0, 1, 0) : new float3(1, 0, 0)));
                float3 b = math.cross(n, t);

                // Occlusion: rays over the hemisphere (uniform in area, weighted by their cosine), each stopped by
                // the first tissue it meets; a near hit occludes more than a far one.
                float occ = 0f, wsum = 0f;
                for (int k = 0; k < Rays; k++)
                {
                    float z = (k + 0.5f) / Rays, rr = math.sqrt(1f - z * z), phi = k * 2.399963f;
                    float3 d = t * (rr * math.cos(phi)) + b * (rr * math.sin(phi)) + n * z;
                    float w = z;
                    wsum += w;
                    for (float s = 2.5f; s <= ReachMm; s += 2.5f)
                    {
                        if (SkinDepthGrid.Sample(Depth, Dims, Spacing, p + d * s) > 0.4f)
                        {
                            occ += w * (1f - s / ReachMm);
                            break;
                        }
                    }
                }
                float ao = 1f - occ / math.max(wsum, 1e-6f);

                // Thickness: inward along the normal until the ray leaves the body.
                float thick = ThickMaxMm;
                for (float s = 1f; s <= ThickMaxMm; s += 1f)
                {
                    if (SkinDepthGrid.Sample(Depth, Dims, Spacing, p - n * s) <= 0.2f) { thick = s; break; }
                }
                Result[i] = new float2(ao, thick);
            }
        }
    }
}
