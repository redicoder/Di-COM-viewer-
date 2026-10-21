using System;
using System.IO;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>Mirror of body.json (backend/tools/prepare_photo_volume.py --unity). Positions in metres.</summary>
    [Serializable]
    public class BodyEye
    {
        public float[] centre_m;
        public float radius_m;
        public float lid_line_y_m;
        public float skin_front_z_m;
    }

    [Serializable]
    public class BodyMeta
    {
        public int[] dims;
        public float[] spacing_mm;
        public float[] size_m;
        public string credit;
        public string licence;
        public BodyEye[] eyes;
        public string lids;
        public string skin_depth;            // R8, units of skin_depth_unit_mm below the outer skin
        public float skin_depth_unit_mm;
    }

    /// <summary>
    /// The photographed body: colour photographs of a real body's 1 mm slices stacked into an RGBA 3D texture and
    /// drawn by the DicomViewer/PhotoBody ray-marching shader, which writes depth so meshes (eyes, organs, blood)
    /// mix in correctly.
    ///
    /// This object's local space is the body's: metres, X = patient left, Y = up, Z = back, origin at the centre.
    /// The child "Volume" cube is scaled to the body's size, so its local -0.5..0.5 is the texture's 0..1, the
    /// convention of VolumeSpace: the dissection mask, picking and the blood simulation share that grid.
    /// </summary>
    public class PhotoBody : MonoBehaviour
    {
        [Tooltip("Folder with body.json + body.raw. Empty: <repo>/backend/out/photo_head next to the project or the built app.")]
        public string folder = "";

        public const int Brick = 8;            // empty-space map: one cell per 8 x 8 x 8 voxels

        public event Action Loaded;
        public BodyMeta Meta { get; private set; }
        public VolumeSpace Space { get; private set; }
        public Transform Volume { get; private set; }
        public Material Material { get; private set; }
        public Texture3D ColourTexture { get; private set; }
        /// <summary>Millimetres below the outer skin (R16 float), for TissueWarp's flaps; null if the export has none.</summary>
        public Texture3D SkinDepthTexture { get; private set; }
        public Vector3 SizeM { get; private set; }
        public bool IsLoaded => Material != null;
        public bool IsLoading { get; private set; }
        public string Error { get; private set; }

        private byte[] rgba;                   // CPU copy (x fastest, then y, then z) for picking and tissue colour
        private Texture3D lidTexture, occupancyTexture, noStain;

        public string Folder => !string.IsNullOrEmpty(folder)
            ? folder
            : Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "backend", "out", "photo_head"));

        public async Task LoadAsync()
        {
            if (IsLoading) return;
            IsLoading = true;
            Error = null;
            string dir = Folder;
            try
            {
                var meta = JsonUtility.FromJson<BodyMeta>(File.ReadAllText(Path.Combine(dir, "body.json")));
                string lidPath = string.IsNullOrEmpty(meta.lids) ? null : Path.Combine(dir, meta.lids);
                string depthPath = string.IsNullOrEmpty(meta.skin_depth) ? null : Path.Combine(dir, meta.skin_depth);
                var dims = new Vector3Int(meta.dims[0], meta.dims[1], meta.dims[2]);
                var (data, lids, occ, occDims, depth) = await Task.Run(() =>
                {
                    byte[] d = File.ReadAllBytes(Path.Combine(dir, "body.raw"));
                    byte[] l = lidPath != null && File.Exists(lidPath) ? File.ReadAllBytes(lidPath) : null;
                    byte[] o = Occupancy(d, dims, out var od);
                    ushort[] sd = depthPath != null && File.Exists(depthPath)
                        ? SkinDepthHalf(File.ReadAllBytes(depthPath), meta.skin_depth_unit_mm) : null;
                    return (d, l, o, od, sd);
                });
                Build(meta, data, lids, occ, occDims, depth);
            }
            catch (Exception e)
            {
                Error = $"Could not load the body from {dir}: {e.Message}";
                Debug.LogError(Error);
            }
            finally
            {
                IsLoading = false;
            }
        }

        /// <summary>Creates the textures, the volume cube and its material. Public so tests can build a body in memory.</summary>
        public void Build(BodyMeta meta, byte[] data, byte[] lids, byte[] occupancy = null, Vector3Int occDims = default,
            ushort[] skinDepthHalf = null)
        {
            var dims = new Vector3Int(meta.dims[0], meta.dims[1], meta.dims[2]);
            if (data.Length != dims.x * dims.y * dims.z * 4)
                throw new InvalidDataException($"body.raw has {data.Length} bytes, expected {dims.x * dims.y * dims.z * 4}");
            if (occupancy == null) occupancy = Occupancy(data, dims, out occDims);
            Meta = meta;
            rgba = data;
            Space = new VolumeSpace(dims, new Vector3(meta.spacing_mm[0], meta.spacing_mm[1], meta.spacing_mm[2]));
            SizeM = new Vector3(meta.size_m[0], meta.size_m[1], meta.size_m[2]);

            // Colour is sRGB (photographs); alpha (tissue) stays linear.
            ColourTexture = new Texture3D(dims.x, dims.y, dims.z, GraphicsFormat.R8G8B8A8_SRGB, TextureCreationFlags.None)
            {
                wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, name = "PhotoBody colour",
            };
            ColourTexture.SetPixelData(data, 0);
            ColourTexture.Apply(false, true);

            bool hasLids = lids != null && lids.Length == dims.x * dims.y * dims.z;
            lidTexture = R8(hasLids ? lids : new byte[1], hasLids ? dims : Vector3Int.one, FilterMode.Bilinear, "PhotoBody eyelids");
            occupancyTexture = R8(occupancy, occDims, FilterMode.Point, "PhotoBody occupancy");
            if (SkinDepthTexture != null) Kill(SkinDepthTexture);
            SkinDepthTexture = null;
            if (skinDepthHalf != null && skinDepthHalf.Length == dims.x * dims.y * dims.z)
            {
                SkinDepthTexture = new Texture3D(dims.x, dims.y, dims.z, GraphicsFormat.R16_SFloat, TextureCreationFlags.None)
                {
                    wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, name = "PhotoBody skin depth (mm)",
                };
                SkinDepthTexture.SetPixelData(skinDepthHalf, 0);
                SkinDepthTexture.Apply(false, true);
            }
            if (noStain == null) noStain = R8(new byte[1], Vector3Int.one, FilterMode.Point, "PhotoBody no stain");

            if (Volume != null) Kill(Volume.gameObject);
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = "Volume";
            DestroyImmediate(cube.GetComponent<Collider>());
            Volume = cube.transform;
            Volume.SetParent(transform, false);
            Volume.localPosition = Vector3.zero;
            Volume.localRotation = Quaternion.identity;
            Volume.localScale = SizeM;
            var mr = cube.GetComponent<MeshRenderer>();
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;

            Shader shader = Shader.Find("DicomViewer/PhotoBody");
            if (shader == null) throw new InvalidOperationException("Shader DicomViewer/PhotoBody not found");
            Material = new Material(shader) { name = "PhotoBody" };
            Material.SetTexture("_ColorTex", ColourTexture);
            Material.SetTexture("_LidTex", lidTexture);
            Material.SetTexture("_OccTex", occupancyTexture);
            Material.SetTexture("_StainTex", noStain);   // until BloodSim binds its own (an unset 3D texture reads grey)
            Material.SetVector("_Dims", new Vector4(dims.x, dims.y, dims.z, 0));
            Material.SetVector("_SizeM", SizeM);
            Material.SetFloat("_HasLids", hasLids ? 1f : 0f);
            if (SkinDepthTexture != null) Material.SetTexture("_SkinDepthTex", SkinDepthTexture);
            mr.sharedMaterial = Material;
            Loaded?.Invoke();
        }

        private static Texture3D R8(byte[] data, Vector3Int dims, FilterMode filter, string name)
        {
            var t = new Texture3D(dims.x, dims.y, dims.z, GraphicsFormat.R8_UNorm, TextureCreationFlags.None)
            {
                wrapMode = TextureWrapMode.Clamp, filterMode = filter, name = name,
            };
            t.SetPixelData(data, 0);
            t.Apply(false, true);
            return t;
        }

        /// <summary>Skin depth from the export (bytes x unit mm) as half floats in millimetres.</summary>
        public static ushort[] SkinDepthHalf(byte[] depth, float unitMm)
        {
            if (unitMm <= 0f) unitMm = 0.25f;
            var lut = new ushort[256];
            for (int i = 0; i < 256; i++) lut[i] = Mathf.FloatToHalf(i * unitMm);
            var half = new ushort[depth.Length];
            for (int i = 0; i < depth.Length; i++) half[i] = lut[depth[i]];
            return half;
        }

        /// <summary>
        /// One cell per Brick^3 voxels: 255 where there is (or may be, after one cell of dilation) any tissue. The
        /// shader strides through empty cells, which is most of the box around a body.
        /// </summary>
        public static byte[] Occupancy(byte[] rgba, Vector3Int dims, out Vector3Int od)
        {
            od = new Vector3Int((dims.x + Brick - 1) / Brick, (dims.y + Brick - 1) / Brick, (dims.z + Brick - 1) / Brick);
            var occ = new byte[od.x * od.y * od.z];
            for (int z = 0; z < dims.z; z++)
            for (int y = 0; y < dims.y; y++)
            {
                int row = (z * dims.y + y) * dims.x, cellRow = ((z / Brick) * od.y + y / Brick) * od.x;
                for (int x = 0; x < dims.x; x++)
                    if (rgba[(row + x) * 4 + 3] != 0) occ[cellRow + x / Brick] = 255;
            }
            var grown = new byte[occ.Length];
            for (int z = 0; z < od.z; z++)
            for (int y = 0; y < od.y; y++)
            for (int x = 0; x < od.x; x++)
            {
                if (occ[(z * od.y + y) * od.x + x] == 0) continue;
                for (int dz = -1; dz <= 1; dz++)
                for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++)
                {
                    int X = x + dx, Y = y + dy, Z = z + dz;
                    if (X < 0 || Y < 0 || Z < 0 || X >= od.x || Y >= od.y || Z >= od.z) continue;
                    grown[(Z * od.y + Y) * od.x + X] = 255;
                }
            }
            return grown;
        }

        // ------------------------------------------------------------------ CPU sampling (picking, tissue colour)

        /// <summary>Tissue (0..1) at a texture coordinate, trilinear: the photo's alpha, before any cuts.</summary>
        public float AlphaAt(Vector3 uvw)
        {
            Vector3Int d = Space.Dims;
            float fx = uvw.x * d.x - 0.5f, fy = uvw.y * d.y - 0.5f, fz = uvw.z * d.z - 0.5f;
            int x0 = Mathf.FloorToInt(fx), y0 = Mathf.FloorToInt(fy), z0 = Mathf.FloorToInt(fz);
            if (x0 < 0 || y0 < 0 || z0 < 0 || x0 >= d.x - 1 || y0 >= d.y - 1 || z0 >= d.z - 1) return 0f;
            float tx = fx - x0, ty = fy - y0, tz = fz - z0;
            int i = (z0 * d.y + y0) * d.x + x0, sy = d.x, sz = d.x * d.y;
            float A(int k) => rgba[k * 4 + 3];
            float c00 = Mathf.Lerp(A(i), A(i + 1), tx), c10 = Mathf.Lerp(A(i + sy), A(i + sy + 1), tx);
            float c01 = Mathf.Lerp(A(i + sz), A(i + sz + 1), tx), c11 = Mathf.Lerp(A(i + sz + sy), A(i + sz + sy + 1), tx);
            return Mathf.Lerp(Mathf.Lerp(c00, c10, ty), Mathf.Lerp(c01, c11, ty), tz) / 255f;
        }

        /// <summary>The photo's colour at a point in the volume cube's local space (-0.5..0.5), nearest voxel.</summary>
        public Color32 ColourAt(Vector3 cubeLocal)
        {
            Vector3 uvw = VolumeSpace.LocalToUvw(cubeLocal);
            Vector3Int d = Space.Dims;
            int x = Mathf.Clamp((int)(uvw.x * d.x), 0, d.x - 1), y = Mathf.Clamp((int)(uvw.y * d.y), 0, d.y - 1),
                z = Mathf.Clamp((int)(uvw.z * d.z), 0, d.z - 1);
            int i = ((z * d.y + y) * d.x + x) * 4;
            return new Color32(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]);
        }

        /// <summary>
        /// The first tissue a world ray meets, skipping what `removed` says was cut away (cube-local point -> bool).
        /// Returns the surface point and its outward normal in world space.
        /// </summary>
        public bool Raycast(Ray ray, Func<Vector3, bool> removed, out Vector3 hit, out Vector3 normal)
        {
            hit = normal = Vector3.zero;
            if (!IsLoaded) return false;
            Vector3 o = Volume.InverseTransformPoint(ray.origin);
            Vector3 d = Volume.InverseTransformVector(ray.direction);       // per world metre along the ray
            if (!BoxEntry(o, d, out float t0, out float t1)) return false;
            float voxelWorld = Volume.TransformVector(new Vector3(1f / Space.Dims.x, 0, 0)).magnitude;
            float step = voxelWorld * 0.4f;

            bool Tissue(float t, out Vector3 local)
            {
                local = o + d * t;
                return AlphaAt(VolumeSpace.LocalToUvw(local)) > 0.5f && (removed == null || !removed(local));
            }

            float prev = t0;
            for (float t = t0; t <= t1; t += step)
            {
                if (!Tissue(t, out _)) { prev = t; continue; }
                float a = prev, b = t;
                for (int k = 0; k < 8; k++)
                {
                    float m = 0.5f * (a + b);
                    if (Tissue(m, out _)) b = m; else a = m;
                }
                Vector3 local = o + d * b;
                hit = Volume.TransformPoint(local);
                normal = NormalWorld(local, ray.direction);
                return true;
            }
            return false;
        }

        /// <summary>Outward surface normal (world) at a cube-local point, from the tissue's gradient.</summary>
        public Vector3 NormalWorld(Vector3 local, Vector3 fallbackRayDir)
        {
            Vector3Int dm = Space.Dims;
            Vector3 e = new Vector3(1f / dm.x, 1f / dm.y, 1f / dm.z);
            Vector3 uvw = VolumeSpace.LocalToUvw(local);
            var g = new Vector3(
                (AlphaAt(uvw + new Vector3(e.x, 0, 0)) - AlphaAt(uvw - new Vector3(e.x, 0, 0))) / (2 * e.x),
                (AlphaAt(uvw + new Vector3(0, e.y, 0)) - AlphaAt(uvw - new Vector3(0, e.y, 0))) / (2 * e.y),
                (AlphaAt(uvw + new Vector3(0, 0, e.z)) - AlphaAt(uvw - new Vector3(0, 0, e.z))) / (2 * e.z));
            // A gradient is a covector: to world with the transpose of world-to-local.
            Matrix4x4 w2l = Volume.worldToLocalMatrix;
            var n = new Vector3(w2l.m00 * g.x + w2l.m10 * g.y + w2l.m20 * g.z,
                                w2l.m01 * g.x + w2l.m11 * g.y + w2l.m21 * g.z,
                                w2l.m02 * g.x + w2l.m12 * g.y + w2l.m22 * g.z);
            return n.sqrMagnitude > 1e-12f ? -n.normalized : -fallbackRayDir.normalized;
        }

        private static bool BoxEntry(Vector3 o, Vector3 d, out float tNear, out float tFar)
        {
            tNear = 0f;
            tFar = float.MaxValue;
            for (int i = 0; i < 3; i++)
            {
                if (Mathf.Abs(d[i]) < 1e-9f)
                {
                    if (o[i] < -0.5f || o[i] > 0.5f) return false;
                    continue;
                }
                float a = (-0.5f - o[i]) / d[i], b = (0.5f - o[i]) / d[i];
                tNear = Mathf.Max(tNear, Mathf.Min(a, b));
                tFar = Mathf.Min(tFar, Mathf.Max(a, b));
            }
            return tNear < tFar;
        }

        private void OnDestroy()
        {
            if (ColourTexture != null) Kill(ColourTexture);
            if (lidTexture != null) Kill(lidTexture);
            if (occupancyTexture != null) Kill(occupancyTexture);
            if (noStain != null) Kill(noStain);
            if (SkinDepthTexture != null) Kill(SkinDepthTexture);
            if (Material != null) Kill(Material);
        }

        private static void Kill(UnityEngine.Object o)
        {
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);                // edit-mode tests and editor snapshots
        }
    }
}
