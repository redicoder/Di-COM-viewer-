using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The Anatomy Lab's scalpel: drag across the body and a No. 10 blade (LabInstruments) draws an incision along
    /// the path; drag across lifted skin (TissueSheets) and the blade cuts through it there. The blade parts the tissue in a thin V (MaskVolume, one undo step per stroke), and behind it the skin's
    /// tension draws the edges apart into a lens-shaped wound (TissueWarp.Gape): widest in the middle and at the skin,
    /// closed at the ends. The tissue the blade reaches decides how much it bleeds (BloodSim).
    /// </summary>
    [RequireComponent(typeof(AnatomyLab))]
    public class LabScalpel : MonoBehaviour
    {
        [Tooltip("Width of the blade's track at the skin, mm (the wound is wider once its edges draw apart).")]
        public float widthMm = 1.8f;
        [Tooltip("Depth of the incision, mm: through the skin into the fat beneath.")]
        public float depthMm = 5f;
        [Tooltip("A new piece of wound every this many mm of finger movement.")]
        public float stepMm = 1.2f;
        [Tooltip("How far each edge of a long incision draws back at the skin, mm.")]
        public float maxGapeMm = 1.6f;
        [Tooltip("Gape per mm of incision length (short cuts hardly open).")]
        public float gapePerMm = 0.035f;
        [Tooltip("How far beside the incision the skin is drawn along, mm.")]
        public float gapeReachMm = 8f;

        // V profile: (centre depth below the skin, radius), as fractions of depth and half-width.
        private static readonly Vector2[] Profile =
        {
            new Vector2(-0.10f, 1.04f), new Vector2(0.30f, 0.80f), new Vector2(0.60f, 0.62f), new Vector2(0.88f, 0.55f),
        };
        private const float MinRadiusMm = 0.45f;          // below about a voxel the mask would miss the cut
        private const float EntryMm = 3f;                 // the blade sinks to full depth over the first mm

        private AnatomyLab lab;
        private MaskVolume mask;
        private BloodSim blood;
        private TissueWarp warp;
        private LabInstruments instruments;
        private TissueSheets sheets;
        private int lastSheet = -1;                   // the blade is in lifted tissue (a sheet) rather than the body
        private Vector2 lastGrid;
        private bool cutting;
        private Vector3 lastPoint, lastNormal, strokeDir;
        private float strokeMm, gapedAtMm;
        private MaskOp liveOp;
        private readonly List<Vector3> stroke = new List<Vector3>();      // this stroke's path, texture coordinates
        // Each stroke's opened wound, so undo, redo and heal can rebuild the gapes the mask still has.
        private readonly Dictionary<MaskOp, (Vector3[] path, float gape)> gapes = new Dictionary<MaskOp, (Vector3[], float)>();
        private readonly List<MaskOp> gaped = new List<MaskOp>();

        private void Awake()
        {
            lab = GetComponent<AnatomyLab>();
            mask = GetComponent<MaskVolume>();
            blood = GetComponent<BloodSim>();
            warp = GetComponent<TissueWarp>();
            instruments = GetComponent<LabInstruments>();
            sheets = GetComponent<TissueSheets>();
            if (mask != null) mask.Changed += OnMaskChanged;
        }

        private void OnDestroy()
        {
            if (mask != null) mask.Changed -= OnMaskChanged;
        }

        private void OnDisable() => End();

        private void Update()
        {
            PhotoBody body = lab.Body;
            if (ViewerUi.ActiveTool != ViewerUi.Tool.Scalpel || body == null || !body.IsLoaded || !lab.Mask.Ready ||
                ViewerUi.ModalOpen || Input.touchCount >= 2 || VolumeOrbitController.GestureRecent)
            {
                End();
                return;
            }
            Camera cam = Camera.main;
            if (cam == null) return;

            bool picked = Pick(cam, out Vector3 p, out Vector3 n, out int sheet, out Vector2 grid);
            if (Input.GetMouseButtonDown(0) && !ViewerUi.PointerOverUi && picked)
            {
                lastSheet = sheet;
                lastGrid = grid;
                lab.Mask.BeginStroke("scalpel");
                liveOp = lab.Mask.StrokeActive ? lab.Mask.Ops[lab.Mask.Ops.Count - 1] : null;
                if (warp != null && warp.IsSetUp) warp.SaveState();
                cutting = true;
                lastPoint = p;
                lastNormal = n;
                strokeMm = gapedAtMm = 0f;
                strokeDir = Vector3.zero;
                stroke.Clear();
                stroke.Add(Uvw(lab.Body, p));
            }
            else if (cutting && Input.GetMouseButton(0) && picked)
            {
                float perMm = body.Space.WorldPerMm(body.Volume);
                float mm = Vector3.Distance(p, lastPoint) / perMm;
                if (mm > 40f)                         // jumped to another part of the body: start afresh there
                {
                    lastPoint = p;
                    lastNormal = n;
                    lastSheet = sheet;
                    lastGrid = grid;
                }
                else if (sheet >= 0 || lastSheet >= 0)
                {
                    // Through lifted skin, in the air: the sheet is cut where the blade passes (no wound in the body).
                    if (sheet >= 0 && sheet == lastSheet && mm > stepMm * 0.5f)
                    {
                        sheets.CutSheet(sheet, lastGrid, grid);
                        strokeDir = (p - lastPoint).normalized;
                    }
                    if (sheet != lastSheet || mm > stepMm * 0.5f)
                    {
                        lastPoint = p;
                        lastNormal = n;
                        lastGrid = grid;
                    }
                    lastSheet = sheet;
                }
                else if (mm > stepMm)
                {
                    float depthScale = Mathf.Lerp(0.4f, 1f, Mathf.Clamp01(strokeMm / EntryMm));
                    Incise(body, lab.Mask, blood, lastPoint, p, (lastNormal + n).normalized, widthMm, depthMm * depthScale, sheets);
                    strokeDir = Vector3.Slerp(strokeDir == Vector3.zero ? (p - lastPoint).normalized : strokeDir, (p - lastPoint).normalized, 0.5f);
                    lastPoint = p;
                    lastNormal = n;
                    strokeMm += mm;
                    stroke.Add(Uvw(body, p));
                    if (strokeMm - gapedAtMm >= 3f) OpenWound(liveStroke: true);
                }
            }
            if (cutting && !Input.GetMouseButton(0)) End();

            // The blade: pressed into the skin while cutting, hovering just above it under a mouse pointer.
            if (instruments != null)
            {
                bool hover = !cutting && picked && Input.mousePresent && Input.touchCount == 0 && !ViewerUi.PointerOverUi;
                if (cutting) instruments.ShowScalpel(lastPoint, lastNormal, strokeDir, depthMm * 0.8f);
                else if (hover) instruments.ShowScalpel(p, n, Vector3.zero, -2f);
            }
        }

        private void End()
        {
            if (!cutting) return;
            cutting = false;
            if (stroke.Count >= 2)
            {
                OpenWound(liveStroke: false);
            }
            lab.Mask.EndStroke();                     // fires Changed: a stroke that removed nothing loses its gape
            liveOp = null;
        }

        /// <summary>Forget the last cut (Heal).</summary>
        public void ForgetCut() => gapes.Clear();

        // The stroke's wound opens behind the blade: the field as it was before the stroke, plus this stroke's gape.
        private void OpenWound(bool liveStroke)
        {
            gapedAtMm = strokeMm;
            if (warp == null || !warp.IsSetUp || liveOp == null || stroke.Count < 2) return;
            float gape = Mathf.Min(maxGapeMm, strokeMm * gapePerMm);
            var path = Resample(stroke, TissueWarp.MaxFlapPoints).ToArray();
            warp.RestoreState();
            warp.Gape(path, gape, gapeReachMm, depthMm);
            if (liveStroke) return;
            gapes[liveOp] = (path, gape);
            gaped.Remove(liveOp);
            gaped.Add(liveOp);
        }

        // Undo, redo, heal: rebuild the gapes of the strokes the mask still has, in order.
        private void OnMaskChanged()
        {
            if (mask.StrokeActive || warp == null || !warp.IsSetUp) return;
            var want = new List<MaskOp>();
            foreach (MaskOp op in mask.Ops) if (gapes.ContainsKey(op)) want.Add(op);
            bool same = want.Count == gaped.Count;
            for (int i = 0; same && i < want.Count; i++) same = want[i] == gaped[i];
            if (same) return;
            warp.ClearDeformation();
            foreach (MaskOp op in want) warp.Gape(gapes[op].path, gapes[op].gape, gapeReachMm, depthMm);
            gaped.Clear();
            gaped.AddRange(want);
        }

        private static List<Vector3> Resample(List<Vector3> points, int max)
        {
            if (points.Count <= max) return new List<Vector3>(points);
            var r = new List<Vector3>(max);
            for (int i = 0; i < max; i++) r.Add(points[Mathf.RoundToInt(i * (points.Count - 1) / (float)(max - 1))]);
            return r;
        }

        private static Vector3 Uvw(PhotoBody body, Vector3 world) => VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(world));

        // What the blade meets first: the body (skipping what was cut away or lifted off) or lifted skin (a sheet).
        private bool Pick(Camera cam, out Vector3 point, out Vector3 normal, out int sheet, out Vector2 grid)
        {
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            bool body = lab.Body.Raycast(ray, lab.IsGoneLocal, out point, out normal) && !lab.InRegion(point);
            sheet = -1;
            grid = default;
            if (sheets != null && sheets.Raycast(ray, out TissueSheets.SheetHit hit) &&
                (!body || hit.distance < Vector3.Distance(ray.origin, point)))
            {
                point = hit.point;
                normal = hit.normal;
                sheet = hit.sheet;
                grid = hit.grid;
                return true;
            }
            return body;
        }

        /// <summary>
        /// One piece of incision from aWorld to bWorld (points on the skin): a V-shaped track removed from the mask,
        /// and bleeding from it; skin a sheet holds there is cut with it. Also used by the editor snapshots.
        /// </summary>
        public static void Incise(PhotoBody body, MaskVolume mask, BloodSim blood, Vector3 aWorld, Vector3 bWorld,
            Vector3 normalWorld, float widthMm, float depthMm, TissueSheets sheets = null)
        {
            VolumeSpace space = body.Space;
            Vector3 a = space.WorldToMm(body.Volume, aWorld), b = space.WorldToMm(body.Volume, bWorld);
            Vector3 inward = -space.WorldDirToMm(body.Volume, normalWorld).normalized;
            float half = widthMm * 0.5f;
            foreach (Vector2 c in Profile)
            {
                Vector3 off = inward * (c.x * depthMm);
                var capsule = new MaskCapsule(a + off, b + off, Mathf.Max(c.y * half, MinRadiusMm));
                mask.ExtendStroke(capsule);
                if (sheets != null) sheets.Incised(capsule.a, capsule.b, capsule.radius);
            }
            if (blood != null) blood.AddWound(aWorld, bWorld, normalWorld, Redness(body, (aWorld + bWorld) * 0.5f, normalWorld));
        }

        /// <summary>How far each edge of an incision this long draws back, mm (the scalpel's defaults).</summary>
        public static float GapeFor(float lengthMm, float maxGapeMm = 1.6f, float gapePerMm = 0.035f) =>
            Mathf.Min(maxGapeMm, lengthMm * gapePerMm);

        // Red muscle and vessels 3 mm down bleed a lot, yellow fat hardly, white bone not at all.
        private static float Redness(PhotoBody body, Vector3 surfaceWorld, Vector3 normalWorld)
        {
            float perMm = body.Space.WorldPerMm(body.Volume);
            Vector3 inside = body.Volume.InverseTransformPoint(surfaceWorld - normalWorld * (3f * perMm));
            Color32 c = body.ColourAt(inside);
            return Mathf.Clamp01((c.r - 0.5f * (c.g + c.b)) / 255f * 3f);
        }
    }
}
