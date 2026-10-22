using System;
using Unity.Collections;
using Unity.Mathematics;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// Depth below the outer skin on a voxel grid (half floats, mm; x fastest; voxel centres at (i + 0.5) x spacing),
    /// in native memory so the skin's physics job (Burst) can read it. Owned by whoever made it; Dispose when done.
    /// </summary>
    public sealed class SkinDepthGrid : IDisposable
    {
        public NativeArray<ushort> Data;
        public readonly Vector3Int Dims;
        public readonly Vector3 SpacingMm;

        public SkinDepthGrid(ushort[] halfMm, Vector3Int dims, Vector3 spacingMm)
        {
            if (halfMm.Length != dims.x * dims.y * dims.z) throw new ArgumentException("skin depth size does not match its grid");
            Data = new NativeArray<ushort>(halfMm, Allocator.Persistent);
            Dims = dims;
            SpacingMm = spacingMm;
        }

        public bool IsCreated => Data.IsCreated;

        /// <summary>Trilinear depth at a point in millimetres; 0 outside the grid (and outside the body).</summary>
        public float Sample(Vector3 mm) => Sample(Data, new int3(Dims.x, Dims.y, Dims.z), SpacingMm, mm);

        /// <summary>The same sampling, for jobs.</summary>
        public static float Sample(NativeArray<ushort> data, int3 d, float3 spacing, float3 mm)
        {
            float3 f = mm / spacing - 0.5f;
            int3 i0 = (int3)math.floor(f);
            if (math.any(i0 < 0) || math.any(i0 >= d - 1)) return 0f;
            float3 t = f - i0;
            int i = (i0.z * d.y + i0.y) * d.x + i0.x, sy = d.x, sz = d.x * d.y;
            float c00 = math.lerp(math.f16tof32(data[i]), math.f16tof32(data[i + 1]), t.x);
            float c10 = math.lerp(math.f16tof32(data[i + sy]), math.f16tof32(data[i + sy + 1]), t.x);
            float c01 = math.lerp(math.f16tof32(data[i + sz]), math.f16tof32(data[i + sz + 1]), t.x);
            float c11 = math.lerp(math.f16tof32(data[i + sz + sy]), math.f16tof32(data[i + sz + sy + 1]), t.x);
            return math.lerp(math.lerp(c00, c10, t.y), math.lerp(c01, c11, t.y), t.z);
        }

        public void Dispose()
        {
            if (Data.IsCreated) Data.Dispose();
        }
    }
}
