using System.Collections.Generic;
using UnityEngine;
using UnityVolumeRendering;

namespace DicomViewer
{
    /// <summary>
    /// Knife: cut the body along a line you draw, then remove one side.
    ///   1. tap (or click) the first point, 2. tap the second point: a cut line across the screen,
    ///   3. tap the half to remove: it vanishes through the whole depth, as seen from this direction.
    /// Each cut is a UnityVolumeRendering CrossSectionPlane through the camera and the drawn line, parented to
    /// the volume so it stays attached to the anatomy when you rotate afterwards. Undo removes the last cut.
    /// Works with mouse and touch (a tap is a press without dragging; a finger drag still rotates).
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class KnifeTool : MonoBehaviour
    {
        [Tooltip("The plugin supports 8 cuts in total, shared with the cutting plane and the dig holes.")]
        public int maxCuts = 6;

        public static bool Active { get; private set; }

        private enum Step { FirstPoint, SecondPoint, ChooseSide }
        private Step step;
        private Vector2 a, b;                 // screen pixels, origin bottom-left
        private Vector3 downPos;
        private float downTime;
        private string message;
        private float messageUntil;

        private VolumeLoader loader;
        private readonly List<CrossSectionPlane> cuts = new List<CrossSectionPlane>();
        private Texture2D white;
        private GUIStyle hint;

        public Texture2D Icon { get; private set; }
        public int CutCount => cuts.Count;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            loader.Loaded += _ => cuts.Clear();   // the planes are children of the old volume and go with it
            Icon = Resources.Load<Texture2D>("knife_icon");
        }

        public void SetActive(bool on)
        {
            Active = on;
            step = Step.FirstPoint;
            if (on)
            {
                var dig = GetComponent<CutTool>();
                if (dig != null) dig.SetDig(false);
            }
        }

        public void Undo()
        {
            if (cuts.Count == 0) return;
            var last = cuts[cuts.Count - 1];
            cuts.RemoveAt(cuts.Count - 1);
            if (last != null) Destroy(last.gameObject);
        }

        public void ClearCuts()
        {
            foreach (var c in cuts)
                if (c != null) Destroy(c.gameObject);
            cuts.Clear();
        }

        private void Update()
        {
            if (!Active || ViewerUi.ModalOpen || loader.Volume == null) return;
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                if (step == Step.FirstPoint) SetActive(false);
                else step = Step.FirstPoint;
                return;
            }

            Camera cam = Camera.main;
            bool overView = cam != null && cam.pixelRect.Contains(Input.mousePosition) && !ViewerUi.PointerOverUi;
            if (Input.GetMouseButtonDown(0) && overView)
            {
                downPos = Input.mousePosition;
                downTime = Time.unscaledTime;
            }
            if (!overView || !ViewerUi.TapReleased(downPos, downTime)) return;

            Vector2 p = Input.mousePosition;
            switch (step)
            {
                case Step.FirstPoint:
                    a = p;
                    step = Step.SecondPoint;
                    break;
                case Step.SecondPoint:
                    if ((p - a).magnitude < 30f * ViewerUi.Scale) return;   // too close: the line direction is unclear
                    b = p;
                    step = Step.ChooseSide;
                    break;
                case Step.ChooseSide:
                    Cut(cam, p);
                    step = Step.FirstPoint;
                    break;
            }
        }

        private void Cut(Camera cam, Vector2 sideTap)
        {
            int inUse = 0;
            foreach (var mb in FindObjectsByType<MonoBehaviour>(FindObjectsSortMode.None))
                if (mb is CrossSectionObject && mb.isActiveAndEnabled) inUse++;
            if (cuts.Count >= maxCuts || inUse >= 8)
            {
                Flash("Too many cuts: undo or clear some first");
                return;
            }

            // Points on the line, at the depth of the volume's centre.
            float depth = Vector3.Dot(loader.Volume.transform.position - cam.transform.position, cam.transform.forward);
            Vector3 pa = cam.ScreenToWorldPoint(new Vector3(a.x, a.y, depth));
            Vector3 pb = cam.ScreenToWorldPoint(new Vector3(b.x, b.y, depth));
            Vector3 pt = cam.ScreenToWorldPoint(new Vector3(sideTap.x, sideTap.y, depth));

            // The plane holds the drawn line and the viewing direction, so everything on one side of the line
            // as you see it is removed, through the whole depth.
            Vector3 n = cam.orthographic
                ? Vector3.Cross(pb - pa, cam.transform.forward)
                : Vector3.Cross(pa - cam.transform.position, pb - cam.transform.position);
            if (n.sqrMagnitude < 1e-12f) return;
            n.Normalize();
            if (Vector3.Dot(n, pt - pa) < 0f) n = -n;   // the plugin removes the side the plane's +z points to

            var go = new GameObject($"KnifeCut{cuts.Count + 1}");
            go.transform.SetPositionAndRotation(pa, Quaternion.LookRotation(n, (pb - pa).normalized));
            go.transform.SetParent(loader.Volume.transform, true);
            var plane = go.AddComponent<CrossSectionPlane>();
            plane.SetTargetObject(loader.Volume);
            cuts.Add(plane);
        }

        private void Flash(string text)
        {
            message = text;
            messageUntil = Time.unscaledTime + 3f;
        }

        // ------------------------------------------------------------------ drawing

        private void OnGUI()
        {
            if (Event.current.type != EventType.Repaint) return;
            float k = ViewerUi.Scale;
            if (hint == null)
            {
                hint = new GUIStyle(GUI.skin.box) { alignment = TextAnchor.MiddleCenter };
                hint.normal.textColor = Color.white;
                white = Texture2D.whiteTexture;
            }
            hint.fontSize = Mathf.RoundToInt(22 * k);

            if (Time.unscaledTime < messageUntil) Banner(message, k);
            if (!Active) return;

            Vector2 ga = ToGui(a), gb = ToGui(b), mouse = Event.current.mousePosition;
            switch (step)
            {
                case Step.FirstPoint:
                    Banner("Knife: tap the first point of the cut", k);
                    break;
                case Step.SecondPoint:
                    Banner("Knife: tap the second point", k);
                    Line(ga, mouse, 3f * k, new Color(1f, 0.85f, 0.2f, 0.6f));
                    Dot(ga, k);
                    break;
                case Step.ChooseSide:
                    Banner("Knife: tap the side to remove", k);
                    ShadeSide(ga, gb, mouse, k);
                    Vector2 dir = (gb - ga).normalized * 4000f;
                    Line(ga - dir, gb + dir, 3f * k, new Color(1f, 0.85f, 0.2f, 0.9f));
                    Dot(ga, k);
                    Dot(gb, k);
                    break;
            }
        }

        private static Vector2 ToGui(Vector2 screen) => new Vector2(screen.x, Screen.height - screen.y);

        private void Banner(string text, float k)
        {
            var size = hint.CalcSize(new GUIContent(text)) + new Vector2(40, 20) * k;
            GUI.Box(new Rect((Screen.width - size.x) / 2, Screen.height - size.y - 30 * k, size.x, size.y), text, hint);
        }

        private void Dot(Vector2 p, float k)
        {
            float r = 9f * k;
            GUI.color = new Color(0f, 0f, 0f, 0.8f);
            GUI.DrawTexture(new Rect(p.x - r - 2, p.y - r - 2, 2 * r + 4, 2 * r + 4), white);
            GUI.color = new Color(1f, 0.85f, 0.2f);
            GUI.DrawTexture(new Rect(p.x - r, p.y - r, 2 * r, 2 * r), white);
            GUI.color = Color.white;
        }

        private void Line(Vector2 p0, Vector2 p1, float width, Color c)
        {
            Matrix4x4 m = GUI.matrix;
            float angle = Mathf.Atan2(p1.y - p0.y, p1.x - p0.x) * Mathf.Rad2Deg;
            GUIUtility.RotateAroundPivot(angle, p0);
            GUI.color = c;
            GUI.DrawTexture(new Rect(p0.x, p0.y - width / 2, (p1 - p0).magnitude, width), white);
            GUI.color = Color.white;
            GUI.matrix = m;
        }

        /// <summary>Tints the half of the screen under the pointer red: the part that will be removed.</summary>
        private void ShadeSide(Vector2 ga, Vector2 gb, Vector2 pointer, float k)
        {
            Vector2 d = (gb - ga).normalized;
            Vector2 normal = new Vector2(-d.y, d.x);
            if (Vector2.Dot(pointer - ga, normal) < 0f) normal = -normal;
            Matrix4x4 m = GUI.matrix;
            float angle = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
            GUIUtility.RotateAroundPivot(angle, ga);
            // In the rotated frame the line is the x axis through ga; the chosen side is +y or -y.
            bool below = Vector2.Dot(normal, new Vector2(-d.y, d.x)) > 0f;
            float big = 6000f;
            GUI.color = new Color(1f, 0.15f, 0.1f, 0.18f);
            GUI.DrawTexture(new Rect(ga.x - big, below ? ga.y : ga.y - big, 2 * big, big), white);
            GUI.color = Color.white;
            GUI.matrix = m;
        }
    }
}
