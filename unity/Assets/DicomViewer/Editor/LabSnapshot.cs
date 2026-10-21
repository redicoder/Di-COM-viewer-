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
        body.Build(meta, data, lids);
        Material m = body.Material;

        // Modelled eyes and lids, as AnatomyLab sets them up.
        var eyes = new GameObject[2];
        Shader eyeShader = Shader.Find("DicomViewer/SimpleEye");
        for (int i = 0; i < 2 && meta.eyes != null && i < meta.eyes.Length; i++)
        {
            BodyEye e = meta.eyes[i];
            m.SetVector(i == 0 ? "_Eye0" : "_Eye1", new Vector4(e.centre_m[0], e.lid_line_y_m, e.centre_m[2], e.radius_m));
            m.SetVector(i == 0 ? "_EyeBall0" : "_EyeBall1", new Vector4(e.centre_m[0], e.centre_m[1], e.centre_m[2], e.radius_m + 0.0005f));
            eyes[i] = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            Object.DestroyImmediate(eyes[i].GetComponent<Collider>());
            eyes[i].transform.SetParent(bodyGo.transform, false);
            eyes[i].transform.localPosition = new Vector3(e.centre_m[0], e.centre_m[1], e.skin_front_z_m + 0.0025f + 0.012f);
            eyes[i].transform.localScale = Vector3.one * 0.024f;
            eyes[i].GetComponent<MeshRenderer>().sharedMaterial = new Material(eyeShader);
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
            mask.BeginStroke("scalpel");
            bool havePrev = false;
            Vector3 prevWorld = default, prevN = default;
            for (float x = -0.03f; x <= 0.0351f; x += 0.0015f)
            {
                var ray = new Ray(bodyGo.transform.TransformPoint(new Vector3(x, 0.045f, -0.2f)), Vector3.forward);
                if (!body.Raycast(ray, mask.IsRemovedLocal, out Vector3 hit, out Vector3 n)) continue;
                if (havePrev)
                {
                    Vector3 nn = (n + prevN).normalized;
                    Vector3 a = body.Space.WorldToMm(body.Volume, prevWorld), b = body.Space.WorldToMm(body.Volume, hit);
                    Vector3 inward = -body.Space.WorldDirToMm(body.Volume, nn).normalized;
                    foreach (var c in new[] { new Vector2(-0.6f, 2.6f), new Vector2(2f, 1.7f), new Vector2(4f, 1f), new Vector2(5.4f, 0.6f) })
                        mask.ExtendStroke(new MaskCapsule(a + inward * c.x, b + inward * c.x, c.y));
                    float perMm = body.Space.WorldPerMm(body.Volume);
                    Color32 col = body.ColourAt(body.Volume.InverseTransformPoint((prevWorld + hit) * 0.5f - nn * (3f * perMm)));
                    blood.AddWound(prevWorld, hit, nn, Mathf.Clamp01((col.r - 0.5f * (col.g + col.b)) / 255f * 3f));
                }
                prevWorld = hit;
                prevN = n;
                havePrev = true;
            }
            mask.EndStroke();
            View(15f, 12f, dist * 0.6f);
            Shot("lab_cut.png");
            blood.Advance(6f);
            Shot("lab_blood.png");
            View(0f, 4f, dist * 0.45f);
            Shot("lab_blood_close.png");
            m.SetFloat("_MaskEnabled", 0f);
        }

        View(90f, 5f, dist);
        Shot("lab_side.png");
        Debug.Log($"LabSnapshot: done -> {outDir}");
    }
}
