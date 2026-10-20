using UnityEngine;
using UnityVolumeRendering;

namespace DicomViewer
{
    /// <summary>
    /// Rotates, moves and zooms the loaded volume. On the SR display the cameras are driven by eye tracking,
    /// so we move the object, never the camera.
    /// Left-drag or arrow keys: rotate. Shift+left-drag, right-drag or Shift+arrows: move.
    /// Mouse wheel: zoom towards the cursor. +/- (or PageUp/PageDown): zoom about the centre. R: reset.
    /// Mouse input only starts over the 3D viewport, so dragging on the SliceViewPanel side does nothing.
    /// Sony's "Run Without Spatial Reality Display" uses right-drag and the wheel for its own navigation:
    /// turn off useWheelAndRightDrag there.
    /// Requires Project Settings > Player > Active Input Handling = Both (or Input Manager).
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class VolumeOrbitController : MonoBehaviour
    {
        public float mouseSensitivity = 0.25f;   // degrees per pixel
        public float keySpeed = 60f;             // degrees per second
        public float scaleStep = 1.1f;
        [Tooltip("Shift+arrow move speed, in screen heights per second.")]
        public float panKeySpeed = 0.5f;
        [Tooltip("Mouse wheel zoom and right-drag move. Turn off with Sony's Run Without Spatial Reality Display, which uses both.")]
        public bool useWheelAndRightDrag = true;

        private enum Drag { None, Rotate, Pan }

        private Transform target;
        private Vector3 initialPosition;
        private Quaternion initialRotation;
        private Vector3 initialScale;
        private Drag drag;
        private Vector3 lastMouse;

        private void Awake() => GetComponent<VolumeLoader>().Loaded += OnLoaded;

        private void OnLoaded(VolumeRenderedObject vol)
        {
            target = vol.transform;
            initialPosition = target.localPosition;
            initialRotation = target.localRotation;
            initialScale = target.localScale;
        }

        // Touch screen: a two-finger gesture runs until every finger is lifted. Tools that act on a tap
        // (organ pick, knife, dig) check GestureRecent so lifting the fingers is not taken as a tap.
        private static bool gestureOn;
        private static int gestureEndFrame = -10;
        public static bool GestureRecent => gestureOn || Time.frameCount - gestureEndFrame <= 2;

        private void Update()
        {
            if (target == null || ViewerUi.ModalOpen) return;
            Camera cam = Camera.main;
            if (cam == null) return;

            if (Input.touchCount >= 2)
            {
                TwoFingerGesture(cam, Input.GetTouch(0), Input.GetTouch(1));
                gestureOn = true;
                drag = Drag.None;
                lastMouse = Input.mousePosition;
                return;
            }
            if (gestureOn)
            {
                if (Input.touchCount == 0 && !Input.GetMouseButton(0))
                {
                    gestureOn = false;
                    gestureEndFrame = Time.frameCount;
                }
                lastMouse = Input.mousePosition;
                return;
            }

            bool shift = Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift);
            bool overView = cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;

            // A drag starts only over the 3D view and lasts until the button is released.
            // (One finger on a touch screen arrives as the left mouse button.)
            if (overView && Input.GetMouseButtonDown(0)) drag = shift ? Drag.Pan : Drag.Rotate;
            if (overView && useWheelAndRightDrag && Input.GetMouseButtonDown(1)) drag = Drag.Pan;
            if (!Input.GetMouseButton(0) && !Input.GetMouseButton(1)) drag = Drag.None;

            if (drag == Drag.Rotate)
            {
                // Mouse X/Y are pixel deltas x 0.1; a finger's delta is in pixels.
                Vector2 delta = Input.touchCount == 1
                    ? Input.GetTouch(0).deltaPosition * 0.1f
                    : new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y"));
                float dx = delta.x * mouseSensitivity * 20f;
                float dy = delta.y * mouseSensitivity * 20f;
                target.Rotate(Vector3.up, -dx, Space.World);
                target.Rotate(Vector3.right, dy, Space.World);
            }
            else if (drag == Drag.Pan)
            {
                // The point under the cursor stays under the cursor ("grab and move").
                target.position += PointOnTargetPlane(cam, Input.mousePosition) - PointOnTargetPlane(cam, lastMouse);
            }
            lastMouse = Input.mousePosition;

            float h = Input.GetAxisRaw("Horizontal"), v = Input.GetAxisRaw("Vertical");
            if (shift && cam != null && (h != 0f || v != 0f))
            {
                float step = panKeySpeed * ViewHeightAt(cam, target.position) * Time.deltaTime;
                target.position += (cam.transform.right * h + cam.transform.up * v) * step;
            }
            else
            {
                if (h != 0f) target.Rotate(Vector3.up, -h * keySpeed * Time.deltaTime, Space.World);
                if (v != 0f) target.Rotate(Vector3.right, v * keySpeed * Time.deltaTime, Space.World);
            }

            float scroll = Input.mouseScrollDelta.y;
            bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            if (useWheelAndRightDrag && overView && scroll != 0f && !shift && !ctrl)   // Shift/Ctrl+wheel belong to the dig tool
                ZoomAbout(PointOnTargetPlane(cam, Input.mousePosition), Mathf.Pow(scaleStep, scroll));

            if (Input.GetKeyDown(KeyCode.Equals) || Input.GetKeyDown(KeyCode.KeypadPlus) || Input.GetKeyDown(KeyCode.PageUp))
                ZoomAbout(target.position, scaleStep);
            if (Input.GetKeyDown(KeyCode.Minus) || Input.GetKeyDown(KeyCode.KeypadMinus) || Input.GetKeyDown(KeyCode.PageDown))
                ZoomAbout(target.position, 1f / scaleStep);

            if (Input.GetKeyDown(KeyCode.R)) ResetView();
        }

        /// <summary>R key and the toolbar's Reset button.</summary>
        public void ResetView()
        {
            if (target == null) return;
            target.localPosition = initialPosition;
            target.localRotation = initialRotation;
            target.localScale = initialScale;
        }

        /// <summary>Pinch to zoom about the point between the fingers, drag both to move, twist to turn.</summary>
        private void TwoFingerGesture(Camera cam, Touch a, Touch b)
        {
            Vector2 pa = a.position, pb = b.position;
            Vector2 qa = pa - a.deltaPosition, qb = pb - b.deltaPosition;   // previous frame
            Vector2 mid = (pa + pb) * 0.5f, prevMid = (qa + qb) * 0.5f;

            target.position += PointOnTargetPlane(cam, mid) - PointOnTargetPlane(cam, prevMid);

            float dist = (pa - pb).magnitude, prevDist = (qa - qb).magnitude;
            if (dist > 10f && prevDist > 10f)
                ZoomAbout(PointOnTargetPlane(cam, mid), dist / prevDist);

            float twist = Vector2.SignedAngle(qb - qa, pb - pa);
            if (Mathf.Abs(twist) > 0.05f && Mathf.Abs(twist) < 45f)
                target.RotateAround(PointOnTargetPlane(cam, mid), cam.transform.forward, -twist);
        }

        // Scale about a world point, so that point stays fixed on screen.
        private void ZoomAbout(Vector3 pivot, float factor)
        {
            target.localScale *= factor;
            target.position = pivot + (target.position - pivot) * factor;
        }

        // Where the mouse ray meets the plane through the volume centre, facing the camera.
        private Vector3 PointOnTargetPlane(Camera cam, Vector3 screenPos)
        {
            if (cam == null) return target.position;
            var plane = new Plane(-cam.transform.forward, target.position);
            Ray ray = cam.ScreenPointToRay(screenPos);
            return plane.Raycast(ray, out float t) ? ray.GetPoint(t) : target.position;
        }

        private static float ViewHeightAt(Camera cam, Vector3 point)
        {
            if (cam.orthographic) return 2f * cam.orthographicSize;
            float dist = Vector3.Dot(point - cam.transform.position, cam.transform.forward);
            return 2f * dist * Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
        }
    }
}
