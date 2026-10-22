using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The instruments seen in the Anatomy Lab, at real size where the finger or pointer is: a scalpel (No. 3 handle,
    /// No. 10 blade) for the Scalpel tool, its belly pressed into the skin along the cut, and a gloved right hand
    /// pinching the tissue for the Pull tool. The tools call ShowScalpel / ShowHand every frame they want one; what
    /// was not asked for is hidden. Both are built in code (no model files) and cast soft shadows on the body
    /// (capsules handed to PhotoBody.shader). The mouse cursor hides while an instrument stands in for it.
    /// </summary>
    [RequireComponent(typeof(PhotoBody))]
    public class LabInstruments : MonoBehaviour
    {
        [Tooltip("The scalpel handle's lean back from the skin's normal, degrees (60: the handle 30 degrees above the skin).")]
        [Range(30f, 75f)] public float scalpelLeanDeg = 60f;
        [Tooltip("The scalpel turned about the cut so its side faces the viewer, degrees.")]
        [Range(0f, 45f)] public float scalpelRollDeg = 38f;
        public bool hideCursor = true;

        public const int MaxShadowCapsules = 8;

        private PhotoBody body;
        private Transform scalpel, scalpelPose, hand, handPose;
        private MeshFilter handFilter;
        private Mesh handOpen, handClosed;
        private Vector3 bladeLowestMm;
        private bool scalpelWanted, handWanted, cursorHidden;
        private Vector3 scalpelDir;
        private readonly List<Material> materials = new List<Material>();
        private readonly List<(Transform space, Vector3 a, Vector3 b, float r)> scalpelCaps = new List<(Transform, Vector3, Vector3, float)>();
        private List<(Vector3 a, Vector3 b, float r)> handCapsOpen, handCapsClosed, handCaps;
        private readonly Vector4[] capA = new Vector4[MaxShadowCapsules], capB = new Vector4[MaxShadowCapsules];

        private PhotoBody Body => body != null ? body : body = GetComponent<PhotoBody>();

        private void OnDisable()
        {
            if (scalpel != null) scalpel.gameObject.SetActive(false);
            if (hand != null) hand.gameObject.SetActive(false);
            scalpelWanted = handWanted = false;
            SetCursorHidden(false);
            PushShadows(0);
        }

        private void OnDestroy() => Release();

        /// <summary>Destroys the instruments (they live outside the lab's hierarchy); the next Show builds them again.</summary>
        public void Release()
        {
            if (scalpel != null) Kill(scalpel.gameObject);
            if (hand != null) Kill(hand.gameObject);
            foreach (Mesh mesh in new[] { handOpen, handClosed }) if (mesh != null) Kill(mesh);
            foreach (Material m in materials) if (m != null) Kill(m);
            materials.Clear();
            scalpelCaps.Clear();
            scalpel = hand = null;
        }

        private static void Kill(Object o)
        {
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }

        /// <summary>
        /// The scalpel at a point on the skin: its belly pressMm below the surface (negative: hovering above it),
        /// its edge facing dirWorld (the way the cut goes; zero keeps the last direction).
        /// </summary>
        public void ShowScalpel(Vector3 pointWorld, Vector3 normalWorld, Vector3 dirWorld, float pressMm)
        {
            if (!Ensure()) return;
            scalpelWanted = true;
            Camera cam = Camera.main;
            Vector3 n = normalWorld.normalized;
            Vector3 v = dirWorld - Vector3.Dot(dirWorld, n) * n;
            if (v.sqrMagnitude < 1e-10f) v = scalpelDir;
            if (v.sqrMagnitude < 1e-10f && cam != null) v = cam.transform.right;
            v -= Vector3.Dot(v, n) * n;
            if (v.sqrMagnitude < 1e-10f) v = Vector3.Cross(n, Vector3.forward);
            v.Normalize();
            scalpelDir = scalpelDir.sqrMagnitude < 1e-10f ? v : Vector3.Slerp(scalpelDir, v, 1f - Mathf.Exp(-Time.deltaTime * 14f));
            scalpelDir = (scalpelDir - Vector3.Dot(scalpelDir, n) * n).normalized;

            // Root: x along the cut, y out of the skin; rolled about the cut so the blade's side faces the camera.
            Quaternion rot = Quaternion.LookRotation(Vector3.Cross(scalpelDir, n), n);
            if (cam != null)
            {
                Vector3 toCam = (cam.transform.position - pointWorld).normalized;
                Quaternion plus = Quaternion.AngleAxis(scalpelRollDeg, scalpelDir) * rot;
                Quaternion minus = Quaternion.AngleAxis(-scalpelRollDeg, scalpelDir) * rot;
                rot = Mathf.Abs(Vector3.Dot(plus * Vector3.forward, toCam)) >= Mathf.Abs(Vector3.Dot(minus * Vector3.forward, toCam)) ? plus : minus;
            }
            scalpel.SetPositionAndRotation(pointWorld, rot);
            scalpel.localScale = Vector3.one * WorldPerMm();
            Quaternion lean = Quaternion.Euler(0f, 0f, scalpelLeanDeg);
            scalpelPose.localRotation = lean;
            scalpelPose.localPosition = -(lean * bladeLowestMm) - Vector3.up * pressMm;
        }

        /// <summary>The gloved hand pinching at a point (gripping) or about to (open), reaching in from the viewer's lower right.</summary>
        public void ShowHand(Vector3 pinchWorld, Vector3 normalWorld, bool gripping)
        {
            if (!Ensure()) return;
            handWanted = true;
            Camera cam = Camera.main;
            Vector3 n = normalWorld.normalized;
            Vector3 f = cam != null ? cam.transform.up * 0.8f - cam.transform.right * 0.45f + cam.transform.forward * 0.6f : Vector3.forward;
            f -= Vector3.Dot(f, n) * n;
            if (f.sqrMagnitude < 1e-8f) f = Vector3.Cross(n, Vector3.right);
            Quaternion rot = Quaternion.LookRotation(f.normalized, n);
            if (hand.gameObject.activeSelf) rot = Quaternion.Slerp(hand.rotation, rot, 1f - Mathf.Exp(-Time.deltaTime * 10f));
            float perMm = WorldPerMm();
            hand.SetPositionAndRotation(pinchWorld + n * ((gripping ? 4f : 12f) * perMm), rot);
            hand.localScale = Vector3.one * (perMm * 1000f);          // the hand is built in metres
            Mesh want = gripping ? handClosed : handOpen;
            if (handFilter.sharedMesh != want) handFilter.sharedMesh = want;
            handCaps = gripping ? handCapsClosed : handCapsOpen;
        }

        private void LateUpdate() => Apply();

        /// <summary>Shows what the tools asked for this frame and hides the rest (LateUpdate; editor snapshots call it).</summary>
        public void Apply()
        {
            if (scalpel != null && scalpel.gameObject.activeSelf != scalpelWanted) scalpel.gameObject.SetActive(scalpelWanted);
            if (hand != null && hand.gameObject.activeSelf != handWanted) hand.gameObject.SetActive(handWanted);
            SetCursorHidden(hideCursor && (scalpelWanted || handWanted) && !ViewerUi.PointerOverUi);

            int count = 0;
            if (scalpelWanted)
                foreach (var c in scalpelCaps)
                    AddCap(ref count, c.space.TransformPoint(c.a), c.space.TransformPoint(c.b), c.r * c.space.lossyScale.x);
            if (handWanted && handCaps != null)
                foreach (var c in handCaps)
                    AddCap(ref count, hand.TransformPoint(c.a), hand.TransformPoint(c.b), c.r * hand.lossyScale.x);
            PushShadows(count);
            scalpelWanted = handWanted = false;
        }

        private void AddCap(ref int count, Vector3 a, Vector3 b, float r)
        {
            if (count >= MaxShadowCapsules) return;
            capA[count] = new Vector4(a.x, a.y, a.z, r);
            capB[count] = b;
            count++;
        }

        private void PushShadows(int count)
        {
            Material m = Body != null ? Body.Material : null;
            if (m == null) return;
            m.SetVectorArray("_InstrA", capA);
            m.SetVectorArray("_InstrB", capB);
            m.SetFloat("_InstrCount", count);
        }

        private void SetCursorHidden(bool hidden)
        {
            if (hidden == cursorHidden) return;
            cursorHidden = hidden;
            Cursor.visible = !hidden;
        }

        private float WorldPerMm()
        {
            PhotoBody b = Body;
            return b != null && b.Volume != null ? b.Space.WorldPerMm(b.Volume) : 0.001f;
        }

        // ------------------------------------------------------------------------------------------------ building

        private bool Ensure()
        {
            if (scalpel != null) return true;
            Shader shader = Shader.Find("DicomViewer/LabInstrument");
            if (shader == null) return false;
            Build(shader);
            return true;
        }

        /// <summary>Makes the instruments (also used by the editor snapshots, outside Play mode).</summary>
        public void Build(Shader shader)
        {
            Material Mat(string name, Color c, float metallic, float smooth, float sheen, float wrap)
            {
                var m = new Material(shader) { name = name };
                m.SetColor("_Color", c);
                m.SetFloat("_Metallic", metallic);
                m.SetFloat("_Smoothness", smooth);
                m.SetFloat("_Sheen", sheen);
                m.SetFloat("_Wrap", wrap);
                materials.Add(m);
                return m;
            }
            Material blade = Mat("Scalpel blade", new Color(0.78f, 0.79f, 0.8f), 1f, 0.9f, 0f, 0f);
            Material handle = Mat("Scalpel handle", new Color(0.62f, 0.63f, 0.65f), 1f, 0.7f, 0f, 0f);
            handle.SetVector("_Ridges", new Vector4(64f, 104f, 2f, 1f));
            Material glove = Mat("Nitrile glove", new Color(0.30f, 0.40f, 0.70f), 0f, 0.5f, 0.5f, 0.45f);
            Material sleeve = Mat("Gown sleeve", new Color(0.22f, 0.45f, 0.42f), 0f, 0.1f, 0.2f, 0.5f);

            // Scalpel, in millimetres: blade tip at the origin, the handle up +y, the cutting edge on the -x side.
            var root = new GameObject("Scalpel") { hideFlags = HideFlags.DontSave };
            scalpel = root.transform;
            scalpelPose = new GameObject("Pose") { hideFlags = HideFlags.DontSave }.transform;
            scalpelPose.SetParent(scalpel, false);
            AddPart(scalpelPose, "Blade", ScalpelBlade(out bladeLowestMm), blade);
            AddPart(scalpelPose, "Handle", ScalpelHandle(), handle);
            scalpelCaps.Add((scalpelPose, new Vector3(-1.5f, 4f, 0f), new Vector3(-1f, 28f, 0f), 3f));
            scalpelCaps.Add((scalpelPose, new Vector3(0f, 32f, 0f), new Vector3(0f, 148f, 0f), 3.5f));
            root.SetActive(false);

            var handRoot = new GameObject("Gloved hand") { hideFlags = HideFlags.DontSave };
            hand = handRoot.transform;
            handOpen = Hand(0.034f, out handCapsOpen);
            handClosed = Hand(0.019f, out handCapsClosed);
            handCaps = handCapsClosed;
            handFilter = handRoot.AddComponent<MeshFilter>();
            handFilter.sharedMesh = handClosed;
            var hr = handRoot.AddComponent<MeshRenderer>();
            hr.sharedMaterials = new[] { glove, sleeve };
            hr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            handRoot.SetActive(false);
        }

        private static void AddPart(Transform parent, string name, Mesh mesh, Material mat)
        {
            var go = new GameObject(name) { hideFlags = HideFlags.DontSave };
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        // No. 10 blade: straight spine, a broad curved belly ending in the point; ground thin toward the edge.
        private Mesh ScalpelBlade(out Vector3 lowest)
        {
            Vector2[] outline =
            {
                new Vector2(1.2f, 0f), new Vector2(2.0f, 1.5f), new Vector2(2.5f, 4f), new Vector2(2.6f, 8f), new Vector2(2.6f, 30f),
                new Vector2(2.0f, 33f), new Vector2(-2.4f, 33f), new Vector2(-3.6f, 29f), new Vector2(-4.9f, 24f),
                new Vector2(-5.4f, 18f), new Vector2(-5.3f, 13f), new Vector2(-4.8f, 8.5f), new Vector2(-3.9f, 5f),
                new Vector2(-2.6f, 2.4f), new Vector2(-1.0f, 0.6f),
            };
            var half = new float[outline.Length];
            for (int i = 0; i < outline.Length; i++) half[i] = i >= 9 || i == 0 ? 0.03f : 0.2f;   // the edge is ground thin
            var mb = new MeshBuilder(1);
            mb.Extrude(outline, half, new Vector2(0f, 16f), 0.2f);

            // The point of the belly that meets the skin once the handle leans back.
            Quaternion lean = Quaternion.Euler(0f, 0f, scalpelLeanDeg);
            lowest = outline[0];
            float best = float.MaxValue;
            foreach (Vector2 p in outline)
            {
                float y = (lean * (Vector3)p).y;
                if (y < best) { best = y; lowest = p; }
            }
            return mb.Build("Scalpel blade");
        }

        // No. 3 handle: a narrow fitting for the blade, then a flat grip with ridges, 125 mm long.
        private static Mesh ScalpelHandle()
        {
            Vector2[] outline =
            {
                new Vector2(-2.4f, 26f), new Vector2(2.4f, 26f), new Vector2(2.6f, 44f), new Vector2(4.6f, 56f),
                new Vector2(4.8f, 140f), new Vector2(4.2f, 148f), new Vector2(2.6f, 151f), new Vector2(-2.6f, 151f),
                new Vector2(-4.2f, 148f), new Vector2(-4.8f, 140f), new Vector2(-4.6f, 56f), new Vector2(-2.6f, 44f),
            };
            var half = new float[outline.Length];
            for (int i = 0; i < outline.Length; i++) half[i] = outline[i].y < 45f ? 0.9f : 1.25f;
            var mb = new MeshBuilder(1);
            mb.Extrude(outline, half, new Vector2(0f, 95f), 1.4f);
            return mb.Build("Scalpel handle");
        }

        // A gloved right hand in a pinch (HandMesh: one smooth surface), with the gown's sleeve behind it.
        private static Mesh Hand(float sep, out List<(Vector3 a, Vector3 b, float r)> caps)
        {
            var verts = new List<Vector3>();
            var tris = new List<int>();
            HandMesh.Glove(sep, verts, tris, out Vector3 pinch, out caps);
            var mb = new MeshBuilder(2);
            mb.Append(verts, tris, 0);
            mb.Sub = 1;
            mb.Frustum(new Vector3(0.003f, 0.004f, -0.060f) - pinch, new Vector3(0f, 0.03f, -0.36f) - pinch, 0.036f, 0.052f, 24);
            return mb.Build(sep > 0.025f ? "Hand (open)" : "Hand (pinching)");
        }

        /// <summary>Triangle lists for the instruments, each face wound to face away from a given inside point.</summary>
        private sealed class MeshBuilder
        {
            private readonly List<Vector3> v = new List<Vector3>();
            private readonly List<int>[] sub;
            public int Sub;

            public MeshBuilder(int submeshes)
            {
                sub = new List<int>[submeshes];
                for (int i = 0; i < submeshes; i++) sub[i] = new List<int>();
            }

            private int Add(Vector3 p)
            {
                v.Add(p);
                return v.Count - 1;
            }

            /// <summary>A ready-made surface (shared vertices) into a submesh.</summary>
            public void Append(List<Vector3> vertices, List<int> triangles, int submesh)
            {
                int o = v.Count;
                v.AddRange(vertices);
                foreach (int i in triangles) sub[submesh].Add(o + i);
            }

            private void Tri(int a, int b, int c, Vector3 outward)
            {
                List<int> t = sub[Sub];
                if (Vector3.Dot(Vector3.Cross(v[b] - v[a], v[c] - v[a]), outward) >= 0f) { t.Add(a); t.Add(b); t.Add(c); }
                else { t.Add(a); t.Add(c); t.Add(b); }
            }

            private void Quad(int a, int b, int c, int d, Vector3 inside)
            {
                Tri(a, b, c, (v[a] + v[b] + v[c]) / 3f - inside);
                Tri(a, c, d, (v[a] + v[c] + v[d]) / 3f - inside);
            }

            /// <summary>A unit sphere through matrix m (an ellipsoid), shared vertices so the normals come out smooth.</summary>
            public void Ellipsoid(Matrix4x4 m, int seg, int rings)
            {
                Vector3 centre = m.MultiplyPoint3x4(Vector3.zero);
                int top = Add(m.MultiplyPoint3x4(Vector3.up));
                int first = v.Count;
                for (int r = 1; r < rings; r++)
                {
                    float th = Mathf.PI * r / rings;
                    for (int s = 0; s < seg; s++)
                    {
                        float ph = 2f * Mathf.PI * s / seg;
                        Add(m.MultiplyPoint3x4(new Vector3(Mathf.Sin(th) * Mathf.Cos(ph), Mathf.Cos(th), Mathf.Sin(th) * Mathf.Sin(ph))));
                    }
                }
                int bottom = Add(m.MultiplyPoint3x4(Vector3.down));
                int Ring(int r, int s) => first + (r - 1) * seg + (s % seg);
                for (int s = 0; s < seg; s++)
                {
                    Tri(top, Ring(1, s), Ring(1, s + 1), v[top] - centre);
                    Tri(bottom, Ring(rings - 1, s + 1), Ring(rings - 1, s), v[bottom] - centre);
                    for (int r = 1; r < rings - 1; r++) Quad(Ring(r, s), Ring(r, s + 1), Ring(r + 1, s + 1), Ring(r + 1, s), centre);
                }
            }

            /// <summary>An open tapered tube from a (radius ra) to b (radius rb); spheres close the ends.</summary>
            public void Frustum(Vector3 a, Vector3 b, float ra, float rb, int seg)
            {
                Vector3 axis = (b - a).normalized;
                Vector3 x = Vector3.Cross(axis, Mathf.Abs(axis.y) < 0.9f ? Vector3.up : Vector3.right).normalized;
                Vector3 y = Vector3.Cross(axis, x);
                int first = v.Count;
                for (int s = 0; s < seg; s++)
                {
                    float ph = 2f * Mathf.PI * s / seg;
                    Vector3 d = x * Mathf.Cos(ph) + y * Mathf.Sin(ph);
                    Add(a + d * ra);
                    Add(b + d * rb);
                }
                for (int s = 0; s < seg; s++)
                {
                    int i0 = first + 2 * s, i1 = first + 2 * ((s + 1) % seg);
                    Vector3 mid = (v[i0] + v[i1] + v[i0 + 1] + v[i1 + 1]) / 4f;
                    Vector3 onAxis = a + axis * Vector3.Dot(mid - a, axis);
                    Quad(i0, i1, i1 + 1, i0 + 1, onAxis);
                }
            }

            /// <summary>
            /// A flat part from a 2D outline in the xy plane (star-shaped around centre): half its thickness at each
            /// outline point (thinner at a ground edge) and at the centre, faces at +z and -z, and the rim.
            /// </summary>
            public void Extrude(Vector2[] outline, float[] half, Vector2 centre, float centreHalf)
            {
                int n = outline.Length;
                foreach (float sign in new[] { 1f, -1f })
                {
                    int c = Add(new Vector3(centre.x, centre.y, sign * centreHalf));
                    int first = v.Count;
                    for (int i = 0; i < n; i++) Add(new Vector3(outline[i].x, outline[i].y, sign * half[i]));
                    for (int i = 0; i < n; i++) Tri(c, first + i, first + (i + 1) % n, new Vector3(0f, 0f, sign));
                }
                Vector3 inside = new Vector3(centre.x, centre.y, 0f);
                for (int i = 0; i < n; i++)
                {
                    int j = (i + 1) % n;
                    int a = Add(new Vector3(outline[i].x, outline[i].y, half[i]));
                    int b = Add(new Vector3(outline[j].x, outline[j].y, half[j]));
                    int bb = Add(new Vector3(outline[j].x, outline[j].y, -half[j]));
                    int aa = Add(new Vector3(outline[i].x, outline[i].y, -half[i]));
                    Quad(a, b, bb, aa, inside);
                }
            }

            public Mesh Build(string name)
            {
                var mesh = new Mesh { name = name, hideFlags = HideFlags.DontSave };
                if (v.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
                mesh.SetVertices(v);
                mesh.subMeshCount = sub.Length;
                for (int i = 0; i < sub.Length; i++) mesh.SetTriangles(sub[i], i);
                mesh.RecalculateNormals();
                mesh.RecalculateBounds();
                return mesh;
            }
        }
    }
}
