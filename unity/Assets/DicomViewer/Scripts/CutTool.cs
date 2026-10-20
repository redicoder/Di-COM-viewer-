using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Dig tool: touch and hold on the body and a round hole deepens under the finger at `speedMm` per second;
    /// moving the finger drags the hole along at its current depth. One press = one undo step.
    /// Radius and speed are set in the tool panel (ViewerToolbar). Cuts go into the dissection mask (MaskVolume),
    /// so there is no limit on how many holes are dug.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    [RequireComponent(typeof(MaskVolume))]
    public class CutTool : MonoBehaviour
    {
        [Range(3f, 40f)] public float radiusMm = 12f;
        [Tooltip("How fast the hole deepens while the finger is held down, in millimetres per second.")]
        [Range(5f, 80f)] public float speedMm = 25f;

        public static bool DigActive => ViewerUi.ActiveTool == ViewerUi.Tool.Dig;

        private VolumeLoader loader;
        private MaskVolume mask;
        private bool digging;
        private float surfaceDistance;     // world distance from the camera ray origin to the body surface
        private float depthMm;
        private Vector3 lastCentreMm;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            mask = GetComponent<MaskVolume>();
        }

        private void Update()
        {
            if (!DigActive || ViewerUi.ModalOpen || loader.Volume == null || !mask.Ready ||
                Input.touchCount >= 2 || VolumeOrbitController.GestureRecent)
            {
                Stop();
                return;
            }
            Camera cam = Camera.main;
            bool overView = cam != null && cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;

            if (Input.GetMouseButtonDown(0) && overView) Begin(cam);
            else if (digging && Input.GetMouseButton(0)) Continue(cam);
            if (digging && !Input.GetMouseButton(0)) Stop();
        }

        private void Begin(Camera cam)
        {
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            if (!loader.RaycastVisible(ray, out var hit, null, 0.2f)) return;   // pressed on empty space
            surfaceDistance = Vector3.Dot(hit.world - ray.origin, ray.direction);
            depthMm = 0f;
            digging = true;
            mask.BeginStroke("dig");
            lastCentreMm = CentreMm(ray);
            mask.ExtendStroke(new MaskCapsule(lastCentreMm, lastCentreMm, radiusMm));
        }

        private void Continue(Camera cam)
        {
            depthMm += speedMm * Time.deltaTime;
            Vector3 c = CentreMm(cam.ScreenPointToRay(Input.mousePosition));
            if ((c - lastCentreMm).magnitude < radiusMm * 0.15f) return;   // not moved enough to matter yet
            mask.ExtendStroke(new MaskCapsule(lastCentreMm, c, radiusMm));
            lastCentreMm = c;
        }

        private void Stop()
        {
            if (!digging) return;
            digging = false;
            mask.EndStroke();
        }

        /// <summary>The hole's centre: on the current finger ray, at the surface depth plus the dug depth.</summary>
        private Vector3 CentreMm(Ray ray)
        {
            Transform c = loader.Volume.volumeContainerObject.transform;
            float worldPerMm = mask.Space.WorldPerMm(c);
            return mask.Space.WorldToMm(c, ray.origin + ray.direction * (surfaceDistance + depthMm * worldPerMm));
        }
    }
}
