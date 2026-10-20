using UnityEngine;
using UnityEngine.UI;
using UnityVolumeRendering;

namespace DicomViewer
{
    /// <summary>
    /// Slider-driven clipping plane using UnityVolumeRendering's CrossSectionPlane.
    /// The plane is parented to the volume so it stays aligned with patient axes while the volume rotates:
    ///   Sagittal = local X (left/right), Axial = local Y (inferior/superior), Coronal = local Z (anterior/posterior).
    /// Keys: [ and ] move the plane, C cycles the axis, F flips which side is removed, X toggles clipping.
    /// Optionally assign a UI Slider (0..1); keys keep it in sync.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class ClippingPlaneController : MonoBehaviour
    {
        public enum Axis { Sagittal, Axial, Coronal }

        public Axis axis = Axis.Coronal;
        [Range(0f, 1f)] public float position = 0.5f;
        public bool flipped = false;
        public bool enabledAtStart = false;
        public Slider slider;
        public float keySpeed = 0.4f;   // fraction of the volume per second

        private VolumeRenderedObject volume;
        private GameObject plane;

        private void Awake()
        {
            GetComponent<VolumeLoader>().Loaded += OnLoaded;
            if (slider != null) slider.onValueChanged.AddListener(v => { position = v; Apply(); });
        }

        private void OnLoaded(VolumeRenderedObject vol)
        {
            volume = vol;
            plane = Object.Instantiate((GameObject)Resources.Load("CrossSectionPlane"));
            plane.name = "ClippingPlane";
            plane.GetComponent<MeshRenderer>().material = new Material(ShaderFactory.GetCrossSectionPlaneShader());
            plane.transform.SetParent(volume.transform, false);
            plane.GetComponent<CrossSectionPlane>().SetTargetObject(volume);
            plane.SetActive(enabledAtStart);
            if (slider != null) slider.SetValueWithoutNotify(position);
            Apply();
        }

        private void Update()
        {
            if (plane == null) return;

            float delta = 0f;
            if (Input.GetKey(KeyCode.RightBracket)) delta += keySpeed * Time.deltaTime;
            if (Input.GetKey(KeyCode.LeftBracket)) delta -= keySpeed * Time.deltaTime;
            if (delta != 0f)
            {
                position = Mathf.Clamp01(position + delta);
                if (slider != null) slider.SetValueWithoutNotify(position);
                Apply();
            }
            if (ViewerUi.ModalOpen) return;
            if (Input.GetKeyDown(KeyCode.C)) NextAxis();
            if (Input.GetKeyDown(KeyCode.F)) Flip();
            if (Input.GetKeyDown(KeyCode.X)) SetEnabled(!IsEnabled);
        }

        // Also driven by the on-screen plane panel (ViewerToolbar), for touch screens without a keyboard.
        public bool IsEnabled => plane != null && plane.activeSelf;
        public void SetEnabled(bool on) { if (plane != null) plane.SetActive(on); }
        public void NextAxis() { axis = (Axis)(((int)axis + 1) % 3); Apply(); }
        public void Flip() { flipped = !flipped; Apply(); }

        public void SetPosition(float value)
        {
            position = Mathf.Clamp01(value);
            if (slider != null) slider.SetValueWithoutNotify(position);
            Apply();
        }

        private void Apply()
        {
            if (plane == null || volume == null) return;
            Vector3 dir = axis switch
            {
                Axis.Sagittal => Vector3.right,
                Axis.Axial => Vector3.up,
                _ => Vector3.forward,
            };
            Vector3 size = volume.dataset.scale;   // container size in metres, in volume-local space
            float extent = Vector3.Dot(size, dir);
            Vector3 up = axis == Axis.Axial ? Vector3.forward : Vector3.up;

            plane.transform.localPosition = dir * ((position - 0.5f) * extent);
            plane.transform.localRotation = Quaternion.LookRotation(flipped ? -dir : dir, up);
            plane.transform.localScale = Vector3.one * (Mathf.Max(size.x, size.y, size.z) * 1.2f);
        }
    }
}
