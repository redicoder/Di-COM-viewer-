using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Organ list for volumes with AI organ labels (Organs preset).
    ///   Panel (O toggles): colour, show/hide tick box and name per organ; clicking a name selects it for
    ///   inspection (InspectPanel shows its card in this place while something is selected).
    ///   Hover: the name of the organ under the mouse. Taps on the body are handled by InspectPanel.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class OrganPanel : MonoBehaviour
    {
        public bool showPanel = true;
        [Tooltip("Width of the organ list in pixels at 1080p; scales with the window.")]
        public float panelWidth = 250f;

        private VolumeLoader loader;
        private Vector3 lastPickPos = new Vector3(-1, -1);
        private float lastPickTime;
        private int hoverOrgan;
        private GUIStyle rowStyle, titleStyle, tipStyle;
        private Texture2D white;
        private Vector2 scroll;

        private bool Active => loader.Volume != null && loader.Organs != null && loader.preset == VolumeLoader.Preset.Organs
                               && loader.OverrideTransferFunction == null;

        private void Awake() => loader = GetComponent<VolumeLoader>();

        private void Update()
        {
            if (ViewerUi.ModalOpen) return;
            bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            if (Input.GetKeyDown(KeyCode.O) && !ctrl) showPanel = !showPanel;   // Ctrl+O opens a scan
            hoverOrgan = 0;
            if (!Active) return;

            Camera cam = Camera.main;
            bool overView = cam != null && cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;
            if (!overView) return;

            // Hover pick: only when the mouse has moved or a moment has passed (a ray march per frame is wasteful).
            bool buttons = Input.GetMouseButton(0) || Input.GetMouseButton(1);
            if (!buttons && ViewerUi.ActiveTool == ViewerUi.Tool.Rotate &&
                ((Input.mousePosition - lastPickPos).sqrMagnitude > 4f || Time.unscaledTime - lastPickTime > 0.25f))
            {
                lastPickPos = Input.mousePosition;
                lastPickTime = Time.unscaledTime;
                hoverOrgan = Pick(cam);
                cachedHover = hoverOrgan;
            }
            else hoverOrgan = cachedHover;
            // Taps on the body are handled by InspectPanel (select and inspect).
        }

        private int cachedHover;

        private int Pick(Camera cam) =>
            loader.RaycastVisible(cam.ScreenPointToRay(Input.mousePosition), out var hit) ? hit.organId : 0;

        private void EnsureStyles()
        {
            if (white == null)
            {
                white = new Texture2D(1, 1);
                white.SetPixel(0, 0, Color.white);
                white.Apply();
            }
            if (rowStyle != null) return;
            rowStyle = new GUIStyle(GUI.skin.button) { alignment = TextAnchor.MiddleLeft };
            titleStyle = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold };
            titleStyle.normal.textColor = Color.white;
            tipStyle = new GUIStyle(GUI.skin.box) { alignment = TextAnchor.MiddleCenter };
            tipStyle.normal.textColor = Color.white;
        }

        private void OnGUI()
        {
            if (!Active) return;
            EnsureStyles();
            float k = ViewerUi.Scale;
            rowStyle.fontSize = titleStyle.fontSize = Mathf.RoundToInt(16 * k);
            tipStyle.fontSize = Mathf.RoundToInt(20 * k);

            if (hoverOrgan > 0 && !ViewerUi.ModalOpen)
            {
                var name = loader.OrganById(hoverOrgan)?.name ?? "";
                Vector2 m = Event.current.mousePosition;
                var size = tipStyle.CalcSize(new GUIContent(name)) + new Vector2(16, 8) * k;
                GUI.Box(new Rect(m.x + 18 * k, m.y + 10 * k, size.x, size.y), name, tipStyle);
            }
            if (!showPanel || loader.SelectedOrgan > 0) return;   // while inspecting, the Inspect card takes this place

            float w = panelWidth * k, rowH = 26 * k, pad = 8 * k;
            int n = loader.Organs.Length;
            float listH = Mathf.Min(n * (rowH + 2), Screen.height * 0.55f);
            float h = listH + rowH * 4.6f + pad * 3;
            var panel = new Rect(Screen.width - w - pad, 104 * k, w, h);   // below the two toolbar rows
            ViewerUi.Block(panel);
            GUI.Box(panel, GUIContent.none);

            GUILayout.BeginArea(new Rect(panel.x + pad, panel.y + pad, panel.width - 2 * pad, panel.height - 2 * pad));
            GUILayout.Label("Organs  (tap one to inspect it)", titleStyle);
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Show all", GUILayout.Height(rowH))) loader.SoloOrgan(0);
            if (GUILayout.Button("Hide all", GUILayout.Height(rowH)))
            {
                foreach (var o in loader.Organs) o.visible = false;
                loader.ApplyTransferFunction();
            }
            GUILayout.EndHorizontal();

            scroll = GUILayout.BeginScrollView(scroll, GUILayout.Height(listH));
            foreach (var o in loader.Organs)
            {
                GUILayout.BeginHorizontal(GUILayout.Height(rowH));
                bool vis = GUILayout.Toggle(o.visible, GUIContent.none, GUILayout.Width(22 * k), GUILayout.Height(rowH));
                if (vis != o.visible) loader.SetOrganVisible(o.id, vis);
                Rect sw = GUILayoutUtility.GetRect(rowH * 0.7f, rowH * 0.7f, GUILayout.Width(rowH * 0.7f));
                var prev = GUI.color;
                GUI.color = new Color(o.color[0], o.color[1], o.color[2], o.visible ? 1f : 0.3f);
                GUI.DrawTexture(new Rect(sw.x, sw.y + rowH * 0.15f, sw.width, sw.height), white);
                GUI.color = prev;
                if (GUILayout.Button((o.id == hoverOrgan ? "> " : "") + o.name, rowStyle, GUILayout.Height(rowH)))
                    loader.Select(o.id, loader.SelectionMode);
                GUILayout.EndHorizontal();
            }
            GUILayout.EndScrollView();

            GUILayout.Label($"Opacity  {loader.organOpacity:F2}", titleStyle);
            float op = GUILayout.HorizontalSlider(loader.organOpacity, 0.02f, 0.3f);
            if (!Mathf.Approximately(op, loader.organOpacity))
            {
                loader.organOpacity = op;
                loader.ApplyTransferFunction();
            }
            bool skel = GUILayout.Toggle(loader.organsShowSkeleton, " Show skeleton");
            if (skel != loader.organsShowSkeleton)
            {
                loader.organsShowSkeleton = skel;
                loader.ApplyTransferFunction();
            }
            GUILayout.EndArea();
        }

        private void OnDestroy()
        {
            if (white != null) Destroy(white);
        }
    }
}
