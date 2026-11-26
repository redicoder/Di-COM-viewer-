using System;
using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The modelled body as layers on the table, outermost first: the skin (body.glb), the muscles (muscles.glb),
    /// the skeleton (skeleton.glb), later the organs. Each layer is a model laid by ModelLab.Lay at the same height
    /// and place. The models are generated one by one and do not nest exactly (the muscle man is broader than the
    /// skin), so only the outermost layer that is on is drawn: take the skin away and the muscles show, take the
    /// muscles away and the skeleton shows. Buttons at the top of the screen (big enough for a finger) pick the
    /// layer to see while the scene plays.
    /// A tap on the body names what was touched (ModelPick finds the structure, ModelNames has its names, ModelCard
    /// shows them) and marks it in colour; a tap on it again, or beside the body, puts the card away. The language button
    /// (top right) goes round Italian, English and Latin.
    /// </summary>
    public class ModelBody : MonoBehaviour
    {
        [Serializable]
        public class Layer
        {
            public string name;
            public GameObject model;
            public bool shown = true;
        }

        public List<Layer> layers = new List<Layer>();

        [Tooltip("The layers come from one body and fit inside one another: every layer that is on is drawn.")]
        public bool nested;

        [Tooltip("The credit lines the data's licences ask for, shown at the foot of the screen.")]
        [TextArea] public string credits = "";

        [Header("Eyes (in the meshes' own space; set by the scene builder from anatomy.json)")]
        public bool hasEyes;
        public Vector3 eyeRight, eyeLeft, eyeForward = Vector3.forward, eyeUp = Vector3.up;
        public float lidUpperDegrees = 46f, lidLowerDegrees = 7f;
        [Range(0f, 1f)] public float lidRight, lidLeft;                 // how far each eye's lids are open

        [Header("Mouth (in the meshes' own space; set by the scene builder from anatomy.json)")]
        public bool hasMouth;
        public Vector3 jawHinge, jawAxis = Vector3.right, mouthGrab;      // a point on the jaw's axis, the axis, a point on the lower lip
        public float jawDegrees = 18f;                                   // the jaw's full turn
        public Vector3 lipDown = Vector3.down;                           // the way the lower lip is drawn off the teeth as the mouth is opened
        public float lipPullMm = 10f;                                    // and how far, with the mouth fully open
        [Range(0f, 1f)] public float jaw;                                // how far the mouth is open
        public Vector3 lipUp = Vector3.up, upperLipGrab;                 // the way the upper lip is lifted off the upper teeth; a point on it
        public float lipLiftMm = 6f;                                     // and how far, lifted fully
        [Range(0f, 1f)] public float upperLip;                           // how far the upper lip is lifted
        [Tooltip("The renderers whose meshes carry jaw weights (TEXCOORD_3): only their materials are told of the jaw.")]
        public List<Renderer> jawRenderers = new List<Renderer>();

        [Header("Names (StreamingAssets/anatomy/model_names.json)")]
        [Tooltip("The language a touched structure is named in; the card shows the other two smaller.")]
        public NameLanguage language = NameLanguage.Italian;

        /// <summary>A lid or a lip is in the hand: the camera does not turn meanwhile (ModelOrbit).</summary>
        public static bool Grabbing { get; private set; }

        private static readonly int JawHingeId = Shader.PropertyToID("_JawHinge"), JawAxisId = Shader.PropertyToID("_JawAxis"), LipPullId = Shader.PropertyToID("_LipPull"),
                                    LipLiftId = Shader.PropertyToID("_LipLift");
        private readonly List<Material> jawMaterials = new List<Material>();
        private float goalRight, goalLeft, goalJaw, goalUpper;
        private int grabbed = -1;                                        // 0 the right eye, 1 the left, 2 the lower lip (the jaw), 3 the upper lip
        private Transform meshSpace;                                     // any of the body's meshes: they share one object space
        private Vector2 lastPointer;
        private readonly List<Material> lidMaterials = new List<Material>();
        private Transform skin;
        private static readonly int PickedId = Shader.PropertyToID("_Picked");
        private const float SkinMark = 0f;                               // how strongly the skin is marked when it is the picked structure
        private ModelNames names;
        private readonly ModelCard card = new ModelCard();
        private Renderer picked;
        private Camera cardCamera;
        private Vector2 downAt;
        private float downTime;
        private bool downOnUi;

        public static readonly string[] LayerNames = { "body", "muscles", "skeleton" };
        public static readonly string[] LayerLabels = { "Skin", "Muscles", "Skeleton" };

        public void Add(string name, GameObject model)
        {
            layers.Add(new Layer { name = name, model = model, shown = true });
            model.transform.SetParent(transform, true);
            Apply();
        }

        public Layer Find(string name) => layers.Find(l => l.name == name);

        public bool Shown(string name) => Find(name)?.shown ?? false;

        /// <summary>The layer that is drawn: the outermost one that is on; null when every layer is off.</summary>
        public Layer Visible => layers.Find(l => l.shown && l.model != null);

        public void Show(string name, bool on)
        {
            Layer l = Find(name);
            if (l == null) return;
            l.shown = on;
            Apply();
        }

        /// <summary>Looks at this layer: the layers outside it go off, it and the ones inside come on.</summary>
        public void LookAt(string name)
        {
            bool outside = true;
            foreach (Layer l in layers)
            {
                if (l.name == name) outside = false;
                l.shown = !outside;
            }
            Apply();
        }

        private void Apply()
        {
            Layer visible = Visible;
            foreach (Layer l in layers)
                if (l.model != null) l.model.SetActive(nested ? l.shown : l == visible);
            if (picked != null && !picked.gameObject.activeInHierarchy) Select(null, cardCamera);      // its layer was taken away
        }

        // ---- taking a structure off -----------------------------------------------------------------------------
        // The simplest dissection: a structure that is touched can be taken off, and what lies behind it is seen and
        // can be touched in its turn. Nothing is cut and nothing is lost: what was taken off is put back, the last
        // one or all of them. (Asked for on 2026-11-26: the heart's sac hides the heart, and so does every layer
        // hide the next; the layers' buttons take a whole layer off, this takes one structure.)

        private readonly List<Renderer> hidden = new List<Renderer>();
        private readonly List<Bounds> hiddenRoom = new List<Bounds>();   // the room each of them took up, as it was taken off
        private readonly Dictionary<Material, float> bakedShadow = new Dictionary<Material, float>();
        private static readonly int OcclusionId = Shader.PropertyToID("_Occlusion");

        /// <summary>Of the shadow baked into a structure, how much is left once something that lay round it is
        /// off. The shadow was baked with everything in its place (the model's build: how open the room over a
        /// surface is): the vessels inside a lung have none of it open, and with the lung taken off they stood
        /// there black.</summary>
        public const float Uncovered = 0.3f;

        /// <summary>The structures taken off, in the order they were taken.</summary>
        public IReadOnlyList<Renderer> Hidden => hidden;

        /// <summary>The baked shadow of every structure, as what is off leaves it: its own again, then eased on
        /// those whose room meets the room of a structure that is off (boxes: a lung's box holds its vessels,
        /// the heart and the windpipe's end, which the lung did lie round). Not the skin's layer.</summary>
        private void Relight()
        {
            foreach (KeyValuePair<Material, float> pair in bakedShadow)
                if (pair.Key != null) pair.Key.SetFloat(OcclusionId, pair.Value);
            bakedShadow.Clear();
            if (hidden.Count == 0) return;
            foreach (Layer l in layers)
            {
                if (l.model == null || l.name == "skin" || l.name == "body") continue;
                foreach (MeshRenderer x in l.model.GetComponentsInChildren<MeshRenderer>(true))
                {
                    Material m = x.sharedMaterial;
                    if (!x.enabled || m == null || !m.HasProperty(OcclusionId) || bakedShadow.ContainsKey(m)) continue;
                    bool uncovered = false;
                    for (int i = 0; i < hiddenRoom.Count && !uncovered; i++) uncovered = hiddenRoom[i].Intersects(x.bounds);
                    if (!uncovered) continue;
                    bakedShadow[m] = m.GetFloat(OcclusionId);
                    m.SetFloat(OcclusionId, bakedShadow[m] * Uncovered);
                }
            }
        }

        /// <summary>The layer a mesh is of: the nearest of its parents that is a layer's model; null if none is.</summary>
        public Layer LayerOf(Renderer r)
        {
            for (Transform t = r != null ? r.transform : null; t != null; t = t.parent)
            {
                Layer l = layers.Find(x => x.model != null && x.model.transform == t);
                if (l != null) return l;
            }
            return null;
        }

        /// <summary>Whether a structure can be taken off by itself: any that is drawn, but nothing of the skin's
        /// layer. The skin goes off with its own button, all of it together: its hair, its nails and its cloth
        /// are not to be left behind without it, nor it without them.</summary>
        public bool CanHide(Renderer r)
        {
            if (r == null || !r.enabled || !r.gameObject.activeInHierarchy) return false;
            Layer of = LayerOf(r);
            return of != null && of.name != "skin" && of.name != "body";
        }

        /// <summary>Takes a structure off: it is no longer drawn and cannot be touched, and its card is put away.
        /// Returns whether it was taken (not: nothing given, the skin's, or off already).</summary>
        public bool Hide(Renderer r)
        {
            if (!CanHide(r)) return false;
            if (r == picked) Select(null, cardCamera);
            hiddenRoom.Add(r.bounds);
            r.enabled = false;
            hidden.Add(r);
            Relight();
            return true;
        }

        /// <summary>Puts back the structure that was taken off last. Returns it; null if none was off.</summary>
        public Renderer ShowLast()
        {
            while (hidden.Count > 0)
            {
                Renderer r = hidden[hidden.Count - 1];
                hidden.RemoveAt(hidden.Count - 1);
                hiddenRoom.RemoveAt(hiddenRoom.Count - 1);
                if (r == null) continue;                                 // (its model is gone)
                r.enabled = true;
                Relight();
                return r;
            }
            Relight();
            return null;
        }

        /// <summary>Puts back every structure that was taken off.</summary>
        public void ShowAll()
        {
            foreach (Renderer r in hidden) if (r != null) r.enabled = true;
            hidden.Clear();
            hiddenRoom.Clear();
            Relight();
        }

        // ---- names ----------------------------------------------------------------------------------------------

        /// <summary>The names table, read when first asked for.</summary>
        public ModelNames Names => names ?? (names = ModelNames.Load());

        /// <summary>The structure whose card is up; null when none is.</summary>
        public Renderer Picked => picked;

        /// <summary>The picked structure as the names table has it; null when nothing is picked or the table does
        /// not have it.</summary>
        public NameEntry PickedEntry => picked != null ? Names.Find(picked.name) : null;

        /// <summary>The card as it is shown now (its lines).</summary>
        public ModelCard Card => card;

        /// <summary>What a finger can touch: every mesh of the layers that are drawn. Not the hair: its strands are
        /// no structure to name, and the skin under them is what was meant.</summary>
        public List<Renderer> Touchable()
        {
            var found = new List<Renderer>();
            foreach (Layer l in layers)
            {
                if (l.model == null || !l.model.activeInHierarchy) continue;
                foreach (MeshRenderer r in l.model.GetComponentsInChildren<MeshRenderer>(false))
                    if (r.enabled && !r.name.StartsWith("hair")) found.Add(r);
            }
            return found;
        }

        /// <summary>A tap at a pixel of this camera's picture (origin bottom-left): the structure in front there is
        /// picked, marked and named on the card; a tap on the picked structure again, or where no structure is,
        /// puts the card away. Returns what is picked afterwards.</summary>
        public Renderer TapAt(Camera cam, Vector2 pixel)
        {
            Renderer hit = ModelPick.At(cam, pixel, Touchable());
            Select(hit == picked ? null : hit, cam);
            return picked;
        }

        /// <summary>Picks a structure (null: none): it is marked (the shader's _Picked), the last one no longer, and
        /// its card shown.</summary>
        public void Select(Renderer r, Camera cam)
        {
            Mark(picked, 0f);
            picked = r;
            if (cam != null) cardCamera = cam;
            if (r == null) { card.Hide(); return; }
            Mark(r, r.name == "skin" ? SkinMark : 1f);                // (the skin is all of him: marked, he is a green man; its card says enough)
            ShowCard();
        }

        private static void Mark(Renderer r, float how)
        {
            if (r != null && r.sharedMaterial != null && r.sharedMaterial.HasProperty(PickedId)) r.sharedMaterial.SetFloat(PickedId, how);
        }

        /// <summary>The language structures are named in; the card that is up is written again.</summary>
        public void SetLanguage(NameLanguage to)
        {
            language = to;
            if (picked != null) ShowCard();
        }

        private void ShowCard()
        {
            Camera cam = cardCamera != null ? cardCamera : Camera.main;
            if (cam == null || picked == null) return;
            card.Show(cam, ModelCard.Compose(Names, Names.Find(picked.name), picked.name, language));
        }

        private void TapUpdate()
        {
            Camera cam = Camera.main;
            if (cam == null) return;
            Vector2 pointer = Input.mousePosition;
            float s = Mathf.Max(1f, Screen.dpi > 0f ? Screen.dpi / 96f : 1f);
            if (Input.GetMouseButtonDown(0))
            {
                downAt = pointer;
                downTime = Time.unscaledTime;
                downOnUi = ViewerUi.PointerOverUi;
            }
            // A tap: down and up at one place within a moment, with one finger, not on a button.
            if (Input.GetMouseButtonUp(0) && !downOnUi && Input.touchCount < 2 && Vector2.Distance(pointer, downAt) < 8f * s && Time.unscaledTime - downTime < 0.45f)
                TapAt(cam, pointer);
        }

        private void LateUpdate() => card.Place(cardCamera != null ? cardCamera : Camera.main);

        private void OnDestroy()
        {
            ShowAll();                                                   // (the materials get their own shadow back)
            Select(null, null);
            card.Destroy();
        }

        private void Start()
        {
            goalRight = lidRight;
            goalLeft = lidLeft;
            goalJaw = jaw;
            goalUpper = upperLip;
            PushLids();
            PushJaw();
        }

        /// <summary>Hands the jaw's hinge and how far it is turned to the materials of the meshes that carry jaw
        /// weights, and to no others (a mesh without the weights would be turned by whatever stands in their place).</summary>
        public void PushJaw()
        {
            if (jawMaterials.Count == 0)
                foreach (Renderer r in jawRenderers)
                    if (r != null && r.sharedMaterial != null && r.sharedMaterial.HasProperty(JawHingeId)) jawMaterials.Add(r.sharedMaterial);
            float angle = hasMouth ? jaw * jawDegrees * Mathf.Deg2Rad : 0f;
            var hinge = new Vector4(jawHinge.x, jawHinge.y, jawHinge.z, angle);
            Vector4 axis = jawAxis.normalized;
            Vector3 down = lipDown.normalized;
            var lip = new Vector4(down.x, down.y, down.z, hasMouth ? jaw * lipPullMm * 0.001f : 0f);
            Vector3 up = lipUp.normalized;
            var lift = new Vector4(up.x, up.y, up.z, hasMouth ? upperLip * lipLiftMm * 0.001f : 0f);
            foreach (Material m in jawMaterials)
            {
                m.SetVector(JawHingeId, hinge);
                m.SetVector(JawAxisId, axis);
                m.SetVector(LipPullId, lip);
                m.SetVector(LipLiftId, lift);
            }
        }

        /// <summary>A point of the upper lip's edge, where it is with the lip lifted by `lifted` (the upper lip does not
        /// go with the jaw).</summary>
        public Vector3 WithLift(Vector3 point, float lifted) => point + lipUp.normalized * (lifted * lipLiftMm * 0.001f);

        /// <summary>A point of the lower lip's edge (it goes wholly with the jaw and with the lip), where it is with the
        /// mouth open by `open`: drawn down, then turned about the jaw's hinge, as the shader does.</summary>
        public Vector3 WithJaw(Vector3 point, float open)
        {
            point += lipDown.normalized * (open * lipPullMm * 0.001f);
            return jawHinge + Quaternion.AngleAxis(open * jawDegrees, jawAxis.normalized) * (point - jawHinge);
        }

        private Transform MeshSpace()
        {
            if (meshSpace == null)
            {
                Renderer r = GetComponentInChildren<MeshRenderer>(true);
                meshSpace = r != null ? r.transform : transform;
            }
            return meshSpace;
        }

        /// <summary>Hands the eyes and how far their lids are open to the shaders of the meshes that carry lid weights
        /// (a third pair of numbers per vertex): the skin, the lashes, and the muscles of the face that lie in the
        /// skin which moves with a lid (they go with it; one that stayed came through the skin under the brow). A
        /// mesh that carries the pair only as a place holder before its jaw weights has zeros there and does not move.
        /// No other mesh is handed them: one without the pair would be turned by whatever stands in its place.</summary>
        public void PushLids()
        {
            if (!hasEyes) return;
            if (lidMaterials.Count == 0)
                foreach (Renderer r in GetComponentsInChildren<Renderer>(true))
                {
                    if (r.sharedMaterial == null) continue;
                    MeshFilter mf = r.GetComponent<MeshFilter>();
                    bool weights = mf != null && mf.sharedMesh != null && mf.sharedMesh.HasVertexAttribute(UnityEngine.Rendering.VertexAttribute.TexCoord2);
                    if (r.name == "skin" || r.name == "hair lashes" || (weights && r.sharedMaterial.HasProperty("_LidOpen")))
                    {
                        lidMaterials.Add(r.sharedMaterial);
                        if (r.name == "skin") skin = r.transform;
                    }
                }
            foreach (Material m in lidMaterials)
            {
                m.SetVector("_EyeR", eyeRight);
                m.SetVector("_EyeL", eyeLeft);
                m.SetVector("_EyeFwd", eyeForward);
                m.SetVector("_EyeUp", eyeUp);
                m.SetVector("_LidOpen", new Vector4(lidRight, lidLeft, lidUpperDegrees * Mathf.Deg2Rad, lidLowerDegrees * Mathf.Deg2Rad));
            }
        }

        // A lid is taken with the pointer on the eye and drawn towards the brow to open it, back to close it; it
        // stays where it is left, as a dead man's lid does. The Open eyes button does both at once.
        // The mouth the same way: the lower lip is taken and drawn towards the chin, and the jaw goes with it (on
        // whatever layer is shown: the jaw is the same jaw under the skin). The upper lip is taken by itself and
        // drawn towards the nose: it comes off the upper teeth and the jaw stays.
        private void Update()
        {
            TapUpdate();
            if (!hasEyes && !hasMouth) return;
            Camera cam = Camera.main;
            bool skinOn = hasEyes && Shown("skin") && skin != null;
            Transform space = MeshSpace();
            if (cam != null)
            {
                Vector2 pointer = Input.mousePosition;
                float s = Mathf.Max(1f, Screen.dpi > 0f ? Screen.dpi / 96f : 1f);
                if (Input.GetMouseButtonDown(0) && Input.touchCount < 2)
                {
                    grabbed = -1;
                    for (int k = 0; k < 2 && skinOn; k++)
                    {
                        Vector3 world = skin.TransformPoint(k == 0 ? eyeRight : eyeLeft);
                        Vector3 screen = cam.WorldToScreenPoint(world);
                        if (screen.z > 0f && Vector2.Distance(screen, pointer) < Mathf.Max(34f * s, PixelsPerMetre(cam, world) * 0.016f)) grabbed = k;
                    }
                    if (grabbed < 0 && hasMouth && Visible != null)
                    {
                        Vector3 world = space.TransformPoint(WithJaw(mouthGrab, jaw));
                        Vector3 screen = cam.WorldToScreenPoint(world);
                        float lower = Vector2.Distance(screen, pointer);
                        if (screen.z > 0f && lower < Mathf.Max(40f * s, PixelsPerMetre(cam, world) * 0.022f)) grabbed = 2;
                        // The upper lip, where the pointer is nearer it than the lower (the two lie a centimetre apart).
                        Vector3 upperWorld = space.TransformPoint(WithLift(upperLipGrab, upperLip));
                        Vector3 upperScreen = cam.WorldToScreenPoint(upperWorld);
                        float upper = Vector2.Distance(upperScreen, pointer);
                        if (upperLipGrab != Vector3.zero && upperScreen.z > 0f && upper < Mathf.Max(34f * s, PixelsPerMetre(cam, upperWorld) * 0.016f) && (grabbed != 2 || upper < lower)) grabbed = 3;
                    }
                    lastPointer = pointer;
                }
                if (grabbed == 2 && Input.GetMouseButton(0))
                {
                    // Where the lip goes on the screen for a tenth more of the jaw's turn: the pointer's travel along that.
                    float from = Mathf.Min(jaw, 0.9f);
                    Vector2 a = cam.WorldToScreenPoint(space.TransformPoint(WithJaw(mouthGrab, from)));
                    Vector2 b = cam.WorldToScreenPoint(space.TransformPoint(WithJaw(mouthGrab, from + 0.1f)));
                    Vector2 towardsChin = b - a;
                    if (towardsChin.sqrMagnitude > 0.01f)
                        goalJaw = jaw = Mathf.Clamp01(jaw + 0.1f * Vector2.Dot(pointer - lastPointer, towardsChin) / towardsChin.sqrMagnitude);
                    lastPointer = pointer;
                }
                else if (grabbed == 3 && Input.GetMouseButton(0))
                {
                    Vector2 a = cam.WorldToScreenPoint(space.TransformPoint(WithLift(upperLipGrab, 0f)));
                    Vector2 b = cam.WorldToScreenPoint(space.TransformPoint(WithLift(upperLipGrab, 1f)));
                    Vector2 towardsNose = b - a;                                  // the lip's whole way on the screen
                    if (towardsNose.sqrMagnitude > 0.01f)
                        goalUpper = upperLip = Mathf.Clamp01(upperLip + Vector2.Dot(pointer - lastPointer, towardsNose) / towardsNose.sqrMagnitude);
                    lastPointer = pointer;
                }
                else if (grabbed >= 0 && grabbed < 2 && skinOn && Input.GetMouseButton(0))
                {
                    Vector3 eye = skin.TransformPoint(grabbed == 0 ? eyeRight : eyeLeft);
                    Vector2 a = cam.WorldToScreenPoint(eye), b = cam.WorldToScreenPoint(eye + skin.TransformDirection(eyeUp) * 0.013f);
                    Vector2 towardsBrow = b - a;                                  // the lid's edge travels about 13 mm
                    if (towardsBrow.sqrMagnitude > 1f)
                    {
                        float change = Vector2.Dot(pointer - lastPointer, towardsBrow) / towardsBrow.sqrMagnitude;
                        if (grabbed == 0) goalRight = lidRight = Mathf.Clamp01(lidRight + change);
                        else goalLeft = lidLeft = Mathf.Clamp01(lidLeft + change);
                    }
                    lastPointer = pointer;
                }
                else grabbed = -1;
            }
            else grabbed = -1;
            Grabbing = grabbed >= 0;
            float step = Time.deltaTime * 1.6f;
            lidRight = Mathf.MoveTowards(lidRight, goalRight, step);
            lidLeft = Mathf.MoveTowards(lidLeft, goalLeft, step);
            jaw = Mathf.MoveTowards(jaw, goalJaw, Time.deltaTime * 1.2f);
            upperLip = Mathf.MoveTowards(upperLip, goalUpper, Time.deltaTime * 1.6f);
            PushLids();
            PushJaw();
        }

        private static float PixelsPerMetre(Camera cam, Vector3 world)
        {
            return Vector2.Distance(cam.WorldToScreenPoint(world), cam.WorldToScreenPoint(world + cam.transform.up));
        }

        private void OnDisable() => Grabbing = false;

        private void OnGUI()
        {
            float s = Mathf.Max(1f, Screen.dpi > 0f ? Screen.dpi / 96f : 1f);
            float h = 44f * s, w = 150f * s, x = 12f * s, y = 12f * s;
            GUI.skin.button.fontSize = Mathf.RoundToInt(18f * s);
            Layer visible = Visible;
            foreach (Layer l in layers)
            {
                int k = Array.IndexOf(LayerNames, l.name);
                string label = (l == visible ? "● " : "") + (k >= 0 ? LayerLabels[k] : char.ToUpper(l.name[0]) + l.name.Substring(1));
                var layerButton = new Rect(x, y, w, h);
                if (GUI.Button(layerButton, label)) LookAt(l.name);
                ViewerUi.Block(layerButton);                             // (a tap on a button is not a tap on the body under it)
                x += w + 8f * s;
            }
            if (hasEyes && Shown("skin"))
            {
                bool open = goalRight > 0.5f || goalLeft > 0.5f;
                var eyesButton = new Rect(x, y, w, h);
                if (GUI.Button(eyesButton, open ? "Close eyes" : "Open eyes")) goalRight = goalLeft = open ? 0f : 1f;
                ViewerUi.Block(eyesButton);
                x += w + 8f * s;
            }
            if (hasMouth && visible != null)
            {
                bool open = goalJaw > 0.5f;
                var mouthButton = new Rect(x, y, w + 20f * s, h);
                if (GUI.Button(mouthButton, open ? "Close mouth" : "Open mouth")) goalJaw = goalUpper = open ? 0f : 1f;      // both lips part
                ViewerUi.Block(mouthButton);
            }
            // The language structures are named in: Italian, English, Latin, round and round.
            var languageButton = new Rect(Screen.width - 108f * s, y, 96f * s, h);
            string tag = language == NameLanguage.Italian ? "IT" : language == NameLanguage.English ? "EN" : "LA";
            if (GUI.Button(languageButton, tag))
                SetLanguage(language == NameLanguage.Italian ? NameLanguage.English : language == NameLanguage.English ? NameLanguage.Latin : NameLanguage.Italian);
            ViewerUi.Block(languageButton);
            // Taking a structure off: a button under its card; and, while any is off, two beside the language's to
            // put back the last one or all of them. In the card's language (Latin names: Italian words, as the card).
            bool english = language == NameLanguage.English;
            if (picked != null && CanHide(picked) && card.Shown)
            {
                var hideButton = new Rect(Screen.width - (ModelCard.Margin + ModelCard.Width) * s, ModelCard.Top * s + card.PixelHeight + 8f * s, 170f * s, h);
                if (GUI.Button(hideButton, english ? "Hide" : "Nascondi")) Hide(picked);
                ViewerUi.Block(hideButton);
            }
            if (hidden.Count > 0)
            {
                var allButton = new Rect(languageButton.x - 8f * s - 210f * s, y, 210f * s, h);
                if (GUI.Button(allButton, (english ? "Show all" : "Mostra tutto") + $" ({hidden.Count})")) ShowAll();
                ViewerUi.Block(allButton);
                var lastButton = new Rect(allButton.x - 8f * s - 130f * s, y, 130f * s, h);
                if (GUI.Button(lastButton, english ? "Back" : "Indietro")) ShowLast();
                ViewerUi.Block(lastButton);
            }
            if (!string.IsNullOrEmpty(credits))
            {
                var style = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(11f * s), wordWrap = true };
                style.normal.textColor = new Color(1f, 1f, 1f, 0.55f);
                float ch = style.CalcHeight(new GUIContent(credits), Screen.width - 24f * s);
                GUI.Label(new Rect(12f * s, Screen.height - ch - 8f * s, Screen.width - 24f * s, ch), credits, style);
            }
        }
    }
}
