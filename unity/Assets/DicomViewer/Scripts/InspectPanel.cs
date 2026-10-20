using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Inspect, as in a CAD / STEP viewer: with the Rotate tool, tap a structure to select it. The other structures
    /// fade to a ghost (or disappear in Isolate mode) and a card shows its name, volume, size and mean density,
    /// with Focus (zoom to fit and rotate around it), Ghost/Isolate, Hide, Show all and Close.
    /// Tap it again, or tap empty space, to deselect. Tissue without an organ label shows its density and the
    /// likely tissue type for a few seconds.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class InspectPanel : MonoBehaviour
    {
        private VolumeLoader loader;
        private VolumeOrbitController orbit;
        private Vector3 downPos;
        private float downTime;

        private float tissueHu;
        private float tissueUntil;
        private GUIStyle title, text, button;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            orbit = GetComponent<VolumeOrbitController>();
            loader.Loaded += _ => tissueUntil = 0f;
        }

        private void Update()
        {
            if (ViewerUi.ModalOpen || loader.Volume == null || ViewerUi.ActiveTool != ViewerUi.Tool.Rotate) return;
            Camera cam = Camera.main;
            bool overView = cam != null && cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;
            if (Input.GetMouseButtonDown(0) && overView)
            {
                downPos = Input.mousePosition;
                downTime = Time.unscaledTime;
            }
            if (!overView || !ViewerUi.TapReleased(downPos, downTime)) return;

            if (!loader.RaycastVisible(cam.ScreenPointToRay(Input.mousePosition), out var hit))
            {
                Deselect();   // tapped empty space
                return;
            }
            if (hit.organId > 0)
            {
                if (hit.organId == loader.SelectedOrgan) Deselect();
                else loader.Select(hit.organId, loader.SelectionMode);
                tissueUntil = 0f;
            }
            else
            {
                tissueHu = hit.hu;
                tissueUntil = Time.unscaledTime + 4f;
            }
        }

        public void Deselect()
        {
            loader.ClearSelection();
            if (orbit != null) orbit.ClearPivot();
        }

        public void Focus()
        {
            if (orbit != null && loader.TryGetOrganWorldBounds(loader.SelectedOrgan, out var centre, out var radius))
                orbit.FocusOn(centre, radius);
        }

        /// <summary>Rough tissue class from the CT value (Hounsfield units), for taps on unlabelled tissue.</summary>
        public static string TissueFromHu(float hu)
        {
            if (hu < -500f) return "Air / lung";
            if (hu < -30f) return "Fat";
            if (hu < 20f) return "Fluid / soft tissue";
            if (hu < 100f) return "Soft tissue / muscle";
            if (hu < 300f) return "Contrast-filled vessel / cartilage";
            return "Bone";
        }

        // ------------------------------------------------------------------ card

        private void EnsureStyles(float k)
        {
            if (title == null)
            {
                title = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, wordWrap = true };
                title.normal.textColor = Color.white;
                text = new GUIStyle(GUI.skin.label) { wordWrap = true };
                text.normal.textColor = new Color(0.88f, 0.88f, 0.88f);
                button = new GUIStyle(GUI.skin.button);
            }
            title.fontSize = Mathf.RoundToInt(24 * k);
            text.fontSize = button.fontSize = Mathf.RoundToInt(17 * k);
        }

        private void OnGUI()
        {
            if (loader.Volume == null) return;
            float k = ViewerUi.Scale;
            EnsureStyles(k);
            bool showOrgan = loader.SelectedOrgan > 0;
            bool showTissue = !showOrgan && Time.unscaledTime < tissueUntil;
            if (!showOrgan && !showTissue) return;

            float w = 360 * k, h = showOrgan ? 330 * k : 120 * k, pad = 12 * k;
            var r = new Rect(Screen.width - w - 8 * k, 104 * k, w, h);
            ViewerUi.Block(r);
            GUI.Box(r, GUIContent.none);
            GUI.Box(r, GUIContent.none);   // the default box is very transparent
            GUILayout.BeginArea(new Rect(r.x + pad, r.y + pad, r.width - 2 * pad, r.height - 2 * pad));

            if (showTissue)
            {
                GUILayout.Label(TissueFromHu(tissueHu), title);
                GUILayout.Label($"Density {tissueHu:F0} HU · no organ label here", text);
                GUILayout.EndArea();
                return;
            }

            var organ = loader.OrganById(loader.SelectedOrgan);
            GUILayout.Label(organ?.name ?? "Structure", title);
            if (loader.TryGetOrganSize(loader.SelectedOrgan, out float ml, out Vector3 size) &&
                loader.TryGetOrganStats(loader.SelectedOrgan, out var stats))
            {
                GUILayout.Label($"Volume  {ml:F0} mL", text);
                GUILayout.Label($"Size  {size.x:F0} × {size.y:F0} × {size.z:F0} mm", text);
                GUILayout.Label("(left-right × head-feet × front-back)", text);
                GUILayout.Label($"Mean density  {stats.meanHu:F0} HU", text);
            }
            else GUILayout.Label("Measuring ...", text);

            GUILayout.FlexibleSpace();
            float bh = 40 * k;
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Focus", button, GUILayout.Height(bh))) Focus();
            bool isolate = loader.SelectionMode == VolumeLoader.SelectMode.Isolate;
            if (GUILayout.Button(isolate ? "Show others (ghost)" : "Isolate", button, GUILayout.Height(bh)))
                loader.Select(loader.SelectedOrgan, isolate ? VolumeLoader.SelectMode.Ghost : VolumeLoader.SelectMode.Isolate);
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Hide this", button, GUILayout.Height(bh)))
            {
                int id = loader.SelectedOrgan;
                Deselect();
                loader.SetOrganVisible(id, false);
            }
            if (GUILayout.Button("Show all", button, GUILayout.Height(bh)))
            {
                Deselect();
                loader.SoloOrgan(0);
            }
            if (GUILayout.Button("Close", button, GUILayout.Height(bh))) Deselect();
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }
    }
}
