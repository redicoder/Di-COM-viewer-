using System.Collections.Generic;
using System.IO;
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
        public const string HeadBody = "photo_head", WholeBody = "photo_body";
        [Tooltip("Which export the lab shows, a folder under backend/out: photo_head (the head at 0.66 mm) or photo_body (the whole body at 2 mm).")]
        public string bodyName = HeadBody;
        [Tooltip("Modelled living eyes behind the eyelids. Off: his real eyes (a dead man's, dull and sunken).")]
        public bool livingEyes = true;
        [Range(0f, 1f)] public float eyesOpenTarget;
        [Tooltip("How fast the eyelids follow the target, per second.")]
        public float eyelidSpeed = 1.6f;

        public PhotoBody Body { get; private set; }
        public MaskVolume Mask { get; private set; }
        public float EyesOpen { get; private set; }
        /// <summary>A whole body lies on his back on the table; a head stands on a tray.</summary>
        public bool Lying { get; private set; }

        private VolumeOrbitController orbit;
        private BloodSim blood;
        private TissueWarp warp;
        private TissueSheets sheets;
        private SkinMesh skinMesh;
        private LabScalpel scalpel;
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
            go.AddComponent<TissueWarp>();
            go.AddComponent<TissueSheets>();
            go.AddComponent<LabRoom>();
            go.AddComponent<SkinMesh>();
            go.AddComponent<AnatomyLab>();          // before the parts that require it, or they would add a second
            go.AddComponent<LabInstruments>();
            go.AddComponent<LabScalpel>();
            go.AddComponent<LabPull>();
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
            warp = GetComponent<TissueWarp>();
            sheets = GetComponent<TissueSheets>();
            skinMesh = GetComponent<SkinMesh>();
            scalpel = GetComponent<LabScalpel>();
            Body.Loaded += OnBodyLoaded;
        }

        public static readonly Color RoomBackground = new Color(0.10f, 0.105f, 0.115f);
        private Color savedBackground;
        private CameraClearFlags savedClear;

        private void OnEnable()
        {
            ViewerUi.ActiveTool = ViewerUi.Tool.Rotate;
            Camera cam = Camera.main;
            if (cam != null)
            {
                savedBackground = cam.backgroundColor;
                savedClear = cam.clearFlags;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = RoomBackground;
            }
            if (!Body.IsLoaded && !Body.IsLoading)
            {
                Body.folder = BodyFolder(bodyName);
                _ = Body.LoadAsync();
            }
        }

        public static string BodyFolder(string name) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "backend", "out", name));

        /// <summary>Loads another export (HeadBody or WholeBody); everything done to the current one is gone.</summary>
        public void UseBody(string name)
        {
            if (Body.IsLoading || (name == bodyName && Body.IsLoaded)) return;
            bodyName = name;
            Body.folder = BodyFolder(name);
            _ = Body.LoadAsync();
        }

        public bool IsWholeBody => bodyName == WholeBody;

        /// <summary>The skin is drawn as a mesh over the volume (the export has one): it does not stretch.</summary>
        public bool SkinMeshOn => skinMesh != null && skinMesh.IsLoaded;

        /// <summary>How a body lies on the table before this camera: on his back, head to the viewer's left, face up to the viewer.</summary>
        public static Quaternion LyingRotation(Transform cam) => Quaternion.LookRotation(cam.forward, -cam.right);

        private void OnBodyLoaded()
        {
            Lying = Body.SizeM.y > 0.5f;                                   // longer than any head: a body
            PlaceInFrontOfCamera();
            orbit.SetTarget(transform);
            Mask.Attach(Body.Space, () => Body.Material);
            MakeEyes();
            if (blood != null) blood.Attach(Body, Mask);
            if (warp != null)
            {
                warp.fieldResolution = 192;          // ~1.3 mm cells on a head: incision gapes are only a few mm
                warp.Setup(Body.Space.Dims, Body.Space.SpacingMm, Body.SkinDepthTexture);
                warp.Bind(Body.Material);
            }
            if (sheets != null) sheets.Attach(Body, Mask);
            if (skinMesh != null) skinMesh.Attach(Body);
            if (scalpel != null) scalpel.ForgetCut();
            // On the table, down is towards the table however the body is turned to look at it; a head on a tray
            // keeps the world's gravity (turn it and the blood runs the other way).
            Vector3 size = Body.Space.SizeMm;
            Vector3 downLocal = Lying ? Vector3.forward : Vector3.zero;
            if (sheets != null) sheets.SetTable(Lying ? Vector3.back : Vector3.up, Lying ? -(size.z + 2f) : TissueSheets.TrayTop);
            if (sheets != null) sheets.downLocalOverride = downLocal;
            if (blood != null) blood.downLocalOverride = downLocal;
        }

        private void OnDisable()
        {
            Camera cam = Camera.main;
            if (cam == null) return;
            cam.backgroundColor = savedBackground;
            cam.clearFlags = savedClear;
        }

        private void PlaceInFrontOfCamera()
        {
            Camera cam = Camera.main;
            if (cam == null) return;
            transform.localScale = Vector3.one;
            float tanHalf = Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad), half = Body.SizeM.y * 0.5f, dist;
            if (Lying)
            {
                transform.rotation = LyingRotation(cam.transform);
                dist = half / (0.84f * cam.aspect) / tanHalf;                   // his length fills ~84 % of the width
            }
            else
            {
                transform.rotation = Quaternion.LookRotation(cam.transform.forward, cam.transform.up);   // face (-z) to camera
                dist = half / 0.80f / tanHalf;                                  // fills ~80 % of the height
            }
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

        /// <summary>
        /// Picking: is the body's tissue at a volume-cube-local point gone, cut away (the mask) or taken over by a
        /// lifted sheet of skin (which is picked separately)?
        /// </summary>
        public bool IsGoneLocal(Vector3 local) => Mask.IsRemovedLocal(local) || (sheets != null && sheets.IsHiddenLocal(local));

        public void OpenEyes(bool open) => eyesOpenTarget = open ? 1f : 0f;

        public void ResetView() => orbit.ResetView();

        /// <summary>Blood shown and cuts bleeding, or a dry dissection (blood hidden, new cuts do not bleed).</summary>
        public bool ShowBlood
        {
            get => blood == null || blood.showBlood;
            set { if (blood != null) blood.showBlood = value; }
        }

        /// <summary>Every cut gone, all blood gone, all lifted or fallen skin back in place: the body as it came.</summary>
        public void HealAll()
        {
            Mask.ResetBody();
            if (blood != null) blood.Clear();
            if (warp != null) warp.ResetAll();
            if (sheets != null) sheets.Clear();
            if (scalpel != null) scalpel.ForgetCut();
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
