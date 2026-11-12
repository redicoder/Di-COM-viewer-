using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// What a game bakes into a character, done for each generated layer when the scene starts (well under a
    /// second each): the normals smoothed across the texture seams (the generator splits the vertices there, which
    /// shows as facets), and per vertex, in the vertex colour as SkinBake stores it, how open the room above the
    /// surface is (ambient occlusion: armpits, between the ribs, the eye sockets), how much tissue lies behind it
    /// (light through ears and fingers) and its curvature (for the skin's pre-integrated scattering). The
    /// occlusion and thickness come from the layer's own surface put into a voxel grid and walked along rays.
    /// LabModel.shader reads them. The source mesh is kept; the baked copy is not saved with the scene.
    /// </summary>
    public class ModelPolish : MonoBehaviour
    {
        [Tooltip("The body's real height, for millimetres.")]
        public float heightM = ModelLab.DefaultHeightM;

        [SerializeField] private List<MeshFilter> filters = new List<MeshFilter>();
        [SerializeField] private List<Mesh> sources = new List<Mesh>();
        [SerializeField] private List<float> mmPerUnits = new List<float>();
        private readonly List<Mesh> baked = new List<Mesh>();

        /// <summary>Registers a layer's meshes (the editor's scene builder calls it); the source meshes are remembered.</summary>
        public void Add(GameObject model, float mmPerUnit = 0f)
        {
            foreach (MeshFilter f in model.GetComponentsInChildren<MeshFilter>(true))
            {
                if (f.sharedMesh == null || filters.Contains(f)) continue;
                filters.Add(f);
                sources.Add(f.sharedMesh);
                mmPerUnits.Add(mmPerUnit);
            }
        }

        private void Awake() => Apply();

        /// <summary>Bakes every registered mesh and hands the lookup texture to the materials.</summary>
        public void Apply()
        {
            Texture2D lut = SkinBake.PreintegratedLut();
            var clock = System.Diagnostics.Stopwatch.StartNew();
            int total = 0;
            for (int i = 0; i < filters.Count; i++)
            {
                MeshFilter f = filters[i];
                Mesh src = i < sources.Count ? sources[i] : null;
                if (f == null || src == null) continue;
                if (!src.isReadable) { Debug.LogWarning($"ModelPolish: mesh {src.name} is not readable, left as it is"); continue; }
                float mmPerUnit = i < mmPerUnits.Count && mmPerUnits[i] > 0f ? mmPerUnits[i] : heightM * 1000f / Mathf.Max(1e-4f, src.bounds.size.y);
                Mesh m = Bake(src, mmPerUnit);
                baked.Add(m);
                f.sharedMesh = m;
                var r = f.GetComponent<Renderer>();
                if (r != null && r.sharedMaterial != null && r.sharedMaterial.HasProperty("_SkinLut"))
                {
                    r.sharedMaterial.SetTexture("_SkinLut", lut);
                    r.sharedMaterial.SetFloat("_SkinLutOn", 1f);
                    r.sharedMaterial.SetFloat("_MmPerUnit", mmPerUnit);
                }
                total += src.vertexCount;
            }
            // The skin's lookup for every layer material under this body (also those that came baked, in metres).
            foreach (Renderer r in GetComponentsInChildren<Renderer>(true))
            {
                Material m = r.sharedMaterial;
                if (m == null || !m.HasProperty("_SkinLut") || m.GetTexture("_SkinLut") == lut) continue;
                m.SetTexture("_SkinLut", lut);
                m.SetFloat("_SkinLutOn", 1f);
                m.SetFloat("_MmPerUnit", 1000f);
            }
            if (filters.Count > 0) Report(total, clock.ElapsedMilliseconds);
        }

        private void Report(int total, long ms) => Debug.Log($"ModelPolish: {filters.Count} meshes, {total} vertices baked in {ms} ms");

        private void OnDestroy()
        {
            // The source meshes go back (the scene must never be saved pointing at a mesh that is not kept).
            for (int i = 0; i < filters.Count; i++)
                if (filters[i] != null && i < sources.Count) filters[i].sharedMesh = sources[i];
            foreach (Mesh m in baked)
                if (m != null) { if (Application.isPlaying) Destroy(m); else DestroyImmediate(m); }
            baked.Clear();
        }

        /// <summary>The source meshes back on the filters (before the editor saves the scene).</summary>
        public void Restore() => OnDestroy();

        /// <summary>A copy of the mesh with seam-smoothed normals and the bake in its vertex colours.</summary>
        public static Mesh Bake(Mesh src, float mmPerUnit)
        {
            Vector3[] verts = src.vertices;
            int[] tris = src.triangles;
            int nv = verts.Length;

            // Vertices at the same place are one point of the surface: weld them for normals and neighbours.
            var weld = new int[nv];
            var first = new Dictionary<Vector3Int, int>(nv);
            float q = 1f / Mathf.Max(1e-6f, src.bounds.size.magnitude * 2e-5f);
            int nw = 0;
            var welded = new List<Vector3>(nv);
            for (int i = 0; i < nv; i++)
            {
                var key = new Vector3Int(Mathf.RoundToInt(verts[i].x * q), Mathf.RoundToInt(verts[i].y * q), Mathf.RoundToInt(verts[i].z * q));
                if (!first.TryGetValue(key, out int w)) { w = nw++; first[key] = w; welded.Add(verts[i]); }
                weld[i] = w;
            }
            var wn = new Vector3[nw];
            for (int t = 0; t < tris.Length; t += 3)
            {
                int a = tris[t], b = tris[t + 1], c = tris[t + 2];
                Vector3 n = Vector3.Cross(verts[b] - verts[a], verts[c] - verts[a]);       // area-weighted
                wn[weld[a]] += n; wn[weld[b]] += n; wn[weld[c]] += n;
            }
            for (int i = 0; i < nw; i++) wn[i] = wn[i].sqrMagnitude > 0f ? wn[i].normalized : Vector3.up;

            // The surface in a voxel grid (about 4 mm cells).
            Bounds bounds = src.bounds;
            float cell = Mathf.Max(Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z)) / 440f, 1.5f / mmPerUnit);   // never finer than 1.5 mm
            Vector3 lo = bounds.min - Vector3.one * cell * 4f;
            int gx = Mathf.CeilToInt(bounds.size.x / cell) + 8, gy = Mathf.CeilToInt(bounds.size.y / cell) + 8, gz = Mathf.CeilToInt(bounds.size.z / cell) + 8;
            var occ = new bool[gx * gy * gz];
            for (int t = 0; t < tris.Length; t += 3)
            {
                Vector3 a = verts[tris[t]], b = verts[tris[t + 1]], c = verts[tris[t + 2]];
                float longest = Mathf.Max((b - a).magnitude, Mathf.Max((c - a).magnitude, (c - b).magnitude));
                int n = Mathf.Min(64, Mathf.CeilToInt(longest / (cell * 0.5f)) + 1);
                for (int i = 0; i <= n; i++)
                for (int j = 0; j <= n - i; j++)
                {
                    Vector3 p = a + (b - a) * ((float)i / n) + (c - a) * ((float)j / n);
                    int x = (int)((p.x - lo.x) / cell), y = (int)((p.y - lo.y) / cell), z = (int)((p.z - lo.z) / cell);
                    occ[(z * gy + y) * gx + x] = true;
                }
            }
            bool Solid(Vector3 p)
            {
                int x = (int)((p.x - lo.x) / cell), y = (int)((p.y - lo.y) / cell), z = (int)((p.z - lo.z) / cell);
                return x >= 0 && y >= 0 && z >= 0 && x < gx && y < gy && z < gz && occ[(z * gy + y) * gx + x];
            }

            // Rays over the hemisphere (elevation 25..80 degrees), the same set turned to each normal.
            var dirs = new List<Vector3>();
            foreach (float el in new[] { 25f, 50f, 78f })
            {
                int count = el < 30f ? 8 : el < 60f ? 6 : 3;
                for (int k = 0; k < count; k++)
                {
                    float az = (k + (el < 30f ? 0f : 0.5f)) * Mathf.PI * 2f / count, e = el * Mathf.Deg2Rad;
                    dirs.Add(new Vector3(Mathf.Cos(az) * Mathf.Cos(e), Mathf.Sin(az) * Mathf.Cos(e), Mathf.Sin(e)));
                }
            }
            float weightSum = 0f;
            foreach (Vector3 d in dirs) weightSum += d.z;
            float reach = SkinBake.ReachMm / mmPerUnit;
            int steps = Mathf.Max(4, Mathf.CeilToInt(reach / cell));
            var sky = new float[nw];
            var thick = new float[nw];
            for (int i = 0; i < nw; i++)
            {
                Vector3 n = wn[i], p0 = welded[i];
                Vector3 tx = Vector3.Cross(n, Mathf.Abs(n.y) < 0.9f ? Vector3.up : Vector3.right).normalized, ty = Vector3.Cross(n, tx);
                Vector3 start = p0 + n * cell * 1.7f;
                float blocked = 0f;
                foreach (Vector3 d in dirs)
                {
                    Vector3 dir = tx * d.x + ty * d.y + n * d.z;
                    for (int s = 1; s <= steps; s++)
                        if (Solid(start + dir * (s * cell))) { blocked += d.z * (1f - (float)(s - 1) / steps); break; }
                }
                sky[i] = 1f - blocked / weightSum;
                // Tissue behind the surface: in along the normal until the far side.
                float depth = SkinBake.ThickMaxMm;
                for (int s = 0; s < 40; s++)
                {
                    float t = cell * (2.4f + s);
                    if (t * mmPerUnit > SkinBake.ThickMaxMm) break;
                    if (Solid(p0 - n * t)) { depth = t * mmPerUnit; break; }
                }
                thick[i] = depth;
            }

            // Neighbours (welded) to smooth the bake a little: a ray set this small is noisy vertex to vertex.
            var nb = new List<int>[nw];
            for (int t = 0; t < tris.Length; t += 3)
                for (int k = 0; k < 3; k++)
                {
                    int a = weld[tris[t + k]], b = weld[tris[t + (k + 1) % 3]];
                    if (a == b) continue;
                    (nb[a] ??= new List<int>(6)).Add(b);
                    (nb[b] ??= new List<int>(6)).Add(a);
                }
            for (int pass = 0; pass < 3; pass++)
            {
                var s2 = new float[nw];
                var t2 = new float[nw];
                for (int i = 0; i < nw; i++)
                {
                    float a = sky[i] * 2f, b = thick[i] * 2f, w = 2f;
                    if (nb[i] != null) foreach (int j in nb[i]) { a += sky[j]; b += thick[j]; w += 1f; }
                    s2[i] = a / w; t2[i] = b / w;
                }
                sky = s2; thick = t2;
            }
            // Curvature (1/mm): how fast the normal turns along the edges that meet at the vertex.
            var curv = new float[nw];
            for (int i = 0; i < nw; i++)
            {
                if (nb[i] == null) continue;
                float sum = 0f; int count = 0;
                foreach (int j in nb[i])
                {
                    float d = (welded[j] - welded[i]).magnitude * mmPerUnit;
                    if (d < 1e-4f) continue;
                    sum += (wn[j] - wn[i]).magnitude / d; count++;
                }
                curv[i] = count > 0 ? sum / count : 0f;
            }

            var normals = new Vector3[nv];
            var colours = new Color32[nv];
            for (int i = 0; i < nv; i++)
            {
                int w = weld[i];
                normals[i] = wn[w];
                colours[i] = new Color32((byte)Mathf.RoundToInt(Mathf.Clamp01(sky[w]) * 255f),
                                         (byte)Mathf.RoundToInt(Mathf.Clamp01(thick[w] / SkinBake.ThickMaxMm) * 255f),
                                         (byte)Mathf.RoundToInt(Mathf.Clamp01(curv[w] / SkinBake.CurvMax) * 255f), 255);
            }
            var mesh = new Mesh { name = src.name + " (baked)", hideFlags = HideFlags.DontSave, indexFormat = src.indexFormat };
            mesh.SetVertices(verts);
            mesh.SetNormals(normals);
            var uv = new List<Vector2>();
            src.GetUVs(0, uv);
            if (uv.Count == nv) mesh.SetUVs(0, uv);
            mesh.SetColors(colours);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
