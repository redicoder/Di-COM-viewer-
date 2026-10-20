using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Scalpel tool: drag a finger across the body and a trench `widthMm` wide and `depthMm` deep is cut along the
    /// stroke, following the visible surface under the finger. One stroke = one undo step.
    /// The trench is built from capsules between consecutive surface points, stacked from the surface down to the
    /// chosen depth, and stored in millimetres in the dissection mask (MaskVolume).
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    [RequireComponent(typeof(MaskVolume))]
    public class ScalpelTool : MonoBehaviour
    {
        [Range(1f, 20f)] public float widthMm = 5f;
        [Range(2f, 80f)] public float depthMm = 12f;

        public static bool Active => ViewerUi.ActiveTool == ViewerUi.Tool.Scalpel;

        private VolumeLoader loader;
        private MaskVolume mask;
        private bool cutting, havePrev;
        private Vector3 prevTop, prevBottom;   // mm
        private Vector2 prevScreen;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            mask = GetComponent<MaskVolume>();
        }

        private void Update()
        {
            if (!Active || ViewerUi.ModalOpen || loader.Volume == null || !mask.Ready ||
                Input.touchCount >= 2 || VolumeOrbitController.GestureRecent)
            {
                Stop();
                return;
            }
            Camera cam = Camera.main;
            bool overView = cam != null && cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;

            if (Input.GetMouseButtonDown(0) && overView)
            {
                cutting = true;
                havePrev = false;
                mask.BeginStroke("scalpel");
                Sample(cam);
            }
            else if (cutting && Input.GetMouseButton(0) &&
                     ((Vector2)Input.mousePosition - prevScreen).magnitude > 6f * ViewerUi.Scale)
                Sample(cam);
            if (cutting && !Input.GetMouseButton(0)) Stop();
        }

        private void Sample(Camera cam)
        {
            prevScreen = Input.mousePosition;
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            if (!loader.RaycastVisible(ray, out var hit, null, 0.25f))
            {
                havePrev = false;   // off the body: do not bridge the gap
                return;
            }
            VolumeSpace space = mask.Space;
            Transform c = loader.Volume.volumeContainerObject.transform;
            Vector3 top = space.WorldToMm(c, hit.world);
            Vector3 bottom = top + space.WorldDirToMm(c, ray.direction).normalized * depthMm;
            float r = widthMm * 0.5f;

            mask.ExtendStroke(new MaskCapsule(top, bottom, r));   // the wall at this point
            if (havePrev)
            {
                // Fill the slice of trench between the previous and this point, level by level.
                int levels = Mathf.Max(1, Mathf.CeilToInt(depthMm / Mathf.Max(r, 0.5f)));
                for (int i = 0; i <= levels; i++)
                {
                    float f = i / (float)levels;
                    mask.ExtendStroke(new MaskCapsule(Vector3.Lerp(prevTop, prevBottom, f), Vector3.Lerp(top, bottom, f), r));
                }
            }
            prevTop = top;
            prevBottom = bottom;
            havePrev = true;
        }

        private void Stop()
        {
            if (!cutting) return;
            cutting = false;
            mask.EndStroke();
        }
    }
}
