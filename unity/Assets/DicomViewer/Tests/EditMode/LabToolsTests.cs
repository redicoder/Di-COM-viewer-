using DicomViewer.AnatomyLab;
using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>The Anatomy Lab's hands-on tools: skin physics on a ball of tissue, the scalpel meeting the skin.</summary>
    public class LabToolsTests
    {
        // A ball of tissue 60 mm across its radius, centred at (100, 100, 100) mm: skin all round, fat beneath.
        private sealed class Ball : ITissueField, System.IDisposable
        {
            public static readonly Vector3 Centre = new Vector3(100f, 100f, 100f);
            public const float R = 60f;
            public float Alpha(Vector3 mm) => Mathf.Clamp01(R - (mm - Centre).magnitude + 0.5f);
            public float SkinDepth(Vector3 mm) => Mathf.Max(0f, R - (mm - Centre).magnitude);
            public SkinDepthGrid Grid { get; }

            public Ball()
            {
                // 1 mm voxels over 200 mm: the ball and room around it.
                var dims = new Vector3Int(200, 200, 200);
                var depth = new ushort[dims.x * dims.y * dims.z];
                for (int z = 0; z < dims.z; z++)
                for (int y = 0; y < dims.y; y++)
                for (int x = 0; x < dims.x; x++)
                    depth[(z * dims.y + y) * dims.x + x] = Mathf.FloatToHalf(SkinDepth(new Vector3(x + 0.5f, y + 0.5f, z + 0.5f)));
                Grid = new SkinDepthGrid(depth, dims, Vector3.one);
            }

            public void Dispose() => Grid.Dispose();
        }

        private static Ball ball;

        [OneTimeSetUp]
        public void MakeBall() => ball = new Ball();

        [OneTimeTearDown]
        public void FreeBall() => ball?.Dispose();

        private TissueSheet made;

        [TearDown]
        public void FreeSheet()
        {
            made?.Dispose();
            made = null;
        }

        private static readonly Vector3 Gravity = new Vector3(0f, -9810f, 0f);

        // The ball's skin at (x, y) mm from the front's centre (the front looks to -z), `depth` mm under it.
        private static Vector3 OnFront(float x, float y, float depth = 0f)
        {
            Vector3 dir = new Vector3(x, y, -Mathf.Sqrt(Ball.R * Ball.R - x * x - y * y)).normalized;
            return Ball.Centre + dir * (Ball.R - depth);
        }

        // A scalpel cut through the skin along a straight line on the front, as the scalpel's capsules make it.
        private static void Cut(TissueSheet sheet, Vector2 from, Vector2 to)
        {
            const int steps = 16;
            for (int k = 0; k < steps; k++)
            {
                Vector2 a = Vector2.Lerp(from, to, k / (float)steps), b = Vector2.Lerp(from, to, (k + 1) / (float)steps);
                sheet.CutCapsule(OnFront(a.x, a.y, 1.5f), OnFront(b.x, b.y, 1.5f), 0.8f);
            }
        }

        private TissueSheet FrontSheet() => made = FrontSheetUnowned();

        private static TissueSheet FrontSheetUnowned()
        {
            var sheet = TissueSheet.Create(ball, OnFront(0f, 0f), Vector3.back, 1.5f, 5f);
            sheet.Table = new Vector4(0f, 1f, 0f, Ball.Centre.y - Ball.R - 1.5f);
            return sheet;
        }

        // The hand takes the skin at (x, y) and moves it by `by` over `seconds`, then lets go.
        private static void Pull(TissueSheet sheet, Vector2 at, Vector3 by, float seconds)
        {
            int node = sheet.NearestNode(OnFront(at.x, at.y));
            Assert.That(node, Is.GreaterThanOrEqualTo(0));
            sheet.Grab(node);
            Vector3 start = sheet.X[2 * node];
            int frames = Mathf.RoundToInt(seconds * 60f);
            for (int f = 1; f <= frames; f++)
            {
                sheet.MoveHand(start + by * (f / (float)frames));
                sheet.Step(1f / 60f, Gravity);
            }
            for (int f = 0; f < 15; f++) sheet.Step(1f / 60f, Gravity);
        }

        private static int Count(TissueSheet sheet, TissueSheet.Node state)
        {
            int c = 0;
            foreach (TissueSheet.Node s in sheet.State) if (s == state) c++;
            return c;
        }

        [Test]
        public void PieceCutAllRoundComesAwayAndFallsOntoTheTray()
        {
            TissueSheet sheet = FrontSheet();
            Cut(sheet, new Vector2(-10f, 10f), new Vector2(10f, 10f));
            Cut(sheet, new Vector2(10f, 10f), new Vector2(10f, -10f));
            Cut(sheet, new Vector2(10f, -10f), new Vector2(-10f, -10f));
            Cut(sheet, new Vector2(-10f, -10f), new Vector2(-10f, 10f));

            Pull(sheet, new Vector2(0f, 7f), new Vector3(0f, 0f, -45f), 1.5f);
            Assert.That(sheet.IsAnchored(sheet.NearestNode(OnFront(0f, 0f))), Is.False, "the piece has come away");
            Assert.That(sheet.State[sheet.NearestNode(OnFront(0f, 20f))], Is.Not.EqualTo(TissueSheet.Node.Peeled),
                "skin outside the cut stays on the body");

            sheet.Release();
            for (int f = 0; f < 240; f++) sheet.Step(1f / 60f, Gravity);
            float low = float.MaxValue, high = float.MinValue;
            for (int n = 0; n < TissueSheet.N * TissueSheet.N; n++)
            {
                if (sheet.State[n] != TissueSheet.Node.Peeled) continue;
                low = Mathf.Min(low, sheet.X[2 * n].y, sheet.X[2 * n + 1].y);
                high = Mathf.Max(high, sheet.X[2 * n].y, sheet.X[2 * n + 1].y);
            }
            Assert.That(low, Is.GreaterThan(sheet.Table.w - 0.5f), "nothing sinks into the tray");
            Assert.That(high, Is.LessThan(sheet.Table.w + 12f), $"the piece lies on the tray (top at {high}, tray at {sheet.Table.w})");
        }

        [Test]
        public void LoosePieceKeepsItsShapeInTheHand()
        {
            // Skin is stiff for its size: a 3 cm piece held by one edge hangs open, it does not fold up like cloth.
            TissueSheet sheet = FrontSheet();
            Cut(sheet, new Vector2(-15f, 10f), new Vector2(15f, 10f));
            Cut(sheet, new Vector2(15f, 10f), new Vector2(15f, -10f));
            Cut(sheet, new Vector2(15f, -10f), new Vector2(-15f, -10f));
            Cut(sheet, new Vector2(-15f, -10f), new Vector2(-15f, 10f));
            Pull(sheet, new Vector2(0f, 8.5f), new Vector3(0f, 0f, -50f), 1.5f);
            for (int f = 0; f < 90; f++) sheet.Step(1f / 60f, Gravity);    // still held: let it settle
            float wide = 0f;
            foreach (var p in sheet.Pieces())
                if (!p.anchored && p.nodes > 50) wide = Mathf.Max(wide, p.size.x / p.restSize.x);
            Assert.That(wide, Is.GreaterThan(0.75f), $"held by its edge the piece stays {wide:P0} as wide as it was");
        }

        [Test]
        public void FlapCutOnThreeSidesFoldsDownAboutItsBase()
        {
            TissueSheet sheet = FrontSheet();
            Cut(sheet, new Vector2(-10f, 10f), new Vector2(10f, 10f));          // top
            Cut(sheet, new Vector2(10f, 10f), new Vector2(10f, -10f));          // sides; the bottom stays
            Cut(sheet, new Vector2(-10f, -10f), new Vector2(-10f, 10f));
            int tip = sheet.NearestNode(OnFront(0f, 8.5f));
            float restY = sheet.X[2 * tip].y;

            // Lifted straight out by its free edge, as a flap is raised, it peels down to its base; let go, it hangs.
            Pull(sheet, new Vector2(0f, 8.5f), new Vector3(0f, 0f, -16f), 1f);
            sheet.Release();
            for (int f = 0; f < 180; f++) sheet.Step(1f / 60f, Gravity);

            Assert.That(sheet.IsAnchored(tip), Is.True, "the flap is still joined at its base");
            Assert.That(sheet.X[2 * tip].y, Is.LessThan(restY - 8f), "the free edge hangs down");
            // Folding undermines the base by a row or two, as on a real body; it does not strip the skin beyond.
            Assert.That(sheet.State[sheet.NearestNode(OnFront(0f, -17f))], Is.Not.EqualTo(TissueSheet.Node.Peeled),
                "skin beyond the base stays on");
        }

        [Test]
        public void SingleCutOnlyLetsItsEdgeLift()
        {
            TissueSheet sheet = FrontSheet();
            Cut(sheet, new Vector2(-12f, 0f), new Vector2(12f, 0f));
            Pull(sheet, new Vector2(0f, -1.5f), new Vector3(0f, 0f, -6f), 0.5f);
            int peeled = Count(sheet, TissueSheet.Node.Peeled);
            Assert.That(peeled, Is.GreaterThan(0));
            // About 8 mm of undermining along a 24 mm cut: a lifted wound edge frees a strip, not the whole skin.
            Assert.That(peeled, Is.LessThan(130), $"{peeled} nodes torn off: lifting a wound's edge does not strip the skin");
            Assert.That(sheet.State[sheet.NearestNode(OnFront(0f, 2f))], Is.Not.EqualTo(TissueSheet.Node.Peeled),
                "the other side of the cut is untouched");
        }

        [Test]
        public void ScalpelBellySitsAtThePressedDepth()
        {
            var go = new GameObject("Instruments test");
            go.AddComponent<PhotoBody>();                        // not loaded: instruments are drawn 1 unit = 1 m
            var tools = go.AddComponent<LabInstruments>();
            try
            {
                tools.scalpelRollDeg = 0f;
                tools.ShowScalpel(Vector3.zero, Vector3.up, Vector3.right, 3f);
                tools.Apply();
                GameObject scalpel = GameObject.Find("Scalpel");
                Assert.That(scalpel, Is.Not.Null, "the scalpel shows when asked for");
                MeshFilter blade = scalpel.transform.Find("Pose/Blade").GetComponent<MeshFilter>();
                float lowest = float.MaxValue, highest = float.MinValue;
                foreach (Vector3 v in blade.sharedMesh.vertices)
                {
                    Vector3 w = blade.transform.TransformPoint(v);
                    lowest = Mathf.Min(lowest, w.y);
                    highest = Mathf.Max(highest, w.y);
                }
                Assert.That(lowest, Is.EqualTo(-0.003f).Within(1e-4f), "the belly 3 mm into the skin");
                Assert.That(highest, Is.GreaterThan(0.005f), "the rest of the blade above it");

                tools.Apply();                                     // not asked for this frame: hidden
                Assert.That(GameObject.Find("Scalpel"), Is.Null);
            }
            finally
            {
                tools.Release();
                Object.DestroyImmediate(go);
            }
        }
    }
}
