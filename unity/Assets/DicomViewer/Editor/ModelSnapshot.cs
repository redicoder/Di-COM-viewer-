using System.IO;
using DicomViewer.AnatomyLab;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// The modelled body (Assets/Models/body.glb) on the table: builds the scene, saves it as Assets/Scenes/ModelLab.unity
/// (open it, press Play, walk round him) and renders it to PNG files without Play mode:
///   Unity.exe -batchmode -projectPath unity -executeMethod ModelSnapshot.Run -logFile - -quit
/// Pictures go to <repo>/build/snapshots/model_*.png.
/// </summary>
public static class ModelSnapshot
{
    public const string BodyAsset = "Assets/Models/body.glb";
    public const string ScenePath = "Assets/Scenes/ModelLab.unity";

    private static readonly int Roughness = Shader.PropertyToID("roughnessFactor");
    private static readonly int Metallic = Shader.PropertyToID("metallicFactor");

    /// <summary>Camera, key light, post-processing, the body laid on the table and the room; his world bounds.</summary>
    private static (Camera cam, GameObject body, Bounds bounds) Build()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        ShaderUtil.allowAsyncCompilation = false;
        var camGo = new GameObject("Camera");
        camGo.tag = "MainCamera";
        var cam = camGo.AddComponent<Camera>();
        cam.fieldOfView = 30f;
        cam.nearClipPlane = 0.01f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = AnatomyLab.RoomBackground;
        var light = new GameObject("Light").AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 2.0f;
        light.color = new Color(1f, 0.985f, 0.96f);
        light.transform.rotation = Quaternion.Euler(52f, -25f, 0f);
        AnatomyLab.LabShadows(light);
        RenderSettings.sun = light;
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.30f, 0.31f, 0.33f);
        AnatomyLab.AddPostProcessing(camGo.transform, cam);

        var asset = AssetDatabase.LoadAssetAtPath<GameObject>(BodyAsset);
        if (asset == null) { Debug.LogError($"ModelSnapshot: {BodyAsset} did not import as a model"); return (cam, null, default); }
        GameObject body = (GameObject)PrefabUtility.InstantiatePrefab(asset);
        body.name = "Body";
        foreach (Renderer r in body.GetComponentsInChildren<Renderer>())
        {
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            Material rm = r.sharedMaterial;
            if (rm == null) continue;
            Debug.Log($"ModelSnapshot: renderer {r.name}, shader {rm.shader.name}, texture "
                      + $"{(rm.mainTexture != null ? rm.mainTexture.name + " " + rm.mainTexture.width + "x" + rm.mainTexture.height : "none")}, "
                      + $"roughness {(rm.HasFloat(Roughness) ? rm.GetFloat(Roughness).ToString("F2") : "-")}, metallic {(rm.HasFloat(Metallic) ? rm.GetFloat(Metallic).ToString("F2") : "-")}");
            // Skin: a little sheen, never metal (the generator leaves the material fully rough).
            var skin = new Material(rm) { name = "Body skin" };
            if (skin.HasFloat(Roughness)) skin.SetFloat(Roughness, 0.62f);
            if (skin.HasFloat(Metallic)) skin.SetFloat(Metallic, 0f);
            r.sharedMaterial = skin;
        }
        Bounds raw = ModelLab.WorldBounds(body);
        Bounds b = ModelLab.Lay(body, ModelLab.DefaultHeightM);
        Debug.Log($"ModelSnapshot: model size as imported {raw.size}, laid {b.size} centre {b.center}");
        ModelLab.Room(b.size.x);
        return (cam, body, b);
    }

    /// <summary>Builds the scene and saves it, with the camera walking round the table (ModelOrbit) in Play mode.</summary>
    [MenuItem("DICOM Viewer/Build Model Lab Scene")]
    public static void BuildScene()
    {
        var (cam, body, b) = Build();
        if (body == null) return;
        var orbit = cam.gameObject.AddComponent<ModelOrbit>();
        orbit.yaw = 0f;
        orbit.pitch = 35f;
        orbit.Frame(b, cam);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(Path.Combine(Application.dataPath, "..", ScenePath))));
        bool saved = EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), ScenePath);
        Debug.Log($"ModelSnapshot: scene {(saved ? "saved" : "NOT saved")} -> {ScenePath}");
    }

    [MenuItem("DICOM Viewer/Model Body Snapshots")]
    public static void Run()
    {
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        var (cam, body, b) = Build();
        if (body == null) return;
        GameObject camGo = cam.gameObject;

        float aspect = 1600f / 900f;
        float dist = b.size.x * 0.5f / (0.84f * aspect) / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
        void View(float yawDeg, float pitchDeg, float distance, Vector3 focus)
        {
            Quaternion q = Quaternion.Euler(pitchDeg, yawDeg, 0f);
            camGo.transform.position = focus + q * new Vector3(0, 0, -distance);
            camGo.transform.rotation = q;
        }
        void Shot(string name)
        {
            var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
            cam.targetTexture = rt;
            cam.Render();
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
            Debug.Log($"ModelSnapshot: wrote {name}");
        }
        Vector3 centre = new Vector3(0f, b.size.y * 0.5f, 0f);
        View(0f, 90f, dist, centre);
        Shot("model_above.png");
        View(0f, 35f, dist, centre);
        Shot("model_oblique.png");
        View(-90f, 10f, dist * 0.8f, centre);
        Shot("model_from_feet.png");
        Vector3 head = new Vector3(b.min.x + 0.12f, b.size.y * 0.6f, 0f);
        View(-30f, 30f, dist * 0.18f, head);
        Shot("model_face.png");
        Vector3 chest = new Vector3(b.min.x + 0.45f, b.size.y * 0.5f, 0f);
        View(-20f, 35f, dist * 0.4f, chest);
        Shot("model_chest.png");
        Debug.Log($"ModelSnapshot: done -> {outDir}");
        BuildScene();
    }
}
