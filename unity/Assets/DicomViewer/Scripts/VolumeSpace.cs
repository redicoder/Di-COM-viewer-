using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Coordinate conversions for one volume. Three spaces:
    ///   local  : the volume container's cube, -0.5..0.5 per axis (UnityVolumeRendering's mesh space)
    ///   uvw    : texture coordinates, 0..1 per axis (= local + 0.5)
    ///   mm     : millimetres from the volume's corner, uvw * size_mm. Isotropic and physical: a sphere in mm
    ///            is a real sphere, whatever the voxel spacing. All dissection maths happens here.
    /// Texture axes: x = patient left, y = superior, z = posterior (backend convention).
    /// Voxel (i, j, k) has its centre at ((i, j, k) + 0.5) * spacing in mm.
    /// </summary>
    public readonly struct VolumeSpace
    {
        public readonly Vector3Int Dims;
        public readonly Vector3 SpacingMm;

        public VolumeSpace(Vector3Int dims, Vector3 spacingMm)
        {
            Dims = dims;
            SpacingMm = spacingMm;
        }

        public Vector3 SizeMm => new Vector3(Dims.x * SpacingMm.x, Dims.y * SpacingMm.y, Dims.z * SpacingMm.z);
        public long VoxelCount => (long)Dims.x * Dims.y * Dims.z;
        public float VoxelVolumeMm3 => SpacingMm.x * SpacingMm.y * SpacingMm.z;

        public static Vector3 LocalToUvw(Vector3 local) => local + new Vector3(0.5f, 0.5f, 0.5f);
        public static Vector3 UvwToLocal(Vector3 uvw) => uvw - new Vector3(0.5f, 0.5f, 0.5f);

        public Vector3 UvwToMm(Vector3 uvw) => Vector3.Scale(uvw, SizeMm);

        public Vector3 MmToUvw(Vector3 mm)
        {
            Vector3 s = SizeMm;
            return new Vector3(mm.x / s.x, mm.y / s.y, mm.z / s.z);
        }

        public Vector3 VoxelCentreMm(int x, int y, int z) =>
            new Vector3((x + 0.5f) * SpacingMm.x, (y + 0.5f) * SpacingMm.y, (z + 0.5f) * SpacingMm.z);

        /// <summary>The voxel containing a mm position (clamped to the grid).</summary>
        public Vector3Int MmToVoxel(Vector3 mm) => new Vector3Int(
            Mathf.Clamp(Mathf.FloorToInt(mm.x / SpacingMm.x), 0, Dims.x - 1),
            Mathf.Clamp(Mathf.FloorToInt(mm.y / SpacingMm.y), 0, Dims.y - 1),
            Mathf.Clamp(Mathf.FloorToInt(mm.z / SpacingMm.z), 0, Dims.z - 1));

        public int Index(int x, int y, int z) => x + y * Dims.x + z * Dims.x * Dims.y;

        // ---- world <-> mm through the container transform (its lossy scale is proportional to size_mm) ----

        public Vector3 WorldToMm(Transform container, Vector3 world) =>
            UvwToMm(LocalToUvw(container.InverseTransformPoint(world)));

        public Vector3 MmToWorld(Transform container, Vector3 mm) =>
            container.TransformPoint(UvwToLocal(MmToUvw(mm)));

        /// <summary>A world direction expressed in mm space (not normalised).</summary>
        public Vector3 WorldDirToMm(Transform container, Vector3 worldDir) =>
            Vector3.Scale(container.InverseTransformVector(worldDir), SizeMm);

        /// <summary>World length of one millimetre inside the volume (uniform volume scale assumed).</summary>
        public float WorldPerMm(Transform container) =>
            container.TransformVector(new Vector3(1f / SizeMm.x, 0f, 0f)).magnitude;
    }
}
