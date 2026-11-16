using DicomViewer.AnatomyLab;
using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>The modelled body's jaw: where a point of the lower lip goes when the mouth is opened.</summary>
    public class ModelBodyTests
    {
        private static ModelBody Body()
        {
            var body = new GameObject("body").AddComponent<ModelBody>();
            body.hasMouth = true;
            body.jawHinge = new Vector3(0.05f, 0.80f, 0.01f);
            body.jawAxis = new Vector3(1f, 0f, 0f);
            body.jawDegrees = 18f;
            body.mouthGrab = new Vector3(0f, 0.75f, 0.11f);       // in front of the hinge and under it
            return body;
        }

        [Test]
        public void TheClosedJawLeavesThePointWhereItIs()
        {
            ModelBody body = Body();
            Assert.That(Vector3.Distance(body.WithJaw(body.mouthGrab, 0f), body.mouthGrab), Is.LessThan(1e-6f));
            Object.DestroyImmediate(body.gameObject);
        }

        [Test]
        public void TheOpenJawCarriesTheLowerLipDownAndBackAboutTheHinge()
        {
            ModelBody body = Body();
            Vector3 open = body.WithJaw(body.mouthGrab, 1f);
            Assert.That(open.y, Is.LessThan(body.mouthGrab.y - 0.035f), "the lip goes down by centimetres (the jaw's turn and the lip's own 10 mm)");
            Assert.That(open.z, Is.LessThan(body.mouthGrab.z), "and back");
            Assert.That(open.x, Is.EqualTo(body.mouthGrab.x).Within(1e-6f), "not sideways");
            float before = Vector3.ProjectOnPlane(body.mouthGrab + Vector3.down * 0.010f - body.jawHinge, body.jawAxis).magnitude;
            float after = Vector3.ProjectOnPlane(open - body.jawHinge, body.jawAxis).magnitude;
            Assert.That(after, Is.EqualTo(before).Within(1e-5f), "drawn down first, it then stays as far from the hinge as it was");
            Object.DestroyImmediate(body.gameObject);
        }

        [Test]
        public void TheUpperLipIsLiftedByItselfUpTheFace()
        {
            ModelBody body = Body();
            body.lipUp = new Vector3(0f, 0.9f, 0.44f);
            Vector3 lip = body.mouthGrab + Vector3.up * 0.012f;
            Assert.That(Vector3.Distance(body.WithLift(lip, 0f), lip), Is.LessThan(1e-7f));
            Vector3 lifted = body.WithLift(lip, 1f);
            Assert.That(Vector3.Distance(lifted, lip), Is.EqualTo(0.006f).Within(1e-6f), "6 mm in all");
            Assert.That(lifted.y, Is.GreaterThan(lip.y + 0.005f), "up the face");
            Assert.That(lifted.z, Is.GreaterThan(lip.z), "and a little forward, off the teeth");
            Object.DestroyImmediate(body.gameObject);
        }

        [Test]
        public void OnlyTheMeshesWithJawWeightsAreHandedTheJawsTurn()
        {
            ModelBody body = Body();
            Shader shader = Shader.Find("DicomViewer/LabModel");
            Assert.That(shader, Is.Not.Null);
            var chin = GameObject.CreatePrimitive(PrimitiveType.Cube).GetComponent<Renderer>();
            var skull = GameObject.CreatePrimitive(PrimitiveType.Cube).GetComponent<Renderer>();
            chin.sharedMaterial = new Material(shader);
            skull.sharedMaterial = new Material(shader);
            body.jawRenderers.Add(chin);
            body.jaw = 0.5f;
            body.PushJaw();
            Vector4 hinge = chin.sharedMaterial.GetVector("_JawHinge");
            Assert.That(hinge.w, Is.EqualTo(9f * Mathf.Deg2Rad).Within(1e-5f));
            Assert.That((Vector3)hinge, Is.EqualTo(body.jawHinge));
            Assert.That(chin.sharedMaterial.GetVector("_LipPull").w, Is.EqualTo(0.005f).Within(1e-6f), "half open: the lip half way down (10 mm in all)");
            Assert.That(chin.sharedMaterial.GetVector("_LipLift").w, Is.EqualTo(0f), "the upper lip is not lifted by the jaw");
            body.upperLip = 0.5f;
            body.PushJaw();
            Assert.That(chin.sharedMaterial.GetVector("_LipLift").w, Is.EqualTo(0.003f).Within(1e-6f), "half lifted: 3 mm of its 6");
            Assert.That(chin.sharedMaterial.GetVector("_JawHinge").w, Is.EqualTo(9f * Mathf.Deg2Rad).Within(1e-5f), "and the jaw stays where it was");
            Assert.That(skull.sharedMaterial.GetVector("_JawHinge").w, Is.EqualTo(0f), "a mesh without jaw weights is not turned");
            body.hasMouth = false;
            body.PushJaw();
            Assert.That(chin.sharedMaterial.GetVector("_JawHinge").w, Is.EqualTo(0f), "a body without a mouth turns nothing");
            Object.DestroyImmediate(chin.sharedMaterial);
            Object.DestroyImmediate(skull.sharedMaterial);
            Object.DestroyImmediate(chin.gameObject);
            Object.DestroyImmediate(skull.gameObject);
            Object.DestroyImmediate(body.gameObject);
        }
    }
}
