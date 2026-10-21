using System;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// Start screen: Scan viewer (open a CT/MRI scan in 3D) or Anatomy lab (a real body to dissect). Each mode is
    /// its own object and only the chosen one is active, so the other loads nothing. A Home button returns here.
    /// Added at start-up when the scene has the scan viewer; the Anatomy Lab rig is built in code
    /// (AnatomyLab.CreateRig), so the scene needs no changes. Command line: -mode lab | -mode viewer skips the menu.
    /// </summary>
    public class AppMode : MonoBehaviour
    {
        public enum Mode { Menu, ScanViewer, AnatomyLab }

        public static Mode Current { get; private set; } = Mode.Menu;

        private GameObject viewer, lab;
        private GUIStyle titleStyle, textStyle, cardStyle, homeStyle;

        // After the scene's Awake calls and before any Start: the viewer has not begun loading yet.
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Bootstrap()
        {
            if (FindAnyObjectByType<AppMode>() != null) return;
            if (FindAnyObjectByType<VolumeLoader>(FindObjectsInactive.Include) == null) return;   // another scene
            new GameObject("App").AddComponent<AppMode>();
        }

        private void Awake()
        {
            var loader = FindAnyObjectByType<VolumeLoader>(FindObjectsInactive.Include);
            viewer = loader != null ? loader.gameObject : null;
            var existing = FindAnyObjectByType<AnatomyLab>(FindObjectsInactive.Include);
            lab = existing != null ? existing.gameObject : AnatomyLab.CreateRig();
            if (viewer != null) viewer.SetActive(false);
            lab.SetActive(false);
            Current = Mode.Menu;

            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-mode") Enter(args[i + 1] == "lab" ? Mode.AnatomyLab : Mode.ScanViewer);
        }

        public void Enter(Mode mode)
        {
            ViewerUi.ActiveTool = ViewerUi.Tool.Rotate;
            ViewerUi.ModalOpen = false;
            if (viewer != null) viewer.SetActive(mode == Mode.ScanViewer);
            lab.SetActive(mode == Mode.AnatomyLab);
            Current = mode;
        }

        private void OnGUI()
        {
            float k = ViewerUi.Scale;
            Styles(k);
            if (Current != Mode.Menu)
            {
                var home = new Rect(12 * k, Screen.height - 58 * k, 110 * k, 46 * k);
                ViewerUi.Block(home);
                if (GUI.Button(home, "Home", homeStyle)) Enter(Mode.Menu);
                return;
            }

            GUI.color = new Color(0.07f, 0.065f, 0.06f, 1f);
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = Color.white;
            ViewerUi.Block(new Rect(0, 0, Screen.width, Screen.height));

            float w = Mathf.Min(1100 * k, Screen.width - 40 * k);
            float x = (Screen.width - w) / 2, y = Screen.height * 0.16f;
            GUI.Label(new Rect(x, y, w, 60 * k), "Dissection Table", titleStyle);
            GUI.Label(new Rect(x, y + 64 * k, w, 30 * k), "For education only - not for diagnostic use.", textStyle);

            float gap = 24 * k, cw = (w - gap) / 2, ch = 260 * k, cy = y + 130 * k;
            if (GUI.Button(new Rect(x, cy, cw, ch),
                    "Scan viewer\n\nOpen a CT or MRI scan (DICOM, NRRD) and look through it in 3D: organs, bones, cutting planes.",
                    cardStyle))
                Enter(Mode.ScanViewer);
            if (GUI.Button(new Rect(x + cw + gap, cy, cw, ch),
                    "Anatomy lab\n\nA real human body, photographed slice by slice. Cut it with a scalpel, open the eyes, look inside.",
                    cardStyle))
                Enter(Mode.AnatomyLab);
        }

        private void Styles(float k)
        {
            if (titleStyle == null)
            {
                titleStyle = new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleLeft };
                titleStyle.normal.textColor = new Color(0.93f, 0.9f, 0.85f);
                textStyle = new GUIStyle(GUI.skin.label) { wordWrap = true };
                textStyle.normal.textColor = new Color(0.65f, 0.62f, 0.57f);
                cardStyle = new GUIStyle(GUI.skin.button) { wordWrap = true, alignment = TextAnchor.UpperLeft };
                homeStyle = new GUIStyle(GUI.skin.button);
            }
            titleStyle.fontSize = Mathf.RoundToInt(44 * k);
            textStyle.fontSize = Mathf.RoundToInt(17 * k);
            cardStyle.fontSize = Mathf.RoundToInt(22 * k);
            cardStyle.padding = new RectOffset(Mathf.RoundToInt(26 * k), Mathf.RoundToInt(26 * k), Mathf.RoundToInt(26 * k), Mathf.RoundToInt(26 * k));
            homeStyle.fontSize = Mathf.RoundToInt(17 * k);
        }
    }
}
