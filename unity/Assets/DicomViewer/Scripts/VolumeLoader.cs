using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;
using UnityVolumeRendering;
// Unity 6.x added UnityEngine.TransferFunction; pin the plugin's type.
using TransferFunction = UnityVolumeRendering.TransferFunction;

namespace DicomViewer
{
    /// <summary>
    /// Loads volume.raw + volume.json produced by the Python backend (file export or HTTP service)
    /// into a UnityVolumeRendering VolumeRenderedObject, applies a Hounsfield-unit transfer function
    /// and scales the object so its longest side equals targetSize metres.
    ///
    /// The backend already writes voxels in Unity texture order (x = patient left, y = superior,
    /// z = posterior), so the dataset is created with rotation = identity. Do NOT use
    /// RawDatasetImporter here: it applies a 90° rotation meant for z-up raw files.
    /// </summary>
    public class VolumeLoader : MonoBehaviour
    {
        public enum Source { LocalFiles, HttpService }

        [Header("Source")]
        public Source source = Source.LocalFiles;
        [Tooltip("Folder containing volume.raw and volume.json (output of `python -m app.export`)")]
        public string localFolder = "";
        [Tooltip("Load the newest conversion from the converter app (the folders listed in Latest Export List) instead of " +
                 "Local Folder. N during Play loads the next folder in that list, or a conversion made since.")]
        public bool useLatestExport = true;
        [Tooltip("Leave empty: found automatically as <repo>/backend/out/latest.txt next to the Unity project or the built app.")]
        public string latestExportList = "";
        public string serverUrl = "http://127.0.0.1:8000";
        [Tooltip("Series folder relative to DICOM_DATA_ROOT on the server")]
        public string seriesPath = "phantom_ct";
        public float targetSpacingMm = 1.0f;
        public int maxDim = 320;

        [Header("Placement")]
        [Tooltip("Longest side of the volume in metres after loading. Keep it inside the SR display box.")]
        public float targetSize = 0.25f;

        [Header("Rendering")]
        [Range(0.2f, 2.0f)] public float samplingRateMultiplier = 1.0f;
        [Tooltip("Gradient shading: surfaces look solid instead of glowing fog. Costs a few seconds of load time.")]
        public bool lighting = true;
        public bool cubicInterpolation = false;
        [Tooltip("High quality (Q toggles): more ray samples and tricubic interpolation while the view is still. " +
                 "Drops back to the settings above while you rotate, move or zoom, so interaction stays smooth.")]
        public bool highQuality = true;
        [Range(1f, 3f)] public float highQualitySamplingRate = 2.0f;
        public bool highQualityCubic = true;

        public enum Preset { Body, Lungs, Organs }

        [Header("CT transfer function (live in Play mode, P cycles presets)")]
        [Tooltip("Body: organs, contrast vessels, bone. Lungs: glass lungs with the vessel tree, for a --lungs-only export " +
                 "(selected automatically when one is loaded). Organs: AI-labelled organs in colour with the skeleton, " +
                 "for a conversion with organ labels (selected automatically when labels.raw is present).")]
        public Preset preset = Preset.Body;
        [Tooltip("Body: everything below this HU is invisible. -20 hides fat; lower it (e.g. -120) to show fat as haze.")]
        [Range(-300f, 0f)] public float fatCutoffHU = -20f;
        [Tooltip("Body: opacity per ray step of organs and muscle (~20-70 HU). Raise for more body context, lower to cut fog.")]
        [Range(0f, 0.03f)] public float softTissueOpacity = 0.007f;
        [Tooltip("Body: opacity of contrast-enhanced tissue (~200 HU): kidney cortex, arteries.")]
        [Range(0f, 1f)] public float enhancedOpacity = 0.3f;
        [Tooltip("Body: opacity of bone (~600 HU and above).")]
        [Range(0f, 1f)] public float boneOpacity = 0.9f;
        [Tooltip("Lungs: opacity per ray step of lung tissue (~-700 HU), the glass outline of the lungs.")]
        [Range(0f, 0.03f)] public float lungGlassOpacity = 0.01f;
        [Tooltip("Lungs: opacity of pulmonary vessels and bronchial walls (~0 HU).")]
        [Range(0f, 1f)] public float lungVesselOpacity = 0.7f;
        [Tooltip("Organs: opacity per ray step of each labelled organ. Higher = solid organs, lower = see-through.")]
        [Range(0f, 0.3f)] public float organOpacity = 0.15f;
        [Tooltip("Organs: also draw the skeleton (B still shows bones only).")]
        public bool organsShowSkeleton = false;
        [Tooltip("Organs: opacity of the skeleton when shown. Below ~0.5 the ribs turn translucent and the organs show through.")]
        [Range(0f, 1f)] public float organSkeletonOpacity = 0.45f;
        [Tooltip("Organs: faint outline of the rest of the body (skin, muscle) for context. 0 hides it.")]
        [Range(0f, 0.01f)] public float bodyGhostOpacity = 0.0015f;

        public VolumeRenderedObject Volume { get; private set; }
        public VolumeMeta Meta { get; private set; }
        public event Action<VolumeRenderedObject> Loaded;

        /// <summary>Organ labels of the loaded volume (labels.json), or null when it has none.</summary>
        public OrganLabel[] Organs { get; private set; }
        private byte[] organVoxels;   // labels.raw, kept for picking
        private MaskVolume mask;

        public bool IsLoading => loading;
        /// <summary>backend\ (the folder holding out\latest.txt's parent), where the converter lives.</summary>
        public string BackendFolder => Path.GetDirectoryName(Path.GetDirectoryName(LatestListPath));

        /// <summary>
        /// The converter's out\latest.txt. An explicit, existing Inspector value wins; otherwise it is found relative
        /// to this project or build: both unity/Assets and build/&lt;app&gt;_Data sit two levels below the repo root.
        /// </summary>
        public string LatestListPath =>
            !string.IsNullOrEmpty(latestExportList) && File.Exists(latestExportList)
                ? latestExportList
                : Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "backend", "out", "latest.txt"));

        /// <summary>When set (e.g. by MarkerCheck's bone-only view), shown instead of the clinical transfer function.</summary>
        public TransferFunction OverrideTransferFunction { get; set; }
        private TransferFunction clinicalTF;

        // Inspector edits during Play re-colour the volume immediately.
        private void OnValidate()
        {
            if (!Application.isPlaying || Volume == null) return;
            ApplyTransferFunction();
            ApplyQuality(qualityHigh);
            _ = Volume.SetLightingEnabledAsync(lighting);   // first enable computes gradients in the background
        }

        private bool qualityHigh;
        private float lastInteraction = -10f;

        private void ApplyQuality(bool high)
        {
            qualityHigh = high;
            if (Volume == null) return;
            Volume.SetSamplingRateMultiplier(high ? highQualitySamplingRate : samplingRateMultiplier);
            Volume.SetCubicInterpolationEnabled(high ? highQualityCubic || cubicInterpolation : cubicInterpolation);
        }

        // High quality only while the view is still: any drag, scroll or navigation key drops to the normal
        // settings for that moment, so rotating and zooming stay fluid even when a still frame is expensive.
        private void UpdateQuality()
        {
            if (Input.GetKeyDown(KeyCode.Q))
            {
                highQuality = !highQuality;
                Debug.Log($"High quality: {(highQuality ? "on (while the view is still)" : "off")}");
            }
            if (Input.GetMouseButton(0) || Input.GetMouseButton(1) || Input.GetMouseButton(2) ||
                Input.mouseScrollDelta.y != 0f || Input.GetAxisRaw("Horizontal") != 0f || Input.GetAxisRaw("Vertical") != 0f ||
                Input.GetKey(KeyCode.LeftBracket) || Input.GetKey(KeyCode.RightBracket))
                lastInteraction = Time.unscaledTime;
            bool want = highQuality && Time.unscaledTime - lastInteraction > 0.25f;
            if (want != qualityHigh) ApplyQuality(want);
        }

        private string[] latestFolders;
        private int latestIndex;
        private bool loading;

        private void Update()
        {
            if (!ViewerUi.ModalOpen && Input.GetKeyDown(KeyCode.N)) NextVersion();
            if (Volume == null) return;
            UpdateQuality();
            if (!ViewerUi.ModalOpen && Input.GetKeyDown(KeyCode.P)) CyclePreset();
        }

        /// <summary>P key and the toolbar's preset button.</summary>
        public void CyclePreset()
        {
            int count = Enum.GetValues(typeof(Preset)).Length;
            do preset = (Preset)(((int)preset + 1) % count);
            while (preset == Preset.Organs && Organs == null);   // Organs needs labels from the converter
            ApplyTransferFunction();
            Debug.Log($"Transfer function preset: {preset}");
        }

        /// <summary>The last conversion produced more than one folder (e.g. the full scan and lungs only).</summary>
        public bool HasOtherVersions => latestFolders != null && latestFolders.Length > 1;

        /// <summary>N key and the toolbar's "Next version" button.</summary>
        public void NextVersion()
        {
            if (!loading) _ = LoadNextLatestAsync();
        }

        private async void Start()
        {
            if (useLatestExport && source == Source.LocalFiles && TryReadLatestList(out var folders))
            {
                latestFolders = folders;
                latestIndex = 0;
                localFolder = folders[0];
            }
            await LoadGuardedAsync();
        }

        private bool TryReadLatestList(out string[] folders)
        {
            folders = File.Exists(LatestListPath)
                ? File.ReadAllLines(LatestListPath).Select(l => l.Trim()).Where(l => l.Length > 0).ToArray()
                : Array.Empty<string>();
            return folders.Length > 0;
        }

        /// <summary>Loads the first folder of the newest conversion (after the in-app converter finishes).</summary>
        public async Task LoadLatestAsync()
        {
            latestFolders = null;   // forces index 0 of whatever the list says now
            await LoadNextLatestAsync();
        }

        // ------------------------------------------------------------------ organs

        public void SetOrganVisible(int id, bool visible)
        {
            var o = Organs?.FirstOrDefault(l => l.id == id);
            if (o == null) return;
            o.visible = visible;
            ApplyTransferFunction();
        }

        /// <summary>Shows only this organ (the others are hidden); id 0 shows all again.</summary>
        public void SoloOrgan(int id)
        {
            if (Organs == null) return;
            foreach (var o in Organs) o.visible = id == 0 || o.id == id;
            if (preset != Preset.Organs) preset = Preset.Organs;
            ApplyTransferFunction();
        }

        public OrganLabel OrganById(int id) => Organs?.FirstOrDefault(l => l.id == id);

        // ------------------------------------------------------------------ selection (Inspect)

        /// <summary>Ghost: the other structures stay as a faint context. Isolate: only the selection is drawn.</summary>
        public enum SelectMode { Ghost, Isolate }

        [Tooltip("Opacity factor of the other organs while one is selected in Ghost mode.")]
        [Range(0f, 1f)] public float ghostFactor = 0.12f;

        public int SelectedOrgan { get; private set; }
        public SelectMode SelectionMode { get; private set; } = SelectMode.Ghost;

        public void Select(int id, SelectMode mode)
        {
            var o = OrganById(id);
            if (o == null) return;
            o.visible = true;
            SelectedOrgan = id;
            SelectionMode = mode;
            if (preset != Preset.Organs) preset = Preset.Organs;
            ApplyTransferFunction();
        }

        public void ClearSelection()
        {
            if (SelectedOrgan == 0) return;
            SelectedOrgan = 0;
            ApplyTransferFunction();
        }

        private float OrganAlpha(int id)
        {
            var o = OrganById(id);
            if (o == null || !o.visible || OverrideTransferFunction != null || preset != Preset.Organs) return 0f;
            float a = organOpacity * o.opacity;
            if (SelectedOrgan > 0 && id != SelectedOrgan) a = SelectionMode == SelectMode.Isolate ? 0f : a * ghostFactor;
            return a;
        }

        // ------------------------------------------------------------------ organ statistics (Inspect card)

        public struct OrganStats
        {
            public long voxels;
            public Vector3Int min, max;     // voxel bounding box, inclusive
            public Vector3 centroid;        // voxel coordinates
            public float meanHu;
        }

        private OrganStats[] organStats;   // indexed by label id; null until computed

        public bool TryGetOrganStats(int id, out OrganStats stats)
        {
            var s = organStats;
            stats = s != null && id > 0 && id < s.Length ? s[id] : default;
            return stats.voxels > 0;
        }

        /// <summary>Volume in millilitres and bounding-box size in millimetres (x = left-right, y = head-feet, z = front-back).</summary>
        public bool TryGetOrganSize(int id, out float millilitres, out Vector3 sizeMm)
        {
            millilitres = 0f;
            sizeMm = Vector3.zero;
            if (!TryGetOrganStats(id, out var s) || Meta == null) return false;
            var sp = new Vector3(Meta.spacing_mm[0], Meta.spacing_mm[1], Meta.spacing_mm[2]);
            millilitres = s.voxels * sp.x * sp.y * sp.z / 1000f;
            sizeMm = Vector3.Scale(s.max - s.min + Vector3Int.one, sp);
            return true;
        }

        /// <summary>World-space centre and radius of an organ's bounding box (for Focus).</summary>
        public bool TryGetOrganWorldBounds(int id, out Vector3 centre, out float radius)
        {
            centre = Vector3.zero;
            radius = 0f;
            if (!TryGetOrganStats(id, out var s) || Volume == null) return false;
            Transform c = Volume.volumeContainerObject.transform;
            var dims = new Vector3(Meta.dim_x, Meta.dim_y, Meta.dim_z);
            Vector3 lo = VolumeSpace.UvwToLocal(new Vector3(s.min.x / dims.x, s.min.y / dims.y, s.min.z / dims.z));
            Vector3 hi = VolumeSpace.UvwToLocal(new Vector3((s.max.x + 1) / dims.x, (s.max.y + 1) / dims.y, (s.max.z + 1) / dims.z));
            Vector3 wlo = c.TransformPoint(lo), whi = c.TransformPoint(hi);
            centre = (wlo + whi) * 0.5f;
            radius = (whi - wlo).magnitude * 0.5f;
            return true;
        }

        private static OrganStats[] ComputeOrganStats(byte[] labels, float[] hu, int nx, int ny, int nz)
        {
            var count = new long[256];
            var sum = new double[256, 4];
            var lo = new Vector3Int[256];
            var hi = new Vector3Int[256];
            for (int i = 0; i < 256; i++)
            {
                lo[i] = new Vector3Int(int.MaxValue, int.MaxValue, int.MaxValue);
                hi[i] = new Vector3Int(-1, -1, -1);
            }
            int idx = 0;
            for (int z = 0; z < nz; z++)
            for (int y = 0; y < ny; y++)
            for (int x = 0; x < nx; x++, idx++)
            {
                int l = labels[idx];
                if (l == 0) continue;
                count[l]++;
                sum[l, 0] += x; sum[l, 1] += y; sum[l, 2] += z; sum[l, 3] += hu[idx];
                var a = lo[l]; var b = hi[l];
                if (x < a.x) a.x = x; if (y < a.y) a.y = y; if (z < a.z) a.z = z;
                if (x > b.x) b.x = x; if (y > b.y) b.y = y; if (z > b.z) b.z = z;
                lo[l] = a; hi[l] = b;
            }
            var stats = new OrganStats[256];
            for (int l = 1; l < 256; l++)
            {
                if (count[l] == 0) continue;
                double n = count[l];
                stats[l] = new OrganStats
                {
                    voxels = count[l], min = lo[l], max = hi[l],
                    centroid = new Vector3((float)(sum[l, 0] / n), (float)(sum[l, 1] / n), (float)(sum[l, 2] / n)),
                    meanHu = (float)(sum[l, 3] / n),
                };
            }
            return stats;
        }

        // ------------------------------------------------------------------ picking

        public struct VolumeHit
        {
            public Vector3 world;   // where the view ray becomes visibly opaque
            public int organId;     // organ there (0 = tissue without a label, e.g. bone)
            public float hu;        // CT value at that point
        }

        /// <summary>
        /// CPU version of what the shader shows: marches the ray through the volume with the current transfer
        /// function, organ overlay and every active cut (plane, sphere, box), and stops where accumulated
        /// opacity reaches `threshold`. Used for hovering/clicking organs and for placing the dig sphere.
        /// </summary>
        public bool RaycastVisible(Ray ray, out VolumeHit hit, CrossSectionObject ignore = null, float threshold = 0.35f)
        {
            hit = default;
            if (Volume == null || Volume.dataset == null || Volume.transferFunction == null) return false;
            Matrix4x4 toLocal = Volume.volumeContainerObject.transform.worldToLocalMatrix;
            Vector3 o = toLocal.MultiplyPoint3x4(ray.origin), d = toLocal.MultiplyVector(ray.direction);

            // Slab test against the unit cube [-0.5, 0.5]^3 (texture coordinate = local + 0.5).
            float t0 = 0f, t1 = float.MaxValue;
            for (int a = 0; a < 3; a++)
            {
                if (Mathf.Abs(d[a]) < 1e-9f)
                {
                    if (o[a] < -0.5f || o[a] > 0.5f) return false;
                    continue;
                }
                float ta = (-0.5f - o[a]) / d[a], tb = (0.5f - o[a]) / d[a];
                t0 = Mathf.Max(t0, Mathf.Min(ta, tb));
                t1 = Mathf.Min(t1, Mathf.Max(ta, tb));
            }
            if (t1 <= t0) return false;

            var cuts = new List<(CrossSectionType type, Matrix4x4 m)>();
            foreach (var mb in FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
                if (mb is CrossSectionObject c && mb.isActiveAndEnabled && !ReferenceEquals(c, ignore))
                    cuts.Add((c.GetCrossSectionType(), c.GetMatrix()));

            VolumeDataset ds = Volume.dataset;
            float[] data = ds.data;
            float min = ds.GetMinDataValue(), range = Mathf.Max(1e-6f, ds.GetMaxDataValue() - min);
            int nx = ds.dimX, ny = ds.dimY, nz = ds.dimZ;
            float stepUvw = 0.5f / Mathf.Max(nx, Mathf.Max(ny, nz));
            float dt = stepUvw / d.magnitude;
            float exponent = stepUvw / (1.732f / 512f);   // TF alphas are per shader step at sampling rate 1
            TransferFunction tf = Volume.transferFunction;

            float acc = 0f;
            var organShare = new Dictionary<int, float>();
            if (mask == null) mask = GetComponent<MaskVolume>();
            for (float t = t0; t <= t1; t += dt)
            {
                Vector3 p = o + d * t;
                if (IsCut(p, cuts)) continue;
                if (mask != null && mask.IsRemovedLocal(p)) continue;   // dissected away
                int x = Mathf.Clamp((int)((p.x + 0.5f) * nx), 0, nx - 1);
                int y = Mathf.Clamp((int)((p.y + 0.5f) * ny), 0, ny - 1);
                int z = Mathf.Clamp((int)((p.z + 0.5f) * nz), 0, nz - 1);
                int idx = x + y * nx + z * nx * ny;

                int organ = organVoxels != null ? organVoxels[idx] : 0;
                float alpha = organ > 0 ? OrganAlpha(organ) : 0f;
                if (alpha <= 0f)
                {
                    organ = 0;
                    alpha = tf.GetColour(Mathf.Clamp01((data[idx] - min) / range)).a;
                }
                if (alpha <= 0f) continue;
                float contrib = (1f - acc) * (1f - Mathf.Pow(1f - alpha, exponent));
                acc += contrib;
                if (organ > 0) organShare[organ] = (organShare.TryGetValue(organ, out var s) ? s : 0f) + contrib;
                if (acc < threshold) continue;

                if (organ == 0 && organShare.Count > 0) organ = organShare.OrderByDescending(kv => kv.Value).First().Key;
                hit = new VolumeHit
                {
                    world = Volume.volumeContainerObject.transform.TransformPoint(p),
                    organId = organ,
                    hu = data[idx],
                };
                return true;
            }
            return false;
        }

        // Same tests as the shader's VolumeCutout.cginc, on container-local positions.
        private static bool IsCut(Vector3 local, List<(CrossSectionType type, Matrix4x4 m)> cuts)
        {
            foreach (var (type, m) in cuts)
            {
                Vector3 q = m.MultiplyPoint3x4(local);
                bool inBox = Mathf.Abs(q.x) <= 0.5f && Mathf.Abs(q.y) <= 0.5f && Mathf.Abs(q.z) <= 0.5f;
                bool clipped = type switch
                {
                    CrossSectionType.Plane => q.z > 0f,
                    CrossSectionType.BoxInclusive => !inBox,
                    CrossSectionType.BoxExclusive => inBox,
                    CrossSectionType.SphereInclusive => q.magnitude > 0.5f,
                    CrossSectionType.SphereExclusive => q.magnitude < 0.5f,
                    _ => false,
                };
                if (clipped) return true;
            }
            return false;
        }

        /// <summary>N key: the next folder of the last conversion, or the first folder of a newer one.</summary>
        private async Task LoadNextLatestAsync()
        {
            if (!TryReadLatestList(out var folders))
            {
                Debug.LogWarning($"No conversions listed in {LatestListPath}. Run the converter app first.");
                return;
            }
            bool sameList = latestFolders != null && folders.SequenceEqual(latestFolders);
            latestIndex = sameList ? (latestIndex + 1) % folders.Length : 0;
            latestFolders = folders;
            localFolder = folders[latestIndex];
            Debug.Log($"Loading {localFolder}");
            await ReloadAsync();
        }

        /// <summary>Replaces the current volume with the one in localFolder; the other components re-bind via Loaded.</summary>
        public async Task ReloadAsync()
        {
            if (Volume != null)
            {
                var old = Volume;
                Volume = null;
                Destroy(old.dataset);
                Destroy(old.gameObject);
                await Task.Yield();                    // let the Destroy calls run, then free the old 3D textures
                Resources.UnloadUnusedAssets();
                GC.Collect();
            }
            OverrideTransferFunction = null;
            await LoadGuardedAsync();
        }

        private async Task LoadGuardedAsync()
        {
            loading = true;
            try { await LoadAsync(); }
            catch (Exception e) { Debug.LogException(e); }
            finally { loading = false; }
        }

        public async Task LoadAsync()
        {
            var t0 = Time.realtimeSinceStartup;
            byte[] raw;
            string json;

            if (source == Source.LocalFiles)
            {
                string rawPath = Path.Combine(localFolder, "volume.raw");
                string jsonPath = Path.Combine(localFolder, "volume.json");
                if (!File.Exists(rawPath) || !File.Exists(jsonPath))
                    throw new FileNotFoundException($"volume.raw / volume.json not found in {localFolder}");
                json = File.ReadAllText(jsonPath);
                raw = await Task.Run(() => File.ReadAllBytes(rawPath));
            }
            else
            {
                string body = $"{{\"path\":\"{seriesPath}\",\"target_spacing_mm\":{targetSpacingMm.ToString(System.Globalization.CultureInfo.InvariantCulture)},\"max_dim\":{maxDim}}}";
                json = Encoding.UTF8.GetString(await Request($"{serverUrl}/api/volume/load", body));
                var m = JsonUtility.FromJson<VolumeMeta>(json);
                raw = await Request($"{serverUrl}/api/volume/{m.volume_id}/raw", null);
            }

            Meta = JsonUtility.FromJson<VolumeMeta>(json);
            if (Meta.format != "int16" || Meta.endianness != "little")
                throw new InvalidDataException($"Unsupported volume format {Meta.format}/{Meta.endianness}");
            if (raw.LongLength != Meta.VoxelCount * 2)
                throw new InvalidDataException($"volume.raw is {raw.LongLength} bytes, expected {Meta.VoxelCount * 2}");
            foreach (var w in Meta.warnings ?? Array.Empty<string>()) Debug.LogWarning("[backend] " + w);

            // ScriptableObject must be created on the main thread; the float conversion can run in the background.
            VolumeDataset ds = ScriptableObject.CreateInstance<VolumeDataset>();
            ds.datasetName = source == Source.LocalFiles ? Path.GetFileName(localFolder) : seriesPath;
            ds.filePath = localFolder;
            ds.dimX = Meta.dim_x; ds.dimY = Meta.dim_y; ds.dimZ = Meta.dim_z;
            ds.data = await Task.Run(() => DecodeInt16(raw));
            ds.scale = new Vector3(Meta.size_mm[0], Meta.size_mm[1], Meta.size_mm[2]) / 1000f;   // metres
            ds.rotation = Quaternion.identity;   // backend already produced Unity axis order
            ds.FixDimensions();

            Volume = await VolumeObjectFactory.CreateObjectAsync(ds);
            Volume.transform.SetParent(transform, false);
            Volume.transform.localPosition = Vector3.zero;
            Volume.transform.localRotation = Quaternion.identity;
            float longest = Mathf.Max(ds.scale.x, ds.scale.y, ds.scale.z);
            Volume.transform.localScale = Vector3.one * (targetSize / longest);

            organVoxels = null;
            organStats = null;
            SelectedOrgan = 0;
            Organs = source == Source.LocalFiles ? await TryAddOrganLabelsAsync(ds) : null;
            if (Meta.lungs_only) preset = Preset.Lungs;
            else if (Organs != null) preset = Preset.Organs;
            else if (preset == Preset.Organs) preset = Preset.Body;
            ApplyTransferFunction();
            ApplyQuality(false);   // Update() switches to high quality once the view is still

            Debug.Log($"Volume loaded: {Meta.dim_x}x{Meta.dim_y}x{Meta.dim_z} ({raw.Length / 1e6:F0} MB), " +
                      $"physical {ds.scale.x * 100:F1}x{ds.scale.y * 100:F1}x{ds.scale.z * 100:F1} cm, " +
                      $"HU={Meta.is_hu}, preset={preset}, in {Time.realtimeSinceStartup - t0:F1}s");
            Loaded?.Invoke(Volume);

            // The volume is already visible unlit; shading appears once the gradients are computed.
            if (lighting)
            {
                float tl = Time.realtimeSinceStartup;
                await Volume.SetLightingEnabledAsync(true);
                Debug.Log($"Lighting ready in {Time.realtimeSinceStartup - tl:F1}s");
            }
        }

        /// <summary>
        /// labels.raw (uint8, same grid as volume.raw, 0 = no organ) + labels.json from tools/segment_organs.py.
        /// Added as a UnityVolumeRendering segmentation; ApplyTransferFunction sets their opacity per preset.
        /// </summary>
        private async Task<OrganLabel[]> TryAddOrganLabelsAsync(VolumeDataset ds)
        {
            string rawPath = Path.Combine(localFolder, "labels.raw"), jsonPath = Path.Combine(localFolder, "labels.json");
            if (!File.Exists(rawPath) || !File.Exists(jsonPath)) return null;

            var file = JsonUtility.FromJson<OrganLabelFile>(File.ReadAllText(jsonPath));
            byte[] labels = await Task.Run(() => File.ReadAllBytes(rawPath));
            if (file?.labels == null || file.labels.Length == 0 || labels.LongLength != Meta.VoxelCount)
            {
                Debug.LogWarning($"Ignoring organ labels in {localFolder}: size or content does not match the volume");
                return null;
            }

            VolumeDataset seg = ScriptableObject.CreateInstance<VolumeDataset>();
            seg.datasetName = ds.datasetName + " organs";
            seg.dimX = ds.dimX; seg.dimY = ds.dimY; seg.dimZ = ds.dimZ;
            seg.data = await Task.Run(() =>
            {
                var f = new float[labels.Length];
                for (int i = 0; i < labels.Length; i++) f[i] = labels[i];
                return f;
            });
            seg.scale = ds.scale;
            seg.rotation = Quaternion.identity;

            // The plugin maps label ids through max(id) and expects the list sorted by id.
            Array.Sort(file.labels, (a, b) => a.id.CompareTo(b.id));
            organVoxels = labels;
            float[] hu = ds.data;
            int nx = ds.dimX, ny = ds.dimY, nz = ds.dimZ;
            _ = Task.Run(() => organStats = ComputeOrganStats(labels, hu, nx, ny, nz));   // for the Inspect card
            Volume.AddSegmentation(seg, SegmentationLabels(file.labels, _ => 0f));
            Volume.SetSegmentationRenderMode(SegmentationRenderMode.OverlayColour);
            Debug.Log($"Organ labels: {string.Join(", ", file.labels.Select(l => l.name))}");
            return file.labels;
        }

        /// <summary>The overlay's label list; each label's alpha is its per-step opacity in the volume shader.</summary>
        private static List<SegmentationLabel> SegmentationLabels(OrganLabel[] organs, Func<int, float> alphaOf) =>
            organs.Select(o => new SegmentationLabel
            {
                id = o.id,
                name = o.name,
                colour = new Color(o.color[0], o.color[1], o.color[2], alphaOf(o.id)),
            }).ToList();

        private static float[] DecodeInt16(byte[] raw)
        {
            int n = raw.Length / 2;
            var shorts = new short[n];
            Buffer.BlockCopy(raw, 0, shorts, 0, raw.Length);   // host is little-endian on x64
            var f = new float[n];
            for (int i = 0; i < n; i++) f[i] = shorts[i];
            return f;
        }

        /// <summary>Rebuilds the clinical transfer function from the Inspector values (or shows the override).</summary>
        public void ApplyTransferFunction()
        {
            if (Volume == null || Meta == null) return;
            // Per-organ opacity: the same OrganAlpha() picking uses, so the GPU shows exactly what can be tapped —
            // visibility, the Organs preset, the bone view override, and the Inspect selection (ghost / isolate).
            if (Organs != null) Volume.SetSegmentationLabels(SegmentationLabels(Organs, OrganAlpha));
            if (OverrideTransferFunction != null)
            {
                Volume.SetTransferFunction(OverrideTransferFunction);
                return;
            }
            // Reuse one instance: GenerateTexture rewrites the same texture, so slider drags don't leak.
            if (clinicalTF == null) clinicalTF = ScriptableObject.CreateInstance<TransferFunction>();
            FillTransferFunction(clinicalTF, Meta);
            Volume.SetTransferFunction(clinicalTF);
        }

        /// <summary>
        /// UnityVolumeRendering normalises the texture to (v - min) / (max - min), so transfer-function
        /// positions are expressed through T(hu). For CT: fat and air invisible, organs a faint dark red,
        /// contrast-enhanced kidney cortex and arteries bright red, bone white.
        ///
        /// Alpha is applied per ray step (~300 steps across the volume) and the URP pass blends with
        /// SrcAlpha on premultiplied colour, so faint values fade quadratically: tune with the sliders.
        /// Organs (liver, spleen, muscle) all sit at ~25-60 HU and cannot be separated by HU alone.
        /// </summary>
        private void FillTransferFunction(TransferFunction tf, VolumeMeta meta)
        {
            tf.colourControlPoints.Clear();
            tf.alphaControlPoints.Clear();
            float lo = meta.value_min, hi = meta.value_max;
            float T(float v) => Mathf.Clamp01((v - lo) / Mathf.Max(1f, hi - lo));

            if (meta.is_hu && preset == Preset.Organs)
            {
                // The organs are drawn by the segmentation overlay in their label colours. Here: the skeleton,
                // and a faint grey ghost of skin and muscle so the organs sit inside a recognisable body.
                tf.AddControlPoint(new TFColourControlPoint(T(-1024), new Color(0.55f, 0.60f, 0.70f)));
                tf.AddControlPoint(new TFColourControlPoint(T(120), new Color(0.60f, 0.64f, 0.72f)));   // ghost
                tf.AddControlPoint(new TFColourControlPoint(T(250), new Color(1.00f, 0.93f, 0.85f)));   // bone
                tf.AddControlPoint(new TFColourControlPoint(T(700), new Color(0.98f, 0.96f, 0.92f)));
                tf.AddControlPoint(new TFColourControlPoint(T(3071), Color.white));

                float ghost = bodyGhostOpacity, bone = organsShowSkeleton ? organSkeletonOpacity : 0f;
                if (SelectedOrgan > 0 && SelectionMode == SelectMode.Isolate) ghost = bone = 0f;   // Inspect: isolate
                tf.AddControlPoint(new TFAlphaControlPoint(T(-300), 0f));           // air, lungs invisible
                tf.AddControlPoint(new TFAlphaControlPoint(T(-100), ghost * 0.3f));  // fat: barely there
                tf.AddControlPoint(new TFAlphaControlPoint(T(20), ghost));           // skin, muscle
                tf.AddControlPoint(new TFAlphaControlPoint(T(150), ghost));
                tf.AddControlPoint(new TFAlphaControlPoint(T(250), bone * 0.4f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(600), bone));
                tf.AddControlPoint(new TFAlphaControlPoint(T(3071), bone));
            }
            else if (meta.is_hu && preset == Preset.Lungs)
            {
                // Meant for a --lungs-only export: lung tissue as pale glass, vessels and bronchial walls red.
                // On a full chest the chest wall falls in the vessel band and covers the lungs.
                tf.AddControlPoint(new TFColourControlPoint(T(-1024), new Color(0.85f, 0.90f, 1.00f)));
                tf.AddControlPoint(new TFColourControlPoint(T(-700), new Color(0.88f, 0.90f, 1.00f)));   // lung tissue
                tf.AddControlPoint(new TFColourControlPoint(T(-450), new Color(0.95f, 0.50f, 0.45f)));
                tf.AddControlPoint(new TFColourControlPoint(T(-100), new Color(0.85f, 0.18f, 0.16f)));   // vessels, bronchial walls
                tf.AddControlPoint(new TFColourControlPoint(T(100), new Color(0.95f, 0.28f, 0.22f)));
                tf.AddControlPoint(new TFColourControlPoint(T(300), new Color(1.00f, 0.85f, 0.75f)));    // calcifications
                tf.AddControlPoint(new TFColourControlPoint(T(3071), Color.white));

                float glass = lungGlassOpacity, vessel = lungVesselOpacity;
                tf.AddControlPoint(new TFAlphaControlPoint(T(-930), 0f));             // air and airways invisible
                tf.AddControlPoint(new TFAlphaControlPoint(T(-880), glass * 0.7f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(-700), glass));
                tf.AddControlPoint(new TFAlphaControlPoint(T(-500), vessel * 0.036f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(-300), vessel * 0.43f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(0), vessel));
                tf.AddControlPoint(new TFAlphaControlPoint(T(200), Mathf.Min(1f, vessel * 1.2f)));
                tf.AddControlPoint(new TFAlphaControlPoint(T(3071), 0.9f));
            }
            else if (meta.is_hu)
            {
                tf.AddControlPoint(new TFColourControlPoint(T(-1024), new Color(0.45f, 0.10f, 0.08f)));
                tf.AddControlPoint(new TFColourControlPoint(T(0), new Color(0.50f, 0.12f, 0.10f)));
                tf.AddControlPoint(new TFColourControlPoint(T(60), new Color(0.80f, 0.30f, 0.25f)));     // organs, muscle
                tf.AddControlPoint(new TFColourControlPoint(T(150), new Color(1.00f, 0.30f, 0.22f)));    // kidney cortex, arteries
                tf.AddControlPoint(new TFColourControlPoint(T(250), new Color(1.00f, 0.55f, 0.40f)));
                tf.AddControlPoint(new TFColourControlPoint(T(400), new Color(1.00f, 0.88f, 0.78f)));    // cancellous bone
                tf.AddControlPoint(new TFColourControlPoint(T(700), new Color(0.98f, 0.96f, 0.92f)));
                tf.AddControlPoint(new TFColourControlPoint(T(3071), Color.white));                       // cortical bone

                // No point below the cutoff: the plugin inserts alpha 0 at the bottom of the range itself,
                // and a duplicate position there would divide by zero in GenerateTexture.
                float soft = softTissueOpacity, enh = enhancedOpacity, bone = boneOpacity;
                tf.AddControlPoint(new TFAlphaControlPoint(T(fatCutoffHU), 0f));     // air, lung, fat invisible
                tf.AddControlPoint(new TFAlphaControlPoint(T(20), soft * 0.57f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(70), soft));
                tf.AddControlPoint(new TFAlphaControlPoint(T(120), enh / 6f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(200), enh));
                tf.AddControlPoint(new TFAlphaControlPoint(T(350), (enh + bone) * 0.5f));
                tf.AddControlPoint(new TFAlphaControlPoint(T(600), bone));
                tf.AddControlPoint(new TFAlphaControlPoint(T(3071), bone));
            }
            else
            {
                // MR / unknown intensities: simple ramp, tune per dataset.
                tf.AddControlPoint(new TFColourControlPoint(0.0f, Color.black));
                tf.AddControlPoint(new TFColourControlPoint(0.5f, new Color(0.8f, 0.5f, 0.4f)));
                tf.AddControlPoint(new TFColourControlPoint(1.0f, Color.white));
                tf.AddControlPoint(new TFAlphaControlPoint(0.0f, 0.0f));
                tf.AddControlPoint(new TFAlphaControlPoint(0.15f, 0.0f));
                tf.AddControlPoint(new TFAlphaControlPoint(0.4f, 0.1f));
                tf.AddControlPoint(new TFAlphaControlPoint(1.0f, 0.8f));
            }
            tf.GenerateTexture();
        }

        private static async Task<byte[]> Request(string url, string jsonBody)
        {
            using var req = jsonBody == null ? UnityWebRequest.Get(url) : new UnityWebRequest(url, "POST");
            if (jsonBody != null)
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(jsonBody));
                req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json");
            }
            req.timeout = 600;
            var op = req.SendWebRequest();
            while (!op.isDone) await Task.Yield();
            if (req.result != UnityWebRequest.Result.Success)
                throw new IOException($"{url}: {req.error} {req.downloadHandler?.text}");
            return req.downloadHandler.data;
        }
    }
}
