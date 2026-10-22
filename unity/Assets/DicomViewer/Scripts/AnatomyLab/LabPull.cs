using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The Anatomy Lab's Pull tool, a gloved hand (LabInstruments) pinching the tissue. Beside a scalpel cut it takes
    /// hold of the wound's edge and the skin behaves as it would on a real body (TissueSheets, physics): it peels off
    /// the fat as far as the pull tears it, a flap cut on three sides folds back about its base and hangs under its
    /// own weight, and a piece cut all round comes away in the hand and falls when let go. Lifted or loose tissue can
    /// be taken hold of again anywhere. Intact skin only stretches with the finger and springs back when let go
    /// (TissueWarp, by Claude Fable). Heal puts everything back.
    /// </summary>
    [RequireComponent(typeof(AnatomyLab), typeof(TissueWarp), typeof(TissueSheets))]
    public class LabPull : MonoBehaviour
    {
        [Tooltip("How much tissue a grab of intact skin takes along, mm (it grows as you pull further).")]
        public float grabRadiusMm = 10f;

        private AnatomyLab lab;
        private TissueWarp warp;
        private TissueSheets sheets;
        private LabInstruments instruments;
        private enum Mode { None, Stretch, Sheet }
        private Mode mode;
        private int grabId = -1;
        private Plane dragPlane;
        private Vector3 grabNormal, dragTarget;

        public bool Ready => warp != null && warp.IsSetUp;

        private void Awake()
        {
            lab = GetComponent<AnatomyLab>();
            warp = GetComponent<TissueWarp>();
            sheets = GetComponent<TissueSheets>();
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

            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            bool picked = body.Raycast(ray, lab.IsGoneLocal, out Vector3 hit, out Vector3 normal) && !lab.InRegion(hit);
            bool onSheet = sheets.Raycast(ray, out TissueSheets.SheetHit sheetHit) &&
                           (!picked || sheetHit.distance < Vector3.Distance(ray.origin, hit));
            if (Input.GetMouseButtonDown(0) && !ViewerUi.PointerOverUi && !VolumeOrbitController.GestureRecent && (picked || onSheet))
                Begin(cam, ray, picked, hit, normal, onSheet, sheetHit);
            else if (mode != Mode.None && Input.GetMouseButton(0))
                Drag(body, cam);
            if (mode != Mode.None && !Input.GetMouseButton(0)) Release();

            // The hand: on what it holds, or open over what the pointer is on.
            if (instruments == null) return;
            if (mode == Mode.Sheet && sheets.HeldPoint(out Vector3 at, out Vector3 up)) instruments.ShowHand(at, up, true);
            else if (mode == Mode.Stretch) instruments.ShowHand(dragTarget, grabNormal, true);
            else if (mode == Mode.None && Input.mousePresent && Input.touchCount == 0 && !ViewerUi.PointerOverUi)
            {
                if (onSheet) instruments.ShowHand(sheetHit.point, sheetHit.normal, false);
                else if (picked) instruments.ShowHand(hit, normal, false);
            }
        }

        private void Begin(Camera cam, Ray ray, bool picked, Vector3 hit, Vector3 normal, bool onSheet, TissueSheets.SheetHit sheetHit)
        {
            Vector3 at = onSheet ? sheetHit.point : hit;
            grabNormal = onSheet ? sheetHit.normal : normal;
            dragTarget = at;
            dragPlane = new Plane(-cam.transform.forward, at);               // the finger moves the tissue in this plane

            // Lifted or loose tissue: take hold of it again. Skin at a cut's edge: take it in hand.
            if ((onSheet && sheets.TryGrabLoose(ray, sheetHit.distance + 1e-4f)) || (picked && !onSheet && sheets.TryPinchSkin(hit, normal)))
            {
                mode = Mode.Sheet;
                return;
            }
            if (!picked || onSheet || lab.SkinMeshOn) return;              // a mesh skin does not stretch
            grabId = warp.BeginGrab(Uvw(lab.Body, hit), grabRadiusMm);
            if (grabId >= 0) mode = Mode.Stretch;
        }

        private void Drag(PhotoBody body, Camera cam)
        {
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            if (!dragPlane.Raycast(ray, out float t)) return;
            dragTarget = ray.GetPoint(t);
            if (mode == Mode.Stretch) warp.UpdateGrab(grabId, Uvw(body, dragTarget));
            else sheets.MoveHand(dragTarget);
        }

        private void Release()
        {
            if (mode == Mode.Stretch && grabId >= 0) warp.EndGrab(grabId, keep: false);   // living skin springs back
            if (mode == Mode.Sheet) sheets.Release();                                    // what was lifted keeps falling
            mode = Mode.None;
            grabId = -1;
        }

        private static Vector3 Uvw(PhotoBody body, Vector3 world) => VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(world));
    }
}
