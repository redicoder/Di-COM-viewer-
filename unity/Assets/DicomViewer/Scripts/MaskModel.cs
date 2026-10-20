using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;

namespace DicomViewer
{
    /// <summary>A capsule in mm space: every voxel whose centre is within `radius` of segment a-b. a == b is a sphere.</summary>
    [Serializable]
    public struct MaskCapsule
    {
        public Vector3 a, b;
        public float radius;

        public MaskCapsule(Vector3 a, Vector3 b, float radius)
        {
            this.a = a;
            this.b = b;
            this.radius = radius;
        }
    }

    /// <summary>
    /// One dissection edit, in mm space so it replays identically on any machine (lessons, undo).
    /// Capsules: scalpel strokes and dig holes (a stroke is one op, however many capsules it has).
    /// HalfSpace: the knife; removes every voxel with dot(normal, p) > offset.
    /// </summary>
    [Serializable]
    public class MaskOp
    {
        public enum Kind { Capsules, HalfSpace }

        public Kind kind;
        public string tool;
        public List<MaskCapsule> capsules = new List<MaskCapsule>();
        public Vector3 normal;
        public float offset;

        public static MaskOp Stroke(string tool) => new MaskOp { kind = Kind.Capsules, tool = tool };

        public static MaskOp HalfSpace(Vector3 normal, float offset) =>
            new MaskOp { kind = Kind.HalfSpace, tool = "knife", normal = normal.normalized, offset = offset };

        /// <summary>Deep copy: the background CPU copy of the mask gets its own objects, never shared lists.</summary>
        public MaskOp Clone() => new MaskOp
        {
            kind = kind, tool = tool, normal = normal, offset = offset,
            capsules = new List<MaskCapsule>(capsules),
        };
    }

    /// <summary>
    /// The dissection state without any GPU: the ordered op list with undo/redo, and a CPU copy of the mask
    /// (1 = tissue present, 0 = removed) that picking uses. The GPU mask (MaskVolume) replays the same ops,
    /// so both always agree. Undo = drop the last op and replay the rest from a full body; replay is cheap
    /// because each op only touches its own bounding box.
    /// </summary>
    public class MaskModel
    {
        public readonly VolumeSpace Space;
        public readonly byte[] Mask;

        private readonly List<MaskOp> ops = new List<MaskOp>();
        private readonly Stack<MaskOp> redo = new Stack<MaskOp>();

        public MaskModel(VolumeSpace space)
        {
            Space = space;
            Mask = new byte[space.VoxelCount];
            Fill(1);
        }

        public IReadOnlyList<MaskOp> Ops => ops;
        public bool CanUndo => ops.Count > 0;
        public bool CanRedo => redo.Count > 0;

        /// <summary>
        /// Records a new op and applies it to the CPU mask. Redo is cleared only by an op that removes something:
        /// a stroke that starts empty (finger pressed, nothing cut yet) leaves redo alone until its first capsule.
        /// </summary>
        public void Add(MaskOp op)
        {
            ops.Add(op);
            if (op.kind == MaskOp.Kind.HalfSpace || op.capsules.Count > 0) redo.Clear();
            Apply(op);
        }

        /// <summary>Extends the last op while its tool is still active (a dig hole deepening, a scalpel stroke).</summary>
        public void AppendToLast(MaskCapsule c)
        {
            if (ops.Count == 0 || ops[ops.Count - 1].kind != MaskOp.Kind.Capsules) return;
            var last = ops[ops.Count - 1];
            if (last.capsules.Count == 0) redo.Clear();   // the stroke now really cuts
            last.capsules.Add(c);
            ApplyCapsule(c);
        }

        /// <summary>Drops the last op without touching redo (a stroke that ended before cutting anything).</summary>
        public void DiscardLastIfEmpty()
        {
            if (ops.Count > 0 && ops[ops.Count - 1].kind == MaskOp.Kind.Capsules && ops[ops.Count - 1].capsules.Count == 0)
                ops.RemoveAt(ops.Count - 1);
        }

        public MaskOp Undo()
        {
            if (ops.Count == 0) return null;
            var op = ops[ops.Count - 1];
            ops.RemoveAt(ops.Count - 1);
            redo.Push(op);
            ReplayAll();
            return op;
        }

        public MaskOp Redo()
        {
            if (redo.Count == 0) return null;
            var op = redo.Pop();
            ops.Add(op);
            Apply(op);
            return op;
        }

        public void Reset()
        {
            ops.Clear();
            redo.Clear();
            Fill(1);
        }

        /// <summary>Replace the whole history (loading a lesson).</summary>
        public void Load(IEnumerable<MaskOp> history)
        {
            ops.Clear();
            redo.Clear();
            ops.AddRange(history);
            ReplayAll();
        }

        public void ReplayAll()
        {
            Fill(1);
            foreach (var op in ops) Apply(op);
        }

        public bool IsRemovedMm(Vector3 mm)
        {
            Vector3Int v = Space.MmToVoxel(mm);
            return Mask[Space.Index(v.x, v.y, v.z)] == 0;
        }

        public long RemovedCount()
        {
            long n = 0;
            foreach (byte b in Mask) if (b == 0) n++;
            return n;
        }

        // ------------------------------------------------------------------ CPU rasterisation

        private void Fill(byte value) => Array.Fill(Mask, value);

        private void Apply(MaskOp op)
        {
            if (op.kind == MaskOp.Kind.HalfSpace) ApplyHalfSpace(op.normal, op.offset);
            else foreach (var c in op.capsules) ApplyCapsule(c);
        }

        /// <summary>
        /// Voxel index range [lo, hi) covering an mm-space box, clamped to the grid. Shared with the GPU
        /// dispatch (MaskVolume), so the CPU copy and the texture always touch exactly the same voxels.
        /// </summary>
        public static void VoxelRange(VolumeSpace space, Vector3 minMm, Vector3 maxMm, out Vector3Int lo, out Vector3Int hi)
        {
            Vector3 s = space.SpacingMm;
            lo = new Vector3Int(
                Mathf.Clamp(Mathf.FloorToInt(minMm.x / s.x - 0.5f), 0, space.Dims.x),
                Mathf.Clamp(Mathf.FloorToInt(minMm.y / s.y - 0.5f), 0, space.Dims.y),
                Mathf.Clamp(Mathf.FloorToInt(minMm.z / s.z - 0.5f), 0, space.Dims.z));
            hi = new Vector3Int(
                Mathf.Clamp(Mathf.CeilToInt(maxMm.x / s.x + 0.5f), 0, space.Dims.x),
                Mathf.Clamp(Mathf.CeilToInt(maxMm.y / s.y + 0.5f), 0, space.Dims.y),
                Mathf.Clamp(Mathf.CeilToInt(maxMm.z / s.z + 0.5f), 0, space.Dims.z));
        }

        public static void CapsuleRange(VolumeSpace space, MaskCapsule c, out Vector3Int lo, out Vector3Int hi)
        {
            Vector3 r = Vector3.one * c.radius;
            VoxelRange(space, Vector3.Min(c.a, c.b) - r, Vector3.Max(c.a, c.b) + r, out lo, out hi);
        }

        public void ApplyCapsule(MaskCapsule c)
        {
            CapsuleRange(Space, c, out var lo, out var hi);
            if (lo.x >= hi.x || lo.y >= hi.y || lo.z >= hi.z) return;
            Vector3 ab = c.b - c.a;
            float abLen2 = Mathf.Max(Vector3.Dot(ab, ab), 1e-12f), r2 = c.radius * c.radius;
            VolumeSpace space = Space;
            byte[] mask = Mask;
            Parallel.For(lo.z, hi.z, z =>
            {
                for (int y = lo.y; y < hi.y; y++)
                for (int x = lo.x; x < hi.x; x++)
                {
                    Vector3 p = space.VoxelCentreMm(x, y, z);
                    float t = Mathf.Clamp01(Vector3.Dot(p - c.a, ab) / abLen2);
                    if ((p - (c.a + t * ab)).sqrMagnitude <= r2) mask[space.Index(x, y, z)] = 0;
                }
            });
        }

        public void ApplyHalfSpace(Vector3 normal, float offset)
        {
            VolumeSpace space = Space;
            byte[] mask = Mask;
            Parallel.For(0, space.Dims.z, z =>
            {
                for (int y = 0; y < space.Dims.y; y++)
                for (int x = 0; x < space.Dims.x; x++)
                    if (Vector3.Dot(normal, space.VoxelCentreMm(x, y, z)) > offset) mask[space.Index(x, y, z)] = 0;
            });
        }
    }
}
