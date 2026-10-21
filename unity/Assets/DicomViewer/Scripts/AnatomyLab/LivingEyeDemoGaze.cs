// Demo helper: both eyes follow the mouse on a plane in front of the face. Legacy Input, as the project
// runs with Active Input Handling = Both.
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    public sealed class LivingEyeDemoGaze : MonoBehaviour
    {
        public LivingEye left, right;
        public Camera viewCamera;
        [Tooltip("Distance in front of the eyes of the plane the gaze target slides on (metres).")]
        public float targetPlaneDistance = 0.10f;

        private void Update()
        {
            if (viewCamera == null || left == null || right == null) return;
            Vector3 between = (left.transform.position + right.transform.position) * 0.5f;
            Vector3 face = (left.transform.parent != null ? left.transform.parent : left.transform).TransformDirection(left.LocalForward);
            var plane = new Plane(-face, between + face * targetPlaneDistance);
            Ray ray = viewCamera.ScreenPointToRay(Input.mousePosition);
            if (!plane.Raycast(ray, out float t)) return;
            Vector3 target = ray.GetPoint(t);
            left.LookAt(target);
            right.LookAt(target);
        }
    }
}
