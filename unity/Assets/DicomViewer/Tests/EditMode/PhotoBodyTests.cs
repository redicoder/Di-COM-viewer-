using DicomViewer.AnatomyLab;
using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>The photographed body's CPU side: picking through the volume cube, cuts respected, empty-space map.</summary>
    public class PhotoBodyTests
    {
        // A 40 x 30 x 20 voxel body (2 x 1 x 3 mm voxels, so 80 x 30 x 60 mm), holding a ball of tissue of radius 12 mm
        // at the centre, coloured red on the patient's left (+x) and green on the right.
        private const int NX = 40, NY = 30, NZ = 20;
        private static readonly Vector3 Spacing = new Vector3(2f, 1f, 3f);
        private GameObject go;
        private PhotoBody body;

        [SetUp]
        public void SetUp()
        {
            go = new GameObject("PhotoBody test");
            body = go.AddComponent<PhotoBody>();
            var data = new byte[NX * NY * NZ * 4];
            Vector3 centre = new Vector3(NX * Spacing.x, NY * Spacing.y, NZ * Spacing.z) * 0.5f;
            for (int z = 0; z < NZ; z++)
            for (int y = 0; y < NY; y++)
            for (int x = 0; x < NX; x++)
            {
                var mm = new Vector3((x + 0.5f) * Spacing.x, (y + 0.5f) * Spacing.y, (z + 0.5f) * Spacing.z);
                int i = ((z * NY + y) * NX + x) * 4;
                bool left = mm.x > centre.x;
                data[i] = (byte)(left ? 220 : 30);
                data[i + 1] = (byte)(left ? 30 : 200);
                data[i + 2] = 40;
                data[i + 3] = (byte)((mm - centre).magnitude < 12f ? 255 : 0);
            }
            var meta = new BodyMeta
            {
                dims = new[] { NX, NY, NZ },
                spacing_mm = new[] { Spacing.x, Spacing.y, Spacing.z },
                size_m = new[] { NX * Spacing.x / 1000f, NY * Spacing.y / 1000f, NZ * Spacing.z / 1000f },
            };
            body.Build(meta, data, null);
            go.transform.position = new Vector3(1f, 2f, 3f);     // away from the origin: world <-> body must hold
        }

        [TearDown]
        public void TearDown() => Object.DestroyImmediate(go);

        [Test]
        public void RayFromTheFrontHitsTheBallAtItsRadius()
        {
            Vector3 centre = go.transform.position;
            var ray = new Ray(centre + Vector3.back * 0.5f, Vector3.forward);      // the face looks to -z
            Assert.IsTrue(body.Raycast(ray, null, out Vector3 hit, out Vector3 normal));
            Assert.That(Vector3.Distance(hit, centre), Is.EqualTo(0.012f).Within(0.0025f));
            Assert.That(Vector3.Dot(normal, Vector3.back), Is.GreaterThan(0.9f), $"normal {normal}");
        }

        [Test]
        public void RayThatMissesTheBallMissesTheBody()
        {
            var ray = new Ray(go.transform.position + new Vector3(0.03f, 0f, -0.5f), Vector3.forward);
            Assert.IsFalse(body.Raycast(ray, null, out _, out _));
        }

        [Test]
        public void CutAwayTissueIsSeenThrough()
        {
            // Everything nearer than the centre is "cut": the ray now meets the far half of the ball's cut face.
            var ray = new Ray(go.transform.position + Vector3.back * 0.5f, Vector3.forward);
            Assert.IsTrue(body.Raycast(ray, local => local.z < 0f, out Vector3 hit, out _));
            Assert.That(hit.z - go.transform.position.z, Is.GreaterThanOrEqualTo(-0.001f));
        }

        [Test]
        public void ColourAtFollowsThePatientsLeft()
        {
            Color32 left = body.ColourAt(new Vector3(0.1f, 0f, 0f)), right = body.ColourAt(new Vector3(-0.1f, 0f, 0f));
            Assert.Greater(left.r, left.g);
            Assert.Greater(right.g, right.r);
        }

        [Test]
        public void OccupancyCoversTheBallAndSkipsEmptyCorners()
        {
            var data = new byte[NX * NY * NZ * 4];
            data[((10 * NY + 15) * NX + 20) * 4 + 3] = 255;                 // one tissue voxel
            byte[] occ = PhotoBody.Occupancy(data, new Vector3Int(NX, NY, NZ), out Vector3Int od);
            Assert.AreEqual(new Vector3Int(5, 4, 3), od);
            int Cell(int x, int y, int z) => occ[(z * od.y + y) * od.x + x];
            Assert.AreEqual(255, Cell(20 / PhotoBody.Brick, 15 / PhotoBody.Brick, 10 / PhotoBody.Brick));
            Assert.AreEqual(255, Cell(1, 2, 0), "grown by one cell");
            Assert.AreEqual(0, Cell(4, 0, 2), "far corner stays empty");
        }
    }
}
