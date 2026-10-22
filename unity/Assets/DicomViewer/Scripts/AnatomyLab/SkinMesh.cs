using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The body's skin as a mesh (skin.mesh, from tools/extract_skin_mesh.py) drawn over the photo volume: lit and
    /// shadowed like any game character, and cheap. The volume stays underneath and keeps everything that happens
    /// to him: it is told (_SkinByMesh) to leave the intact outer skin to the mesh and draw only cut tissue, the
    /// wound beds and what is deeper, while the mesh cuts itself away where the mask, a lifted sheet or the eyes'
    /// opening say so. Every frame the mesh's material takes the body material's state (mask, blood, sheets,
    /// instruments, eyes), so the two always agree.
    /// </summary>
    [RequireComponent(typeof(PhotoBody))]
    public class SkinMesh : MonoBehaviour
    {
        [Range(0f, 1f)] public float living = 1f;

        public Material Material { get; private set; }
        public bool IsLoaded => mesh != null;

        private PhotoBody body;
        private Mesh mesh;
        private GameObject part;

        private static readonly string[] Floats = { "_MaskEnabled", "_ShowStain", "_HasLids", "_Open", "_SheetCount", "_InstrCount" };
        private static readonly string[] Vectors = { "_Eye0", "_Eye1", "_SizeM" };
        private static readonly string[] Textures = { "_MaskTex", "_StainTex", "_SheetMaps" };
        private static readonly string[] VectorArrays = { "_SheetOrigin", "_SheetE1", "_SheetE2", "_SheetE3", "_InstrA", "_InstrB" };

        /// <summary>Loads the export's skin.mesh, if it has one, and puts it over the body.</summary>
        public bool Attach(PhotoBody photoBody)
        {
            Clear();
            body = photoBody;
            if (body == null || !body.IsLoaded || string.IsNullOrEmpty(body.Meta.skin_mesh)) return false;
            string path = Path.Combine(body.Folder, body.Meta.skin_mesh);
            if (!File.Exists(path)) return false;
            Shader shader = Shader.Find("DicomViewer/LabSkinMesh");
            if (shader == null) return false;
            mesh = Load(path);
            if (mesh == null) return false;

            Material = new Material(shader) { name = "Skin mesh" };
            Material.SetTexture("_ColorTex", body.ColourTexture);
            if (body.SkinDepthTexture != null) Material.SetTexture("_SkinDepthTex", body.SkinDepthTexture);
            Material.SetVector("_SizeMm", body.Space.SizeMm);
            Material.SetVector("_SizeM", body.SizeM);
            Material.SetFloat("_Living", living);

            part = new GameObject("Skin mesh") { hideFlags = HideFlags.DontSave };
            part.transform.SetParent(body.Volume, false);
            part.transform.localPosition = -0.5f * Vector3.one;                     // vertices are in body millimetres
            Vector3 size = body.Space.SizeMm;
            part.transform.localScale = new Vector3(1f / size.x, 1f / size.y, 1f / size.z);
            part.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = part.AddComponent<MeshRenderer>();
            r.sharedMaterial = Material;
            r.shadowCastingMode = ShadowCastingMode.Off;
            body.Material.SetFloat("_SkinByMesh", 1f);
            Sync();
            return true;
        }

        /// <summary>skin.mesh: "SKIN", counts, positions (mm), normals, uint32 indices.</summary>
        public static Mesh Load(string path)
        {
            using var f = new BinaryReader(File.OpenRead(path));
            if (new string(f.ReadChars(4)) != "SKIN") return null;
            int nv = (int)f.ReadUInt32(), ni = (int)f.ReadUInt32();
            var verts = new Vector3[nv];
            for (int i = 0; i < nv; i++) verts[i] = new Vector3(f.ReadSingle(), f.ReadSingle(), f.ReadSingle());
            var norms = new Vector3[nv];
            for (int i = 0; i < nv; i++) norms[i] = new Vector3(f.ReadSingle(), f.ReadSingle(), f.ReadSingle());
            var tris = new int[ni];
            for (int i = 0; i < ni; i++) tris[i] = (int)f.ReadUInt32();
            var m = new Mesh { name = "Skin", hideFlags = HideFlags.DontSave, indexFormat = IndexFormat.UInt32 };
            m.vertices = verts;
            m.normals = norms;
            m.triangles = tris;
            m.RecalculateBounds();
            return m;
        }

        private void LateUpdate() => Sync();

        /// <summary>The body material's state onto the mesh's (LateUpdate; editor snapshots call it).</summary>
        public void Sync()
        {
            if (Material == null || body == null || body.Material == null) return;
            Material src = body.Material;
            foreach (string n in Floats) if (src.HasProperty(n)) Material.SetFloat(n, src.GetFloat(n));
            foreach (string n in Vectors) if (src.HasProperty(n)) Material.SetVector(n, src.GetVector(n));
            foreach (string n in Textures)
            {
                Texture t = src.HasProperty(n) ? src.GetTexture(n) : null;
                if (t != null) Material.SetTexture(n, t);
            }
            foreach (string n in VectorArrays)
            {
                Vector4[] a = src.HasProperty(n) ? src.GetVectorArray(n) : null;
                if (a != null && a.Length > 0) Material.SetVectorArray(n, a);
            }
            Material.SetFloat("_Living", living);
        }

        public void Clear()
        {
            if (body != null && body.Material != null) body.Material.SetFloat("_SkinByMesh", 0f);
            if (part != null) Kill(part);
            if (mesh != null) Kill(mesh);
            if (Material != null) Kill(Material);
            part = null;
            mesh = null;
            Material = null;
        }

        private void OnDestroy() => Clear();

        private static void Kill(Object o)
        {
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
