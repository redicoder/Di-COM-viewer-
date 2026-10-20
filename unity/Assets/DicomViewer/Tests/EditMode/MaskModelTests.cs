using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>The CPU dissection mask: cut volumes against analytic shapes, and undo/redo/reset by replay.</summary>
    public class MaskModelTests
    {
        // Anisotropic voxels on purpose: cuts must be round in millimetres, not in voxels.
        private static readonly VolumeSpace Space = new VolumeSpace(new Vector3Int(80, 64, 48), new Vector3(0.8f, 1.0f, 1.25f));
        private static Vector3 Centre => Space.SizeMm * 0.5f;

        private static float RemovedMm3(MaskModel m) => m.RemovedCount() * Space.VoxelVolumeMm3;

        [Test]
        public void SphereRemovesItsVolumeWithin2Percent()
        {
            var m = new MaskModel(Space);
            const float r = 15f;
            var op = MaskOp.Stroke("dig");
            op.capsules.Add(new MaskCapsule(Centre, Centre, r));
            m.Add(op);
            float analytic = 4f / 3f * Mathf.PI * r * r * r;
            Assert.That(Mathf.Abs(RemovedMm3(m) - analytic) / analytic, Is.LessThan(0.02f));
        }

        [Test]
        public void CapsuleRemovesItsVolumeWithin2Percent()
        {
            var m = new MaskModel(Space);
            const float r = 6f, len = 20f;
            var a = Centre - new Vector3(len / 2, 0f, 0f);
            var b = Centre + new Vector3(len / 2, 0f, 0f);
            var op = MaskOp.Stroke("scalpel");
            op.capsules.Add(new MaskCapsule(a, b, r));
            m.Add(op);
            float analytic = Mathf.PI * r * r * len + 4f / 3f * Mathf.PI * r * r * r;
            Assert.That(Mathf.Abs(RemovedMm3(m) - analytic) / analytic, Is.LessThan(0.02f));
        }

        [Test]
        public void HalfSpaceRemovesExactlyOneSide()
        {
            var m = new MaskModel(Space);
            m.Add(MaskOp.HalfSpace(Vector3.right, Centre.x));   // x > centre removed: exactly half the columns
            Assert.AreEqual(Space.VoxelCount / 2, m.RemovedCount());
            Assert.IsTrue(m.IsRemovedMm(Centre + new Vector3(5f, 0f, 0f)));
            Assert.IsFalse(m.IsRemovedMm(Centre - new Vector3(5f, 0f, 0f)));
        }

        [Test]
        public void UndoRedoAndResetReplayToTheSameState()
        {
            var m = new MaskModel(Space);
            var dig = MaskOp.Stroke("dig");
            dig.capsules.Add(new MaskCapsule(Centre, Centre, 8f));
            m.Add(dig);
            byte[] afterDig = (byte[])m.Mask.Clone();

            m.Add(MaskOp.HalfSpace(new Vector3(0f, 1f, 1f), Vector3.Dot(new Vector3(0f, 1f, 1f).normalized, Centre)));
            byte[] afterKnife = (byte[])m.Mask.Clone();

            m.Undo();
            CollectionAssert.AreEqual(afterDig, m.Mask, "undo must restore the state before the knife");
            Assert.IsTrue(m.CanRedo);
            m.Redo();
            CollectionAssert.AreEqual(afterKnife, m.Mask, "redo must give the same state as the direct edit");

            m.Reset();
            Assert.AreEqual(0, m.RemovedCount());
            Assert.IsFalse(m.CanUndo || m.CanRedo);
        }

        [Test]
        public void AStrokeIsOneUndoStepAndAnEmptyStrokeIsDropped()
        {
            var m = new MaskModel(Space);
            m.Add(MaskOp.Stroke("scalpel"));
            m.AppendToLast(new MaskCapsule(Centre, Centre + Vector3.right * 10f, 3f));
            m.AppendToLast(new MaskCapsule(Centre + Vector3.right * 10f, Centre + Vector3.up * 10f, 3f));
            Assert.Greater(m.RemovedCount(), 0);
            Assert.AreEqual(1, m.Ops.Count);
            m.Undo();
            Assert.AreEqual(0, m.RemovedCount());

            m.Add(MaskOp.Stroke("dig"));   // pressed but never cut
            m.DiscardLastIfEmpty();
            Assert.AreEqual(0, m.Ops.Count);
            Assert.IsTrue(m.CanRedo, "dropping an empty stroke must not clear the redo of real cuts");
        }

        [Test]
        public void CutsOutsideTheVolumeAreHarmless()
        {
            var m = new MaskModel(Space);
            var op = MaskOp.Stroke("dig");
            op.capsules.Add(new MaskCapsule(new Vector3(-500f, -500f, -500f), new Vector3(-400f, -400f, -400f), 10f));
            m.Add(op);
            Assert.AreEqual(0, m.RemovedCount());
        }
    }
}
