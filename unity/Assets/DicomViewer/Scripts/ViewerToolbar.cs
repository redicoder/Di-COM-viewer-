using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Makes the viewer a standalone app: a toolbar (Open scan, Organs, Dig, Clear cuts, High quality, Help),
    /// the Windows file dialog, conversion through the Python backend (tools\convert_cli.py, same pipeline as
    /// the converter window) with live progress, then loading the result. Ctrl+O opens a scan, H shows the
    /// controls, F11 toggles full screen.
    /// A DICOM folder is opened by picking any file inside it; a .zip or .nrrd is used as it is.
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class ViewerToolbar : MonoBehaviour
    {
        public bool showHelpAtStart = false;

        private VolumeLoader loader;
        private CutTool cutTool;
        private ScalpelTool scalpel;
        private MaskVolume mask;
        private InspectPanel inspect;
        private OrganPanel organPanel;

        private enum Dialog { None, Options, Converting, Help, ResetConfirm }
        private Dialog dialog;
        private string pickedPath;
        private int quality;                    // index into Qualities
        private bool aiOrgans = true, removeTable = true;
        private int lungs;                      // 0 auto, 1 yes, 2 no
        private static readonly string[] Qualities = { "standard", "high", "ultra", "fast" };
        private static readonly string[] QualityLabels = { "Standard", "High detail", "Ultra (RTX)", "Fast" };
        private static readonly string[] LungLabels = { "Auto (chest CT)", "Yes", "No" };

        private Process proc;
        private readonly ConcurrentQueue<string> output = new ConcurrentQueue<string>();
        private readonly List<string> lines = new List<string>();
        private float convertStart;
        private bool convertFailed;

        private GUIStyle bar, title, text, mono;

        private string PythonExe => Path.Combine(loader.BackendFolder, ".venv", "Scripts", "python.exe");
        private string ConvertScript => Path.Combine(loader.BackendFolder, "tools", "convert_cli.py");
        private bool HasAi => File.Exists(Path.Combine(loader.BackendFolder, ".venv-seg", "Scripts", "python.exe"));

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            cutTool = GetComponent<CutTool>();
            scalpel = GetComponent<ScalpelTool>();
            mask = GetComponent<MaskVolume>();
            inspect = GetComponent<InspectPanel>();
            organPanel = GetComponent<OrganPanel>();
            knife = GetComponent<KnifeTool>();
            bones = GetComponent<MarkerCheck>();
            slices = GetComponent<SliceViewPanel>();
            plane = GetComponent<ClippingPlaneController>();
            orbit = GetComponent<VolumeOrbitController>();
            if (showHelpAtStart) dialog = Dialog.Help;
        }

        private KnifeTool knife;
        private MarkerCheck bones;
        private SliceViewPanel slices;
        private ClippingPlaneController plane;
        private VolumeOrbitController orbit;

        private void Start()
        {
            background = Mathf.Clamp(PlayerPrefs.GetInt("viewer.background", 0), 0, Backgrounds.Length - 1);
            ApplyBackground();
        }

        private void Update()
        {
            ViewerUi.ModalOpen = dialog == Dialog.Options || dialog == Dialog.Converting || dialog == Dialog.ResetConfirm;
            bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            if (Input.GetKeyDown(KeyCode.F11)) Screen.fullScreen = !Screen.fullScreen;
            if (dialog == Dialog.None && ctrl && Input.GetKeyDown(KeyCode.O)) PickScan();
            if (dialog == Dialog.None && ctrl && mask != null)
            {
                if (Input.GetKeyDown(KeyCode.Z)) mask.Undo();
                if (Input.GetKeyDown(KeyCode.Y)) mask.Redo();
            }
            if (Input.GetKeyDown(KeyCode.H) && !ViewerUi.ModalOpen) dialog = dialog == Dialog.Help ? Dialog.None : Dialog.Help;
            if (Input.GetKeyDown(KeyCode.Escape) && dialog != Dialog.Converting) dialog = Dialog.None;

            while (output.TryDequeue(out var line)) lines.Add(line);
            if (proc != null && proc.HasExited)
            {
                int code = proc.ExitCode;
                proc.Dispose();
                proc = null;
                convertFailed = code != 0 || !lines.Exists(l => l.StartsWith("RESULT "));
                if (!convertFailed)
                {
                    dialog = Dialog.None;
                    _ = loader.LoadLatestAsync();
                }
            }
        }

        // ------------------------------------------------------------------ open + convert

        private void PickScan()
        {
            string path = NativeFileDialog.Open("Open a scan: a DICOM zip, an NRRD file, or any file inside a DICOM folder",
                "Scans (zip, nrrd, dcm)\0*.zip;*.nrrd;*.nhdr;*.dcm\0All files\0*.*\0\0");
            if (string.IsNullOrEmpty(path)) return;
            string ext = Path.GetExtension(path).ToLowerInvariant();
            pickedPath = ext == ".zip" || ext == ".nrrd" || ext == ".nhdr" ? path : Path.GetDirectoryName(path);
            aiOrgans = HasAi;
            dialog = Dialog.Options;
        }

        private void StartConvert()
        {
            if (!File.Exists(PythonExe) || !File.Exists(ConvertScript))
            {
                lines.Clear();
                lines.Add($"Converter not found in {loader.BackendFolder}");
                lines.Add("Set Volume Loader > Latest Export List to <backend>\\out\\latest.txt.");
                convertFailed = true;
                dialog = Dialog.Converting;
                return;
            }
            string args = $"-u \"{ConvertScript}\" \"{pickedPath}\" --quality {Qualities[quality]} " +
                          $"--lungs {(lungs == 0 ? "auto" : lungs == 1 ? "yes" : "no")}" +
                          (aiOrgans ? " --organs" : "") + (removeTable ? "" : " --keep-table");
            var psi = new ProcessStartInfo(PythonExe, args)
            {
                WorkingDirectory = loader.BackendFolder,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            lines.Clear();
            convertFailed = false;
            convertStart = Time.unscaledTime;
            proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
            proc.OutputDataReceived += (_, e) => { if (!string.IsNullOrWhiteSpace(e.Data) && !e.Data.Contains("%|")) output.Enqueue(e.Data); };
            proc.ErrorDataReceived += (_, e) => { if (!string.IsNullOrWhiteSpace(e.Data) && !e.Data.Contains("%|")) output.Enqueue(e.Data); };
            proc.Start();
            proc.BeginOutputReadLine();
            proc.BeginErrorReadLine();
            dialog = Dialog.Converting;
        }

        private void OnDestroy()
        {
            if (proc != null && !proc.HasExited) proc.Kill();
        }

        // ------------------------------------------------------------------ GUI

        private void EnsureStyles()
        {
            if (bar != null) return;
            bar = new GUIStyle(GUI.skin.button);
            title = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, wordWrap = true };
            title.normal.textColor = Color.white;
            text = new GUIStyle(GUI.skin.label) { wordWrap = true };
            text.normal.textColor = new Color(0.88f, 0.88f, 0.88f);
            mono = new GUIStyle(text) { wordWrap = false, font = Font.CreateDynamicFontFromOSFont("Consolas", 14) };
        }

        private void OnGUI()
        {
            EnsureStyles();
            float k = ViewerUi.Scale;
            bar.fontSize = text.fontSize = Mathf.RoundToInt(16 * k);
            title.fontSize = Mathf.RoundToInt(20 * k);
            mono.fontSize = Mathf.RoundToInt(13 * k);

            DrawToolbar(k);
            switch (dialog)
            {
                case Dialog.Options: DrawOptions(k); break;
                case Dialog.Converting: DrawConverting(k); break;
                case Dialog.Help: DrawHelp(k); break;
                case Dialog.ResetConfirm: DrawResetConfirm(k); break;
            }
        }

        private struct Item
        {
            public string label;
            public Texture2D icon;
            public Action act;
            public bool on;        // drawn highlighted (active tool, panel shown)
            public bool enabled;

            public Item(string label, Action act, bool on = false, bool enabled = true, Texture2D icon = null)
            {
                this.label = label;
                this.act = act;
                this.on = on;
                this.enabled = enabled;
                this.icon = icon;
            }
        }

        // Every keyboard shortcut also has a button: a touch screen has no keyboard.
        // Row 1 = view and display; row 2 = tools (one armed at a time) and the dissection history.
        private void DrawToolbar(float k)
        {
            var view = new List<Item>
            {
                new Item("Open scan...", PickScan),
                new Item("Reset view", () => orbit?.ResetView()),
                new Item($"Preset: {loader.preset}", loader.CyclePreset),
            };
            if (loader.HasOtherVersions) view.Add(new Item("Next version", loader.NextVersion));
            if (slices != null)
            {
                view.Add(new Item("2D slices", slices.Toggle, slices.Visible));
                if (slices.Visible) view.Add(new Item($"Contrast: {slices.WindowName}", slices.NextWindow));
            }
            if (loader.Organs != null && organPanel != null)
                view.Add(new Item("Organ list", () => organPanel.showPanel = !organPanel.showPanel, organPanel.showPanel));
            if (bones != null) view.Add(new Item("Bones only", bones.ToggleBones, bones.BoneMode));
            view.Add(new Item($"Background: {Backgrounds[background].name}", NextBackground));
            view.Add(new Item($"Quality: {(loader.highQuality ? "High" : "Normal")}", () => loader.highQuality = !loader.highQuality));
            view.Add(new Item("Help", () => dialog = dialog == Dialog.Help ? Dialog.None : Dialog.Help));

            bool canCut = mask != null && mask.Ready;
            var tools = new List<Item>
            {
                ToolItem("Rotate / inspect", ViewerUi.Tool.Rotate, true),
                ToolItem("Scalpel", ViewerUi.Tool.Scalpel, canCut && scalpel != null),
                ToolItem("Dig", ViewerUi.Tool.Dig, canCut && cutTool != null),
                ToolItem("Knife", ViewerUi.Tool.Knife, canCut && knife != null, knife != null ? knife.Icon : null),
            };
            if (plane != null) tools.Add(new Item("Plane", () => plane.SetEnabled(!plane.IsEnabled), plane.IsEnabled));
            if (mask != null)
            {
                tools.Add(new Item("Undo", mask.Undo, false, mask.CanUndo));
                tools.Add(new Item("Redo", mask.Redo, false, mask.CanRedo));
                tools.Add(new Item("Reset body", () => dialog = Dialog.ResetConfirm, false, canCut));
            }

            float h = 38 * k, pad = 8 * k;
            GUI.enabled = !ViewerUi.ModalOpen;
            ButtonRow(view, pad, h, k);
            ButtonRow(tools, pad + h + 6 * k, h, k);
            if (plane != null && plane.IsEnabled) DrawPlanePanel(k);
            if (ViewerUi.ActiveTool == ViewerUi.Tool.Scalpel || ViewerUi.ActiveTool == ViewerUi.Tool.Dig) DrawToolPanel(k);
            GUI.enabled = true;

            if (loader.IsLoading && dialog == Dialog.None)
                GUI.Label(new Rect(pad, Screen.height - 40 * k, 600 * k, 30 * k), "Loading scan ...", title);
        }

        private static Item ToolItem(string label, ViewerUi.Tool tool, bool available, Texture2D icon = null) =>
            new Item(label, () => ViewerUi.ActiveTool = tool, ViewerUi.ActiveTool == tool, available, icon);

        /// <summary>One right-aligned row of buttons; an icon, if any, is drawn at the left of its button.</summary>
        private void ButtonRow(List<Item> items, float y, float h, float k)
        {
            if (items.Count == 0) return;
            // Shrink the text if the row would not fit the window (large touch scale on a 1080p screen).
            int baseFont = bar.fontSize;
            for (int attempt = 0; attempt < 6; attempt++)
            {
                float total = 0f;
                foreach (var it in items)
                    total += bar.CalcSize(new GUIContent(it.label)).x + 34 * k + (it.icon != null ? h : 0f);
                if (total <= Screen.width * 0.97f) break;
                bar.fontSize = Mathf.Max(10, Mathf.RoundToInt(bar.fontSize * 0.9f));
            }
            float x = Screen.width - 8 * k;
            var rects = new Rect[items.Count];
            for (int i = items.Count - 1; i >= 0; i--)
            {
                float w = bar.CalcSize(new GUIContent(items[i].label)).x + 28 * k + (items[i].icon != null ? h : 0f);
                x -= w;
                rects[i] = new Rect(x, y, w, h);
                x -= 6 * k;
            }
            ViewerUi.Block(new Rect(x, y - 4 * k, Screen.width - x, h + 8 * k));
            bool wasEnabled = GUI.enabled;
            for (int i = 0; i < items.Count; i++)
            {
                Item it = items[i];
                GUIStyle style = StyleFor(it, h);
                GUI.enabled = wasEnabled && it.enabled;
                bool clicked = GUI.Button(rects[i], it.label, style);
                GUI.enabled = wasEnabled;
                if (it.icon != null)
                    GUI.DrawTexture(new Rect(rects[i].x + 6 * k, rects[i].y + 3 * k, h - 6 * k, h - 6 * k), it.icon, ScaleMode.ScaleToFit);
                if (clicked) it.act();
            }
            bar.fontSize = baseFont;
        }

        private GUIStyle barOn, iconButton, iconButtonOn;

        // Highlighted = the button's pressed look with yellow bold text; icon buttons get room for the icon.
        private GUIStyle StyleFor(Item it, float h)
        {
            if (barOn == null)
            {
                barOn = new GUIStyle(bar) { normal = bar.onNormal, hover = bar.onHover, fontStyle = FontStyle.Bold };
                barOn.normal.textColor = barOn.hover.textColor = new Color(1f, 0.85f, 0.3f);
                iconButton = new GUIStyle(bar);
                iconButtonOn = new GUIStyle(barOn);
            }
            barOn.fontSize = iconButton.fontSize = iconButtonOn.fontSize = bar.fontSize;
            if (it.icon == null) return it.on ? barOn : bar;
            var st = it.on ? iconButtonOn : iconButton;
            st.padding = new RectOffset(Mathf.RoundToInt(h + 6), bar.padding.right, bar.padding.top, bar.padding.bottom);
            return st;
        }

        /// <summary>Sliders of the armed scalpel or dig tool, at the bottom centre.</summary>
        private void DrawToolPanel(float k)
        {
            bool isScalpel = ViewerUi.ActiveTool == ViewerUi.Tool.Scalpel;
            if (isScalpel ? scalpel == null : cutTool == null) return;
            var r = new Rect((Screen.width - 560 * k) / 2, Screen.height - 170 * k, 560 * k, 150 * k);
            ViewerUi.Block(r);
            GUI.Box(r, GUIContent.none);
            GUI.Box(r, GUIContent.none);
            GUILayout.BeginArea(new Rect(r.x + 14 * k, r.y + 10 * k, r.width - 28 * k, r.height - 20 * k));
            GUILayout.Label(isScalpel ? "Scalpel: drag across the body" : "Dig: touch and hold on the body", title);
            if (isScalpel)
            {
                scalpel.widthMm = SliderRow($"Width  {scalpel.widthMm:F0} mm", scalpel.widthMm, 1f, 20f, k);
                scalpel.depthMm = SliderRow($"Depth  {scalpel.depthMm:F0} mm", scalpel.depthMm, 2f, 80f, k);
            }
            else
            {
                cutTool.radiusMm = SliderRow($"Size  {cutTool.radiusMm * 2f:F0} mm", cutTool.radiusMm, 3f, 40f, k);
                cutTool.speedMm = SliderRow($"Speed  {cutTool.speedMm:F0} mm/s", cutTool.speedMm, 5f, 80f, k);
            }
            GUILayout.EndArea();
        }

        private float SliderRow(string label, float value, float min, float max, float k)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label(label, text, GUILayout.Width(200 * k));
            float v = GUILayout.HorizontalSlider(value, min, max, GUILayout.Height(30 * k));
            GUILayout.EndHorizontal();
            return v;
        }

        private void DrawResetConfirm(float k)
        {
            var r = Centered(520, 220, k);
            GUILayout.BeginArea(new Rect(r.x + 24 * k, r.y + 20 * k, r.width - 48 * k, r.height - 40 * k));
            GUILayout.Label("Reset the body?", title);
            GUILayout.Label("All cuts are removed and every organ is shown again. This cannot be undone.", text);
            GUILayout.FlexibleSpace();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Cancel", bar, GUILayout.Height(44 * k))) dialog = Dialog.None;
            if (GUILayout.Button("Reset body", bar, GUILayout.Height(44 * k)))
            {
                ResetBody();
                dialog = Dialog.None;
            }
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        /// <summary>The body whole again: no cuts, every organ visible, nothing selected.</summary>
        private void ResetBody()
        {
            if (mask != null) mask.ResetBody();
            if (inspect != null) inspect.Deselect();
            if (loader.Organs != null) loader.SoloOrgan(0);
        }

        private void DrawPlanePanel(float k)
        {
            var r = new Rect(Screen.width - 430 * k, Screen.height - 150 * k, 410 * k, 130 * k);
            ViewerUi.Block(r);
            GUI.Box(r, GUIContent.none);
            GUI.Box(r, GUIContent.none);
            GUILayout.BeginArea(new Rect(r.x + 12 * k, r.y + 8 * k, r.width - 24 * k, r.height - 16 * k));
            GUILayout.BeginHorizontal();
            GUILayout.Label("Cutting plane", title);
            if (GUILayout.Button($"Axis: {plane.axis}", bar, GUILayout.Height(34 * k))) plane.NextAxis();
            if (GUILayout.Button("Flip", bar, GUILayout.Height(34 * k))) plane.Flip();
            GUILayout.EndHorizontal();
            GUILayout.Space(12 * k);
            float p = GUILayout.HorizontalSlider(plane.position, 0f, 1f, GUILayout.Height(30 * k));
            if (!Mathf.Approximately(p, plane.position)) plane.SetPosition(p);
            GUILayout.EndArea();
        }

        // ------------------------------------------------------------------ background

        private static readonly (string name, Color colour)[] Backgrounds =
        {
            ("Black", new Color(0.02f, 0.02f, 0.03f)),
            ("Navy", new Color(0.04f, 0.07f, 0.15f)),
            ("Grey", new Color(0.30f, 0.31f, 0.33f)),
            ("White", new Color(0.94f, 0.94f, 0.95f)),
        };
        private int background;

        private void NextBackground()
        {
            background = (background + 1) % Backgrounds.Length;
            ApplyBackground();
        }

        private void ApplyBackground()
        {
            PlayerPrefs.SetInt("viewer.background", background);   // remembered for the next start
            Camera cam = Camera.main;
            if (cam == null) return;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Backgrounds[background].colour;
        }

        private Rect Centered(float w, float h, float k)
        {
            var r = new Rect((Screen.width - w * k) / 2, (Screen.height - h * k) / 2, w * k, h * k);
            ViewerUi.Block(r);
            GUI.Box(r, GUIContent.none);
            GUI.Box(r, GUIContent.none);   // twice: the default skin's box is very transparent
            return r;
        }

        private void DrawOptions(float k)
        {
            var r = Centered(620, 470, k);
            GUILayout.BeginArea(new Rect(r.x + 20 * k, r.y + 16 * k, r.width - 40 * k, r.height - 32 * k));
            GUILayout.Label("Open scan", title);
            GUILayout.Label(pickedPath, text);
            GUILayout.Space(10 * k);
            GUILayout.Label("Quality", title);
            quality = GUILayout.Toolbar(quality, QualityLabels, bar, GUILayout.Height(32 * k));
            GUILayout.Label(quality == 2 ? "Finest detail. Needs the 8 GB GPU and free RAM; close other apps."
                : quality == 3 ? "Smallest volume: smoothest frame rate, least detail."
                : quality == 1 ? "More detail, more memory." : "Good detail, loads fast.", text);
            GUILayout.Space(10 * k);
            GUI.enabled = HasAi;
            aiOrgans = GUILayout.Toggle(aiOrgans && HasAi, HasAi
                ? "  Find internal organs with AI (adds a few minutes)"
                : "  Find internal organs with AI (AI environment not installed)", GUILayout.Height(28 * k));
            GUI.enabled = true;
            removeTable = GUILayout.Toggle(removeTable, "  Remove the scanner table and cushions", GUILayout.Height(28 * k));
            GUILayout.Label("Lungs-only version", text);
            lungs = GUILayout.Toolbar(lungs, LungLabels, bar, GUILayout.Height(30 * k));
            GUILayout.FlexibleSpace();
            GUILayout.BeginHorizontal();
            GUILayout.FlexibleSpace();
            if (GUILayout.Button("Cancel", bar, GUILayout.Width(140 * k), GUILayout.Height(38 * k))) dialog = Dialog.None;
            if (GUILayout.Button("Convert and open", bar, GUILayout.Width(220 * k), GUILayout.Height(38 * k))) StartConvert();
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        private void DrawConverting(float k)
        {
            var r = Centered(900, 560, k);
            GUILayout.BeginArea(new Rect(r.x + 20 * k, r.y + 16 * k, r.width - 40 * k, r.height - 32 * k));
            if (convertFailed)
                GUILayout.Label("Conversion failed", title);
            else
            {
                int secs = Mathf.FloorToInt(Time.unscaledTime - convertStart);
                string spin = "|/-\\"[(int)(Time.unscaledTime * 6) % 4].ToString();
                GUILayout.Label($"Converting {spin}   {secs / 60}:{secs % 60:00}", title);
            }
            GUILayout.Label(pickedPath, text);
            GUILayout.Space(8 * k);
            int first = Mathf.Max(0, lines.Count - 22);
            for (int i = first; i < lines.Count; i++) GUILayout.Label(lines[i], mono);
            GUILayout.FlexibleSpace();
            GUILayout.BeginHorizontal();
            GUILayout.FlexibleSpace();
            if (convertFailed)
            {
                if (GUILayout.Button("Close", bar, GUILayout.Width(140 * k), GUILayout.Height(38 * k))) dialog = Dialog.None;
            }
            else if (GUILayout.Button("Cancel", bar, GUILayout.Width(140 * k), GUILayout.Height(38 * k)))
            {
                if (proc != null && !proc.HasExited) proc.Kill();
                lines.Add("Cancelled.");
                convertFailed = true;
            }
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        private void DrawHelp(float k)
        {
            var r = Centered(820, 860, k);
            GUILayout.BeginArea(new Rect(r.x + 24 * k, r.y + 16 * k, r.width - 48 * k, r.height - 32 * k));
            GUILayout.Label("Controls  (every key also has a button in the toolbar)", title);
            Row("1 finger / left-drag", "rotate (Rotate tool) or cut (cutting tools)");
            Row("Pinch / mouse wheel", "zoom towards the fingers / cursor");
            Row("2 fingers drag / right-drag", "move (also while a cutting tool is armed)");
            Row("2 fingers twist", "turn in the screen plane");
            Row("Tap a structure", "inspect: name, volume, size; Focus, Isolate");
            Row("R", "reset view");
            GUILayout.Space(6 * k);
            Row("Scalpel", "drag across the body: a trench (width, depth below)");
            Row("Dig", "touch and hold: the hole deepens under the finger");
            Row("Knife", "tap 2 points, then tap the side to remove");
            Row("Undo / Redo  (Ctrl+Z / Ctrl+Y)", "step through the cuts");
            Row("Reset body", "every cut gone, every organ back");
            Row("X", "cutting plane;  [ ] move it,  C change axis,  F flip side");
            GUILayout.Space(6 * k);
            Row("P", "presets: Body / Lungs / Organs");
            Row("O", "organ list");
            Row("B", "bones only");
            Row("Q", "high quality while the view is still");
            GUILayout.Space(6 * k);
            Row("V", "2D hospital slice view;  L contrast window");
            Row("N", "next version of the scan (e.g. lungs only)");
            Row("Ctrl+O", "open another scan");
            Row("F11 / F1 / H", "full screen / FPS counter / this help");
            GUILayout.FlexibleSpace();
            if (GUILayout.Button("Close", bar, GUILayout.Height(36 * k))) dialog = Dialog.None;
            GUILayout.EndArea();

            void Row(string key, string what)
            {
                GUILayout.BeginHorizontal();
                GUILayout.Label(key, title, GUILayout.Width(250 * k));
                GUILayout.Label(what, text);
                GUILayout.EndHorizontal();
            }
        }
    }

    /// <summary>The standard Windows "Open" dialog (comdlg32), usable from a standalone Unity player.</summary>
    public static class NativeFileDialog
    {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private class OpenFileName
        {
            public int structSize;
            public IntPtr owner;
            public IntPtr instance;
            public string filter;
            public string customFilter;
            public int maxCustFilter;
            public int filterIndex;
            public string file;
            public int maxFile;
            public string fileTitle;
            public int maxFileTitle;
            public string initialDir;
            public string title;
            public int flags;
            public short fileOffset;
            public short fileExtension;
            public string defExt;
            public IntPtr custData;
            public IntPtr hook;
            public string templateName;
            public IntPtr reservedPtr;
            public int reservedInt;
            public int flagsEx;
        }

        [DllImport("comdlg32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool GetOpenFileName([In, Out] OpenFileName ofn);

        [DllImport("user32.dll")]
        private static extern IntPtr GetActiveWindow();

        private const int OFN_NOCHANGEDIR = 0x8, OFN_PATHMUSTEXIST = 0x800, OFN_FILEMUSTEXIST = 0x1000, OFN_EXPLORER = 0x80000;

        public static string Open(string title, string filter)
        {
#if UNITY_STANDALONE_WIN || UNITY_EDITOR_WIN
            var ofn = new OpenFileName
            {
                structSize = Marshal.SizeOf(typeof(OpenFileName)),
                owner = GetActiveWindow(),
                filter = filter,
                file = new string('\0', 2048),
                maxFile = 2048,
                fileTitle = new string('\0', 256),
                maxFileTitle = 256,
                initialDir = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile) + "\\Downloads",
                title = title,
                flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR,
            };
            if (!GetOpenFileName(ofn)) return null;
            int end = ofn.file.IndexOf('\0');
            return end >= 0 ? ofn.file.Substring(0, end) : ofn.file;
#else
            UnityEngine.Debug.LogWarning("The file dialog is only available on Windows.");
            return null;
#endif
        }
    }
}
