using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The modelled body: a 3D model (a GLB made from reference pictures, Assets/Models) lying on his back on the
    /// steel table at real size. World frame: up is +y, the table top is y = 0, he lies along x with his head at
    /// -x (the viewer's left) and his face up. The table and the floor are plain lit meshes (URP Lit) that receive
    /// the key light's shadow of him.
    /// </summary>
    public static class ModelLab
    {
        public const float DefaultHeightM = 1.78f;
        public static readonly Color TableColour = new Color(0.74f, 0.76f, 0.78f);
        public static readonly Color FloorColour = new Color(0.36f, 0.36f, 0.35f);

        /// <summary>
        /// Lays the model on the table: scaled to heightM, his length along x (head at -x), face up, his back on
        /// the table top. The model's own frame is taken as y up and z forward (the glTF convention); faceDown
        /// turns him over for a model that came in facing the other way. Returns his world bounds.
        /// </summary>
        public static Bounds Lay(GameObject model, float heightM = DefaultHeightM, bool faceDown = false)
        {
            Transform t = model.transform;
            t.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            t.localScale = Vector3.one;
            Bounds own = WorldBounds(model);
            float scale = own.size.y > 1e-4f ? heightM / own.size.y : 1f;
            t.localScale = Vector3.one * scale;
            // His up (model y) along -x, his front (model z) up.
            t.rotation = Quaternion.LookRotation(faceDown ? Vector3.down : Vector3.up, Vector3.left);
            Bounds b = WorldBounds(model);
            t.position -= new Vector3(b.center.x, b.min.y, b.center.z);
            return WorldBounds(model);
        }

        /// <summary>The renderers' bounds together, world; an empty box at the origin when there are none.</summary>
        public static Bounds WorldBounds(GameObject model)
        {
            var renderers = model.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0) return new Bounds(Vector3.zero, Vector3.zero);
            Bounds b = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) b.Encapsulate(renderers[i].bounds);
            return b;
        }

        /// <summary>
        /// The steel table (top at y = 0, along x) with its rim and legs, and the floor 90 cm below, for a body
        /// this long; a parent named "Lab room" holds them.
        /// </summary>
        public static GameObject Room(float bodyLengthM, float widthM = 0.76f, float floorDropM = 0.9f)
        {
            var root = new GameObject("Lab room");
            Shader lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) { Debug.LogWarning("ModelLab: URP Lit shader not found"); return root; }
            float length = bodyLengthM + 0.3f, thick = 0.004f, rim = 0.014f, wall = 0.003f, leg = 0.045f;
            Vector3 lo = new Vector3(-length * 0.5f, -thick, -widthM * 0.5f), hi = new Vector3(length * 0.5f, 0f, widthM * 0.5f);
            var boxes = new List<(Vector3, Vector3)>
            {
                (lo, hi),                                                                                     // the top
                (new Vector3(lo.x, 0f, lo.z), new Vector3(lo.x + wall, rim, hi.z)),                           // the rim
                (new Vector3(hi.x - wall, 0f, lo.z), new Vector3(hi.x, rim, hi.z)),
                (new Vector3(lo.x, 0f, lo.z), new Vector3(hi.x, rim, lo.z + wall)),
                (new Vector3(lo.x, 0f, hi.z - wall), new Vector3(hi.x, rim, hi.z)),
            };
            foreach (float x in new[] { lo.x + 0.03f, hi.x - 0.03f - leg })
            foreach (float z in new[] { lo.z + 0.03f, hi.z - 0.03f - leg })
                boxes.Add((new Vector3(x, -floorDropM + 0.001f, z), new Vector3(x + leg, -thick, z + leg)));
            Part(root.transform, "Table", LabRoom.BoxMesh(boxes), Make(lit, "Lab table", TableColour, 0.55f, 0.42f));
            var floor = new List<(Vector3, Vector3)> { (new Vector3(-4f, -floorDropM - 0.006f, -4f), new Vector3(4f, -floorDropM, 4f)) };
            Part(root.transform, "Floor", LabRoom.BoxMesh(floor), Make(lit, "Lab floor", FloorColour, 0f, 0.15f));
            return root;
        }

        private static Material Make(Shader shader, string name, Color colour, float metallic, float smooth)
        {
            var m = new Material(shader) { name = name };
            m.SetColor("_BaseColor", colour);
            m.SetFloat("_Metallic", metallic);
            m.SetFloat("_Smoothness", smooth);
            return m;
        }

        private static void Part(Transform parent, string name, Mesh mesh, Material material)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = material;
            r.shadowCastingMode = ShadowCastingMode.Off;
            r.receiveShadows = true;
        }
    }
}
