using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

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
        private LabRegion region;
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
            go.AddComponent<LabRegion>();
            go.AddComponent<AnatomyLab>();          // before the parts that require it, or they would add a second
            go.AddComponent<LabInstruments>();
            go.AddComponent<LabScalpel>();
            go.AddComponent<LabPull>();
            go.AddComponent<LabToolbar>();
            var light = new GameObject("Lab light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 2.0f;                  // tone-mapped (ACES) rendering wants more light
            light.color = new Color(1f, 0.985f, 0.96f);   // a white room light, barely warm
            LabShadows(light);
            light.transform.SetParent(null);
            light.transform.rotation = Quaternion.Euler(52f, -30f, 0f);   // high, as a lamp over a table
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
            region = GetComponent<LabRegion>();
            scalpel = GetComponent<LabScalpel>();
            Body.Loaded += OnBodyLoaded;
        }

        public static readonly Color RoomBackground = new Color(0.10f, 0.105f, 0.115f);
        private Color savedBackground;
        private CameraClearFlags savedClear;
        private bool savedPost;

        /// <summary>
        /// The lab's look as a game renders: ACES tone mapping, a little bloom on the wet highlights, contrast and
        /// a vignette, as a global volume under `parent` (gone with it) and post-processing on the camera.
        /// </summary>
        public static Volume AddPostProcessing(Transform parent, Camera cam)
        {
            if (cam != null) cam.GetUniversalAdditionalCameraData().renderPostProcessing = true;
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            profile.hideFlags = HideFlags.DontSave;
            profile.Add<Tonemapping>(true).mode.Override(TonemappingMode.ACES);
            var bloom = profile.Add<Bloom>(true);
            bloom.intensity.Override(0.3f);
            bloom.threshold.Override(0.95f);
            bloom.scatter.Override(0.6f);
            var colour = profile.Add<ColorAdjustments>(true);
            colour.postExposure.Override(0.3f);
            colour.contrast.Override(5f);
            colour.saturation.Override(2f);
            var vignette = profile.Add<Vignette>(true);
            vignette.intensity.Override(0.16f);
            vignette.smoothness.Override(0.5f);
            var go = new GameObject("Lab post-processing") { hideFlags = HideFlags.DontSave };
            go.transform.SetParent(parent, false);
            var volume = go.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 10f;
            volume.profile = profile;
            return volume;
        }

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
                savedPost = cam.GetUniversalAdditionalCameraData().renderPostProcessing;
            }
            if (transform.Find("Lab post-processing") == null) AddPostProcessing(transform, cam);
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
            ClearPieces();
            Body.folder = BodyFolder(name);
            _ = Body.LoadAsync();
        }

        public bool IsWholeBody => bodyName == WholeBody;

        /// <summary>Skin drawn as one even tone over his shape (a dissection table's body) rather than the photographs.</summary>
        public bool CleanSkin
        {
            get => cleanSkin;
            set { cleanSkin = value; if (Body != null && Body.Material != null) Body.Material.SetFloat("_SkinMode", value ? 1f : 0f); }
        }
        private bool cleanSkin = true;

        /// <summary>
        /// Where briefs go on the clean skin, body mm (from y to y; none when the body has no labels): from just
        /// above the hip bones to a hand below the genitals.
        /// </summary>
        public static Vector4 Briefs(PhotoBody body)
        {
            if (body == null || body.Labels == null) return Vector4.zero;
            if (!body.Labels.BoundsY(new[] { "left hip bone", "right hip bone" }, out _, out int hipTop)) return Vector4.zero;
            if (!body.Labels.BoundsY(new[] { "scrotum", "penis", "testis" }, out int genitalBottom, out _)) return Vector4.zero;
            float sy = body.Space.SpacingMm.y;
            return new Vector4((genitalBottom + 0.5f) * sy - 30f, (hipTop + 0.5f) * sy + 10f, 0f, 0f);
        }

        /// <summary>The lab's key light casts soft shadows (the skin mesh casts and receives them).</summary>
        public static void LabShadows(Light light)
        {
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.9f;
            light.shadowBias = 0.02f;
            light.shadowNormalBias = 0.4f;
        }

        /// <summary>Inside a region drawn at finer detail (the face on the whole body): the tools look away.</summary>
        public bool InRegion(Vector3 world) => region != null && region.Contains(world);

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
            Body.Material.SetFloat("_SkinMode", cleanSkin ? 1f : 0f);
            Body.Material.SetVector("_Underwear", Briefs(Body));
            if (skinMesh != null) skinMesh.Attach(Body);
            if (region != null) region.Attach(Body);
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
            cam.GetUniversalAdditionalCameraData().renderPostProcessing = savedPost;
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
            bool modelled = livingEyes && eyeObjects.Count == 2 && LayerShown("organ");
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
            HeldUpdate(cam);
            m.SetFloat("_HighlightIndex", held == null ? Hover(cam) : 0f);
        }

        /// <summary>The name of the structure under the cursor (the SIO labels), or null: for the toolbar.</summary>
        public string UnderCursor { get; private set; }

        // Whatever tool is in hand, the structure under the pointer is named and, where a cut shows it, lifted.
        private PhotoBody hoverBody;
        private int hoverIndex;
        private readonly System.Collections.Generic.List<OrganPiece> pieces = new System.Collections.Generic.List<OrganPiece>();
        private OrganPiece held;
        private Vector3 holdPlanePoint, holdOffset;

        /// <summary>The pieces taken out so far (on the tray or in the hand).</summary>
        public System.Collections.Generic.IReadOnlyList<OrganPiece> Pieces => pieces;

        // A piece in hand follows the pointer on a plane facing the camera, lifted clear of the body; let go, it
        // glides to the next free spot on the table beside him (or the tray beside a head).
        private void HeldUpdate(Camera cam)
        {
            if (held == null) return;
            if (!Input.GetMouseButton(0) || ViewerUi.ActiveTool != ViewerUi.Tool.TakeOut || Input.touchCount >= 2) { ReleaseHeld(); return; }
            if (cam == null) return;
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            var plane = new Plane(-cam.transform.forward, holdPlanePoint);
            if (plane.Raycast(ray, out float t)) held.Follow(ray.GetPoint(t) + holdOffset);
            var instruments = GetComponent<LabInstruments>();
            if (instruments != null) instruments.ShowHand(held.Centre, -cam.transform.forward, true);
        }

        private void ReleaseHeld()
        {
            if (held == null) return;
            held.Drop(TraySpot(Body, Lying, pieces.IndexOf(held)), DownWorld(Body, Lying));
            held = null;
        }

        /// <summary>Takes the structure out as a piece and puts it in the hand.</summary>
        public void TakeOutPiece(PhotoBody body, int index)
        {
            if (body == null || body.Labels == null || index <= 0 || body.Labels.ObjectHidden(index)) return;
            TakeOut(body, index);
            OrganPiece piece = OrganPiece.Create(body, index);
            if (piece == null) return;
            pieces.Add(piece);
            piece.Hold();
            held = piece;
            Camera cam = Camera.main;
            holdPlanePoint = cam != null ? piece.Centre - cam.transform.forward * 0.06f : piece.Centre;
            holdOffset = Vector3.zero;
            if (cam != null)
            {
                Ray ray = cam.ScreenPointToRay(Input.mousePosition);
                var plane = new Plane(-cam.transform.forward, holdPlanePoint);
                if (plane.Raycast(ray, out float t)) holdOffset = holdPlanePoint - ray.GetPoint(t);
            }
        }

        /// <summary>Where the slot-th piece rests: on the table beside a lying body, on the tray beside a head (world).</summary>
        public static Vector3 TraySpot(PhotoBody body, bool lying, int slot)
        {
            Vector3 size = body.SizeM;
            Vector3 local = lying
                ? new Vector3(size.x * 0.5f + 0.16f + 0.14f * (slot % 3), 0.35f - 0.18f * (slot / 3), size.z * 0.5f + 0.002f)
                : new Vector3(0.16f + 0.12f * (slot % 3), -size.y * 0.5f - 0.0015f, -0.12f * (slot / 3));
            return body.transform.TransformPoint(local);
        }

        /// <summary>Down for a piece: towards the table a lying body is on, else the world's down for a head on its tray.</summary>
        public static Vector3 DownWorld(PhotoBody body, bool lying) => lying ? body.transform.forward : -body.transform.up;

        private void ClearPieces()
        {
            held = null;
            foreach (OrganPiece p in pieces) if (p != null) Destroy(p.gameObject);
            pieces.Clear();
        }

        private int Hover(Camera cam)
        {
            UnderCursor = null;
            hoverBody = null;
            hoverIndex = 0;
            if (cam == null || ViewerUi.ModalOpen || ViewerUi.PointerOverUi) return 0;
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            bool hitBody = Body.Raycast(ray, IsGoneLocal, out Vector3 hit, out _);
            if (region != null && (!hitBody || InRegion(hit)))
            {
                UnderCursor = region.Hover(ray, out hoverBody, out hoverIndex);   // the face at full detail names itself
                TakeOutInput();
                return 0;
            }
            if (region != null) region.Hover(default, out _, out _, false);
            if (!hitBody || Body.Labels == null) return 0;
            Vector3 uvw = VolumeSpace.LocalToUvw(Body.Volume.InverseTransformPoint(hit));
            hoverIndex = Body.Labels.IndexAt(uvw);
            hoverBody = Body;
            UnderCursor = Body.Labels.Name(hoverIndex);
            TakeOutInput();
            return hoverIndex;
        }

        // Take out tool: a tap (or click) on a named structure takes it out of the body; Put back returns them all.
        private void TakeOutInput()
        {
            if (ViewerUi.ActiveTool != ViewerUi.Tool.TakeOut || !Input.GetMouseButtonDown(0) || Input.touchCount >= 2) return;
            if (VolumeOrbitController.GestureRecent) return;
            TakeOutPiece(hoverBody, hoverIndex);
        }

        public static void TakeOut(PhotoBody body, int index)
        {
            if (body == null || body.Labels == null || index <= 0) return;
            body.Labels.HideObject(index, true);
            body.Material.SetFloat("_LayersOn", 1f);
        }

        /// <summary>How many structures have been taken out, over the body and its regions.</summary>
        public int TakenOut => (Body.Labels?.TakenOut ?? 0) + (region != null ? region.TakenOut : 0);

        public void PutBackAll()
        {
            ClearPieces();
            if (Body.Labels != null)
            {
                Body.Labels.PutBackObjects();
                Body.Material.SetFloat("_LayersOn", Body.Labels.AnyHidden ? 1f : 0f);
            }
            if (region != null) region.PutBackAll();
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
        public bool IsGoneLocal(Vector3 local) => Mask.IsRemovedLocal(local) || (sheets != null && sheets.IsHiddenLocal(local))
            || (Body.Labels != null && Body.Labels.HiddenAt(VolumeSpace.LocalToUvw(local)));

        /// <summary>Layers (skin, fat, muscle, bone, organ) the student can take away where the body has labels.</summary>
        public bool LayerShown(string layer) => Body.Labels == null || Body.Labels.LayerShown(layer);

        public void ShowLayer(string layer, bool shown)
        {
            if (Body.Labels == null) return;
            Body.Labels.ShowLayer(layer, shown);
            Body.Material.SetFloat("_LayersOn", Body.Labels.AnyHidden ? 1f : 0f);
            if (region != null) region.ShowLayer(layer, shown);
        }

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
