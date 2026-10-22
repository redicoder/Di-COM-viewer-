using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The Anatomy Lab's buttons (IMGUI, like the scan viewer's toolbar until the UI Toolkit port): tools (Turn,
    /// Scalpel, Pull, Eyelids), eyes open / close, undo / redo / heal, living or real eyes, blood on / off, front view; the body's credit
    /// and the note that bleeding is a simulation. Ctrl+Z / Ctrl+Y undo and redo cuts.
    /// </summary>
    [RequireComponent(typeof(AnatomyLab))]
    public class LabToolbar : MonoBehaviour
    {
        private AnatomyLab lab;
        private GUIStyle bar, barOn, note;

        private void Awake() => lab = GetComponent<AnatomyLab>();

        private void Update()
        {
            if (ViewerUi.ModalOpen) return;
            bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
            if (ctrl && Input.GetKeyDown(KeyCode.Z)) lab.Mask.Undo();
            if (ctrl && Input.GetKeyDown(KeyCode.Y)) lab.Mask.Redo();
        }

        private void OnGUI()
        {
            float k = ViewerUi.Scale;
            Styles(k);
            float h = 46 * k, pad = 8 * k, x = pad, y = pad;
            PhotoBody body = lab.Body;

            if (body == null || !body.IsLoaded)
            {
                string msg = body != null && body.Error != null ? body.Error
                    : "Loading the photographed body...  (made by backend/tools/prepare_photo_volume.py --unity)";
                GUI.Label(new Rect(pad, pad, Screen.width - 2 * pad, 60 * k), msg, note);
                return;
            }

            Tool("Turn", ViewerUi.Tool.Rotate);
            Tool("Scalpel", ViewerUi.Tool.Scalpel);
            Tool("Pull", ViewerUi.Tool.Pull);
            Tool("Eyelids", ViewerUi.Tool.Eyelids);
            x += pad * 2;
            if (Button("Open eyes", 120)) lab.OpenEyes(true);
            if (Button("Close eyes", 120)) lab.OpenEyes(false);
            x += pad * 2;
            GUI.enabled = lab.Mask.CanUndo;
            if (Button("Undo", 80)) lab.Mask.Undo();
            GUI.enabled = lab.Mask.CanRedo;
            if (Button("Redo", 80)) lab.Mask.Redo();
            GUI.enabled = true;
            if (Button("Heal all", 100)) lab.HealAll();
            x += pad * 2;
            if (Button(lab.livingEyes ? "Eyes: living" : "Eyes: his real", 150)) lab.livingEyes = !lab.livingEyes;
            if (Button(lab.ShowBlood ? "Blood: on" : "Blood: off", 120)) lab.ShowBlood = !lab.ShowBlood;
            if (Button("Front view", 120)) lab.ResetView();
            if (Button(lab.IsWholeBody ? "Body: whole" : "Body: head", 130))
                lab.UseBody(lab.IsWholeBody ? AnatomyLab.HeadBody : AnatomyLab.WholeBody);

            string credit = string.IsNullOrEmpty(body.Meta.credit) ? "" : body.Meta.credit + ". ";
            var noteRect = new Rect(pad, y + h + pad, Screen.width - 2 * pad, 30 * k);
            string bleeding = lab.ShowBlood ? "Bleeding is a simulation: a real dead body does not bleed. "
                : "Dry dissection: cuts do not bleed, blood hidden. ";
            GUI.Label(noteRect, credit + bleeding + "For education only.", note);

            void Wrap(float width)                     // touch screens make buttons bigger: continue on a new row
            {
                if (x + width <= Screen.width - pad || x <= pad) return;
                x = pad;
                y += h + pad;
            }

            void Tool(string label, ViewerUi.Tool tool)
            {
                Wrap(110 * k);
                var r = new Rect(x, y, 110 * k, h);
                ViewerUi.Block(r);
                if (GUI.Button(r, label, ViewerUi.ActiveTool == tool ? barOn : bar)) ViewerUi.ActiveTool = tool;
                x += r.width + pad;
            }

            bool Button(string label, float width)
            {
                Wrap(width * k);
                var r = new Rect(x, y, width * k, h);
                ViewerUi.Block(r);
                x += r.width + pad;
                return GUI.Button(r, label, bar);
            }
        }

        private void Styles(float k)
        {
            if (bar == null)
            {
                bar = new GUIStyle(GUI.skin.button);
                barOn = new GUIStyle(bar) { normal = bar.onNormal, hover = bar.onHover, fontStyle = FontStyle.Bold };
                barOn.normal.textColor = barOn.hover.textColor = new Color(1f, 0.85f, 0.3f);
                note = new GUIStyle(GUI.skin.label) { wordWrap = true };
                note.normal.textColor = new Color(0.8f, 0.78f, 0.74f);
            }
            bar.fontSize = barOn.fontSize = Mathf.RoundToInt(16 * k);
            note.fontSize = Mathf.RoundToInt(14 * k);
        }
    }
}
