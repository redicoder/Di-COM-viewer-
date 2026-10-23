using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The dissection room round the body: the steel table he lies on (top, rim, legs) just under the table plane
    /// (TissueSheets.SetTable) and the floor 90 cm below it, built in body millimetres under the body's volume so
    /// they turn with him. The table's shader (LabTable.shader) casts the body's shadow on it by marching the
    /// photo volume towards the light, and darkens where he touches it.
    /// </summary>
    [RequireComponent(typeof(PhotoBody))]
    public class LabRoom : MonoBehaviour
    {
        public Color tableColour = new Color(0.74f, 0.76f, 0.78f);     // brushed stainless steel
        public Color floorColour = new Color(0.36f, 0.36f, 0.35f);
        [Tooltip("The floor this far below the table top, mm.")]
        public float floorDropMm = 900f;

        private PhotoBody body;
        private Transform root;
        private Material tableMaterial, floorMaterial;
        private readonly List<Mesh> meshes = new List<Mesh>();
        private Vector3 normalBody;

        private PhotoBody Body => body != null ? body : body = GetComponent<PhotoBody>();

        /// <summary>Builds the room for a body of this size (mm) lying on this table plane (unit normal, offset).</summary>
        public void Build(Vector3 sizeMm, Vector4 plane)
        {
            Clear();
            Shader shader = Shader.Find("DicomViewer/LabTable");
            if (shader == null || Body == null || Body.Volume == null) return;
            root = new GameObject("Lab room") { hideFlags = HideFlags.DontSave }.transform;
            root.SetParent(Body.Volume, false);
            root.localPosition = -0.5f * Vector3.one;                             // children are in body millimetres
            root.localScale = new Vector3(1f / sizeMm.x, 1f / sizeMm.y, 1f / sizeMm.z);
            Vector3 n = plane;
            normalBody = n.normalized;
            tableMaterial = Make(shader, "Lab table", tableColour, 0.55f, 0.42f, sizeMm, 700f);
            floorMaterial = Make(shader, "Lab floor", floorColour, 0f, 0.15f, sizeMm, 1600f);

            // The plane's normal lies along one body axis: up for a head on a tray, forward for a body on his back.
            int k = Mathf.Abs(n.x) >= Mathf.Abs(n.y) && Mathf.Abs(n.x) >= Mathf.Abs(n.z) ? 0 : Mathf.Abs(n.y) >= Mathf.Abs(n.z) ? 1 : 2;
            float sign = Mathf.Sign(n[k]);
            float top = plane.w / sign;                                            // the surface's coordinate along k
            int a1 = (k + 1) % 3, a2 = (k + 2) % 3;
            float margin = sizeMm.y > 500f ? 160f : 110f, thick = 4f, rim = 14f, wall = 3f, leg = 45f;
            Vector3 lo = -Vector3.one * margin, hi = sizeMm + Vector3.one * margin;

            var boxes = new List<(Vector3, Vector3)>();
            Vector3 Set(Vector3 v, int axis, float value) { v[axis] = value; return v; }
            boxes.Add((Set(lo, k, top - thick * sign), Set(hi, k, top)));                          // the top
            Vector3 rlo = Set(lo, k, top), rhi = Set(hi, k, top + rim * sign);                     // the rim
            boxes.Add((rlo, Set(rhi, a1, lo[a1] + wall)));
            boxes.Add((Set(rlo, a1, hi[a1] - wall), rhi));
            boxes.Add((rlo, Set(rhi, a2, lo[a2] + wall)));
            boxes.Add((Set(rlo, a2, hi[a2] - wall), rhi));
            foreach (float u in new[] { lo[a1] + 30f, hi[a1] - 30f - leg })                        // the legs
            foreach (float w in new[] { lo[a2] + 30f, hi[a2] - 30f - leg })
            {
                Vector3 l0 = Set(Set(Set(Vector3.zero, a1, u), a2, w), k, top - (floorDropMm - 1f) * sign);
                Vector3 l1 = Set(Set(Set(Vector3.zero, a1, u + leg), a2, w + leg), k, top - thick * sign);
                boxes.Add((l0, l1));
            }
            AddPart("Table", BoxMesh(boxes), tableMaterial);

            Vector3 flo = Set(Set(Set(Vector3.zero, a1, lo[a1] - 2500f), a2, lo[a2] - 2500f), k, top - floorDropMm * sign);
            Vector3 fhi = Set(Set(Set(Vector3.zero, a1, hi[a1] + 2500f), a2, hi[a2] + 2500f), k, top - (floorDropMm + 6f) * sign);
            AddPart("Floor", BoxMesh(new List<(Vector3, Vector3)> { (flo, fhi) }), floorMaterial);
        }

        private Material Make(Shader shader, string name, Color colour, float metallic, float smooth, Vector3 sizeMm, float shadowRange)
        {
            var m = new Material(shader) { name = name };
            m.SetColor("_Color", colour);
            m.SetFloat("_Metallic", metallic);
            m.SetFloat("_Smoothness", smooth);
            m.SetVector("_SizeMm", sizeMm);
            m.SetFloat("_ShadowRange", shadowRange);
            m.SetTexture("_BodyTex", Body.ColourTexture);
            return m;
        }

        private void AddPart(string name, Mesh mesh, Material material)
        {
            var go = new GameObject(name) { hideFlags = HideFlags.DontSave };
            go.transform.SetParent(root, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = material;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            meshes.Add(mesh);
        }

        // Boxes with flat faces (every face its own vertices), wound to face outward.
        private static Mesh BoxMesh(List<(Vector3 lo, Vector3 hi)> boxes)
        {
            var v = new List<Vector3>();
            var t = new List<int>();
            foreach (var (lo0, hi0) in boxes)
            {
                Vector3 a = Vector3.Min(lo0, hi0), b = Vector3.Max(lo0, hi0), centre = (a + b) * 0.5f;
                var c = new Vector3[8];
                for (int i = 0; i < 8; i++) c[i] = new Vector3((i & 1) == 0 ? a.x : b.x, (i & 2) == 0 ? a.y : b.y, (i & 4) == 0 ? a.z : b.z);
                int[] q = { 0, 2, 3, 1, 4, 5, 7, 6, 0, 1, 5, 4, 2, 6, 7, 3, 0, 4, 6, 2, 1, 3, 7, 5 };
                for (int f = 0; f < 6; f++)
                {
                    Vector3 p0 = c[q[4 * f]], p1 = c[q[4 * f + 1]], p2 = c[q[4 * f + 2]], p3 = c[q[4 * f + 3]];
                    bool outward = Vector3.Dot(Vector3.Cross(p1 - p0, p2 - p0), (p0 + p1 + p2 + p3) * 0.25f - centre) >= 0f;
                    int o = v.Count;
                    v.Add(p0); v.Add(p1); v.Add(p2); v.Add(p3);
                    if (outward) { t.Add(o); t.Add(o + 1); t.Add(o + 2); t.Add(o); t.Add(o + 2); t.Add(o + 3); }
                    else { t.Add(o); t.Add(o + 2); t.Add(o + 1); t.Add(o); t.Add(o + 3); t.Add(o + 2); }
                }
            }
            var mesh = new Mesh { name = "Room part", hideFlags = HideFlags.DontSave };
            if (v.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.SetVertices(v);
            mesh.SetTriangles(t, 0);
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        private void LateUpdate() => PushLight();

        /// <summary>The light's direction in body axes, for the shadow (LateUpdate; editor snapshots call it).</summary>
        public void PushLight()
        {
            if (root == null || Body == null || Body.Volume == null) return;
            Light sun = RenderSettings.sun;
            if (sun == null)
                foreach (Light l in FindObjectsByType<Light>(FindObjectsSortMode.None))
                    if (l.type == LightType.Directional) { sun = l; break; }
            Vector3 toLight = sun != null ? -sun.transform.forward : Vector3.up;
            Vector3 local = Body.Volume.InverseTransformDirection(toLight);
            Vector3 size = Body.Space.SizeMm;
            Vector3 mm = new Vector3(local.x * size.x, local.y * size.y, local.z * size.z).normalized;   // in millimetre axes
            Material src = Body.Material;
            foreach (Material m in new[] { tableMaterial, floorMaterial })
            {
                if (m == null) continue;
                m.SetVector("_LightDirBody", mm);
                m.SetVector("_NormalBody", normalBody);
                if (src == null) continue;
                m.SetFloat("_LayersOn", src.HasFloat("_LayersOn") ? src.GetFloat("_LayersOn") : 0f);
                foreach (string n in new[] { "_LabelTex", "_LabelHideTex" })
                {
                    Texture t = src.HasTexture(n) ? src.GetTexture(n) : null;
                    if (t != null) m.SetTexture(n, t);
                }
            }
        }

        public void Clear()
        {
            if (root != null) Kill(root.gameObject);
            root = null;
            foreach (Mesh m in meshes) if (m != null) Kill(m);
            meshes.Clear();
            if (tableMaterial != null) Kill(tableMaterial);
            if (floorMaterial != null) Kill(floorMaterial);
            tableMaterial = floorMaterial = null;
        }

        private void OnDestroy() => Clear();

        private static void Kill(Object o)
        {
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
