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
        [Tooltip("The renderers whose meshes carry jaw weights (TEXCOORD_3): only their materials are told of the jaw.")]
        public List<Renderer> jawRenderers = new List<Renderer>();

        /// <summary>A lid or the lower lip is in the hand: the camera does not turn meanwhile (ModelOrbit).</summary>
        public static bool Grabbing { get; private set; }

        private static readonly int JawHingeId = Shader.PropertyToID("_JawHinge"), JawAxisId = Shader.PropertyToID("_JawAxis"), LipPullId = Shader.PropertyToID("_LipPull");
        private readonly List<Material> jawMaterials = new List<Material>();
        private float goalRight, goalLeft, goalJaw;
        private int grabbed = -1;                                        // 0 the right eye, 1 the left, 2 the mouth
        private Transform meshSpace;                                     // any of the body's meshes: they share one object space
        private Vector2 lastPointer;
        private readonly List<Material> lidMaterials = new List<Material>();
        private Transform skin;

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
        }

        private void Start()
        {
            goalRight = lidRight;
            goalLeft = lidLeft;
            goalJaw = jaw;
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
            foreach (Material m in jawMaterials)
            {
                m.SetVector(JawHingeId, hinge);
                m.SetVector(JawAxisId, axis);
                m.SetVector(LipPullId, lip);
            }
        }

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

        /// <summary>Hands the eyes and how far their lids are open to the skin's and the lashes' shaders.</summary>
        public void PushLids()
        {
            if (!hasEyes) return;
            if (lidMaterials.Count == 0)
                foreach (Renderer r in GetComponentsInChildren<Renderer>(true))
                    if (r.sharedMaterial != null && (r.name == "skin" || r.name == "hair lashes"))
                    {
                        lidMaterials.Add(r.sharedMaterial);
                        if (r.name == "skin") skin = r.transform;
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
        // whatever layer is shown: the jaw is the same jaw under the skin).
        private void Update()
        {
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
                        if (screen.z > 0f && Vector2.Distance(screen, pointer) < Mathf.Max(40f * s, PixelsPerMetre(cam, world) * 0.022f)) grabbed = 2;
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
                if (GUI.Button(new Rect(x, y, w, h), label)) LookAt(l.name);
                x += w + 8f * s;
            }
            if (hasEyes && Shown("skin"))
            {
                bool open = goalRight > 0.5f || goalLeft > 0.5f;
                if (GUI.Button(new Rect(x, y, w, h), open ? "Close eyes" : "Open eyes")) goalRight = goalLeft = open ? 0f : 1f;
                x += w + 8f * s;
            }
            if (hasMouth && visible != null)
            {
                bool open = goalJaw > 0.5f;
                if (GUI.Button(new Rect(x, y, w + 20f * s, h), open ? "Close mouth" : "Open mouth")) goalJaw = open ? 0f : 1f;
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
