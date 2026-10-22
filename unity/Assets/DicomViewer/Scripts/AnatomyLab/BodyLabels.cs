using System;
using System.IO;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

namespace DicomViewer.AnatomyLab
{
    [Serializable]
    public class LabelObject
    {
        public int index;
        public string name;
        public int[] sio_labels;
        public int voxels;
        public string layer;                 // skin, fat, muscle, bone, organ (tools/import_sio_labels.py)
    }

    /// <summary>Mirror of labels.json (backend/tools/import_sio_labels.py).</summary>
    [Serializable]
    public class LabelTable
    {
        public int[] dims;
        public LabelObject[] objects;
        public string source;
        public string licence;
        public string credit;
    }

    /// <summary>
    /// Names for the photographed body's voxels: an object index per voxel (labels.raw, uint8, the body's own
    /// grid; 0 = nothing) and the table of objects (labels.json), brought onto his photographs from the
    /// Segmented Internal Organs of the Visible Human Male (CC BY 4.0) by tools/import_sio_labels.py. The lab
    /// names what is under the cursor, and the body shader lifts the named object's voxels (_LabelTex,
    /// _HighlightIndex) where a cut has opened him.
    /// </summary>
    public sealed class BodyLabels : IDisposable
    {
        public readonly byte[] Index;
        public readonly Vector3Int Dims;
        public readonly LabelTable Table;
        public Texture3D Texture { get; private set; }
        /// <summary>256 x 1, 1 where an object's index is hidden (a layer taken away).</summary>
        public Texture2D HideTexture { get; private set; }
        private readonly string[] names;
        private readonly string[] layers;
        private readonly byte[] hidden = new byte[256];
        private readonly System.Collections.Generic.HashSet<string> hiddenLayers = new System.Collections.Generic.HashSet<string>();

        public static readonly string[] LayerNames = { "skin", "fat", "muscle", "bone", "organ" };
        public bool AnyHidden => hiddenLayers.Count > 0;
        public bool LayerShown(string layer) => !hiddenLayers.Contains(layer);

        public int Count => Table.objects?.Length ?? 0;
        public string Credit => Table.credit;

        /// <summary>Reads the files named in body.json; null when the export has no labels or they do not fit.</summary>
        public static (byte[] index, string table) Read(string dir, BodyMeta meta)
        {
            if (meta == null || string.IsNullOrEmpty(meta.labels) || string.IsNullOrEmpty(meta.label_table)) return (null, null);
            string raw = Path.Combine(dir, meta.labels), json = Path.Combine(dir, meta.label_table);
            if (!File.Exists(raw) || !File.Exists(json)) return (null, null);
            return (File.ReadAllBytes(raw), File.ReadAllText(json));
        }

        /// <summary>Builds the lookup and its texture (main thread); null when the data does not fit the body.</summary>
        public static BodyLabels Build(Vector3Int dims, byte[] index, string tableJson)
        {
            if (index == null || tableJson == null) return null;
            if (index.Length != dims.x * dims.y * dims.z)
            {
                Debug.LogWarning($"labels.raw has {index.Length} bytes, the body {dims.x * dims.y * dims.z}: ignored");
                return null;
            }
            var table = JsonUtility.FromJson<LabelTable>(tableJson);
            if (table?.objects == null) return null;
            return new BodyLabels(dims, index, table);
        }

        private BodyLabels(Vector3Int dims, byte[] index, LabelTable table)
        {
            Dims = dims;
            Index = index;
            Table = table;
            names = new string[256];
            layers = new string[256];
            foreach (LabelObject o in table.objects)
                if (o.index > 0 && o.index < 256) { names[o.index] = o.name; layers[o.index] = o.layer ?? "organ"; }
            HideTexture = new Texture2D(256, 1, TextureFormat.R8, false, true)
            {
                wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Point, name = "PhotoBody hidden labels",
            };
            HideTexture.SetPixelData(hidden, 0);
            HideTexture.Apply(false, false);
            Texture = new Texture3D(dims.x, dims.y, dims.z, GraphicsFormat.R8_UNorm, TextureCreationFlags.None)
            {
                wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Point, name = "PhotoBody labels",
            };
            Texture.SetPixelData(index, 0);
            Texture.Apply(false, true);
        }

        /// <summary>The object index at a texture coordinate (nearest voxel); 0 outside or unlabelled.</summary>
        public int IndexAt(Vector3 uvw)
        {
            int x = Mathf.FloorToInt(uvw.x * Dims.x), y = Mathf.FloorToInt(uvw.y * Dims.y), z = Mathf.FloorToInt(uvw.z * Dims.z);
            if (x < 0 || y < 0 || z < 0 || x >= Dims.x || y >= Dims.y || z >= Dims.z) return 0;
            return Index[(z * Dims.y + y) * Dims.x + x];
        }

        /// <summary>The object's name at a texture coordinate, or null.</summary>
        public string NameAt(Vector3 uvw) => Name(IndexAt(uvw));

        public string Name(int index) => index > 0 && index < 256 ? names[index] : null;

        public string Layer(int index) => index > 0 && index < 256 ? layers[index] : null;

        /// <summary>Is the voxel at a texture coordinate in a layer the student has taken away?</summary>
        public bool HiddenAt(Vector3 uvw) => hiddenLayers.Count > 0 && hidden[IndexAt(uvw)] != 0;

        /// <summary>Shows or hides a whole layer (skin, fat, muscle, bone, organ); the texture follows.</summary>
        public void ShowLayer(string layer, bool shown)
        {
            if (shown) hiddenLayers.Remove(layer); else hiddenLayers.Add(layer);
            for (int i = 1; i < 256; i++) hidden[i] = (byte)(layers[i] != null && hiddenLayers.Contains(layers[i]) ? 255 : 0);
            HideTexture.SetPixelData(hidden, 0);
            HideTexture.Apply(false, false);
        }

        public void Dispose()
        {
            Kill(Texture);
            Kill(HideTexture);
            Texture = null;
            HideTexture = null;
        }

        private static void Kill(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) UnityEngine.Object.Destroy(o);
            else UnityEngine.Object.DestroyImmediate(o);
        }
    }
}
