using System.Collections.Generic;
using DicomViewer.AnatomyLab;
using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>The Anatomy Lab's hands-on tools: flaps folding about a curved cut, the scalpel meeting the skin.</summary>
    public class LabToolsTests
    {
        private static readonly Vector3 SizeMm = new Vector3(100f, 100f, 100f);

        // A 60 mm cut along x that bows 10 mm out of the body (towards -z, the way the face looks) in its middle,
        // like a cut across a forehead.
        private static List<Vector3> BowedCut()
        {
            var cut = new List<Vector3>();
            for (int i = 0; i <= 20; i++)
            {
                float s = i / 20f;
                cut.Add(new Vector3(20f + 60f * s, 60f, 50f - 40f * s * (1f - s)) / 100f);
            }
            return cut;
        }

        [Test]
        public void FlapHingesAlongTheCutsCurveNotItsChord()
        {
            var go = new GameObject("Flaps test");
            try
            {
                var flaps = go.AddComponent<TissueFlaps>();
                flaps.Bind(null, SizeMm);
                List<Vector3> cut = BowedCut();
                int id = flaps.Begin(cut, Vector3.down, Vector3.back, 14f, 5f);
                flaps.SetFold(id, 90f / flaps.maxFoldAngleDeg);

                // Folded to 90 degrees, the free edge (the cut) stands straight out of the skin above the hinge,
                // 14 mm below the cut. A hinge on the chord would put it 10 mm deeper, inside the head.
                Vector3 mid = Vector3.Scale(cut[10], SizeMm);
                Vector3 shown = Vector3.Scale(flaps.DisplayUvw(id, cut[10]), SizeMm);
                Vector3 expected = mid + Vector3.down * 14f + Vector3.back * 14f;
                Assert.That(Vector3.Distance(shown, expected), Is.LessThan(0.6f), $"shown at {shown}, expected {expected}");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void UnfoldedFlapLeavesTissueInPlace()
        {
            var go = new GameObject("Flaps test");
            try
            {
                var flaps = go.AddComponent<TissueFlaps>();
                flaps.Bind(null, SizeMm);
                List<Vector3> cut = BowedCut();
                int id = flaps.Begin(cut, Vector3.down, Vector3.back, 14f, 5f);
                Vector3 p = cut[7] + new Vector3(0f, -0.05f, 0.01f);
                Assert.That(Vector3.Distance(flaps.DisplayUvw(id, p), p), Is.LessThan(1e-5f));
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
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
