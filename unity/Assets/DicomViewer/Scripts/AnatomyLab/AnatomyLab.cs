using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The Anatomy Lab mode: the photographed body (PhotoBody), the dissection mask (MaskVolume, the same engine as the
    /// scan viewer), turning and zooming (VolumeOrbitController), the scalpel (LabScalpel), bleeding (BloodSim),
    /// eyelids that open, and modelled living eyes in place of the real ones.
    /// The object's transform is the body's: the orbit controller turns and zooms it, the camera stays put.
    /// </summary>
    [RequireComponent(typeof(PhotoBody), typeof(MaskVolume), typeof(VolumeOrbitController))]
    public class AnatomyLab : MonoBehaviour
    {
        [Tooltip("Modelled living eyes behind the eyelids. Off: his real eyes (a dead man's, dull and sunken).")]
        public bool livingEyes = true;
        [Range(0f, 1f)] public float eyesOpenTarget;
        [Tooltip("How fast the eyelids follow the target, per second.")]
        public float eyelidSpeed = 1.6f;

        public PhotoBody Body { get; private set; }
        public MaskVolume Mask { get; private set; }
        public float EyesOpen { get; private set; }

        private VolumeOrbitController orbit;
        private BloodSim blood;
        private readonly List<LivingEye> eyeObjects = new List<LivingEye>();
        private bool lidDrag;
        private float lidDragY;

        /// <summary>The whole lab built in code (inactive; AppMode switches it on), so the scene needs no edits.</summary>
        public static GameObject CreateRig()
        {
            var go = new GameObject("Anatomy Lab");
            go.SetActive(false);
            go.AddComponent<PhotoBody>();
            go.AddComponent<MaskVolume>();
            go.AddComponent<VolumeOrbitController>();
            go.AddComponent<BloodSim>();
            go.AddComponent<AnatomyLab>();          // before the parts that require it, or they would add a second
            go.AddComponent<LabScalpel>();
            go.AddComponent<LabToolbar>();
            var light = new GameObject("Lab light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.25f;
            light.color = new Color(1f, 0.96f, 0.9f);
            light.transform.SetParent(null);
            light.transform.rotation = Quaternion.Euler(35f, -30f, 0f);
            light.gameObject.AddComponent<FollowActive>().owner = go;
            return go;
        }

        private void Awake()
        {
            Body = GetComponent<PhotoBody>();
            Mask = GetComponent<MaskVolume>();
            orbit = GetComponent<VolumeOrbitController>();
            blood = GetComponent<BloodSim>();
            Body.Loaded += OnBodyLoaded;
        }

        private void OnEnable()
        {
            ViewerUi.ActiveTool = ViewerUi.Tool.Rotate;
            if (!Body.IsLoaded && !Body.IsLoading) _ = Body.LoadAsync();
        }

        private void OnBodyLoaded()
        {
            PlaceInFrontOfCamera();
            orbit.SetTarget(transform);
            Mask.Attach(Body.Space, () => Body.Material);
            MakeEyes();
            if (blood != null) blood.Attach(Body, Mask);
        }

        private void PlaceInFrontOfCamera()
        {
            Camera cam = Camera.main;
            if (cam == null) return;
            transform.localScale = Vector3.one;
            transform.rotation = Quaternion.LookRotation(cam.transform.forward, cam.transform.up);   // face (-z) to camera
            float half = Body.SizeM.y * 0.5f;
            float dist = half / 0.40f / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);       // fills ~80 % of the height
            transform.position = cam.transform.position + cam.transform.forward * dist;
        }

        private void MakeEyes()
        {
            foreach (var e in eyeObjects) if (e != null) Destroy(e.gameObject);
            eyeObjects.Clear();
            BodyEye[] eyes = Body.Meta.eyes;
            Material m = Body.Material;
            if (eyes == null || eyes.Length < 2)
            {
                m.SetFloat("_HasLids", 0f);
                return;
            }
            for (int i = 0; i < 2; i++)
            {
                BodyEye e = eyes[i];
                var real = new Vector4(e.centre_m[0], e.centre_m[1], e.centre_m[2], e.radius_m + 0.0005f);
                m.SetVector(i == 0 ? "_Eye0" : "_Eye1", new Vector4(e.centre_m[0], e.lid_line_y_m, e.centre_m[2], e.radius_m));
                m.SetVector(i == 0 ? "_EyeBall0" : "_EyeBall1", real);
                LivingEye eye = LivingEye.Create(transform, LivingEyeCentre(e), LivingEyeRadius, Vector3.back);
                eye.name = i == 0 ? "Right eye" : "Left eye";
                eyeObjects.Add(eye);
            }
        }

        public const float LivingEyeRadius = 0.012f;

        /// <summary>
        /// Where a living eye goes: on his eyeball's axis, with the cornea's tip 2.5 mm behind the closed lids' skin
        /// (his own eyes have sunk since death; a living one sits forward). The cornea's apex is ~13 mm in front of
        /// the eye's centre for a 12 mm eye (LivingEye's geometry).
        /// </summary>
        public static Vector3 LivingEyeCentre(BodyEye e) =>
            new Vector3(e.centre_m[0], e.centre_m[1], e.skin_front_z_m + 0.0025f + LivingEyeRadius * 1.085f);

        private void Update()
        {
            if (!Body.IsLoaded) return;
            EyelidInput();
            EyesOpen = Mathf.MoveTowards(EyesOpen, eyesOpenTarget, eyelidSpeed * Time.deltaTime);
            bool modelled = livingEyes && eyeObjects.Count == 2;
            Camera cam = Camera.main;
            foreach (LivingEye e in eyeObjects)
            {
                e.gameObject.SetActive(modelled);
                if (!modelled) continue;
                if (EyesOpen > 0.3f && cam != null) e.LookAt(cam.transform.position);   // open eyes look at you
                else e.LookForward();
            }
            bool moving = Input.GetMouseButton(0) || Input.GetMouseButton(1) || Input.touchCount > 0;
            Material m = Body.Material;
            m.SetFloat("_Open", EyesOpen);
            m.SetFloat("_ModelEyes", modelled ? 1f : 0f);
            m.SetFloat("_StepScale", moving ? 1f : 0.5f);
        }

        // Eyelids tool: one finger (or the mouse) up opens the eyes, down closes them.
        private void EyelidInput()
        {
            if (ViewerUi.ActiveTool != ViewerUi.Tool.Eyelids || ViewerUi.ModalOpen || Input.touchCount >= 2)
            {
                lidDrag = false;
                return;
            }
            if (Input.GetMouseButtonDown(0) && !ViewerUi.PointerOverUi)
            {
                lidDrag = true;
                lidDragY = Input.mousePosition.y;
            }
            if (lidDrag && Input.GetMouseButton(0))
            {
                eyesOpenTarget = Mathf.Clamp01(eyesOpenTarget + (Input.mousePosition.y - lidDragY) / (Screen.height * 0.25f));
                EyesOpen = eyesOpenTarget;               // follow the finger directly
                lidDragY = Input.mousePosition.y;
            }
            if (Input.GetMouseButtonUp(0)) lidDrag = false;
        }

        public void OpenEyes(bool open) => eyesOpenTarget = open ? 1f : 0f;

        public void ResetView() => orbit.ResetView();

        /// <summary>Blood shown and cuts bleeding, or a dry dissection (blood hidden, new cuts do not bleed).</summary>
        public bool ShowBlood
        {
            get => blood == null || blood.showBlood;
            set { if (blood != null) blood.showBlood = value; }
        }

        /// <summary>Every cut gone, all blood gone: the body as it came.</summary>
        public void HealAll()
        {
            Mask.ResetBody();
            if (blood != null) blood.Clear();
        }
    }

    /// <summary>Keeps a helper object (the lab's light) active only while its owner is.</summary>
    public class FollowActive : MonoBehaviour
    {
        public GameObject owner;
        private Light lightComponent;

        private void Awake() => lightComponent = GetComponent<Light>();

        private void LateUpdate()
        {
            if (owner == null) return;
            if (lightComponent != null) lightComponent.enabled = owner.activeInHierarchy;
        }
    }
}
