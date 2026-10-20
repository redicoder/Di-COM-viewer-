using UnityEngine;
using UnityVolumeRendering;

namespace DicomViewer
{
    /// <summary>
    /// Demo split screen: the left panel shows the scan the way it is read in hospitals today
    /// (one greyscale slice, CT window/level, radiological orientation letters), the right side keeps
    /// the 3D volume. The slice follows ClippingPlaneController's axis and position, so [ and ] scroll
    /// through slices and C switches axial / coronal / sagittal in both views at once.
    /// V: show/hide the panel. L: cycle the window (soft tissue / lung / bone).
    /// W/A/S/D are taken by VolumeOrbitController (Input Manager "Vertical"/"Horizontal" axes).
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class SliceViewPanel : MonoBehaviour
    {
        [Tooltip("Show the 2D panel when Play starts.")]
        public bool showAtStart = true;
        [Tooltip("Fraction of the screen width used by the 2D panel.")]
        [Range(0.25f, 0.6f)] public float panelWidth = 0.42f;
        [Tooltip("Shrink the main camera's viewport so the 3D view sits beside the panel. Turn off on the SR display.")]
        public bool shrinkCamera = true;

        private struct WindowPreset
        {
            public string name; public float level, width;
            public WindowPreset(string n, float l, float w) { name = n; level = l; width = w; }
        }

        // Standard CT presets (window level / width in HU), as found in any PACS viewer.
        private static readonly WindowPreset[] Presets =
        {
            new WindowPreset("Soft tissue", 40f, 400f),
            new WindowPreset("Lung", -600f, 1500f),
            new WindowPreset("Bone", 400f, 1800f),
        };

        private VolumeLoader loader;
        private ClippingPlaneController clip;
        private VolumeDataset ds;
        private bool visible, initialised;
        private int preset;

        private Texture2D slice, black;
        private Color32[] pixels;
        private ClippingPlaneController.Axis shownAxis;
        private int shownIndex = -1, shownDepth, shownPreset = -1;

        private Camera cam;
        private Rect originalCamRect;
        private GUIStyle titleStyle, infoStyle, letterStyle, hintStyle;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            clip = GetComponent<ClippingPlaneController>();
            loader.Loaded += vol =>
            {
                ds = vol.dataset;
                shownIndex = -1;   // force a redraw: a reloaded volume can sit at the same axis/index
                if (!initialised) SetVisible(showAtStart);   // a reload keeps whatever V last chose
                initialised = true;
            };
        }

        private void Update()
        {
            if (ds == null) return;
            if (!ViewerUi.ModalOpen)
            {
                if (Input.GetKeyDown(KeyCode.V)) Toggle();
                if (Input.GetKeyDown(KeyCode.L)) NextWindow();
            }
            if (visible) RefreshSlice();
        }

        // Also the toolbar's "2D slices" / "Contrast" buttons.
        public bool Visible => visible;
        public void Toggle() => SetVisible(!visible);
        public void NextWindow() => preset = (preset + 1) % Presets.Length;
        public string WindowName => Presets[preset].name;

        private void OnDisable() => RestoreCamera();

        private void SetVisible(bool on)
        {
            visible = on;
            if (on && shrinkCamera && cam == null)
            {
                cam = Camera.main;
                if (cam != null)
                {
                    originalCamRect = cam.rect;
                    cam.rect = new Rect(panelWidth, 0f, 1f - panelWidth, 1f);
                }
            }
            else if (!on) RestoreCamera();
        }

        private void RestoreCamera()
        {
            if (cam != null) cam.rect = originalCamRect;
            cam = null;
        }

        private ClippingPlaneController.Axis CurrentAxis => clip != null ? clip.axis : ClippingPlaneController.Axis.Axial;
        private float CurrentPosition => clip != null ? clip.position : 0.5f;

        // Texture axes: x = patient left (+), y = superior (+), z = posterior (+).
        private void SliceSize(ClippingPlaneController.Axis axis, out int w, out int h, out int depth)
        {
            switch (axis)
            {
                case ClippingPlaneController.Axis.Axial: w = ds.dimX; h = ds.dimZ; depth = ds.dimY; break;
                case ClippingPlaneController.Axis.Coronal: w = ds.dimX; h = ds.dimY; depth = ds.dimZ; break;
                default: w = ds.dimZ; h = ds.dimY; depth = ds.dimX; break;
            }
        }

        private void RefreshSlice()
        {
            var axis = CurrentAxis;
            SliceSize(axis, out int w, out int h, out int depth);
            // Same mapping as ClippingPlaneController: position 0..1 spans the volume along its axis.
            int index = Mathf.Clamp(Mathf.RoundToInt(CurrentPosition * (depth - 1)), 0, depth - 1);
            if (slice != null && axis == shownAxis && index == shownIndex && preset == shownPreset) return;

            if (slice == null || slice.width != w || slice.height != h)
            {
                if (slice != null) Destroy(slice);
                slice = new Texture2D(w, h, TextureFormat.RGBA32, false)
                {
                    filterMode = FilterMode.Bilinear,
                    wrapMode = TextureWrapMode.Clamp,
                };
                pixels = new Color32[w * h];
            }

            var p = Presets[preset];
            float lo = p.level - p.width * 0.5f, scale = 255f / p.width;
            float[] d = ds.data;
            int nx = ds.dimX, nxy = ds.dimX * ds.dimY, nz = ds.dimZ;

            // Texture row 0 is the bottom of the image.
            for (int r = 0; r < h; r++)
            {
                for (int c = 0; c < w; c++)
                {
                    int i;
                    if (axis == ClippingPlaneController.Axis.Axial)
                        i = c + index * nx + (nz - 1 - r) * nxy;   // from the feet: patient right on the left, anterior up
                    else if (axis == ClippingPlaneController.Axis.Coronal)
                        i = c + r * nx + index * nxy;              // from the front: patient right on the left, head up
                    else
                        i = index + r * nx + c * nxy;              // from the patient's left: anterior on the left, head up
                    byte g = (byte)Mathf.Clamp((d[i] - lo) * scale, 0f, 255f);
                    pixels[c + r * w] = new Color32(g, g, g, 255);
                }
            }
            slice.SetPixels32(pixels);
            slice.Apply(false);
            shownAxis = axis; shownIndex = index; shownDepth = depth; shownPreset = preset;
        }

        private void EnsureStyles()
        {
            if (black == null)
            {
                black = new Texture2D(1, 1);
                black.SetPixel(0, 0, Color.black);
                black.Apply();
            }
            if (titleStyle == null)
            {
                titleStyle = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleLeft };
                titleStyle.normal.textColor = Color.white;
                infoStyle = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleLeft };
                infoStyle.normal.textColor = new Color(0.8f, 0.8f, 0.8f);
                letterStyle = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
                letterStyle.normal.textColor = new Color(1f, 0.85f, 0.3f);
                hintStyle = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, wordWrap = true };
                hintStyle.normal.textColor = new Color(0.6f, 0.6f, 0.6f);
            }
            // Scale text with the window so it reads the same in the editor and full screen.
            float sh = Screen.height;
            titleStyle.fontSize = Mathf.RoundToInt(sh * 0.030f);
            infoStyle.fontSize = Mathf.RoundToInt(sh * 0.022f);
            letterStyle.fontSize = Mathf.RoundToInt(sh * 0.026f);
            hintStyle.fontSize = Mathf.RoundToInt(sh * 0.018f);
        }

        private void OnGUI()
        {
            if (!visible || slice == null || loader.Meta == null) return;
            EnsureStyles();

            float sw = Screen.width, sh = Screen.height, pw = sw * panelWidth, pad = sh * 0.02f;
            GUI.DrawTexture(new Rect(0, 0, pw, sh), black);

            // Header (starts below the FPS counter in the top-left corner).
            float y = sh * 0.11f, lineH = sh * 0.045f;   // below the toolbar rows
            GUI.Label(new Rect(pad, y, pw - 2 * pad, lineH), "Standard CT viewer  ·  2D slice", titleStyle);
            y += lineH;
            var p = Presets[shownPreset];
            GUI.Label(new Rect(pad, y, pw - 2 * pad, lineH),
                $"{shownAxis}  {shownIndex + 1} / {shownDepth}      {p.name}  (W {p.width:F0} / L {p.level:F0})", infoStyle);
            y += lineH;

            // Image, letterboxed at its physical aspect ratio (spacing per texture axis x, y, z).
            float[] s = loader.Meta.spacing_mm;
            float mmW, mmH;
            switch (shownAxis)
            {
                case ClippingPlaneController.Axis.Axial: mmW = slice.width * s[0]; mmH = slice.height * s[2]; break;
                case ClippingPlaneController.Axis.Coronal: mmW = slice.width * s[0]; mmH = slice.height * s[1]; break;
                default: mmW = slice.width * s[2]; mmH = slice.height * s[1]; break;
            }
            float letterW = letterStyle.fontSize * 1.6f;
            float hintH = sh * 0.07f;
            var area = new Rect(pad + letterW, y + letterW, pw - 2 * (pad + letterW), sh - y - hintH - 2 * letterW - pad);
            float k = Mathf.Min(area.width / mmW, area.height / mmH);
            var img = new Rect(area.x + (area.width - mmW * k) * 0.5f, area.y + (area.height - mmH * k) * 0.5f, mmW * k, mmH * k);
            GUI.DrawTexture(img, slice, ScaleMode.StretchToFill);

            // Orientation letters, as on a PACS screen.
            string left, right, top, bottom;
            switch (shownAxis)
            {
                case ClippingPlaneController.Axis.Axial: left = "R"; right = "L"; top = "A"; bottom = "P"; break;
                case ClippingPlaneController.Axis.Coronal: left = "R"; right = "L"; top = "S"; bottom = "I"; break;
                default: left = "A"; right = "P"; top = "S"; bottom = "I"; break;
            }
            GUI.Label(new Rect(img.x - letterW, img.center.y - letterW * 0.5f, letterW, letterW), left, letterStyle);
            GUI.Label(new Rect(img.xMax, img.center.y - letterW * 0.5f, letterW, letterW), right, letterStyle);
            GUI.Label(new Rect(img.center.x - letterW * 0.5f, img.y - letterW, letterW, letterW), top, letterStyle);
            GUI.Label(new Rect(img.center.x - letterW * 0.5f, img.yMax, letterW, letterW), bottom, letterStyle);

            GUI.Label(new Rect(pad, sh - hintH - pad * 0.5f, pw - 2 * pad, hintH),
                "[ ]  scroll slices     C  axial / coronal / sagittal     L  window     V  hide panel", hintStyle);

            // Caption over the 3D side so the audience can tell the two apart.
            GUI.Label(new Rect(pw + pad, y - lineH * 2, sw - pw - 2 * pad, lineH), "3D volume  ·  same scan", titleStyle);
        }

        private void OnDestroy()
        {
            if (slice != null) Destroy(slice);
            if (black != null) Destroy(black);
        }
    }
}
