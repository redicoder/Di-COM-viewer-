using System.Collections.Generic;
using UnityEngine;
using UnityVolumeRendering;

namespace DicomViewer
{
    /// <summary>
    /// "Dig" tool: a cut-away sphere that follows the mouse over the body and opens a window into it, like a
    /// torch looking under the skin. K toggles it. While digging: click pins the hole where it is (pinned holes
    /// rotate with the body), Shift+wheel sets the hole size, Ctrl+wheel how deep it reaches past the surface,
    /// Backspace removes all pinned holes.
    ///
    /// The sphere is UnityVolumeRendering's CutoutSphere (exclusive: removes what is inside it). The plugin
    /// handles at most 8 cuts in total, shared with ClippingPlaneController's plane.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class CutTool : MonoBehaviour
    {
        [Tooltip("Hole radius as a fraction of the volume's longest side.")]
        [Range(0.02f, 0.5f)] public float radius = 0.07f;
        [Tooltip("How far past the visible surface the hole reaches, as a fraction of the longest side.")]
        [Range(0f, 0.4f)] public float depth = 0.04f;
        public int maxPinned = 6;

        public static bool DigActive { get; private set; }

        private VolumeLoader loader;
        private CutoutSphere live;
        private readonly List<CutoutSphere> pinned = new List<CutoutSphere>();
        private Vector3 downPos;
        private float downTime;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            // The spheres are children of the volume, so a reload destroys them with it.
            loader.Loaded += _ => { live = null; pinned.Clear(); };
        }

        public void SetDig(bool on)
        {
            DigActive = on;
            if (on) GetComponent<KnifeTool>()?.SetActive(false);
            if (live != null) live.gameObject.SetActive(false);
        }

        public void ClearPinned()
        {
            foreach (var s in pinned)
                if (s != null) Destroy(s.gameObject);
            pinned.Clear();
        }

        public int PinnedCount => pinned.Count;

        private CutoutSphere CreateSphere(string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(loader.Volume.transform, false);
            var s = go.AddComponent<CutoutSphere>();
            s.CutoutType = CutoutType.Exclusive;
            s.SetTargetObject(loader.Volume);
            return s;
        }

        private void Update()
        {
            if (ViewerUi.ModalOpen) return;
            if (Input.GetKeyDown(KeyCode.K)) SetDig(!DigActive);
            if (Input.GetKeyDown(KeyCode.Backspace) || Input.GetKeyDown(KeyCode.Delete)) ClearPinned();
            if (!DigActive || loader.Volume == null) return;

            bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            bool shift = Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift);
            float wheel = Input.mouseScrollDelta.y;
            if (wheel != 0f && shift) radius = Mathf.Clamp(radius * Mathf.Pow(1.12f, wheel), 0.02f, 0.5f);
            if (wheel != 0f && ctrl) depth = Mathf.Clamp(depth + 0.01f * wheel, 0f, 0.4f);

            if (live == null) live = CreateSphere("DigSphere");
            Camera cam = Camera.main;
            bool overView = cam != null && cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;
            Ray ray = overView ? cam.ScreenPointToRay(Input.mousePosition) : default;

            // Find the visible surface under the mouse, ignoring the live sphere itself (otherwise the hole
            // would keep chasing its own floor deeper and deeper).
            if (overView && loader.RaycastVisible(ray, out var hit, live, 0.2f))
            {
                Transform vol = loader.Volume.transform;
                Vector3 size = loader.Volume.dataset.scale;
                float longest = Mathf.Max(size.x, Mathf.Max(size.y, size.z)) * vol.lossyScale.x;
                live.gameObject.SetActive(true);
                live.transform.position = hit.world + ray.direction * (depth * longest);
                live.transform.localScale = Vector3.one * (2f * radius * longest / vol.lossyScale.x);
            }
            else live.gameObject.SetActive(false);

            if (Input.GetMouseButtonDown(0)) { downPos = Input.mousePosition; downTime = Time.unscaledTime; }
            bool click = ViewerUi.TapReleased(downPos, downTime);
            if (click && overView && live.gameObject.activeSelf && pinned.Count < maxPinned)
            {
                var p = CreateSphere($"PinnedHole{pinned.Count + 1}");
                p.transform.localPosition = live.transform.localPosition;
                p.transform.localRotation = live.transform.localRotation;
                p.transform.localScale = live.transform.localScale;
                pinned.Add(p);
            }
        }
    }
}
