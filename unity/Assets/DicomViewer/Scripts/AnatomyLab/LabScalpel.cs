using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The Anatomy Lab's scalpel: drag across the body and the skin opens along the path. Each stroke is one undo step
    /// in the dissection mask (MaskVolume), made of capsules stacked into a V: wide at the skin, narrow at the bottom,
    /// so the wound gapes like a real incision. The tissue the blade reaches decides how much it bleeds (BloodSim).
    /// </summary>
    [RequireComponent(typeof(AnatomyLab))]
    public class LabScalpel : MonoBehaviour
    {
        [Tooltip("Width of the wound at the skin, mm.")]
        public float widthMm = 5f;
        [Tooltip("Depth of the wound, mm.")]
        public float depthMm = 6f;
        [Tooltip("A new piece of wound every this many mm of finger movement.")]
        public float stepMm = 1.2f;

        // V profile: (centre depth below the skin, radius), as fractions of depth and half-width.
        private static readonly Vector2[] Profile =
        {
            new Vector2(-0.10f, 1.04f), new Vector2(0.33f, 0.68f), new Vector2(0.66f, 0.40f), new Vector2(0.90f, 0.24f),
        };

        private AnatomyLab lab;
        private BloodSim blood;
        private bool cutting;
        private Vector3 lastPoint, lastNormal;

        private void Awake()
        {
            lab = GetComponent<AnatomyLab>();
            blood = GetComponent<BloodSim>();
        }

        private void OnDisable() => End();

        private void Update()
        {
            PhotoBody body = lab.Body;
            if (ViewerUi.ActiveTool != ViewerUi.Tool.Scalpel || body == null || !body.IsLoaded || !lab.Mask.Ready ||
                ViewerUi.ModalOpen || Input.touchCount >= 2 || VolumeOrbitController.GestureRecent)
            {
                End();
                return;
            }
            Camera cam = Camera.main;
            if (cam == null) return;

            if (Input.GetMouseButtonDown(0) && !ViewerUi.PointerOverUi && Pick(cam, out Vector3 p, out Vector3 n))
            {
                lab.Mask.BeginStroke("scalpel");
                cutting = true;
                lastPoint = p;
                lastNormal = n;
            }
            else if (cutting && Input.GetMouseButton(0) && Pick(cam, out p, out n))
            {
                float perMm = body.Space.WorldPerMm(body.Volume);
                float mm = Vector3.Distance(p, lastPoint) / perMm;
                if (mm > 40f)                         // jumped to another part of the body: start afresh there
                {
                    lastPoint = p;
                    lastNormal = n;
                }
                else if (mm > stepMm)
                {
                    Segment(body, lastPoint, p, (lastNormal + n).normalized);
                    lastPoint = p;
                    lastNormal = n;
                }
            }
            if (cutting && !Input.GetMouseButton(0)) End();
        }

        private void End()
        {
            if (!cutting) return;
            cutting = false;
            lab.Mask.EndStroke();
        }

        private bool Pick(Camera cam, out Vector3 point, out Vector3 normal) =>
            lab.Body.Raycast(cam.ScreenPointToRay(Input.mousePosition), lab.Mask.IsRemovedLocal, out point, out normal);

        private void Segment(PhotoBody body, Vector3 aWorld, Vector3 bWorld, Vector3 normalWorld)
        {
            VolumeSpace space = body.Space;
            Vector3 a = space.WorldToMm(body.Volume, aWorld), b = space.WorldToMm(body.Volume, bWorld);
            Vector3 inward = -space.WorldDirToMm(body.Volume, normalWorld).normalized;
            float half = widthMm * 0.5f;
            foreach (Vector2 c in Profile)
            {
                Vector3 off = inward * (c.x * depthMm);
                lab.Mask.ExtendStroke(new MaskCapsule(a + off, b + off, c.y * half));
            }
            if (blood != null) blood.AddWound(aWorld, bWorld, normalWorld, Redness(body, (aWorld + bWorld) * 0.5f, normalWorld));
        }

        // Red muscle and vessels 3 mm down bleed a lot, yellow fat hardly, white bone not at all.
        private static float Redness(PhotoBody body, Vector3 surfaceWorld, Vector3 normalWorld)
        {
            float perMm = body.Space.WorldPerMm(body.Volume);
            Vector3 inside = body.Volume.InverseTransformPoint(surfaceWorld - normalWorld * (3f * perMm));
            Color32 c = body.ColourAt(inside);
            return Mathf.Clamp01((c.r - 0.5f * (c.g + c.b)) / 255f * 3f);
        }
    }
}
