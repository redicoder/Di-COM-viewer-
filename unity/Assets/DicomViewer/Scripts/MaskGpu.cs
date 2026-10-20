using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

namespace DicomViewer
{
    /// <summary>
    /// The GPU half of the dissection mask: a 3D R8 texture (1 = tissue, 0 = removed) edited by
    /// Resources/MaskOps.compute. Same voxel ranges as MaskModel (MaskModel.CapsuleRange), so the GPU texture
    /// and the CPU copy always remove exactly the same voxels (tested in MaskGpuTests).
    /// </summary>
    public sealed class MaskGpu : IDisposable
    {
        public readonly VolumeSpace Space;
        public RenderTexture Texture { get; private set; }

        private readonly ComputeShader cs;
        private readonly int kFill, kCapsule, kHalfSpace;

        public static bool Supported => SystemInfo.supportsComputeShaders && Resources.Load<ComputeShader>("MaskOps") != null;

        public MaskGpu(VolumeSpace space)
        {
            Space = space;
            cs = Resources.Load<ComputeShader>("MaskOps");
            if (cs == null) throw new InvalidOperationException("Resources/MaskOps.compute not found");
            kFill = cs.FindKernel("Fill");
            kCapsule = cs.FindKernel("CutCapsule");
            kHalfSpace = cs.FindKernel("CutHalfSpace");

            var desc = new RenderTextureDescriptor(space.Dims.x, space.Dims.y, GraphicsFormat.R8_UNorm, 0)
            {
                dimension = TextureDimension.Tex3D,
                volumeDepth = space.Dims.z,
                enableRandomWrite = true,
                msaaSamples = 1,
            };
            Texture = new RenderTexture(desc) { filterMode = FilterMode.Bilinear, wrapMode = TextureWrapMode.Clamp, name = "DissectionMask" };
            Texture.Create();
            Fill(1f);
        }

        public void Dispose()
        {
            if (Texture == null) return;
            Texture.Release();
            if (Application.isPlaying) UnityEngine.Object.Destroy(Texture);
            else UnityEngine.Object.DestroyImmediate(Texture);   // edit-mode tests
            Texture = null;
        }

        public void Fill(float value)
        {
            SetCommon();
            cs.SetFloat("_Value", value);
            cs.SetTexture(kFill, "_Mask", Texture);
            cs.Dispatch(kFill, Groups(Space.Dims.x), Groups(Space.Dims.y), Groups(Space.Dims.z));
        }

        public void Replay(IEnumerable<MaskOp> ops)
        {
            Fill(1f);
            foreach (var op in ops) Apply(op);
        }

        public void Apply(MaskOp op)
        {
            if (op.kind == MaskOp.Kind.HalfSpace) HalfSpace(op.normal, op.offset);
            else foreach (var c in op.capsules) Capsule(c);
        }

        public void Capsule(MaskCapsule c)
        {
            MaskModel.CapsuleRange(Space, c, out var lo, out var hi);
            Vector3Int size = hi - lo;
            if (size.x <= 0 || size.y <= 0 || size.z <= 0) return;
            SetCommon();
            cs.SetInts("_Offset", lo.x, lo.y, lo.z);
            cs.SetFloat("_Value", 0f);
            cs.SetVector("_A", c.a);
            cs.SetVector("_B", c.b);
            cs.SetFloat("_Radius", c.radius);
            cs.SetTexture(kCapsule, "_Mask", Texture);
            cs.Dispatch(kCapsule, Groups(size.x), Groups(size.y), Groups(size.z));
        }

        public void HalfSpace(Vector3 normal, float offset)
        {
            SetCommon();
            cs.SetFloat("_Value", 0f);
            cs.SetVector("_Normal", normal);
            cs.SetFloat("_D", offset);
            cs.SetTexture(kHalfSpace, "_Mask", Texture);
            cs.Dispatch(kHalfSpace, Groups(Space.Dims.x), Groups(Space.Dims.y), Groups(Space.Dims.z));
        }

        /// <summary>Synchronous read-back (tests and diagnostics only): one byte per voxel, x fastest.</summary>
        public byte[] ReadBack()
        {
            var request = AsyncGPUReadback.Request(Texture, 0);
            request.WaitForCompletion();
            if (request.hasError) throw new InvalidOperationException("GPU read-back failed");
            var result = new byte[Space.VoxelCount];
            int slice = Space.Dims.x * Space.Dims.y;
            for (int z = 0; z < Space.Dims.z; z++)
            {
                var layer = request.GetData<byte>(z);
                for (int i = 0; i < slice; i++) result[z * slice + i] = layer[i] > 127 ? (byte)1 : (byte)0;
            }
            return result;
        }

        private void SetCommon()
        {
            cs.SetInts("_Dims", Space.Dims.x, Space.Dims.y, Space.Dims.z);
            cs.SetVector("_Spacing", Space.SpacingMm);
        }

        private static int Groups(int n) => Mathf.Max(1, (n + 7) / 8);
    }
}
