using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The skin that has been taken in hand (TissueSheet, physics): up to four sheets over the body, drawn as meshes
    /// coloured from the photos, with the body's own copy of that tissue hidden (PhotoBody.shader reads the hidden
    /// maps). A steel tray under the neck catches what comes off. Everything lives in the body's millimetre space and
    /// turns with it; gravity is the real one, so turning the head moves what hangs and slides what lies loose.
    /// </summary>
    [RequireComponent(typeof(PhotoBody))]
    public class TissueSheets : MonoBehaviour
    {
        public const int MaxSheets = 4;

        [Tooltip("Grid spacing of a sheet, mm.")]
        public float spacingMm = 1.5f;
        [Tooltip("Thickness of the skin and fat a sheet holds, mm.")]
        public float thicknessMm = 5f;
        [Tooltip("Pinching works this close to a scalpel cut, mm.")]
        public float pinchNearCutMm = 6f;

        private PhotoBody body;
        private MaskVolume mask;
        private readonly List<TissueSheet> sheets = new List<TissueSheet>();
        private readonly List<MeshFilter> meshes = new List<MeshFilter>();
        private Transform root;
        private GameObject tray;
        private Material sheetMaterial, trayMaterial;
        private Texture2DArray maps;
        private ushort[] mapData;
        private readonly Vector4[] origins = new Vector4[MaxSheets], e1s = new Vector4[MaxSheets], e2s = new Vector4[MaxSheets], e3s = new Vector4[MaxSheets];
        private Field field;
        private int heldSheet = -1;

        public int Count => sheets.Count;
        public IReadOnlyList<TissueSheet> Sheets => sheets;
        public bool Holding => heldSheet >= 0;

        private sealed class Field : ITissueField
        {
            private readonly PhotoBody b;
            private readonly Vector3 inv;
            public Field(PhotoBody body)
            {
                b = body;
                Vector3 s = body.Space.SizeMm;
                inv = new Vector3(1f / s.x, 1f / s.y, 1f / s.z);
            }
            public float Alpha(Vector3 mm) => b.AlphaAt(Vector3.Scale(mm, inv));
            public float SkinDepth(Vector3 mm) => b.SkinDepthMm(mm);
            public SkinDepthGrid Grid => b.SkinGrid;
        }

        /// <summary>After the body has loaded (AnatomyLab; editor snapshots call it directly).</summary>
        public void Attach(PhotoBody photoBody, MaskVolume maskVolume)
        {
            body = photoBody;
            mask = maskVolume;
            Clear();
            field = new Field(body);
            if (root != null) Kill(root.gameObject);
            root = new GameObject("Tissue sheets") { hideFlags = HideFlags.DontSave }.transform;
            root.SetParent(body.Volume, false);
            Vector3 size = body.Space.SizeMm;
            root.localPosition = -0.5f * Vector3.one;                        // children are in body millimetres
            root.localScale = new Vector3(1f / size.x, 1f / size.y, 1f / size.z);
            if (sheetMaterial == null)
            {
                Shader s = Shader.Find("DicomViewer/TissueSheet");
                if (s != null) sheetMaterial = new Material(s) { name = "Tissue sheet" };
            }
            MakeTray(size);
            if (maps == null)
            {
                maps = new Texture2DArray(TissueSheet.N, TissueSheet.N, MaxSheets, GraphicsFormat.R16G16_SFloat, TextureCreationFlags.None)
                {
                    wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, name = "Tissue sheet maps",
                };
                mapData = new ushort[TissueSheet.N * TissueSheet.N * 2];
            }
            PushToBody();
        }

        public bool Ready => body != null && body.IsLoaded && body.HasSkinDepth && field != null && sheetMaterial != null;

        // A stainless tray under the neck: what comes off lands here.
        private void MakeTray(Vector3 size)
        {
            if (tray != null) Kill(tray);
            Shader s = Shader.Find("DicomViewer/LabInstrument");
            if (s == null) return;
            if (trayMaterial == null)
            {
                trayMaterial = new Material(s) { name = "Steel tray" };
                trayMaterial.SetColor("_Color", new Color(0.62f, 0.64f, 0.66f));
                trayMaterial.SetFloat("_Metallic", 1f);
                trayMaterial.SetFloat("_Smoothness", 0.55f);
            }
            Vector3 min = new Vector3(-70f, TrayTop - 3f, -230f), max = new Vector3(size.x + 70f, TrayTop, size.z + 50f);
            var v = new List<Vector3>();
            var t = new List<int>();
            void Box(Vector3 a, Vector3 b)
            {
                int o = v.Count;
                for (int k = 0; k < 8; k++) v.Add(new Vector3((k & 1) == 0 ? a.x : b.x, (k & 2) == 0 ? a.y : b.y, (k & 4) == 0 ? a.z : b.z));
                int[] q = { 0, 2, 3, 1, 4, 5, 7, 6, 0, 1, 5, 4, 2, 6, 7, 3, 0, 4, 6, 2, 1, 3, 7, 5 };
                Vector3 centre = (a + b) * 0.5f;
                void Tri(int i, int j, int k)
                {
                    // Unity draws clockwise faces: the cross product points at the viewer, so out of the box.
                    Vector3 n = Vector3.Cross(v[j] - v[i], v[k] - v[i]);
                    if (Vector3.Dot(n, (v[i] + v[j] + v[k]) / 3f - centre) >= 0f) { t.Add(i); t.Add(j); t.Add(k); }
                    else { t.Add(i); t.Add(k); t.Add(j); }
                }
                for (int f = 0; f < 6; f++)
                {
                    Tri(o + q[4 * f], o + q[4 * f + 1], o + q[4 * f + 2]);
                    Tri(o + q[4 * f], o + q[4 * f + 2], o + q[4 * f + 3]);
                }
            }
            Box(min, max);
            const float rim = 14f, wall = 2f;
            Box(new Vector3(min.x, max.y, min.z), new Vector3(max.x, max.y + rim, min.z + wall));
            Box(new Vector3(min.x, max.y, max.z - wall), new Vector3(max.x, max.y + rim, max.z));
            Box(new Vector3(min.x, max.y, min.z), new Vector3(min.x + wall, max.y + rim, max.z));
            Box(new Vector3(max.x - wall, max.y, min.z), new Vector3(max.x, max.y + rim, max.z));
            var mesh = new Mesh { name = "Tray", hideFlags = HideFlags.DontSave };
            mesh.SetVertices(v);
            mesh.SetTriangles(t, 0);
            // Flat faces: split so each face has its own normals.
            var flat = new Mesh { name = "Tray", hideFlags = HideFlags.DontSave };
            var fv = new List<Vector3>();
            var ft = new List<int>();
            for (int i = 0; i < t.Count; i++) { fv.Add(v[t[i]]); ft.Add(i); }
            flat.SetVertices(fv);
            flat.SetTriangles(ft, 0);
            flat.RecalculateNormals();
            flat.RecalculateBounds();
            Kill(mesh);
            tray = new GameObject("Steel tray") { hideFlags = HideFlags.DontSave };
            tray.transform.SetParent(root, false);
            tray.AddComponent<MeshFilter>().sharedMesh = flat;
            var r = tray.AddComponent<MeshRenderer>();
            r.sharedMaterial = trayMaterial;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            trayMin = new Vector2(min.x + wall, min.z + wall);
            trayMax = new Vector2(max.x - wall, max.z - wall);
        }

        public const float TrayTop = -1.5f;          // body mm: just under the neck's cut
        private Vector2 trayMin, trayMax;

        // ------------------------------------------------------------------------------------------- tools

        /// <summary>
        /// Pinch the skin at a point beside a scalpel cut (world): a sheet takes over that skin and the hand holds it.
        /// False where there is no cut edge to take hold of (intact skin only stretches).
        /// </summary>
        public bool TryPinchSkin(Vector3 hitWorld, Vector3 normalWorld)
        {
            if (!Ready || mask == null) return false;
            Vector3 mm = ToMm(hitWorld);
            if (!NearScalpelCut(mm, pinchNearCutMm)) return false;
            int s = SheetCovering(mm);
            if (s < 0)
            {
                if (sheets.Count >= MaxSheets) return false;
                Vector3 n = body.Space.WorldDirToMm(body.Volume, normalWorld).normalized;
                TissueSheet sheet = TissueSheet.Create(field, mm, n, spacingMm, thicknessMm, p => SheetCovering(p, 0f) >= 0);
                sheet.HiddenAt = HiddenAtMm;
                ApplyTray(sheet);
                foreach (MaskOp op in mask.Ops)
                    if (op.kind == MaskOp.Kind.Capsules)
                        foreach (MaskCapsule c in op.capsules) sheet.CutCapsule(c.a, c.b, c.radius);
                AddSheet(sheet);
                s = sheets.Count - 1;
            }
            int node = sheets[s].NearestNode(mm);
            if (node < 0 || !sheets[s].NearFreeEdge(node, 4)) return false;
            sheets[s].Grab(node);
            heldSheet = s;
            return true;
        }

        /// <summary>Takes hold of a lifted or loose piece of tissue the ray meets first (world ray).</summary>
        public bool TryGrabLoose(Ray ray, float maxDistance)
        {
            if (!Raycast(ray, out SheetHit hit) || hit.distance > maxDistance) return false;
            sheets[hit.sheet].Grab(hit.node);
            heldSheet = hit.sheet;
            return true;
        }

        /// <summary>Takes hold of a given node of a sheet (editor snapshots).</summary>
        public void GrabNode(int sheet, int node)
        {
            if (sheet < 0 || sheet >= sheets.Count) return;
            sheets[sheet].Grab(node);
            heldSheet = sheet;
        }

        public void MoveHand(Vector3 world)
        {
            if (heldSheet >= 0) sheets[heldSheet].MoveHand(ToMm(world));
        }

        public void Release()
        {
            if (heldSheet >= 0 && heldSheet < sheets.Count) sheets[heldSheet].Release();
            heldSheet = -1;
        }

        /// <summary>Where the hand holds the tissue now (world) and the skin's outward normal there.</summary>
        public bool HeldPoint(out Vector3 world, out Vector3 normal)
        {
            world = normal = default;
            if (heldSheet < 0) return false;
            TissueSheet s = sheets[heldSheet];
            int n = s.HeldNode;
            if (n < 0) return false;
            world = ToWorld(s.X[2 * n]);
            normal = ToWorldDir(s.NormalAt(n));
            return true;
        }

        public struct SheetHit
        {
            public int sheet, node;
            public Vector2 grid;
            public float distance;          // world
            public Vector3 point, normal;   // world
        }

        /// <summary>The nearest drawn sheet surface along a world ray.</summary>
        public bool Raycast(Ray ray, out SheetHit hit)
        {
            hit = default;
            if (!Ready) return false;
            Vector3 o = ToMm(ray.origin), d = ToMm(ray.origin + ray.direction) - o;
            float best = float.MaxValue;
            bool any = false;
            for (int s = 0; s < sheets.Count; s++)
            {
                if (!sheets[s].Raycast(o, d, out float t, out Vector2 g, out int node) || t >= best) continue;
                best = t;
                any = true;
                hit = new SheetHit { sheet = s, node = node, grid = g, distance = t, point = ray.GetPoint(t), normal = ToWorldDir(sheets[s].NormalAt(node)) };
            }
            return any;
        }

        /// <summary>The scalpel through lifted tissue: a cut between two points on the same sheet (grid coordinates).</summary>
        public void CutSheet(int sheet, Vector2 from, Vector2 to)
        {
            if (sheet >= 0 && sheet < sheets.Count) sheets[sheet].CutGrid(from, to);
        }

        /// <summary>An incision on the body (mm capsule): sheets lying there are cut with it.</summary>
        public void Incised(Vector3 aMm, Vector3 bMm, float radiusMm)
        {
            foreach (TissueSheet s in sheets) s.CutCapsule(aMm, bMm, radiusMm);
        }

        /// <summary>Is the body's tissue at a volume-cube-local point taken over by a sheet (for picking)?</summary>
        public bool IsHiddenLocal(Vector3 local)
        {
            if (sheets.Count == 0 || body == null) return false;
            return HiddenAtMm(body.Space.UvwToMm(VolumeSpace.LocalToUvw(local)));
        }

        public void Clear()
        {
            heldSheet = -1;
            foreach (TissueSheet s in sheets) s.Dispose();
            sheets.Clear();
            foreach (MeshFilter m in meshes)
                if (m != null)
                {
                    Kill(m.sharedMesh);
                    Kill(m.gameObject);
                }
            meshes.Clear();
            PushToBody();
        }

        // ------------------------------------------------------------------------------------------- update

        private void Update()
        {
            if (!Ready) return;
            Simulate(Time.deltaTime);
        }

        /// <summary>Advances every sheet and draws it (Update; editor snapshots call it with their own clock).</summary>
        public void Simulate(float dt)
        {
            if (!Ready || sheets.Count == 0) return;
            Vector3 g = body.Space.WorldDirToMm(body.Volume, Vector3.down).normalized * 9810f;
            bool mapsChanged = false;
            for (int s = 0; s < sheets.Count; s++)
            {
                TissueSheet sheet = sheets[s];
                bool wasAsleep = sheet.Asleep;
                sheet.Step(dt, g);
                if (!wasAsleep || !sheet.Asleep || sheet.TopologyChanged) sheet.FillMesh(meshes[s].sharedMesh, body.Space.SizeMm);
                mapsChanged |= sheet.HiddenChanged;
            }
            if (mapsChanged) PushToBody();
        }

        private void AddSheet(TissueSheet sheet)
        {
            sheets.Add(sheet);
            var go = new GameObject("Tissue sheet " + sheets.Count) { hideFlags = HideFlags.DontSave };
            go.transform.SetParent(root, false);
            var mf = go.AddComponent<MeshFilter>();
            mf.sharedMesh = new Mesh { name = "Tissue sheet", hideFlags = HideFlags.DontSave };
            mf.sharedMesh.MarkDynamic();
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = sheetMaterial;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            meshes.Add(mf);
            sheet.FillMesh(mf.sharedMesh, body.Space.SizeMm);
            PushToBody();
        }

        private void ApplyTray(TissueSheet s)
        {
            s.TrayY = TrayTop;
            s.TrayMinXZ = trayMin;
            s.TrayMaxXZ = trayMax;
        }

        // The hidden maps and sheet frames to the body's shader; the photo and blood textures to the sheets'.
        private void PushToBody()
        {
            if (body == null || body.Material == null) return;
            Material m = body.Material;
            int count = 0;
            for (int s = 0; s < sheets.Count && s < MaxSheets; s++, count++)
            {
                TissueSheet sh = sheets[s];
                sh.FillHiddenMap(mapData);
                maps.SetPixelData(mapData, 0, s);
                origins[s] = new Vector4(sh.Origin.x, sh.Origin.y, sh.Origin.z, sh.H);
                e1s[s] = new Vector4(sh.E1.x, sh.E1.y, sh.E1.z, sh.T);
                e2s[s] = sh.E2;
                e3s[s] = sh.E3;
            }
            if (maps != null)
            {
                maps.Apply(false, false);
                m.SetTexture("_SheetMaps", maps);
            }
            m.SetVectorArray("_SheetOrigin", origins);
            m.SetVectorArray("_SheetE1", e1s);
            m.SetVectorArray("_SheetE2", e2s);
            m.SetVectorArray("_SheetE3", e3s);
            m.SetFloat("_SheetCount", count);
            if (sheetMaterial != null)
            {
                sheetMaterial.SetTexture("_ColorTex", body.ColourTexture);
                sheetMaterial.SetVector("_SizeMm", body.Space.SizeMm);
                Texture stain = m.GetTexture("_StainTex");
                if (stain != null) sheetMaterial.SetTexture("_StainTex", stain);
                sheetMaterial.SetFloat("_ShowStain", m.GetFloat("_ShowStain"));
            }
        }

        private void LateUpdate()
        {
            // Blood may be switched on or off, and BloodSim binds its stain texture after load.
            if (sheetMaterial != null && body != null && body.Material != null && sheets.Count > 0)
            {
                Texture stain = body.Material.GetTexture("_StainTex");
                if (stain != null) sheetMaterial.SetTexture("_StainTex", stain);
                sheetMaterial.SetFloat("_ShowStain", body.Material.GetFloat("_ShowStain"));
            }
        }

        // ------------------------------------------------------------------------------------------- helpers

        private bool HiddenAtMm(Vector3 mm)
        {
            foreach (TissueSheet s in sheets)
                if (s.HiddenHere(mm)) return true;
            return false;
        }

        private int SheetCovering(Vector3 mm, float marginNodes = 4f)
        {
            for (int s = 0; s < sheets.Count; s++)
                if (sheets[s].Covers(mm, marginNodes)) return s;
            return -1;
        }

        private bool NearScalpelCut(Vector3 mm, float within)
        {
            foreach (MaskOp op in mask.Ops)
            {
                if (op.kind != MaskOp.Kind.Capsules) continue;
                foreach (MaskCapsule c in op.capsules)
                    if (TissueSheet.SegmentDistance(mm, mm, c.a, c.b) < c.radius + within) return true;
            }
            return false;
        }

        public Vector3 ToMm(Vector3 world) => body.Space.UvwToMm(VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(world)));
        public Vector3 ToWorld(Vector3 mm) => body.Volume.TransformPoint(VolumeSpace.UvwToLocal(body.Space.MmToUvw(mm)));
        private Vector3 ToWorldDir(Vector3 mmDir) => (ToWorld(mmDir) - ToWorld(Vector3.zero)).normalized;

        private void OnDestroy()
        {
            Clear();
            if (root != null) Kill(root.gameObject);
            if (sheetMaterial != null) Kill(sheetMaterial);
            if (trayMaterial != null) Kill(trayMaterial);
            if (maps != null) Kill(maps);
        }

        private static void Kill(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
