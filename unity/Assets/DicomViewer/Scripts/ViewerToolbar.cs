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
        private OrganPanel organPanel;

        private enum Dialog { None, Options, Converting, Help }
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
            ViewerUi.ModalOpen = dialog == Dialog.Options || dialog == Dialog.Converting;
            bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            if (Input.GetKeyDown(KeyCode.F11)) Screen.fullScreen = !Screen.fullScreen;
            if (dialog == Dialog.None && ctrl && Input.GetKeyDown(KeyCode.O)) PickScan();
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
            }
        }

        // Every keyboard shortcut also has a button: a touch screen has no keyboard.
        private void DrawToolbar(float k)
        {
            string OnOff(bool on) => on ? "on" : "off";
            var view = new List<(string label, Texture2D icon, Action act)>
            {
                ("Open scan...", null, PickScan),
                ("Reset view", null, () => orbit?.ResetView()),
                ($"Preset: {loader.preset}", null, loader.CyclePreset),
            };
            if (loader.HasOtherVersions) view.Add(("Next version", null, loader.NextVersion));
            if (slices != null)
            {
                view.Add(($"2D slices: {OnOff(slices.Visible)}", null, slices.Toggle));
                if (slices.Visible) view.Add(($"Contrast: {slices.WindowName}", null, slices.NextWindow));
            }
            view.Add(($"Background: {Backgrounds[background].name}", null, NextBackground));
            view.Add(($"Quality: {(loader.highQuality ? "High" : "Normal")}", null, () => loader.highQuality = !loader.highQuality));
            view.Add(("Help", null, () => dialog = dialog == Dialog.Help ? Dialog.None : Dialog.Help));

            var tools = new List<(string label, Texture2D icon, Action act)>();
            if (loader.Organs != null)
                tools.Add(($"Organ list: {OnOff(organPanel != null && organPanel.showPanel)}", null,
                    () => { if (organPanel != null) organPanel.showPanel = !organPanel.showPanel; loader.SoloOrgan(0); }));
            if (bones != null) tools.Add(($"Bones only: {OnOff(bones.BoneMode)}", null, bones.ToggleBones));
            if (knife != null)
            {
                tools.Add(($"Knife: {OnOff(KnifeTool.Active)}", knife.Icon, () => knife.SetActive(!KnifeTool.Active)));
                if (knife.CutCount > 0)
                {
                    tools.Add(($"Undo cut ({knife.CutCount})", null, knife.Undo));
                    tools.Add(("Clear cuts", null, knife.ClearCuts));
                }
            }
            if (cutTool != null)
            {
                tools.Add(($"Dig: {OnOff(CutTool.DigActive)}", null, () => cutTool.SetDig(!CutTool.DigActive)));
                if (cutTool.PinnedCount > 0) tools.Add(($"Clear holes ({cutTool.PinnedCount})", null, cutTool.ClearPinned));
            }
            if (plane != null) tools.Add(($"Plane: {OnOff(plane.IsEnabled)}", null, () => plane.SetEnabled(!plane.IsEnabled)));

            float h = 38 * k, pad = 8 * k;
            GUI.enabled = !ViewerUi.ModalOpen;
            ButtonRow(view, pad, h, k);
            ButtonRow(tools, pad + h + 6 * k, h, k);
            if (plane != null && plane.IsEnabled) DrawPlanePanel(k);
            GUI.enabled = true;

            if (loader.IsLoading && dialog == Dialog.None)
                GUI.Label(new Rect(pad, Screen.height - 40 * k, 600 * k, 30 * k), "Loading scan ...", title);
        }

        /// <summary>One right-aligned row of buttons; an icon, if any, is drawn at the left of its button.</summary>
        private void ButtonRow(List<(string label, Texture2D icon, Action act)> items, float y, float h, float k)
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
            for (int i = 0; i < items.Count; i++)
            {
                var (label, icon, act) = items[i];
                Rect r = rects[i];
                bool clicked = icon != null
                    ? GUI.Button(r, new GUIContent(label), IconButton(h))
                    : GUI.Button(r, label, bar);
                if (icon != null)
                    GUI.DrawTexture(new Rect(r.x + 6 * k, r.y + 3 * k, h - 6 * k, h - 6 * k), icon, ScaleMode.ScaleToFit);
                if (clicked) act();
            }
            bar.fontSize = baseFont;
        }

        private GUIStyle iconButton;
        private GUIStyle IconButton(float h)
        {
            if (iconButton == null) iconButton = new GUIStyle(bar);
            iconButton.fontSize = bar.fontSize;
            iconButton.padding = new RectOffset(Mathf.RoundToInt(h + 6), bar.padding.right, bar.padding.top, bar.padding.bottom);
            return iconButton;
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
            Row("1 finger / left-drag", "rotate");
            Row("Pinch / mouse wheel", "zoom towards the fingers / cursor");
            Row("2 fingers drag / right-drag", "move");
            Row("2 fingers twist", "turn in the screen plane");
            Row("Tap / click an organ", "show it alone (again: all organs)");
            Row("Knife button", "tap 2 points, then tap the side to remove");
            Row("R", "reset view");
            GUILayout.Space(6 * k);
            Row("P", "presets: Body / Lungs / Organs");
            Row("O", "organ list");
            Row("B", "bones only");
            Row("Q", "high quality while the view is still");
            GUILayout.Space(6 * k);
            Row("K", "dig tool: a hole follows the mouse; click pins it");
            Row("Shift+wheel / Ctrl+wheel", "hole size / hole depth");
            Row("Backspace", "remove pinned holes");
            Row("X", "cutting plane;  [ ] move it,  C change axis,  F flip side");
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
