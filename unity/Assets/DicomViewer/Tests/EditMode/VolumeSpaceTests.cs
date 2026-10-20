using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>World / texture / millimetre conversions, including anisotropic spacing and a moved body.</summary>
    public class VolumeSpaceTests
    {
        private static readonly VolumeSpace Space = new VolumeSpace(new Vector3Int(40, 30, 20), new Vector3(0.8f, 1.25f, 2.0f));

        private static void Near(Vector3 expected, Vector3 actual, float tol = 1e-3f) =>
            Assert.That((expected - actual).magnitude, Is.LessThan(tol), $"expected {expected}, got {actual}");

        [Test]
        public void SizeIsDimsTimesSpacing() => Near(new Vector3(32f, 37.5f, 40f), Space.SizeMm);

        [Test]
        public void VoxelCentresAreHalfAVoxelIn()
        {
            Near(new Vector3(0.4f, 0.625f, 1.0f), Space.VoxelCentreMm(0, 0, 0));
            Near(new Vector3(31.6f, 36.875f, 39f), Space.VoxelCentreMm(39, 29, 19));
        }

        [Test]
        public void MmToVoxelFindsTheContainingVoxelAndClamps()
        {
            Assert.AreEqual(new Vector3Int(3, 2, 4), Space.MmToVoxel(Space.VoxelCentreMm(3, 2, 4)));
            Assert.AreEqual(new Vector3Int(0, 0, 0), Space.MmToVoxel(new Vector3(-5f, -5f, -5f)));
            Assert.AreEqual(new Vector3Int(39, 29, 19), Space.MmToVoxel(new Vector3(500f, 500f, 500f)));
        }

        [Test]
        public void UvwAndMmRoundTrip()
        {
            var mm = new Vector3(12.3f, 4.5f, 33.3f);
            Near(mm, Space.UvwToMm(Space.MmToUvw(mm)));
            Near(new Vector3(0.5f, 0.5f, 0.5f), Space.MmToUvw(Space.SizeMm * 0.5f));
            Near(Vector3.zero, VolumeSpace.LocalToUvw(new Vector3(-0.5f, -0.5f, -0.5f)));
        }

        [Test]
        public void WorldRoundTripThroughARotatedScaledContainer()
        {
            // Same set-up as the viewer: a root that is moved, turned and scaled; the container scaled to the
            // volume's size so one container unit per axis is the full extent.
            var root = new GameObject("root");
            var container = new GameObject("container");
            try
            {
                container.transform.SetParent(root.transform, false);
                container.transform.localScale = Space.SizeMm / 1000f;
                root.transform.SetPositionAndRotation(new Vector3(1f, -2f, 3f), Quaternion.Euler(20f, 135f, -40f));
                root.transform.localScale = Vector3.one * 7.5f;
                Transform c = container.transform;

                var mm = new Vector3(10f, 20f, 30f);
                Near(mm, Space.WorldToMm(c, Space.MmToWorld(c, mm)), 1e-2f);

                // mm space is physical: 10 mm along any axis is the same world length.
                float lx = (Space.MmToWorld(c, new Vector3(10f, 0f, 0f)) - Space.MmToWorld(c, Vector3.zero)).magnitude;
                float lz = (Space.MmToWorld(c, new Vector3(0f, 0f, 10f)) - Space.MmToWorld(c, Vector3.zero)).magnitude;
                Assert.That(Mathf.Abs(lx - lz), Is.LessThan(1e-4f));
                Assert.That(Mathf.Abs(Space.WorldPerMm(c) * 10f - lx), Is.LessThan(1e-4f));

                // A world direction maps to the matching mm direction.
                Vector3 dirMm = new Vector3(1f, 2f, -1f).normalized;
                Vector3 worldDir = Space.MmToWorld(c, dirMm * 5f) - Space.MmToWorld(c, Vector3.zero);
                Near(dirMm, Space.WorldDirToMm(c, worldDir).normalized, 1e-3f);
            }
            finally
            {
                Object.DestroyImmediate(root);
            }
        }
    }
}
