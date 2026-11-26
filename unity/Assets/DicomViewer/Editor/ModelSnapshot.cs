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
    [System.Serializable] private class MouthInfo { public float[] hinge; public float[] axis; public float[] grab; public float degrees; public float[] lip_down; public float lip_pull_m; public float[] lip_up; public float lip_lift_m; public float[] grab_upper; }
    [System.Serializable] private class AnatomyInfo { public EyesInfo eyes; public MouthInfo mouth; }

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

    private static void ReadMouth(ModelBody body)
    {
        string path = Path.Combine(Application.dataPath, "Models", "anatomy.json");
        if (!File.Exists(path)) return;
        AnatomyInfo info = JsonUtility.FromJson<AnatomyInfo>(File.ReadAllText(path));
        if (info == null || info.mouth == null || info.mouth.hinge == null || info.mouth.hinge.Length < 3 || info.mouth.axis == null || info.mouth.axis.Length < 3) return;
        body.hasMouth = true;
        body.jawHinge = MeshSpace(info.mouth.hinge);
        body.jawAxis = -MeshSpace(info.mouth.axis).normalized;      // an axis of turning: mirrored with the meshes, it points the other way
        body.mouthGrab = MeshSpace(info.mouth.grab);
        if (info.mouth.degrees > 0f) body.jawDegrees = info.mouth.degrees;
        if (info.mouth.lip_down != null && info.mouth.lip_down.Length >= 3) body.lipDown = MeshSpace(info.mouth.lip_down).normalized;
        body.lipPullMm = info.mouth.lip_pull_m * 1000f;
        if (info.mouth.lip_up != null && info.mouth.lip_up.Length >= 3 && info.mouth.lip_lift_m > 0f)
        {
            body.lipUp = MeshSpace(info.mouth.lip_up).normalized;
            body.lipLiftMm = info.mouth.lip_lift_m * 1000f;
            if (info.mouth.grab_upper != null && info.mouth.grab_upper.Length >= 3) body.upperLipGrab = MeshSpace(info.mouth.grab_upper);
        }
        else body.lipLiftMm = 0f;                                   // a model built before the upper lip was given its lift
        Debug.Log($"ModelSnapshot: jaw hinge at {body.jawHinge}, axis {body.jawAxis} (mesh space), {body.jawDegrees} degrees; lower lip at {body.mouthGrab}");
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
    private static readonly float[] ToothLook = { 0.30f, 0.50f, 0f, 0f, 1f, 1f };          // enamel: smooth and wet
    private static readonly float[] MouthLook = { 0.85f, 0.45f, 0f, 0f, 0.8f, 1.05f };     // the mouth's lining and the gums: wet skin without pores
    private static readonly float[] NailLook = { 0.35f, 0.55f, 0f, 0f, 1f, 1f };           // a nail's plate: horn, hard and smooth

    private static bool IsTooth(string name) => name.Contains("incisor") || name.Contains("canine") || name.Contains("molar") || name.Contains("teeth");
    private static bool IsMouthLining(string name) => name == "lining of the mouth" || name == "lining of the throat" || name == "wall of the mouth" || name.EndsWith(" gum");
    private static bool IsNail(string name) => name.StartsWith("nail of ");

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
                       + "CC BY 4.0, doi:10.57967/hf/10464, based on Andreassen et al., Sci Data 10, 34 (2023). Head and neck structures labelled with TotalSegmentator (Wasserthal et al. 2023). "
                       + "Muscles of the hips and legs, knee ligaments and joint cartilage: Andreassen et al., Three Dimensional Lower Extremity Musculoskeletal Geometry of the "
                       + "Visible Human Female and Male, Sci Data 10, 34 (2023), University of Denver, CC BY 4.0. "
                       + "The skull's bones outlined after BodyParts3D, \u00a9 The Database Center for Life Science licensed under CC Attribution 4.0 International. "
                       + "Changes were made. For education only.";
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
                bool mouth = IsMouthLining(r.name) || r.name == "tongue";      // the tongue is lit as the lining round it is (as an organ it stood dark and dull in the mouth)
                float[] own = cloth ? ClothLook : IsTooth(r.name) ? ToothLook : mouth ? MouthLook : IsNail(r.name) ? NailLook : look;
                Material m = LabMaterial(r.name, own, null, Color.white, cloth ? new Color(0.7f, 0.7f, 0.72f) : mouth ? new Color(0.62f, 0.30f, 0.30f) : cavity);
                if (m != null && r.name == "tongue")
                {
                    m.SetFloat("_SkinDetail", 0.8f);                 // its fine dots and mottle, as skin has pores (the papillae)
                    m.SetFloat("_Gloss", 0.6f);
                }
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
        ReadMouth(body);
        body.jawRenderers.Clear();
        foreach (MeshFilter mf in model.GetComponentsInChildren<MeshFilter>(true))
            if (mf.sharedMesh != null && mf.sharedMesh.HasVertexAttribute(UnityEngine.Rendering.VertexAttribute.TexCoord3) && mf.GetComponent<Renderer>() != null)
                body.jawRenderers.Add(mf.GetComponent<Renderer>());
        body.jaw = body.upperLip = 0f;
        body.PushJaw();
        Debug.Log($"ModelSnapshot: {body.jawRenderers.Count} meshes carry jaw weights");
        foreach (MeshFilter mf in model.GetComponentsInChildren<MeshFilter>(true))
            if (mf.name == "hair lashes" || mf.name == "skin")
            {
                var uv3 = new System.Collections.Generic.List<Vector2>();
                mf.sharedMesh.GetUVs(2, uv3);
                float most = 0f, least = 0f;
                foreach (Vector2 q in uv3) { most = Mathf.Max(most, q.x); least = Mathf.Min(least, q.x); }
                Debug.Log($"ModelSnapshot: {mf.name}: lid weights on {uv3.Count} of {mf.sharedMesh.vertexCount} vertices, from {least:F2} to {most:F2}; material {mf.GetComponent<Renderer>().sharedMaterial.shader.name}");
            }
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

    /// <summary>Taking structures off (ModelBody.Hide): the organs' layer seen at the chest, whole; then with the
    /// two lungs taken off; then with the liver and the stomach's parts off as well; and what is put back.
    /// Pictures hide_*.png beside the others; the log says what was taken and what is touched afterwards.</summary>
    public static void RunHide()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null) return;
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        body.GetComponent<ModelPolish>().Apply();
        float dist = b.size.x * 0.5f / (0.84f * 1600f / 900f) / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
        var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
        cam.targetTexture = rt;
        Vector3 chest = new Vector3(b.min.x + 0.50f, b.size.y * 0.5f, 0f);
        Quaternion q = Quaternion.Euler(50f, -20f, 0f);
        cam.transform.position = chest + q * new Vector3(0, 0, -dist * 0.3f);
        cam.transform.rotation = q;
        void Shot(string name)
        {
            cam.Render();
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, "hide_" + name + ".png"), tex.EncodeToPNG());
            RenderTexture.active = null;
            Object.DestroyImmediate(tex);
            Debug.Log($"ModelSnapshot: wrote hide_{name}.png");
        }
        string InFront()
        {
            Renderer r = ModelPick.At(cam, new Vector2(rt.width * 0.5f, rt.height * 0.5f), body.Touchable());
            return r != null ? r.name : "nothing";
        }
        void Off(params string[] structures)
        {
            foreach (string structure in structures)
            {
                Renderer target = null;
                foreach (Renderer r in body.Touchable()) if (r.name == structure) target = r;
                bool taken = target != null && body.Hide(target);
                Debug.Log($"ModelSnapshot: '{structure}' " + (taken ? "taken off" : target == null ? "is not on the layers shown" : "cannot be taken off"));
            }
        }
        body.LookAt("organs");
        Debug.Log($"ModelSnapshot: hide: in front at the picture's middle: {InFront()}");
        Shot("0_whole");
        Off("left lung", "right lung");
        Debug.Log($"ModelSnapshot: hide: {body.Hidden.Count} off; in front at the picture's middle: {InFront()}");
        Shot("1_lungs_off");
        Off("liver", "fundus of stomach", "body of stomach", "pericardium");
        Debug.Log($"ModelSnapshot: hide: {body.Hidden.Count} off; in front at the picture's middle: {InFront()}");
        Shot("2_liver_and_stomach_off");
        Renderer back = body.ShowLast();
        Debug.Log($"ModelSnapshot: hide: put back '{(back != null ? back.name : "nothing")}'; {body.Hidden.Count} still off");
        body.ShowAll();
        Debug.Log($"ModelSnapshot: hide: all put back; {body.Hidden.Count} off; in front at the picture's middle: {InFront()}");
        body.LookAt("skin");
        Off("skin");
        cam.targetTexture = null;
        Object.DestroyImmediate(rt);
        Debug.Log("ModelSnapshot: hide done");
    }

    /// <summary>Tapping a structure to learn its name (build/snapshots/names_*.png): on each layer a structure is
    /// tapped where it lies on the screen, and the picture shows it tinted with its card. The log says what each
    /// tap picked and what the card reads.</summary>
    public static void RunNames()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null) return;
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        body.GetComponent<ModelPolish>().Apply();
        Debug.Log($"ModelSnapshot: names table: {body.Names.Count} structures");
        float dist = b.size.x * 0.5f / (0.84f * 1600f / 900f) / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
        var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
        cam.targetTexture = rt;                                 // (kept while tapping: the taps are in this picture's pixels)
        void View(float yawDeg, float pitchDeg, float distance, Vector3 focus)
        {
            Quaternion q = Quaternion.Euler(pitchDeg, yawDeg, 0f);
            cam.transform.position = focus + q * new Vector3(0, 0, -distance);
            cam.transform.rotation = q;
        }
        void Shot(string name)
        {
            cam.Render();
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, "names_" + name + ".png"), tex.EncodeToPNG());
            RenderTexture.active = null;
            Object.DestroyImmediate(tex);
            Debug.Log($"ModelSnapshot: wrote names_{name}.png");
        }
        string CardText()
        {
            var parts = new System.Collections.Generic.List<string>();
            foreach (ModelCard.Line l in body.Card.Lines) parts.Add(l.text);
            return body.Card.Shown ? string.Join(" | ", parts) : "(no card)";
        }
        // A tap where the named structure lies on the screen: at its middle, or at the first of a few places
        // round it where it is the structure in front.
        void Tap(string structure)
        {
            body.Select(null, cam);
            Renderer target = null;
            foreach (Renderer r in body.Touchable()) if (r.name == structure) target = r;
            if (target == null) { Debug.LogWarning($"ModelSnapshot: no structure '{structure}' on the layers shown"); return; }
            Bounds tb = target.bounds;
            Vector2 at = cam.WorldToScreenPoint(tb.center);
            foreach (Vector3 f in new[] { Vector3.zero, new Vector3(0.25f, 0f, 0f), new Vector3(-0.25f, 0f, 0f), new Vector3(0f, 0f, 0.25f), new Vector3(0f, 0f, -0.25f),
                                          new Vector3(0.25f, 0.3f, 0.25f), new Vector3(-0.25f, 0.3f, -0.25f), new Vector3(0f, 0.45f, 0f), new Vector3(0.4f, 0.2f, 0f), new Vector3(-0.4f, 0.2f, 0f) })
            {
                Vector2 p = cam.WorldToScreenPoint(tb.center + Vector3.Scale(tb.size, f));
                if (ModelPick.At(cam, p, body.Touchable()) == target) { at = p; break; }
            }
            Renderer got = body.TapAt(cam, at);
            Debug.Log($"ModelSnapshot: tapped at {at} for '{structure}': picked '{(got != null ? got.name : "nothing")}'; card: {CardText()}");
        }
        Vector3 head = new Vector3(b.min.x + 0.12f, b.size.y * 0.6f, 0f);
        Vector3 chest = new Vector3(b.min.x + 0.50f, b.size.y * 0.5f, 0f);
        Vector3 legs = new Vector3(b.min.x + 1.25f, b.size.y * 0.5f, 0f);
        Vector3 feet = new Vector3(b.max.x - 0.07f, b.size.y * 0.55f, 0f);

        body.LookAt("skin");
        View(-20f, 35f, dist * 0.4f, chest);
        Tap("skin");
        Shot("skin");
        View(90f, 55f, dist * 0.11f, feet + new Vector3(0.03f, 0.04f, 0.165f));
        Tap("nail of the left great toe");
        Shot("skin_nail");

        body.LookAt("muscles");
        View(0f, 40f, dist * 0.2f, legs);
        Tap("right rectus femoris");
        Shot("muscles_leg");
        View(-90f, 80f, dist * 0.16f, head + new Vector3(0.03f, 0f, 0f));
        Tap("left zygomaticus major");
        Shot("muscles_face_drawn");

        body.LookAt("skeleton");
        View(0f, 40f, dist * 0.2f, legs);
        Tap("left femur");
        Shot("skeleton_femur");
        body.SetLanguage(NameLanguage.English);
        Debug.Log($"ModelSnapshot: in English: {CardText()}");
        Shot("skeleton_femur_en");
        body.SetLanguage(NameLanguage.Latin);
        Debug.Log($"ModelSnapshot: in Latin: {CardText()}");
        Shot("skeleton_femur_la");
        body.SetLanguage(NameLanguage.Italian);
        View(-90f, 80f, dist * 0.16f, head + new Vector3(0.03f, 0f, 0f));
        Tap("frontal bone");
        Shot("skeleton_skull");

        body.LookAt("organs");
        View(-20f, 35f, dist * 0.4f, chest);
        Tap("liver");
        Shot("organs_liver");
        // A tap beside the body puts the card away; so does a second tap on what is picked.
        Renderer left = body.TapAt(cam, new Vector2(6f, 6f));
        Debug.Log($"ModelSnapshot: a tap beside the body: picked '{(left != null ? left.name : "nothing")}'; card: {CardText()}");

        body.Select(null, cam);
        body.LookAt("skin");
        cam.targetTexture = null;
        Object.DestroyImmediate(rt);
        Debug.Log("ModelSnapshot: names done");
    }

    /// <summary>What shows through the skin, and what through the fat: with every layer on (then with the skin
    /// off), the body is looked at from the views the pictures are taken from, and every pixel is asked which
    /// mesh is in front (ModelPick.Map). Whatever is in front and is not of the outermost layer shows through
    /// it. The log lists it view by view (structure, pixels, where in the picture) and the sum; nothing is
    /// written but the log. Through the skin nothing should show. Through the fat only what lies in its two
    /// kinds of opening does, by design: over the eyes (the eyeballs and what is round them: the lids are the
    /// skin's) and over the red of the lips (the lips' muscle, the teeth behind it); anything else is a fault.
    /// Then the skin once more with THE MOUTH OPEN (the jaw's whole turn, both lips drawn off the teeth), from
    /// the sides the mouth's pictures are taken from: the teeth and the tongue are seen then, by design, and
    /// are counted apart; what lies under the skin moves with the jaw by its own weights, and where it moved
    /// otherwise than the skin it came through it only in that pose.</summary>
    public static void RunThrough()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null) return;
        var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
        cam.targetTexture = rt;
        Through(cam, body, b, "skin");
        Through(cam, body, b, "fat");
        body.LookAt("skin");
        if (body.hasMouth) ThroughWithTheMouthOpen(cam, body);
        cam.targetTexture = null;
        Object.DestroyImmediate(rt);
    }

    /// <summary>The opened mouth's part of RunThrough by itself (a minute), with a picture of every view in which
    /// each mesh has a flat colour by what it is (build/snapshots/through_open_*.png): the skin's layer dark grey,
    /// the teeth and the tongue light grey, and whatever shows through the skin loud: fat yellow, the lower lip's
    /// muscle green, the upper lip's dark green, the mandible blue, a cheek's muscle cyan, the maxilla violet,
    /// anything else magenta. The log says how many pixels of each; the picture says where.</summary>
    public static void RunThroughOpen()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null || !body.hasMouth) return;
        var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
        cam.targetTexture = rt;
        body.LookAt("skin");
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        ThroughWithTheMouthOpen(cam, body, outDir);
        // The same seven views with the mouth SHUT (what of it is the view's and not the pose's: the nostrils seen
        // from below are in no other survey), and with the mouth open and only the skin's layer drawn (black inside
        // the face: a gap in the skin's own surfaces, through which whatever lies behind is seen).
        ThroughWithTheMouthOpen(cam, body, outDir, 0f, false);
        ThroughWithTheMouthOpen(cam, body, outDir, 1f, true);
        BehindWhatShows(cam, body);
        cam.targetTexture = null;
        Object.DestroyImmediate(rt);
    }

    /// <summary>For what shows through the skin with the mouth open: WHICH of the skin's own surfaces it stands
    /// before (the skin with the lips' inner sides, the lining, the gums, the mouth's wall), pixel by pixel: every
    /// view's picture is read twice, with all layers and with the skin's alone. The log lists, for each
    /// structure that shows, the skin's surfaces behind it and how many pixels of each.</summary>
    private static void BehindWhatShows(Camera cam, ModelBody body)
    {
        var all = body.Touchable();
        var ofSkin = new System.Collections.Generic.HashSet<Renderer>();
        foreach (Renderer r in FindDeep(body.transform, "skin").GetComponentsInChildren<Renderer>(true)) ofSkin.Add(r);
        var alone = all.FindAll(r => ofSkin.Contains(r));
        Renderer skinRenderer = null;
        foreach (Renderer r in body.GetComponentsInChildren<Renderer>(true)) if (r.name == "skin") skinRenderer = r;
        Transform space = skinRenderer.transform;
        Vector3 mouth = space.TransformPoint(body.mouthGrab);
        Vector3 up = space.TransformDirection(body.eyeUp), forward = space.TransformDirection(body.eyeForward);
        Vector3 across = Vector3.Cross(up, forward).normalized;
        Vector3 face = mouth + up * 0.03f - forward * 0.02f, inside = mouth - up * 0.012f - forward * 0.02f;
        var views = new (string name, Vector3 from, Vector3 lookAt)[]
        {
            ("front", forward * 0.30f, face), ("below", (forward * 0.9f - up * 0.45f).normalized * 0.26f, inside),
            ("side", (forward * 0.5f + across).normalized * 0.34f, face), ("other side", (forward * 0.5f - across).normalized * 0.34f, face),
            ("close", (forward * 0.95f - up * 0.3f).normalized * 0.15f, inside), ("above", (forward * 0.8f + up * 0.6f).normalized * 0.2f, inside),
            ("under the chin", (forward * 0.3f - up).normalized * 0.34f, face - up * 0.06f),
        };
        body.jaw = body.upperLip = 1f;
        body.PushJaw();
        var tally = new System.Collections.Generic.Dictionary<string, System.Collections.Generic.Dictionary<string, int>>();
        foreach (var view in views)
        {
            cam.transform.position = view.lookAt + view.from;
            cam.transform.rotation = Quaternion.LookRotation(-view.from.normalized, up);
            int[] whole = ModelPick.Map(cam, all, out int w, out int h);
            int[] skins = ModelPick.Map(cam, alone, out _, out _);
            for (int i = 0; i < whole.Length; i++)
            {
                if (whole[i] == 0 || ofSkin.Contains(all[whole[i] - 1]) || OfTheMouth(all[whole[i] - 1].name)) continue;
                string shows = all[whole[i] - 1].name, behind = skins[i] == 0 ? "nothing of the skin's" : alone[skins[i] - 1].name;
                if (!tally.ContainsKey(shows)) tally[shows] = new System.Collections.Generic.Dictionary<string, int>();
                tally[shows][behind] = tally[shows].TryGetValue(behind, out int n) ? n + 1 : 1;
            }
        }
        foreach (var pair in tally)
        {
            var parts = new System.Collections.Generic.List<string>();
            foreach (var b in pair.Value) parts.Add($"{b.Key} {b.Value}");
            Debug.Log($"ModelSnapshot: with the mouth open '{pair.Key}' stands before: " + string.Join("; ", parts));
        }
        body.jaw = body.upperLip = 0f;
        body.PushJaw();
    }

    private static Color32 LoudColour(string name)
    {
        if (name == "subcutaneous fat" || name == "visceral fat") return new Color32(255, 220, 0, 255);
        if (name == "orbicularis oris, lower lip") return new Color32(0, 255, 0, 255);
        if (name == "orbicularis oris, upper lip") return new Color32(0, 150, 60, 255);
        if (name == "mandible") return new Color32(40, 90, 255, 255);
        if (name.Contains("buccinator")) return new Color32(0, 255, 255, 255);
        if (name.Contains("maxilla")) return new Color32(170, 120, 255, 255);
        return new Color32(255, 0, 255, 255);
    }

    private static bool OfTheMouth(string name)
    {
        return name == "tongue" || name.Contains("incisor") || name.Contains("canine") || name.Contains("molar") || name.Contains("teeth");
    }

    private static void ThroughWithTheMouthOpen(Camera cam, ModelBody body, string pictures = null, float open = 1f, bool skinOnly = false)
    {
        var renderers = body.Touchable();
        var ofSkin = new System.Collections.Generic.HashSet<Renderer>();
        foreach (Renderer r in FindDeep(body.transform, "skin").GetComponentsInChildren<Renderer>(true)) ofSkin.Add(r);
        Renderer skinRenderer = null;
        foreach (Renderer r in body.GetComponentsInChildren<Renderer>(true)) if (r.name == "skin") skinRenderer = r;
        Transform space = skinRenderer.transform;
        Vector3 mouth = space.TransformPoint(body.mouthGrab);
        Vector3 up = space.TransformDirection(body.eyeUp), forward = space.TransformDirection(body.eyeForward);
        Vector3 across = Vector3.Cross(up, forward).normalized;
        Vector3 face = mouth + up * 0.03f - forward * 0.02f, inside = mouth - up * 0.012f - forward * 0.02f;
        var views = new (string name, Vector3 from, Vector3 lookAt)[]
        {
            ("front", forward * 0.30f, face), ("below", (forward * 0.9f - up * 0.45f).normalized * 0.26f, inside),
            ("side", (forward * 0.5f + across).normalized * 0.34f, face), ("other side", (forward * 0.5f - across).normalized * 0.34f, face),
            ("close", (forward * 0.95f - up * 0.3f).normalized * 0.15f, inside), ("above", (forward * 0.8f + up * 0.6f).normalized * 0.2f, inside),
            ("under the chin", (forward * 0.3f - up).normalized * 0.34f, face - up * 0.06f),
        };
        body.jaw = body.upperLip = open;
        body.PushJaw();
        if (skinOnly) renderers = renderers.FindAll(r => ofSkin.Contains(r));
        string what = skinOnly ? "skin alone, the mouth open" : open > 0f ? "skin, the mouth open" : "skin, the mouth shut, seen as the open mouth is";
        string tag = skinOnly ? "through_open_alone_" : open > 0f ? "through_open_" : "through_shut_";
        long all = 0;
        foreach (var view in views)
        {
            cam.transform.position = view.lookAt + view.from;
            cam.transform.rotation = Quaternion.LookRotation(-view.from.normalized, up);
            all += Seen(cam, renderers, ofSkin, what, view.name, OfTheMouth,
                        pictures != null ? Path.Combine(pictures, tag + view.name.Replace(' ', '_') + ".png") : null);
        }
        Debug.Log($"ModelSnapshot: through the {what}, {views.Length} views: {all} pixels in all (the teeth and the tongue not counted)");
        body.jaw = body.upperLip = 0f;
        body.PushJaw();
    }

    /// <summary>One view: every pixel asked which mesh is in front; what is not of `outer` is listed in the log
    /// (structure, pixels, where in the picture). Returns the pixels that show through; those of structures
    /// `meant` to be seen are named in the log but not counted.</summary>
    private static long Seen(Camera cam, System.Collections.Generic.List<Renderer> renderers, System.Collections.Generic.HashSet<Renderer> outer, string what, string viewName,
                             System.Func<string, bool> meant = null, string picture = null)
    {
        int[] map = ModelPick.Map(cam, renderers, out int w, out int h);
        if (picture != null)
        {
            var flat = new Color32[map.Length];                            // (the map's rows count from the bottom, as a texture's do)
            for (int i = 0; i < map.Length; i++)
            {
                int id = map[i];
                if (id == 0) flat[i] = new Color32(0, 0, 0, 255);
                else if (outer.Contains(renderers[id - 1])) flat[i] = new Color32(70, 70, 70, 255);
                else if (meant != null && meant(renderers[id - 1].name)) flat[i] = new Color32(150, 150, 150, 255);
                else flat[i] = LoudColour(renderers[id - 1].name);
            }
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.SetPixels32(flat);
            tex.Apply();
            File.WriteAllBytes(picture, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
        }
        var count = new System.Collections.Generic.Dictionary<int, int>();
        var box = new System.Collections.Generic.Dictionary<int, RectInt>();
        int outerPixels = 0;
        for (int i = 0; i < map.Length; i++)
        {
            int id = map[i];
            if (id == 0) continue;
            if (outer.Contains(renderers[id - 1])) { outerPixels++; continue; }
            int x = i % w, y = h - 1 - i / w;                              // as in the saved pictures: y from the top
            if (!count.ContainsKey(id)) { count[id] = 0; box[id] = new RectInt(x, y, 0, 0); }
            count[id]++;
            RectInt r = box[id];
            int x0 = Mathf.Min(r.xMin, x), y0 = Mathf.Min(r.yMin, y), x1 = Mathf.Max(r.xMax, x), y1 = Mathf.Max(r.yMax, y);
            box[id] = new RectInt(x0, y0, x1 - x0, y1 - y0);
        }
        var parts = new System.Collections.Generic.List<string>();
        int through = 0, byDesign = 0;
        foreach (var pair in count)
        {
            string name = renderers[pair.Key - 1].name;
            if (meant != null && meant(name)) { byDesign += pair.Value; continue; }
            through += pair.Value;
            RectInt r = box[pair.Key];
            parts.Add($"{name} {pair.Value} px (x {r.xMin}..{r.xMax}, y {r.yMin}..{r.yMax})");
        }
        Debug.Log($"ModelSnapshot: through the {what}, view '{viewName}': {through} pixels of {outerPixels + through + byDesign} of him" + (meant != null ? $" ({byDesign} more of what is meant to be seen)" : "")
                  + (parts.Count > 0 ? ": " + string.Join("; ", parts) : ""));
        return through;
    }

    private static void Through(Camera cam, ModelBody body, Bounds b, string outer)
    {
        float dist = b.size.x * 0.5f / (0.84f * 1600f / 900f) / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
        body.LookAt(outer);
        var renderers = body.Touchable();
        var ofSkin = new System.Collections.Generic.HashSet<Renderer>();
        Transform skinLayer = FindDeep(body.transform, outer);
        foreach (Renderer r in skinLayer.GetComponentsInChildren<Renderer>(true)) ofSkin.Add(r);
        Vector3 centre = new Vector3(0f, b.size.y * 0.5f, 0f);
        Vector3 head = new Vector3(b.min.x + 0.12f, b.size.y * 0.6f, 0f);
        Vector3 chest = new Vector3(b.min.x + 0.50f, b.size.y * 0.5f, 0f);
        Vector3 legs = new Vector3(b.min.x + 1.25f, b.size.y * 0.5f, 0f);
        Vector3 feet = new Vector3(b.max.x - 0.07f, b.size.y * 0.55f, 0f);
        Vector3 hands = new Vector3(b.min.x + 0.86f, b.size.y * 0.75f, 0f);
        var views = new (string name, float yaw, float pitch, float distance, Vector3 focus)[]
        {
            ("whole", 0f, 35f, dist, centre), ("above", 0f, 90f, dist, centre), ("from his other side", 180f, 35f, dist, centre),
            ("chest", -20f, 35f, dist * 0.4f, chest), ("chest from the other side", 160f, 35f, dist * 0.4f, chest), ("belly from above", 0f, 80f, dist * 0.4f, new Vector3(b.min.x + 0.75f, b.size.y * 0.5f, 0f)),
            ("head", -30f, 30f, dist * 0.18f, head), ("face", -90f, 80f, dist * 0.16f, head + new Vector3(0.03f, 0f, 0f)), ("head from the other side", 150f, 30f, dist * 0.18f, head),
            ("legs", 0f, 40f, dist * 0.2f, legs), ("legs from the other side", 180f, 40f, dist * 0.2f, legs), ("thighs from above", 0f, 80f, dist * 0.3f, new Vector3(b.min.x + 1.05f, b.size.y * 0.5f, 0f)),
            ("shins from above", 0f, 80f, dist * 0.3f, new Vector3(b.min.x + 1.5f, b.size.y * 0.5f, 0f)),
            ("feet", -90f, 28f, dist * 0.2f, feet), ("feet from the side", -40f, 38f, dist * 0.2f, feet), ("hands", 0f, 78f, dist * 0.17f, hands),
        };
        long all = 0;
        foreach (var view in views)
        {
            Quaternion q = Quaternion.Euler(view.pitch, view.yaw, 0f);
            cam.transform.position = view.focus + q * new Vector3(0, 0, -view.distance);
            cam.transform.rotation = q;
            all += Seen(cam, renderers, ofSkin, outer, view.name);
        }
        Debug.Log($"ModelSnapshot: through the {outer}, {views.Length} views: {all} pixels in all");
    }

    /// <summary>The eyes only, quickly (build/snapshots/eye_*.png): closed, half open and open, from the front and from both sides.</summary>
    public static void RunEyes()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null || !body.hasEyes) return;
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        Transform skin = FindDeep(body.transform, "skin");
        Renderer skinRenderer = null, lashes = null;
        foreach (Renderer r in body.GetComponentsInChildren<Renderer>(true)) { if (r.name == "skin") skinRenderer = r; if (r.name == "hair lashes") lashes = r; }
        Vector3 eye = skinRenderer.transform.TransformPoint(body.eyeRight);
        Vector3 up = skinRenderer.transform.TransformDirection(body.eyeUp), forward = skinRenderer.transform.TransformDirection(body.eyeForward);
        Vector3 across = Vector3.Cross(up, forward).normalized;
        void Shot(string name, Vector3 from)
        {
            cam.transform.position = eye + from;
            cam.transform.rotation = Quaternion.LookRotation(-from.normalized, up);
            var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
            cam.targetTexture = rt;
            cam.Render();
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, "eye_" + name + ".png"), tex.EncodeToPNG());
            RenderTexture.active = null;
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(tex);
        }
        Vector3 front = forward * 0.16f, side = (forward * 0.45f + across * 1f).normalized * 0.16f, sideOther = (forward * 0.45f - across * 1f).normalized * 0.16f;
        Shot("closed_front", front);
        Shot("closed_side", side);
        foreach (float open in new[] { 0.5f, 1f })
        {
            body.lidRight = body.lidLeft = open;
            body.PushLids();
            Shot($"open{Mathf.RoundToInt(open * 100)}_front", front);
            Shot($"open{Mathf.RoundToInt(open * 100)}_side", side);
            Shot($"open{Mathf.RoundToInt(open * 100)}_side2", sideOther);
        }
        Debug.Log("ModelSnapshot: eyes done");
    }

    /// <summary>The mouth only, quickly (build/snapshots/mouth_*.png): closed, half open and open, from the front, from below and from the side; open on the inner layers.</summary>
    public static void RunMouth()
    {
        var (cam, body, b) = BuildAnatomy();
        if (body == null || !body.hasMouth) { Debug.LogError("ModelSnapshot: the model has no mouth (anatomy.json)"); return; }
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "snapshots"));
        Directory.CreateDirectory(outDir);
        Renderer skinRenderer = null;
        foreach (Renderer r in body.GetComponentsInChildren<Renderer>(true)) if (r.name == "skin") skinRenderer = r;
        Transform space = skinRenderer.transform;
        Vector3 mouth = space.TransformPoint(body.mouthGrab);
        Vector3 up = space.TransformDirection(body.eyeUp), forward = space.TransformDirection(body.eyeForward);
        Vector3 across = Vector3.Cross(up, forward).normalized;
        void Shot(string name, Vector3 from, Vector3 lookAt)
        {
            cam.transform.position = lookAt + from;
            cam.transform.rotation = Quaternion.LookRotation(-from.normalized, up);
            var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32);
            cam.targetTexture = rt;
            cam.Render();
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            File.WriteAllBytes(Path.Combine(outDir, "mouth_" + name + ".png"), tex.EncodeToPNG());
            RenderTexture.active = null;
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(tex);
        }
        Vector3 front = forward * 0.30f, below = (forward * 0.9f - up * 0.45f).normalized * 0.26f, side = (forward * 0.5f + across).normalized * 0.34f;
        Vector3 face = mouth + up * 0.03f - forward * 0.02f, inside = mouth - up * 0.012f - forward * 0.02f;
        foreach (float open in new[] { 0f, 0.5f, 1f })
        {
            body.jaw = body.upperLip = open;                         // both lips part, as with the Open mouth button
            body.PushJaw();
            string tag = $"open{Mathf.RoundToInt(open * 100):000}";
            Shot(tag + "_front", front, face);
            Shot(tag + "_below", below, inside);
            Shot(tag + "_side", side, face);
            if (open == 1f)
            {
                Shot(tag + "_close", (forward * 0.95f - up * 0.3f).normalized * 0.15f, inside);
                Shot(tag + "_above", (forward * 0.8f + up * 0.6f).normalized * 0.2f, inside);
                // Into the throat: from a little under the lips' level, as one looks past the tongue at the uvula.
                Shot(tag + "_throat", (forward * 0.97f - up * 0.24f).normalized * 0.13f, inside - forward * 0.025f);
            }
        }
        foreach (string layer in new[] { "fat", "muscles", "skeleton" })
        {
            body.LookAt(layer);
            Shot("open100_" + layer, (forward * 0.9f + across * 0.45f).normalized * 0.34f, face);
        }
        body.LookAt("skin");
        body.jaw = body.upperLip = 0f;
        body.PushJaw();
        Debug.Log("ModelSnapshot: mouth done");
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
            // The feet: from the foot of the table (the toes towards the viewer), and from his left side.
            Vector3 feet = new Vector3(b.max.x - 0.07f, b.size.y * 0.55f, 0f);
            View(-90f, 28f, dist * 0.2f, feet);
            Shot($"{layer.name}_feet.png");
            View(-40f, 38f, dist * 0.2f, feet);
            Shot($"{layer.name}_feet_side.png");
            if (layer.name == "skin")
            {
                // The toes' backs and their nails: from above the shins, looking down along the feet; both feet, then each.
                View(90f, 55f, dist * 0.30f, feet + new Vector3(0.02f, 0.03f, 0f));
                Shot("skin_toes.png");
                View(90f, 55f, dist * 0.11f, feet + new Vector3(0.03f, 0.04f, 0.165f));
                Shot("skin_toes_left.png");
                View(90f, 55f, dist * 0.11f, feet + new Vector3(0.03f, 0.04f, -0.165f));
                Shot("skin_toes_right.png");
                // The hands as they lie on him, from above.
                View(0f, 78f, dist * 0.17f, new Vector3(b.min.x + 0.86f, b.size.y * 0.75f, 0f));
                Shot("skin_hands.png");
            }
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
        if (body.hasMouth)
        {
            // The mouth: half open and open, on the skin; open on the layers under it.
            foreach ((string name, float open) in new[] { ("half", 0.5f), ("open", 1f) })
            {
                body.jaw = body.upperLip = open;
                body.PushJaw();
                View(-90f, 80f, dist * 0.16f, head + new Vector3(0.03f, 0f, 0f));
                Shot($"mouth_{name}.png");
                View(-90f, 35f, dist * 0.13f, head + new Vector3(0.07f, 0f, 0f));       // from the chin's side, looking in
                Shot($"mouth_{name}_in.png");
            }
            foreach (ModelBody.Layer layer in body.layers)
            {
                if (layer.name == "skin") continue;
                body.LookAt(layer.name);
                View(-60f, 40f, dist * 0.16f, head + new Vector3(0.05f, 0f, 0f));
                Shot($"mouth_open_{layer.name}.png");
            }
            body.LookAt(body.layers[0].name);
            body.jaw = body.upperLip = 0f;
            body.PushJaw();
        }
        body.GetComponent<ModelPolish>().Restore();
        Debug.Log($"ModelSnapshot: done -> {outDir}");
    }
}
