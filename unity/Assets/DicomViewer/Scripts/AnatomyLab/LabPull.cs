using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The Anatomy Lab's Pull tool (TissueWarp, by Claude Fable). Grab skin next to the last scalpel cut and drag
    /// away from it: that side of the wound folds back as a flap of skin and fat, follows the finger, and stays open.
    /// Grab skin anywhere else: it stretches with the finger and springs back when you let go, as living skin does.
    /// Heal puts everything back. A gloved hand (LabInstruments) pinches the tissue being pulled.
    /// </summary>
    [RequireComponent(typeof(AnatomyLab), typeof(TissueWarp), typeof(TissueFlaps))]
    public class LabPull : MonoBehaviour
    {
        [Tooltip("How much tissue a grab takes along, mm (it grows as you pull further).")]
        public float grabRadiusMm = 10f;
        [Tooltip("A grab within this distance of the last cut folds it back as a flap, mm.")]
        public float flapPickMm = 10f;
        [Tooltip("Flap thickness below the skin, mm (skin and the fat under it).")]
        public float flapDepthMm = 5f;
        [Tooltip("Flap width from the cut to its hinge, mm: the distance from the cut to the grab, times this, within the limits below.")]
        public float flapWidthPerGrab = 1.5f;
        public float minFlapWidthMm = 5f, maxFlapWidthMm = 20f;
        [Tooltip("Finger distance that folds a flap fully back, as a multiple of its width.")]
        public float fullFoldPerWidth = 1.2f;

        private AnatomyLab lab;
        private TissueWarp warp;
        private TissueFlaps flaps;
        private LabScalpel scalpel;
        private LabInstruments instruments;
        private int flapId = -1;
        private float flapWidthMm;
        private bool flapMoved;
        private readonly List<Vector3> cut = new List<Vector3>();
        private enum Mode { None, Stretch, Flap }
        private Mode mode;
        private int grabId = -1;
        private Plane dragPlane;
        private Vector3 grabWorld, grabUvw, grabNormal, foldDirUvw, dragTarget;

        public bool Ready => warp != null && warp.IsSetUp;

        private void Awake()
        {
            lab = GetComponent<AnatomyLab>();
            warp = GetComponent<TissueWarp>();
            flaps = GetComponent<TissueFlaps>();
            scalpel = GetComponent<LabScalpel>();
            instruments = GetComponent<LabInstruments>();
        }

        private void OnDisable() => Release();

        private void Update()
        {
            PhotoBody body = lab.Body;
            if (ViewerUi.ActiveTool != ViewerUi.Tool.Pull || body == null || !body.IsLoaded || !Ready ||
                ViewerUi.ModalOpen || Input.touchCount >= 2)
            {
                Release();
                return;
            }
            Camera cam = Camera.main;
            if (cam == null) return;

            bool picked = body.Raycast(cam.ScreenPointToRay(Input.mousePosition), lab.Mask.IsRemovedLocal, out Vector3 hit, out Vector3 normal);
            if (Input.GetMouseButtonDown(0) && !ViewerUi.PointerOverUi && !VolumeOrbitController.GestureRecent && picked)
                Begin(body, cam, hit, normal);
            else if (mode != Mode.None && Input.GetMouseButton(0))
                Drag(body, cam);
            if (mode != Mode.None && !Input.GetMouseButton(0)) Release();
            ShowHand(body, picked, hit, normal);
        }

        // The hand holds what is being pulled: the flap's edge where it has turned to, or the stretched skin at the
        // finger. Under a mouse pointer an open hand hovers, ready to pinch.
        private void ShowHand(PhotoBody body, bool picked, Vector3 hit, Vector3 normal)
        {
            if (instruments == null) return;
            if (mode == Mode.Flap)
            {
                Vector3 n = body.Space.WorldDirToMm(body.Volume, grabNormal).normalized;
                Vector3 nUvw = new Vector3(n.x / body.Space.SizeMm.x, n.y / body.Space.SizeMm.y, n.z / body.Space.SizeMm.z) * 3f;
                Vector3 at = World(body, flaps.DisplayUvw(flapId, grabUvw));
                Vector3 up = World(body, flaps.DisplayUvw(flapId, grabUvw + nUvw)) - at;
                instruments.ShowHand(at, up.sqrMagnitude > 1e-12f ? up.normalized : grabNormal, true);
            }
            else if (mode == Mode.Stretch) instruments.ShowHand(dragTarget, grabNormal, true);
            else if (picked && Input.mousePresent && Input.touchCount == 0 && !ViewerUi.PointerOverUi)
                instruments.ShowHand(hit, normal, false);
        }

        private static Vector3 World(PhotoBody body, Vector3 uvw) => body.Volume.TransformPoint(VolumeSpace.UvwToLocal(uvw));

        private void Begin(PhotoBody body, Camera cam, Vector3 hit, Vector3 normal)
        {
            grabWorld = dragTarget = hit;
            grabNormal = normal;
            grabUvw = Uvw(body, hit);
            dragPlane = new Plane(-cam.transform.forward, hit);              // the finger moves the tissue in this plane

            // Next to the last cut (and the body has a skin-depth map): fold back a flap on the grabbed side.
            cut.Clear();
            if (scalpel != null && body.SkinDepthTexture != null) cut.AddRange(scalpel.LastCutUvw);
            if (cut.Count >= 2)
            {
                Vector3 nearest = NearestOnPolyline(cut, grabUvw, body.Space.SizeMm, out float distMm);
                if (distMm <= flapPickMm)
                {
                    foldDirUvw = grabUvw - nearest;
                    if (foldDirUvw.sqrMagnitude < 1e-12f) foldDirUvw = Vector3.down;
                    // A flap is never wider than its cut is long: a small cut lifts a small flap.
                    float cutMm = Vector3.Distance(Vector3.Scale(cut[0], body.Space.SizeMm), Vector3.Scale(cut[cut.Count - 1], body.Space.SizeMm));
                    flapWidthMm = Mathf.Min(Mathf.Clamp(distMm * flapWidthPerGrab, minFlapWidthMm, maxFlapWidthMm), Mathf.Max(cutMm, 3f));
                    Vector3 outwardMm = body.Space.WorldDirToMm(body.Volume, normal);
                    flapId = flaps.Begin(cut, foldDirUvw, outwardMm, flapWidthMm, flapDepthMm);
                    if (flapId >= 0)
                    {
                        mode = Mode.Flap;
                        flapMoved = false;
                        return;
                    }
                }
            }
            grabId = warp.BeginGrab(grabUvw, grabRadiusMm);
            if (grabId >= 0) mode = Mode.Stretch;
        }

        private void Drag(PhotoBody body, Camera cam)
        {
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            if (!dragPlane.Raycast(ray, out float t)) return;
            Vector3 target = ray.GetPoint(t);
            dragTarget = target;
            if (mode == Mode.Stretch)
            {
                warp.UpdateGrab(grabId, Uvw(body, target));
                return;
            }
            // Flap: the farther the finger has pulled, the further the flap folds back (fully at about its width).
            float mm = Vector3.Distance(target, grabWorld) / body.Space.WorldPerMm(body.Volume);
            float amount = Mathf.Clamp01(mm / (flapWidthMm * fullFoldPerWidth));
            flaps.SetFold(flapId, amount);
            flapMoved |= amount > 0.02f;
        }

        private void Release()
        {
            if (mode == Mode.Stretch && grabId >= 0) warp.EndGrab(grabId, keep: false);   // living skin springs back
            if (mode == Mode.Flap && !flapMoved) flaps.Remove(flapId);                   // a tap, not a fold
            mode = Mode.None;                                                              // a folded flap stays
            grabId = flapId = -1;
        }

        private static Vector3 Uvw(PhotoBody body, Vector3 world) => VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(world));

        /// <summary>Nearest point of a polyline (texture coordinates) to p, and its distance in millimetres.</summary>
        public static Vector3 NearestOnPolyline(IReadOnlyList<Vector3> line, Vector3 p, Vector3 sizeMm, out float distMm)
        {
            Vector3 best = line[0];
            distMm = float.MaxValue;
            Vector3 pm = Vector3.Scale(p, sizeMm);
            for (int i = 0; i + 1 < line.Count; i++)
            {
                Vector3 a = Vector3.Scale(line[i], sizeMm), b = Vector3.Scale(line[i + 1], sizeMm);
                Vector3 ab = b - a;
                float s = ab.sqrMagnitude > 1e-12f ? Mathf.Clamp01(Vector3.Dot(pm - a, ab) / ab.sqrMagnitude) : 0f;
                Vector3 q = a + ab * s;
                float d = Vector3.Distance(pm, q);
                if (d < distMm)
                {
                    distMm = d;
                    best = new Vector3(q.x / sizeMm.x, q.y / sizeMm.y, q.z / sizeMm.z);
                }
            }
            return best;
        }
    }
}
