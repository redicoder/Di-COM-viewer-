using System.IO;
using DicomViewer.AnatomyLab;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// The modelled body on the table. Two bodies: the **anatomy** (Assets/Models/anatomy.glb, from
/// backend/tools/build_model_meshes.py: every labelled structure as its own mesh, layers skin / muscles /
/// skeleton / organs that fit inside one another) and the **prototype** (body.glb, muscles.glb, skeleton.glb:
/// generated models, one layer drawn at a time). Builds the scene, saves it (Assets/Scenes/ModelLab.unity, or
/// ModelLabPrototype.unity; open it, press Play, walk round him, switch the layers) and renders PNG files:
///   Unity.exe -batchmode -projectPath unity -executeMethod ModelSnapshot.Run -logFile - -quit
/// Pictures go to <repo>/build/snapshots/anatomy_*.png (or model_*.png for the prototype, RunPrototype).
/// </summary>
public static class ModelSnapshot
{
    public const string ModelsFolder = "Assets/Models";
    public const string AnatomyAsset = ModelsFolder + "/anatomy.glb";
    public const string ScenePath = "Assets/Scenes/ModelLab.unity";
    public const string PrototypeScenePath = "Assets/Scenes/ModelLabPrototype.unity";

    private static readonly int BaseColorTexture = Shader.PropertyToID("baseColorTexture");

    // anatomy.json beside the model: what the builder knows and the importer does not hand over.
    [System.Serializable] private class Sides { public float[] right; public float[] left; }
    [System.Serializable] private class SideValues { public float right; public float left; }
    [System.Serializable] private class EyesInfo { public Sides centres; public SideValues radius; public float[] forward; public float[] up; public float upper_degrees; public float lower_degrees; }
    [System.Serializable] private class AnatomyInfo { public EyesInfo eyes; }

    // glTF's x runs the other way in the imported meshes.
    private static Vector3 MeshSpace(float[] a) => new Vector3(-a[0], a[1], a[2]);

    private static void ReadEyes(ModelBody body)
    {
        string path = Path.Combine(Application.dataPath, "Models", "anatomy.json");
        if (!File.Exists(path)) return;
        AnatomyInfo info = JsonUtility.FromJson<AnatomyInfo>(File.ReadAllText(path));
        if (info == null || info.eyes == null || info.eyes.centres == null || info.eyes.centres.right == null || info.eyes.centres.right.Length < 3) return;
        body.hasEyes = true;
        body.eyeRight = MeshSpace(info.eyes.centres.right);
        body.eyeLeft = MeshSpace(info.eyes.centres.left);
        body.eyeForward = MeshSpace(info.eyes.forward).normalized;
        body.eyeUp = MeshSpace(info.eyes.up).normalized;
        if (info.eyes.upper_degrees > 0f) body.lidUpperDegrees = info.eyes.upper_degrees;
        if (info.eyes.lower_degrees > 0f) body.lidLowerDegrees = info.eyes.lower_degrees;
        Debug.Log($"ModelSnapshot: eyes at {body.eyeRight} and {body.eyeLeft} (mesh space), forward {body.eyeForward}, up {body.eyeUp}");
    }

    private static Camera Stage()
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
        return cam;
    }

    //                                              scatters  gloss  relief mm  grain  occlusion  saturation
    private static readonly float[] SkinLook = { 1f, 0.10f, 0.35f, 0f, 0.55f, 1.08f };
    private static readonly float[] MuscleLook = { 0.35f, 0.70f, 1.6f, 0f, 0.9f, 1.12f };
    private static readonly float[] BoneLook = { 0.20f, 0.08f, 0.9f, 0.3f, 1f, 0.95f };
    private static readonly float[] OrganLook = { 0.45f, 0.75f, 0f, 0f, 0.9f, 0.85f };
    private static readonly float[] ClothLook = { 0f, 0.02f, 0f, 0.15f, 0.6f, 1f };
    private static readonly float[] FatLook = { 0.6f, 0.55f, 0f, 0f, 0.85f, 1f };

    private static Material LabMaterial(string name, float[] look, Texture tex, Color tint, Color cavity)
    {
        Shader lab = Shader.Find("DicomViewer/LabModel");
        if (lab == null) { Debug.LogError("ModelSnapshot: shader DicomViewer/LabModel not found"); return null; }
        var m = new Material(lab) { name = name };
        if (tex != null) m.SetTexture("_BaseTex", tex);
        m.SetFloat("_VertexAlbedo", tex != null ? 0f : 1f);          // the anatomy model has its colour in the vertices
        m.SetFloat("_SkinDetail", look[0] > 0.9f ? 1f : 0f);         // skin's own unevenness, on skin only
        m.SetFloat("_Skin", look[0]);
        m.SetFloat("_Gloss", look[1]);
        m.SetFloat("_Bump", tex != null ? look[2] : 0f);
        m.SetFloat("_Grain", look[3]);
        m.SetFloat("_Occlusion", look[4]);
        m.SetFloat("_Saturation", look[5]);
        m.SetColor("_Tint", tint);
        m.SetColor("_CavityTint", cavity);
        return m;
    }

    /// <summary>The anatomy: one GLB, its four child nodes the layers, every structure its own mesh and colour.</summary>
    private static (Camera cam, ModelBody body, Bounds bounds) BuildAnatomy()
    {
        Camera cam = Stage();
        var asset = AssetDatabase.LoadAssetAtPath<GameObject>(AnatomyAsset);
        if (asset == null) { Debug.LogError($"ModelSnapshot: no {AnatomyAsset} (backend/tools/build_model_meshes.py makes it)"); return (cam, null, default); }
        GameObject model = (GameObject)PrefabUtility.InstantiatePrefab(asset);
        PrefabUtility.UnpackPrefabInstance(model, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
        model.name = "Body";
        var body = model.AddComponent<ModelBody>();
        body.nested = true;
        body.credits = "Body: Visible Human Male, courtesy of the U.S. National Library of Medicine. Organs and torso: Segmented Internal Organs of the Visible Human Male, "
                       + "H\u00f6hne et al., University Medical Center Hamburg-Eppendorf, CC BY 4.0, doi:10.5281/zenodo.15882018. Bones: Visible-Human-3d-Models, Alavi and Asseln (BoneHub), "
                       + "CC BY 4.0, doi:10.57967/hf/10464, based on Andreassen et al., Sci Data 10, 34 (2023). Changes were made. For education only.";
        var polish = model.AddComponent<ModelPolish>();
        Bounds b = ModelLab.Lay(model, 0f);                       // real size as built
        int structures = 0;
        foreach (string layer in new[] { "skin", "fat", "muscles", "skeleton", "organs" })
        {
            Transform t = FindDeep(model.transform, layer);
            if (t == null) { Debug.LogWarning($"ModelSnapshot: anatomy has no layer {layer}"); continue; }
            float[] look = layer == "skin" ? SkinLook : layer == "fat" ? FatLook : layer == "muscles" ? MuscleLook : layer == "skeleton" ? BoneLook : OrganLook;
            Color cavity = layer == "skin" ? new Color(0.93f, 0.80f, 0.76f) : layer == "fat" ? new Color(0.75f, 0.52f, 0.32f)
                         : layer == "skeleton" ? new Color(0.50f, 0.40f, 0.30f) : new Color(0.55f, 0.30f, 0.28f);
            foreach (Renderer r in t.GetComponentsInChildren<Renderer>(true))
            {
                if (r.name.StartsWith("hair"))                       // strands: their own shader, no shadow of their own
                {
                    Shader hairShader = Shader.Find("DicomViewer/LabHair");
                    if (hairShader != null) r.sharedMaterial = new Material(hairShader) { name = r.name };
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    structures++;
                    continue;
                }
                bool cloth = r.name == "briefs";
                Material m = LabMaterial(r.name, cloth ? ClothLook : look, null, Color.white, cloth ? new Color(0.7f, 0.7f, 0.72f) : cavity);
                if (m != null) r.sharedMaterial = m;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                structures++;
            }
            // No bake here: build_model_meshes.py wrote occlusion and thickness into the vertex colours.
            body.Add(layer, t.gameObject);
        }
        // How the importer hands the vertex data over (the colour travels in the texture coordinates).
        Transform skinNode = FindDeep(model.transform, "skin");
        MeshFilter skinMesh = skinNode != null ? skinNode.GetComponentInChildren<MeshFilter>(true) : null;
        if (skinMesh != null && skinMesh.sharedMesh != null && skinMesh.sharedMesh.isReadable)
        {
            Mesh sm = skinMesh.sharedMesh;
            Debug.Log($"ModelSnapshot: skin mesh {skinMesh.name}: {sm.vertexCount} vertices, uv0[0] {sm.uv[0]}, uv1[0] {(sm.uv2.Length > 0 ? sm.uv2[0].ToString() : "none")}, colour[0] {sm.colors32[0]}");
        }
        ReadEyes(body);
        body.PushLids();
        Debug.Log($"ModelSnapshot: anatomy {structures} structures, laid {b.size} centre {b.center}");
        ModelLab.Room(b.size.x);
        return (cam, body, b);
    }

    private static Transform FindDeep(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform c in root) { Transform f = FindDeep(c, name); if (f != null) return f; }
        return null;
    }

    /// <summary>The prototype: three generated models, each a layer, laid at the same height and place.</summary>
    private static (Camera cam, ModelBody body, Bounds bounds) BuildPrototype()
    {
        Camera cam = Stage();
        var body = new GameObject("Body").AddComponent<ModelBody>();
        var polish = body.gameObject.AddComponent<ModelPolish>();
        Bounds bounds = default;
        bool any = false;
        foreach (string name in ModelBody.LayerNames)
        {
            string path = $"{ModelsFolder}/{name}.glb";
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (asset == null) { Debug.LogWarning($"ModelSnapshot: no {path}"); continue; }
            GameObject model = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            model.name = name;
            foreach (Renderer r in model.GetComponentsInChildren<Renderer>())
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                Material rm = r.sharedMaterial;
                if (rm == null) continue;
                Texture tex = rm.HasTexture(BaseColorTexture) ? rm.GetTexture(BaseColorTexture) : rm.mainTexture;
                // The generated textures are painted bright, as if already lit: taken down to tissue's own colour.
                Material m = name == "muscles" ? LabMaterial(name, MuscleLook, tex, new Color(0.86f, 0.80f, 0.80f), new Color(0.55f, 0.30f, 0.28f))
                           : name == "skeleton" ? LabMaterial(name, BoneLook, tex, new Color(0.80f, 0.77f, 0.70f), new Color(0.50f, 0.40f, 0.30f))
                           : LabMaterial(name, SkinLook, tex, new Color(0.88f, 0.84f, 0.83f), new Color(0.80f, 0.58f, 0.52f));
                if (m != null) r.sharedMaterial = m;
            }
            Bounds b = ModelLab.Lay(model, ModelLab.DefaultHeightM);
            polish.Add(model);
            body.Add(name, model);
            if (!any) { bounds = b; any = true; } else bounds.Encapsulate(b);
        }
        if (!any) { Debug.LogError($"ModelSnapshot: no models in {ModelsFolder}"); return (cam, null, default); }
        ModelLab.Room(bounds.size.x);
        return (cam, body, bounds);
    }

    private static void Save(Camera cam, ModelBody body, Bounds b, string scenePath)
    {
        if (body == null) return;
        var orbit = cam.gameObject.AddComponent<ModelOrbit>();
        orbit.yaw = 0f;
        orbit.pitch = 35f;
        orbit.Frame(b, cam);
        bool saved = EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), scenePath);
        Debug.Log($"ModelSnapshot: scene {(saved ? "saved" : "NOT saved")} -> {scenePath}");
    }

    [MenuItem("DICOM Viewer/Build Model Lab Scene")]
    public static void BuildScene()
    {
        var (cam, body, b) = BuildAnatomy();
        Save(cam, body, b, ScenePath);
    }

    [MenuItem("DICOM Viewer/Build Model Lab Scene (prototype)")]
    public static void BuildPrototypeScene()
    {
        var (cam, body, b) = BuildPrototype();
        Save(cam, body, b, PrototypeScenePath);
    }

    [MenuItem("DICOM Viewer/Model Body Snapshots")]
    public static void Run()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null) return;
        Shots(cam, body, b, "anatomy_");
        BuildScene();
    }

    public static void RunPrototype()
    {
        var (cam, body, b) = BuildPrototype();
        if (body == null) return;
        Shots(cam, body, b, "model_");
        BuildPrototypeScene();
    }

    private static void Shots(Camera cam, ModelBody body, Bounds b, string prefix)
    {
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        GameObject camGo = cam.gameObject;
        body.GetComponent<ModelPolish>().Apply();          // what Play mode does on Awake: the bake

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
            File.WriteAllBytes(Path.Combine(outDir, prefix + name), tex.EncodeToPNG());
            RenderTexture.active = null;
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(tex);
            Debug.Log($"ModelSnapshot: wrote {prefix}{name}");
        }
        Vector3 centre = new Vector3(0f, b.size.y * 0.5f, 0f);
        Vector3 head = new Vector3(b.min.x + 0.12f, b.size.y * 0.6f, 0f);
        Vector3 chest = new Vector3(b.min.x + 0.50f, b.size.y * 0.5f, 0f);
        foreach (ModelBody.Layer layer in body.layers)
        {
            body.LookAt(layer.name);
            View(0f, 35f, dist, centre);
            Shot($"{layer.name}.png");
            View(0f, 90f, dist, centre);
            Shot($"{layer.name}_above.png");
            View(-20f, 35f, dist * 0.4f, chest);
            Shot($"{layer.name}_chest.png");
            View(-30f, 30f, dist * 0.18f, head);
            Shot($"{layer.name}_head.png");
            View(-90f, 80f, dist * 0.16f, head + new Vector3(0.03f, 0f, 0f));       // straight down on the face, chin to the right
            Shot($"{layer.name}_face.png");
            View(0f, 40f, dist * 0.2f, new Vector3(b.min.x + 1.25f, b.size.y * 0.5f, 0f));
            Shot($"{layer.name}_legs.png");
        }
        body.LookAt(body.layers[0].name);
        if (body.hasEyes)
        {
            // The eyelids: half open, open, and one eye only (as a lid is drawn up with a finger).
            foreach ((string name, float right, float left) in new[] { ("half", 0.5f, 0.5f), ("open", 1f, 1f), ("one", 1f, 0f) })
            {
                body.lidRight = right;
                body.lidLeft = left;
                body.PushLids();
                View(-90f, 80f, dist * 0.16f, head + new Vector3(0.03f, 0f, 0f));
                Shot($"eyes_{name}.png");
                View(-30f, 30f, dist * 0.10f, head + new Vector3(0.0f, 0.02f, 0f));
                Shot($"eyes_{name}_side.png");
            }
            body.lidRight = body.lidLeft = 0f;
            body.PushLids();
        }
        body.GetComponent<ModelPolish>().Restore();
        Debug.Log($"ModelSnapshot: done -> {outDir}");
    }
}
