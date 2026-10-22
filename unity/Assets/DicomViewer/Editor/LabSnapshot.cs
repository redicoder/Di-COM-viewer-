using System.IO;
using DicomViewer;
using DicomViewer.AnatomyLab;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Renders the Anatomy Lab's photographed body to PNG files without entering Play mode: front, eyes open with the
/// modelled eyes, a scalpel cut across the forehead and its bleeding, and from the side. For checking the shader after changes:
///   Unity.exe -batchmode -projectPath unity -executeMethod LabSnapshot.Run -logFile - -quit
/// (no -nographics: it needs the GPU). Pictures go to <repo>/build/snapshots/.
/// </summary>
public static class LabSnapshot
{
    [MenuItem("DICOM Viewer/Anatomy Lab Snapshots")]
    public static void Run()
    {
        DicomViewer.AnatomyLab.EditorTools.BloodFluidDemo.Install();           // liquid blood on the URP renderer
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Camera");
        camGo.tag = "MainCamera";                                      // the instruments face Camera.main
        var cam = camGo.AddComponent<Camera>();
        cam.fieldOfView = 30f;
        cam.nearClipPlane = 0.01f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = AnatomyLab.RoomBackground;
        var light = new GameObject("Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.9f;
        light.color = new Color(1f, 0.96f, 0.9f);
        light.transform.rotation = Quaternion.Euler(35f, -30f, 0f);
        AnatomyLab.LabShadows(light);
        AnatomyLab.AddPostProcessing(camGo.transform, cam);

        var bodyGo = new GameObject("Body");
        var body = bodyGo.AddComponent<PhotoBody>();
        BodyMeta meta = LoadBody(body);
        Material m = body.Material;

        // Living eyes and lids, as AnatomyLab sets them up.
        var eyes = new GameObject[2];
        for (int i = 0; i < 2 && meta.eyes != null && i < meta.eyes.Length; i++)
        {
            BodyEye e = meta.eyes[i];
            m.SetVector(i == 0 ? "_Eye0" : "_Eye1", new Vector4(e.centre_m[0], e.lid_line_y_m, e.centre_m[2], e.radius_m));
            m.SetVector(i == 0 ? "_EyeBall0" : "_EyeBall1", new Vector4(e.centre_m[0], e.centre_m[1], e.centre_m[2], e.radius_m + 0.0005f));
            eyes[i] = LivingEye.Create(bodyGo.transform, AnatomyLab.LivingEyeCentre(e), AnatomyLab.LivingEyeRadius, Vector3.back).gameObject;
        }

        float dist = body.SizeM.y * 0.5f / 0.80f / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);   // the head at 80 % of the height
        void View(float yawDeg, float pitchDeg, float distance, Vector3 focus = default)
        {
            Quaternion q = Quaternion.Euler(pitchDeg, yawDeg, 0f);
            camGo.transform.position = focus + q * new Vector3(0, 0, -distance);
            camGo.transform.rotation = q;
        }
        Vector3 eyeFocus = meta.eyes != null && meta.eyes.Length > 0
            ? new Vector3(meta.eyes[0].centre_m[0], meta.eyes[0].centre_m[1], meta.eyes[0].skin_front_z_m) : new Vector3(-0.033f, 0.008f, -0.084f);
        Vector3 noseFocus = new Vector3(0f, -0.02f, -0.085f), mouthFocus = new Vector3(0f, -0.05f, -0.07f);
        void Shot(string name)
        {
            foreach (var sm in bodyGo.GetComponents<SkinMesh>()) sm.Sync();
            var rt = new RenderTexture(1200, 1200, 24, RenderTextureFormat.ARGB32);
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, name), tex.EncodeToPNG());
            RenderTexture.active = null;
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(tex);
            Debug.Log($"LabSnapshot: wrote {name}");
        }

        m.SetFloat("_StepScale", 0.5f);
        m.SetFloat("_Open", 0f);
        m.SetFloat("_ModelEyes", 0f);
        foreach (var e in eyes) if (e != null) e.SetActive(false);
        View(20f, 5f, dist);
        Shot("lab_front.png");

        m.SetFloat("_Open", 1f);
        m.SetFloat("_ModelEyes", 1f);
        foreach (var e in eyes) if (e != null) e.SetActive(true);
        View(0f, 3f, dist * 0.55f);
        Shot("lab_eyes_living.png");
        View(8f, 2f, dist * 0.22f);
        Shot("lab_eye_close.png");
        View(0f, 3f, dist * 0.55f);
        m.SetFloat("_ModelEyes", 0f);
        foreach (var e in eyes) if (e != null) e.SetActive(false);
        Shot("lab_eyes_real.png");
        // Close-ups of the features (eyelids half open and open with the modelled eyes, nose from below, mouth).
        m.SetFloat("_ModelEyes", 1f);
        foreach (var e in eyes) if (e != null) e.SetActive(true);
        m.SetFloat("_Open", 0.5f);
        View(-15f, 0f, dist * 0.12f, eyeFocus);
        Shot("lab_lids_half.png");
        m.SetFloat("_Open", 1f);
        Shot("lab_lids_open.png");
        View(25f, -10f, dist * 0.12f, eyeFocus);
        Shot("lab_lids_open_side.png");
        m.SetFloat("_Open", 0f);
        m.SetFloat("_ModelEyes", 0f);
        foreach (var e in eyes) if (e != null) e.SetActive(false);
        View(0f, -35f, dist * 0.16f, noseFocus);
        Shot("lab_nose.png");
        View(0f, 5f, dist * 0.16f, mouthFocus);
        Shot("lab_mouth.png");
        View(50f, 0f, dist * 0.16f, mouthFocus);
        Shot("lab_mouth_side.png");

        // A scalpel stroke across the forehead, the way LabScalpel builds it, then 6 s of bleeding.
        var mask = bodyGo.AddComponent<MaskVolume>();
        mask.Attach(body.Space, () => body.Material);
        if (mask.Ready)
        {
            m.SetTexture("_MaskTex", mask.MaskTexture);              // MaskVolume binds in LateUpdate, which edit mode skips
            m.SetFloat("_MaskEnabled", 1f);
            var blood = bodyGo.AddComponent<BloodSim>();
            blood.Attach(body, mask);
            var room = bodyGo.AddComponent<LabRoom>();
            var warp = bodyGo.AddComponent<TissueWarp>();
            warp.fieldResolution = 192;
            warp.Setup(body.Space.Dims, body.Space.SpacingMm, body.SkinDepthTexture);
            warp.Bind(m);
            var tools = bodyGo.AddComponent<LabInstruments>();
            tools.Build(Shader.Find("DicomViewer/LabInstrument"));

            // A scalpel stroke across the forehead as LabScalpel makes it: the V track, bleeding, the edges drawn apart.
            mask.BeginStroke("scalpel");
            var cutUvw = new System.Collections.Generic.List<Vector3>();
            bool havePrev = false;
            Vector3 prevWorld = default, prevN = default;
            float cutMm = 0f;
            for (float x = -0.03f; x <= 0.0351f; x += 0.0015f)
            {
                var ray = new Ray(bodyGo.transform.TransformPoint(new Vector3(x, 0.045f, -0.2f)), Vector3.forward);
                if (!body.Raycast(ray, mask.IsRemovedLocal, out Vector3 hit, out Vector3 n)) continue;
                if (havePrev)
                {
                    float cutDepth = 5f * Mathf.Lerp(0.4f, 1f, Mathf.Clamp01(cutMm / 3f));
                    LabScalpel.Incise(body, mask, blood, prevWorld, hit, (n + prevN).normalized, 1.8f, cutDepth);
                    cutMm += Vector3.Distance(prevWorld, hit) / body.Space.WorldPerMm(body.Volume);
                }
                prevWorld = hit;
                prevN = n;
                havePrev = true;
                cutUvw.Add(VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(hit)));
            }
            mask.EndStroke();

            // Half way through the stroke, the blade in the skin and the wound opening behind it.
            int halfway = cutUvw.Count / 2;
            warp.SaveState();
            warp.Gape(cutUvw.GetRange(0, halfway + 1), LabScalpel.GapeFor(cutMm * 0.5f), 8f, 5f);
            Vector3 bladeAt = body.Volume.TransformPoint(VolumeSpace.UvwToLocal(cutUvw[halfway]));
            tools.ShowScalpel(bladeAt, Vector3.back, Vector3.right, 4f);
            tools.Apply();
            View(15f, 12f, dist * 0.6f);
            Shot("lab_scalpel.png");
            View(0f, 4f, dist * 0.2f, new Vector3(0f, 0.04f, -0.08f));
            Shot("lab_scalpel_close.png");
            tools.Apply();                                             // nothing asked for: the scalpel goes
            warp.RestoreState();
            warp.Gape(cutUvw, LabScalpel.GapeFor(cutMm), 8f, 5f);
            View(15f, 12f, dist * 0.6f);
            Shot("lab_cut.png");
            View(0f, 4f, dist * 0.2f, new Vector3(0f, 0.04f, -0.08f));
            Shot("lab_cut_close.png");
            blood.Advance(6f);
            View(15f, 12f, dist * 0.6f);
            Shot("lab_blood.png");
            View(0f, 4f, dist * 0.45f);
            Shot("lab_blood_close.png");
            blood.showBlood = false;                                   // the Blood: off button
            m.SetFloat("_ShowStain", 0f);
            blood.Advance(0.1f);
            Shot("lab_blood_off.png");
            blood.showBlood = true;
            m.SetFloat("_ShowStain", 1f);

            // The Pull tool on a real body: two cuts down from the first make a flap; the hand peels it down and lets go,
            // it hangs; its base is cut while the hand holds it again, it comes away and falls onto the tray.
            var sheets = bodyGo.AddComponent<TissueSheets>();
            sheets.Attach(body, mask);
            room.PushLight();
            var skin = bodyGo.AddComponent<SkinMesh>();
            Debug.Log($"LabSnapshot: skin mesh {(skin.Attach(body) ? "on" : "absent")}");
            void CutLine(Vector2 from, Vector2 to)
            {
                mask.BeginStroke("scalpel");
                bool have = false;
                Vector3 pw = default, pn = default;
                for (int k = 0; k <= 24; k++)
                {
                    Vector2 q = Vector2.Lerp(from, to, k / 24f);
                    var ray = new Ray(bodyGo.transform.TransformPoint(new Vector3(q.x, q.y, -0.2f)), Vector3.forward);
                    if (!body.Raycast(ray, mask.IsRemovedLocal, out Vector3 hit, out Vector3 n)) continue;
                    if (have) LabScalpel.Incise(body, mask, blood, pw, hit, (n + pn).normalized, 1.8f, 5f, sheets);
                    pw = hit;
                    pn = n;
                    have = true;
                }
                mask.EndStroke();
            }
            CutLine(new Vector2(-0.02f, 0.045f), new Vector2(-0.02f, 0.022f));
            CutLine(new Vector2(0.02f, 0.045f), new Vector2(0.02f, 0.022f));
            void Run(float seconds, System.Func<float, Vector3> hand = null)
            {
                int frames = Mathf.RoundToInt(seconds * 60f);
                var clock = System.Diagnostics.Stopwatch.StartNew();
                for (int f = 1; f <= frames; f++)
                {
                    if (hand != null) sheets.MoveHand(hand(f / (float)frames));
                    sheets.Simulate(1f / 60f);
                }
                Debug.Log($"LabSnapshot: skin physics {clock.Elapsed.TotalMilliseconds / frames:F2} ms per frame over {frames} frames; " +
                          $"rebuild {TissueSheet.Prof[0].Elapsed.TotalMilliseconds / frames:F2} job {TissueSheet.Prof[1].Elapsed.TotalMilliseconds / frames:F2} " +
                          $"after {TissueSheet.Prof[2].Elapsed.TotalMilliseconds / frames:F2} mesh {TissueSheet.Prof[3].Elapsed.TotalMilliseconds / frames:F2}; {sheets.Sheets[0].ProfCounts}");
                foreach (var w in TissueSheet.Prof) w.Reset();
            }
            void ShowHeld()
            {
                if (sheets.HeldPoint(out Vector3 at, out Vector3 up)) tools.ShowHand(at, up, true);
                tools.Apply();
            }
            var pinchRay = new Ray(bodyGo.transform.TransformPoint(new Vector3(0f, 0.0425f, -0.2f)), Vector3.forward);
            var made = System.Diagnostics.Stopwatch.StartNew();
            if (body.Raycast(pinchRay, mask.IsRemovedLocal, out Vector3 pinch, out Vector3 pinchN) && sheets.TryPinchSkin(pinch, pinchN))
            {
                Debug.Log($"LabSnapshot: taking hold of the skin (a new sheet) took {made.Elapsed.TotalMilliseconds:F0} ms");
                Vector3 start = pinch;
                Run(1.2f, u => start + (Vector3.back * 0.03f + Vector3.down * 0.02f) * Mathf.SmoothStep(0f, 1f, u));
                ShowHeld();
                View(12f, 10f, dist * 0.6f);
                Shot("lab_skin_flap.png");
                View(65f, 5f, dist * 0.6f);
                Shot("lab_skin_flap_side.png");
                TissueSheet sheet = sheets.Sheets[0];
                int heldNode = sheet.HeldNode;
                sheets.Release();
                tools.Apply();
                Run(1.5f);
                Pieces(sheet, "hanging");
                View(30f, 8f, dist * 0.6f);
                Shot("lab_skin_flap_hanging.png");

                // Hold the flap's edge again, cut its base, carry it away and let it fall.
                sheets.GrabNode(0, heldNode);
                CutLine(new Vector2(-0.024f, 0.0225f), new Vector2(0.024f, 0.0225f));
                Vector3 from = sheets.ToWorld(sheet.X[2 * heldNode]);
                Run(1.2f, u => from + (Vector3.back * 0.04f + Vector3.right * 0.02f) * Mathf.SmoothStep(0f, 1f, u));
                ShowHeld();
                Pieces(sheet, "in the hand");
                View(25f, 8f, dist * 0.7f);
                Shot("lab_skin_in_hand.png");
                sheets.Release();
                tools.Apply();
                Run(2.5f);
                View(25f, 22f, dist * 1.1f);
                Shot("lab_skin_fallen.png");
                Pieces(sheet, "on the tray");
                Debug.Log($"LabSnapshot: sheet nodes peeled {Count(sheet, TissueSheet.Node.Peeled)}, gone {Count(sheet, TissueSheet.Node.Gone)}, anchored {sheet.IsAnchored(heldNode)}");
            }
            else Debug.LogError("LabSnapshot: could not take hold of the skin beside the cut");
            sheets.Clear();
            warp.ResetAll();
            var cheekRay = new Ray(bodyGo.transform.TransformPoint(new Vector3(0.045f, -0.02f, -0.2f)), Vector3.forward);
            if (body.Raycast(cheekRay, mask.IsRemovedLocal, out Vector3 cheek, out Vector3 cheekN))
            {
                Vector3 from = VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(cheek));
                Vector3 to = VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(cheek + cheekN * 0.007f + Vector3.down * 0.004f));
                int id = warp.BeginGrab(from, 10f);
                warp.UpdateGrab(id, to);
                warp.Bind(m);                                          // pushes the handle (Update does it in Play mode)
                tools.ShowHand(cheek + cheekN * 0.007f + Vector3.down * 0.004f, cheekN, true);
                tools.Apply();
            }
            View(35f, 5f, dist * 0.5f);
            Shot("lab_pull.png");
            tools.Apply();
            warp.ResetAll();
            warp.Bind(m);
            m.SetFloat("_MaskEnabled", 0f);
        }

        View(90f, 5f, dist);
        Shot("lab_side.png");
        Debug.Log($"LabSnapshot: done -> {outDir}");
    }

    /// <summary>Loads the body in body.Folder outside Play mode, the way PhotoBody.LoadAsync does.</summary>
    private static BodyMeta LoadBody(PhotoBody body)
    {
        string dir = body.Folder;
        var meta = JsonUtility.FromJson<BodyMeta>(File.ReadAllText(Path.Combine(dir, "body.json")));
        byte[] data = File.ReadAllBytes(Path.Combine(dir, "body.raw"));
        string lidPath = meta.lids != null ? Path.Combine(dir, meta.lids) : null;
        byte[] lids = lidPath != null && File.Exists(lidPath) ? File.ReadAllBytes(lidPath) : null;
        string depthPath = meta.skin_depth != null ? Path.Combine(dir, meta.skin_depth) : null;
        ushort[] depth = depthPath != null && File.Exists(depthPath)
            ? PhotoBody.SkinDepthHalf(File.ReadAllBytes(depthPath), meta.skin_depth_unit_mm) : null;
        body.Build(meta, data, lids, null, default, depth);
        var labels = BodyLabels.Read(dir, meta);
        body.AttachLabels(BodyLabels.Build(new Vector3Int(meta.dims[0], meta.dims[1], meta.dims[2]), labels.index, labels.table));
        return meta;
    }

    /// <summary>For checking the ray-marcher: the whole body drawn without empty-space skipping.</summary>
    public static bool DebugNoBricks;
    public static void RunWholeBodyNoBricks()
    {
        DebugNoBricks = true;
        RunWholeBody();
    }

    /// <summary>The whole body on the table: lying as the lab places him, from above and from the side, with a cut.</summary>
    [MenuItem("DICOM Viewer/Anatomy Lab Snapshots (whole body)")]
    public static void RunWholeBody()
    {
        DicomViewer.AnatomyLab.EditorTools.BloodFluidDemo.Install();
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var camGo = new GameObject("Camera");
        camGo.tag = "MainCamera";
        var cam = camGo.AddComponent<Camera>();
        cam.fieldOfView = 30f;
        cam.nearClipPlane = 0.01f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = AnatomyLab.RoomBackground;
        var light = new GameObject("Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.9f;
        light.color = new Color(1f, 0.96f, 0.9f);
        light.transform.rotation = Quaternion.Euler(50f, -25f, 0f);
        AnatomyLab.LabShadows(light);
        AnatomyLab.AddPostProcessing(camGo.transform, cam);

        var bodyGo = new GameObject("Body");
        var body = bodyGo.AddComponent<PhotoBody>();
        body.folder = AnatomyLab.BodyFolder(AnatomyLab.WholeBody);
        BodyMeta meta2 = LoadBody(body);
        Material m = body.Material;
        m.SetFloat("_StepScale", 0.5f);
        Texture occupancy = m.GetTexture("_OccTex");
        if (DebugNoBricks)
        {
            var full = new Texture3D(1, 1, 1, UnityEngine.Experimental.Rendering.GraphicsFormat.R8_UNorm, UnityEngine.Experimental.Rendering.TextureCreationFlags.None);
            full.SetPixelData(new byte[] { 255 }, 0);
            full.Apply(false, true);
            m.SetTexture("_OccTex", full);
        }
        // Lying before a camera at the origin looking down +z: the body at the origin, so the views orbit him.
        camGo.transform.position = new Vector3(0f, 0f, -1f);
        bodyGo.transform.rotation = AnatomyLab.LyingRotation(camGo.transform);
        var mask = bodyGo.AddComponent<MaskVolume>();
        mask.Attach(body.Space, () => body.Material);
        m.SetTexture("_MaskTex", mask.MaskTexture);
        m.SetFloat("_MaskEnabled", 1f);
        var blood = bodyGo.AddComponent<BloodSim>();
        blood.Attach(body, mask);
        blood.downLocalOverride = Vector3.forward;
        var room = bodyGo.AddComponent<LabRoom>();
        var sheets = bodyGo.AddComponent<TissueSheets>();
        sheets.Attach(body, mask);
        sheets.SetTable(Vector3.back, -(body.Space.SizeMm.z + 2f));
        room.PushLight();
        var skin = bodyGo.AddComponent<SkinMesh>();
        Debug.Log($"LabSnapshot: skin mesh {(skin.Attach(body) ? "on" : "absent")}");
        var regions = bodyGo.AddComponent<LabRegion>();
        regions.Attach(body, LoadBody);
        Debug.Log($"LabSnapshot: {regions.Count} region(s) at full detail");

        float aspect = 1600f / 900f;
        float dist = body.SizeM.y * 0.5f / (0.84f * aspect) / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);   // his length at 84 % of the width
        void View(float yawDeg, float pitchDeg, float distance, Vector3 focus = default)
        {
            Quaternion q = Quaternion.Euler(pitchDeg, yawDeg, 0f);
            camGo.transform.position = focus + q * new Vector3(0, 0, -distance);
            camGo.transform.rotation = q;
        }
        void Shot(string name)
        {
            skin.Sync();
            regions.Sync();
            var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, name), tex.EncodeToPNG());
            RenderTexture.active = null;
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(tex);
            Debug.Log($"LabSnapshot: wrote {name}");
        }
        View(0f, 0f, dist);
        Shot("body_above.png");
        {
            // How big he is on the frame: the lab places him with the same formula.
            cam.aspect = aspect;
            Vector3 head = cam.WorldToViewportPoint(bodyGo.transform.TransformPoint(new Vector3(0f, body.SizeM.y * 0.5f, 0f)));
            Vector3 feet = cam.WorldToViewportPoint(bodyGo.transform.TransformPoint(new Vector3(0f, -body.SizeM.y * 0.5f, 0f)));
            Debug.Log($"LabSnapshot: camera {dist:F2} m away, aspect {cam.aspect:F2}, fov {cam.fieldOfView}; head at viewport x {head.x:F2}, feet at {feet.x:F2} (z {head.z:F2})");
        }
        if (DebugNoBricks)
        {
            Vector3 chestFocus = bodyGo.transform.TransformPoint(new Vector3(0f, 0.32f, -0.06f));
            View(-20f, 25f, dist * 0.22f, chestFocus);
            Shot("dbg_nobricks.png");
            m.SetFloat("_MaskEnabled", 0f);
            Shot("dbg_nobricks_nomask.png");
            m.SetTexture("_OccTex", occupancy);
            Shot("dbg_bricks_nomask.png");
            m.SetFloat("_StepScale", 0.25f);
            Shot("dbg_bricks_nomask_fine.png");
            m.SetFloat("_StepScale", 0.5f);
            m.SetFloat("_MaskEnabled", 1f);
            Debug.Log("LabSnapshot: whole body done -> debug");
            return;
        }
        View(0f, 35f, dist);
        Shot("body_oblique.png");
        // His face on the table, eyes closed and open (the eyes carried over from the head export).
        if (meta2.eyes != null && meta2.eyes.Length >= 2)
        {
            var eyes2 = new GameObject[2];
            for (int i = 0; i < 2; i++)
            {
                BodyEye e = meta2.eyes[i];
                m.SetVector(i == 0 ? "_Eye0" : "_Eye1", new Vector4(e.centre_m[0], e.lid_line_y_m, e.centre_m[2], e.radius_m));
                m.SetVector(i == 0 ? "_EyeBall0" : "_EyeBall1", new Vector4(e.centre_m[0], e.centre_m[1], e.centre_m[2], e.radius_m + 0.0005f));
                eyes2[i] = LivingEye.Create(bodyGo.transform, AnatomyLab.LivingEyeCentre(e), AnatomyLab.LivingEyeRadius, Vector3.back).gameObject;
                eyes2[i].SetActive(false);
            }
            Vector3 face = bodyGo.transform.TransformPoint(new Vector3(0f, body.SizeM.y * 0.5f - 0.10f, -0.08f));
            View(-25f, 20f, dist * 0.12f, face);
            Shot("body_face.png");
            m.SetFloat("_Open", 1f);
            m.SetFloat("_ModelEyes", 1f);
            foreach (var e in eyes2) e.SetActive(true);
            Shot("body_face_eyes.png");
            m.SetFloat("_Open", 0f);
            m.SetFloat("_ModelEyes", 0f);
            foreach (var e in eyes2) e.SetActive(false);
        }
        // The chest from closer; the body's +y (head) runs to the viewer's left.
        Vector3 chest = bodyGo.transform.TransformPoint(new Vector3(0f, 0.32f, -0.06f));
        View(-20f, 25f, dist * 0.3f, chest);
        Shot("body_chest.png");

        // A scalpel stroke down the chest, as the tool makes it, then bleeding.
        mask.BeginStroke("scalpel");
        bool have = false;
        Vector3 pw = default, pn = default;
        for (float y = 0.40f; y >= 0.20f; y -= 0.004f)
        {
            Vector3 start = bodyGo.transform.TransformPoint(new Vector3(0.01f, y, -0.30f));
            Vector3 dir = bodyGo.transform.TransformDirection(Vector3.forward);
            if (!body.Raycast(new Ray(start, dir), mask.IsRemovedLocal, out Vector3 hit, out Vector3 n)) continue;
            if (have) LabScalpel.Incise(body, mask, blood, pw, hit, (n + pn).normalized, 1.8f, 5f, sheets);
            pw = hit; pn = n; have = true;
        }
        mask.EndStroke();
        blood.Advance(5f);
        Shot("body_chest_cut.png");
        if (body.Labels != null)
        {
            // What the cut shows at its middle, named as the lab names what is under the cursor, and lifted.
            Vector3 start = bodyGo.transform.TransformPoint(new Vector3(0.01f, 0.30f, -0.30f));
            Vector3 dir = bodyGo.transform.TransformDirection(Vector3.forward);
            if (body.Raycast(new Ray(start, dir), mask.IsRemovedLocal, out Vector3 hit, out _))
            {
                Vector3 uvw = VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(hit));
                int index = body.Labels.IndexAt(uvw);
                Debug.Log($"LabSnapshot: under the chest cut: {body.Labels.Name(index) ?? "nothing labelled"} (index {index}); "
                          + $"skin there: {body.Labels.NameAt(uvw + new Vector3(0f, 0f, -0.012f / body.SizeM.z)) ?? "none"}");
                m.SetFloat("_HighlightIndex", index);
                Shot("body_chest_label.png");
                m.SetFloat("_HighlightIndex", 0f);
            }
        }
        Debug.Log($"LabSnapshot: whole body done -> {outDir}");
    }

    private static void Pieces(TissueSheet sheet, string when)
    {
        foreach (var p in sheet.Pieces())
            if (p.nodes > 2) Debug.Log($"LabSnapshot: {when}: piece of {p.nodes} nodes, anchored {p.anchored}, centre {p.centre}, fastest {p.maxSpeed:F0} mm/s, size {p.size} (at rest {p.restSize})");
    }

    private static int Count(TissueSheet sheet, TissueSheet.Node state)
    {
        int c = 0;
        foreach (TissueSheet.Node s in sheet.State) if (s == state) c++;
        return c;
    }
}
