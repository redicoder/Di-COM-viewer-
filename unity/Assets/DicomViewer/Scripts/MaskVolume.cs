using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// The dissection engine. A 3D mask texture on the volume's grid (1 = tissue, 0 = removed, MaskGpu) is bound
    /// to the forked volume shader as _MaskTex, so cuts are unlimited (unlike UnityVolumeRendering's 8 cross
    /// sections).
    ///
    /// Every edit is a MaskOp in millimetres. The main thread owns the op history (undo/redo, lessons) and runs
    /// each op on the GPU at once. A CPU copy of the mask (MaskModel) is kept up to date on a background thread
    /// with copies of the same ops; picking reads it. Undo/redo/reset replay the history on both sides.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class MaskVolume : MonoBehaviour
    {
        public event Action Changed;

        private VolumeLoader loader;
        private MaskGpu gpu;

        private readonly List<MaskOp> ops = new List<MaskOp>();
        private readonly Stack<MaskOp> redo = new Stack<MaskOp>();
        private MaskOp live;                   // a stroke still being drawn (dig held down, scalpel dragging)

        private MaskModel cpu;                 // touched only inside `lane`
        private Task lane = Task.CompletedTask;

        public VolumeSpace Space { get; private set; }
        public bool Ready => gpu != null;
        public IReadOnlyList<MaskOp> Ops => ops;
        public bool CanUndo => ops.Count > 0 && live == null;
        public bool CanRedo => redo.Count > 0 && live == null;
        public int CutCount => ops.Count;
        public bool StrokeActive => live != null;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            loader.Loaded += _ => OnVolumeLoaded();
        }

        private void OnVolumeLoaded()
        {
            gpu?.Dispose();
            gpu = null;
            ops.Clear();
            redo.Clear();
            live = null;

            VolumeMeta m = loader.Meta;
            Space = new VolumeSpace(new Vector3Int(m.dim_x, m.dim_y, m.dim_z),
                new Vector3(m.spacing_mm[0], m.spacing_mm[1], m.spacing_mm[2]));
            if (!MaskGpu.Supported)
            {
                Debug.LogWarning("Dissection mask unavailable: compute shaders not supported or MaskOps.compute missing");
                return;
            }
            gpu = new MaskGpu(Space);
            Bind();

            VolumeSpace space = Space;
            lane = Task.Run(() => cpu = new MaskModel(space));
            Changed?.Invoke();
        }

        // UnityVolumeRendering rewrites its material's properties now and then; re-assert ours every frame.
        private void LateUpdate() => Bind();

        private void Bind()
        {
            var mr = loader.Volume != null ? loader.Volume.meshRenderer : null;
            if (mr == null || mr.sharedMaterial == null) return;
            mr.sharedMaterial.SetTexture("_MaskTex", gpu?.Texture);
            mr.sharedMaterial.SetFloat("_MaskEnabled", gpu != null ? 1f : 0f);
        }

        private void OnDestroy() => gpu?.Dispose();

        // ------------------------------------------------------------------ edits

        /// <summary>A complete op (the knife): recorded as one undo step and applied at once.</summary>
        public void Apply(MaskOp op)
        {
            if (!Ready) return;
            EndStroke();
            ops.Add(op);
            redo.Clear();
            gpu.Apply(op);
            var copy = op.Clone();
            Enqueue(m => m.Add(copy));
            Changed?.Invoke();
        }

        /// <summary>Starts a stroke (scalpel, dig): one undo step however many capsules it gets.</summary>
        public void BeginStroke(string tool)
        {
            if (!Ready) return;
            EndStroke();
            live = MaskOp.Stroke(tool);
            ops.Add(live);   // redo is cleared by the first capsule, not by merely touching the screen
            var copy = live.Clone();
            Enqueue(m => m.Add(copy));
            Changed?.Invoke();
        }

        public void ExtendStroke(MaskCapsule c)
        {
            if (live == null || !Ready) return;
            if (live.capsules.Count == 0) redo.Clear();
            live.capsules.Add(c);
            gpu.Capsule(c);
            Enqueue(m => m.AppendToLast(c));
        }

        /// <summary>Ends the current stroke; a stroke that removed nothing is dropped from the history.</summary>
        public void EndStroke()
        {
            if (live == null) return;
            var finished = live;
            live = null;
            if (finished.capsules.Count == 0)
            {
                ops.Remove(finished);
                Enqueue(m => m.DiscardLastIfEmpty());
            }
            Changed?.Invoke();
        }

        public void Undo()
        {
            if (!CanUndo) return;
            redo.Push(ops[ops.Count - 1]);
            ops.RemoveAt(ops.Count - 1);
            gpu.Replay(ops);
            Enqueue(m => m.Undo());
            Changed?.Invoke();
        }

        public void Redo()
        {
            if (!CanRedo) return;
            var op = redo.Pop();
            ops.Add(op);
            gpu.Apply(op);
            Enqueue(m => m.Redo());
            Changed?.Invoke();
        }

        /// <summary>The whole body again: every cut gone (Undo cannot bring them back).</summary>
        public void ResetBody()
        {
            if (!Ready) return;
            live = null;
            ops.Clear();
            redo.Clear();
            gpu.Fill(1f);
            Enqueue(m => m.Reset());
            Changed?.Invoke();
        }

        /// <summary>Replaces the history (loading a lesson) and replays it.</summary>
        public void LoadHistory(IEnumerable<MaskOp> history)
        {
            if (!Ready) return;
            live = null;
            ops.Clear();
            redo.Clear();
            ops.AddRange(history);
            gpu.Replay(ops);
            var copies = ops.Select(o => o.Clone()).ToList();
            Enqueue(m => m.Load(copies));
            Changed?.Invoke();
        }

        /// <summary>Picking: is the tissue at this container-local position removed? (CPU copy; may lag a frame.)</summary>
        public bool IsRemovedLocal(Vector3 local)
        {
            MaskModel m = cpu;
            return m != null && m.IsRemovedMm(Space.UvwToMm(VolumeSpace.LocalToUvw(local)));
        }

        private void Enqueue(Action<MaskModel> work)
        {
            lane = lane.ContinueWith(_ =>
            {
                try
                {
                    if (cpu != null) work(cpu);
                }
                catch (Exception e)
                {
                    Debug.LogException(e);
                }
            }, TaskScheduler.Default);
        }
    }
}
