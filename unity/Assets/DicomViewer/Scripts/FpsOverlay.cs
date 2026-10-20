using UnityEngine;

namespace DicomViewer
{
    /// <summary>Tiny FPS counter for the optimisation phase. Toggle with F1.</summary>
    public class FpsOverlay : MonoBehaviour
    {
        public bool show = true;
        private float smoothed;

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.F1)) show = !show;
            smoothed = Mathf.Lerp(smoothed, 1f / Mathf.Max(Time.unscaledDeltaTime, 1e-4f), 0.05f);
        }

        private void OnGUI()
        {
            if (!show) return;
            GUI.Label(new Rect(10, 10, 300, 40), $"{smoothed:F0} FPS   {Time.unscaledDeltaTime * 1000f:F1} ms",
                new GUIStyle(GUI.skin.label) { fontSize = 18 });
        }
    }
}
