using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>
    /// The GPU mask (MaskOps.compute) must remove the same voxels as the CPU copy that picking uses.
    /// Needs a GPU with compute shaders; skipped otherwise (e.g. -nographics batch runs).
    /// </summary>
    public class MaskGpuTests
    {
        private static readonly VolumeSpace Space = new VolumeSpace(new Vector3Int(64, 48, 40), new Vector3(0.8f, 1.0f, 1.25f));

        private static List<MaskOp> SampleOps()
        {
            Vector3 c = Space.SizeMm * 0.5f;
            var dig = MaskOp.Stroke("dig");
            dig.capsules.Add(new MaskCapsule(c, c, 9f));
            var scalpel = MaskOp.Stroke("scalpel");
            scalpel.capsules.Add(new MaskCapsule(c + new Vector3(-15f, 8f, 0f), c + new Vector3(15f, 12f, 5f), 3f));
            var n = new Vector3(1f, 0.3f, -0.5f).normalized;
            var knife = MaskOp.HalfSpace(n, Vector3.Dot(n, c + new Vector3(12f, 0f, 0f)));
            return new List<MaskOp> { dig, scalpel, knife };
        }

        [Test]
        public void GpuAndCpuMasksAgree()
        {
            if (!MaskGpu.Supported) Assert.Ignore("No compute shader support");
            var ops = SampleOps();
            var cpu = new MaskModel(Space);
            foreach (var op in ops) cpu.Add(op);

            using var gpu = new MaskGpu(Space);
            gpu.Replay(ops);
            byte[] g = gpu.ReadBack();

            int differ = 0;
            for (int i = 0; i < g.Length; i++) if (g[i] != cpu.Mask[i]) differ++;
            // Same maths on both sides; allow a handful of voxels exactly on a boundary (float rounding).
            Assert.That(differ, Is.LessThanOrEqualTo(g.Length / 2000), $"{differ} voxels differ");
            Assert.Greater(cpu.RemovedCount(), 0);
        }

        [Test]
        public void ResetFillsTheWholeVolume()
        {
            if (!MaskGpu.Supported) Assert.Ignore("No compute shader support");
            using var gpu = new MaskGpu(Space);
            gpu.Replay(SampleOps());
            gpu.Fill(1f);
            foreach (byte b in gpu.ReadBack()) Assert.AreEqual(1, b);
        }
    }
}
