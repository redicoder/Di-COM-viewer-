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
        cam.backgroundColor = new Color(0.05f, 0.045f, 0.04f);
        var light = new GameObject("Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.25f;
        light.color = new Color(1f, 0.96f, 0.9f);
        light.transform.rotation = Quaternion.Euler(35f, -30f, 0f);

        var bodyGo = new GameObject("Body");
        var body = bodyGo.AddComponent<PhotoBody>();
        string dir = body.Folder;
        var meta = JsonUtility.FromJson<BodyMeta>(File.ReadAllText(Path.Combine(dir, "body.json")));
        byte[] data = File.ReadAllBytes(Path.Combine(dir, "body.raw"));
        string lidPath = meta.lids != null ? Path.Combine(dir, meta.lids) : null;
        byte[] lids = lidPath != null && File.Exists(lidPath) ? File.ReadAllBytes(lidPath) : null;
        string depthPath = meta.skin_depth != null ? Path.Combine(dir, meta.skin_depth) : null;
        ushort[] depth = depthPath != null && File.Exists(depthPath)
            ? PhotoBody.SkinDepthHalf(File.ReadAllBytes(depthPath), meta.skin_depth_unit_mm) : null;
        body.Build(meta, data, lids, null, default, depth);
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

        float dist = body.SizeM.y * 0.5f / 0.42f / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
        void View(float yawDeg, float pitchDeg, float distance)
        {
            Quaternion q = Quaternion.Euler(pitchDeg, yawDeg, 0f);
            camGo.transform.position = q * new Vector3(0, 0, -distance);
            camGo.transform.rotation = q;
        }
        void Shot(string name)
        {
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
        m.SetFloat("_Open", 0f);

        // A scalpel stroke across the forehead, the way LabScalpel builds it, then 6 s of bleeding.
        var mask = bodyGo.AddComponent<MaskVolume>();
        mask.Attach(body.Space, () => body.Material);
        if (mask.Ready)
        {
            m.SetTexture("_MaskTex", mask.MaskTexture);              // MaskVolume binds in LateUpdate, which edit mode skips
            m.SetFloat("_MaskEnabled", 1f);
            var blood = bodyGo.AddComponent<BloodSim>();
            blood.Attach(body, mask);
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
            View(0f, 4f, dist * 0.32f);
            Shot("lab_scalpel_close.png");
            tools.Apply();                                             // nothing asked for: the scalpel goes
            warp.RestoreState();
            warp.Gape(cutUvw, LabScalpel.GapeFor(cutMm), 8f, 5f);
            View(15f, 12f, dist * 0.6f);
            Shot("lab_cut.png");
            View(0f, 4f, dist * 0.32f);
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

            // The Pull tool: fold the skin below the cut back as a flap, then stretch a cheek.
            var flaps = bodyGo.AddComponent<TissueFlaps>();
            flaps.Bind(m, body.Space.SizeMm);
            int flap = flaps.Begin(cutUvw, Vector3.down, Vector3.back, 14f, 5f);
            flaps.SetFold(flap, 0.4f);
            flaps.PushNow();
            View(12f, 18f, dist * 0.5f);
            Shot("lab_flap_half.png");
            flaps.SetFold(flap, 0.85f);
            flaps.PushNow();
            Shot("lab_flap.png");
            Vector3 grabUvw = cutUvw[cutUvw.Count / 2] + new Vector3(0f, -6f / body.Space.SizeMm.y, 0f);
            Vector3 nUvw = new Vector3(0f, 0f, -3f / body.Space.SizeMm.z);
            Vector3 heldAt = body.Volume.TransformPoint(VolumeSpace.UvwToLocal(flaps.DisplayUvw(flap, grabUvw)));
            Vector3 heldUp = body.Volume.TransformPoint(VolumeSpace.UvwToLocal(flaps.DisplayUvw(flap, grabUvw + nUvw))) - heldAt;
            tools.ShowHand(heldAt, heldUp.normalized, true);
            tools.Apply();
            View(12f, 10f, dist * 0.6f);
            Shot("lab_hand.png");
            View(60f, 5f, dist * 0.6f);
            Shot("lab_hand_side.png");
            tools.Apply();
            View(12f, 18f, dist * 0.5f);
            View(70f, 0f, dist * 0.5f);
            Shot("lab_flap_side.png");
            View(0f, -10f, dist * 0.45f);
            Shot("lab_flap_low.png");
            flaps.Clear();
            flaps.PushNow();
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
}
