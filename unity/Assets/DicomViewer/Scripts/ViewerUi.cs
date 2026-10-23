using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer
{
    /// <summary>
    /// Screen areas covered by on-screen panels (toolbar, organ list, dialogs), so mouse input over them does
    /// not also rotate, pick or cut the volume. Panels call Block() from OnGUI; Update() code reads
    /// PointerOverUi, which therefore reflects the previous frame's panels (one frame of lag is invisible).
    /// </summary>
    public static class ViewerUi
    {
        private static readonly List<Rect> rects = new List<Rect>();
        private static int rectsFrame = -10;

        /// <summary>Call from OnGUI with the panel's GUI-space rect (origin top-left).</summary>
        public static void Block(Rect guiRect)
        {
            if (Event.current.type != EventType.Repaint) return;
            if (rectsFrame != Time.frameCount)
            {
                rects.Clear();
                rectsFrame = Time.frameCount;
            }
            rects.Add(guiRect);
        }

        public static bool PointerOverUi
        {
            get
            {
                if (rectsFrame < Time.frameCount - 1) return false;   // nothing drawn recently
                Vector2 m = Input.mousePosition;
                var gui = new Vector2(m.x, Screen.height - m.y);
                foreach (var r in rects)
                    if (r.Contains(gui)) return true;
                return false;
            }
        }

        /// <summary>A modal dialog is open: the 3D view ignores the mouse and keyboard shortcuts.</summary>
        public static bool ModalOpen { get; set; }

        /// <summary>
        /// The armed tool. Rotate is the default: one finger rotates, a tap selects a structure to inspect.
        /// With a cutting tool armed, one finger (left mouse) cuts; two fingers (right mouse) still navigate.
        /// Eyelids and Pull belong to the Anatomy Lab: one finger opens and closes the eyes / pulls tissue.
        /// </summary>
        public enum Tool { Rotate, Scalpel, Dig, Knife, Eyelids, Pull, TakeOut }

        public static Tool ActiveTool { get; set; } = Tool.Rotate;
        public static bool CuttingToolArmed => ActiveTool != Tool.Rotate;

        /// <summary>
        /// Size factor for on-screen panels: 1 at 1080p, larger on touch screens so buttons are finger-sized.
        /// </summary>
        public static float Scale => Screen.height / 1080f * (Input.touchSupported ? 1.3f : 1f);

        /// <summary>A short press without dragging (mouse click or finger tap), ignoring the end of a pinch.</summary>
        public static bool TapReleased(Vector3 downPosition, float downTime) =>
            Input.GetMouseButtonUp(0) && !VolumeOrbitController.GestureRecent &&
            (Input.mousePosition - downPosition).magnitude < 12f * Screen.height / 1080f &&
            Time.unscaledTime - downTime < 0.5f;
    }
}
