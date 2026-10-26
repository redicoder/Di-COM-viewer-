using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The camera walking round the table: it orbits a focus point (drag with one finger or the left button),
    /// comes closer or backs off (pinch, the wheel) and slides sideways (two fingers together, the right or
    /// middle button). The room stays where it is; up stays up. Set Focus and Distance to frame the body.
    /// </summary>
    public class ModelOrbit : MonoBehaviour
    {
        public Vector3 focus = new Vector3(0f, 0.2f, 0f);
        public float distance = 2.5f;
        public float yaw = 0f, pitch = 35f;
        public float minDistance = 0.12f, maxDistance = 6f;
        public float minPitch = -10f, maxPitch = 89f;
        public float degreesPerPixel = 0.25f;

        private Vector2 lastMouse;
        private float lastPinch;
        private Vector2 lastTouchMid;
        private bool dragging;

        private void Start() => Apply();

        /// <summary>Puts the camera at its yaw, pitch and distance from the focus.</summary>
        public void Apply()
        {
            pitch = Mathf.Clamp(pitch, minPitch, maxPitch);
            distance = Mathf.Clamp(distance, minDistance, maxDistance);
            Quaternion q = Quaternion.Euler(pitch, yaw, 0f);
            transform.SetPositionAndRotation(focus + q * new Vector3(0f, 0f, -distance), q);
        }

        /// <summary>Frames a box: the focus at its centre, the camera far enough to see it whole.</summary>
        public void Frame(Bounds b, Camera cam, float fill = 0.84f)
        {
            focus = b.center;
            float radius = b.extents.magnitude;
            float fov = cam != null ? cam.fieldOfView : 30f;
            float aspect = cam != null ? cam.aspect : 16f / 9f;
            float halfAngle = Mathf.Min(fov * 0.5f, Mathf.Atan(Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad) * aspect) * Mathf.Rad2Deg);
            distance = radius / fill / Mathf.Tan(halfAngle * Mathf.Deg2Rad);
            Apply();
        }

        private void Update()
        {
            if (Input.touchCount >= 2)
            {
                Touch a = Input.GetTouch(0), b = Input.GetTouch(1);
                float pinch = (a.position - b.position).magnitude;
                Vector2 mid = (a.position + b.position) * 0.5f;
                if (a.phase == TouchPhase.Began || b.phase == TouchPhase.Began) { lastPinch = pinch; lastTouchMid = mid; }
                else
                {
                    if (lastPinch > 1f) distance *= lastPinch / Mathf.Max(1f, pinch);
                    Pan(mid - lastTouchMid);
                    lastPinch = pinch; lastTouchMid = mid;
                }
                dragging = false;
                Apply();
                return;
            }
            if (Input.touchCount == 1)
            {
                Touch t = Input.GetTouch(0);
                if (t.phase == TouchPhase.Moved) Rotate(t.deltaPosition);
                Apply();
                return;
            }
            float wheel = Input.mouseScrollDelta.y;
            if (wheel != 0f) distance *= Mathf.Pow(0.9f, wheel);
            bool left = Input.GetMouseButton(0), other = Input.GetMouseButton(1) || Input.GetMouseButton(2);
            Vector2 mouse = Input.mousePosition;
            if ((left || other) && dragging)
            {
                Vector2 d = mouse - lastMouse;
                if (left) Rotate(d); else Pan(d);
            }
            dragging = left || other;
            lastMouse = mouse;
            Apply();
        }

        private void Rotate(Vector2 pixels)
        {
            yaw += pixels.x * degreesPerPixel;
            pitch -= pixels.y * degreesPerPixel;
        }

        private void Pan(Vector2 pixels)
        {
            Camera cam = GetComponent<Camera>();
            float fov = cam != null ? cam.fieldOfView : 30f;
            float worldPerPixel = 2f * distance * Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad) / Mathf.Max(1, Screen.height);
            focus -= (transform.right * pixels.x + transform.up * pixels.y) * worldPerPixel;
        }
    }
}
