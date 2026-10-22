using System.Collections.Generic;
using System.IO;
using DicomViewer;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Rendering;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Menu "DICOM Viewer":
///   Set Up Scene        adds the viewer components (organ list, dig tool, toolbar, ...) to the VolumeLoader object
///   Build Windows App   sets up the scene, includes the volume shaders, builds a standalone .exe
/// The volume-rendering shaders are loaded by name at runtime (Shader.Find), so a build only contains them when
/// they are in Graphics Settings > Always Included Shaders; this script puts them there.
/// </summary>
public static class BuildViewer
{
    private const string ScenePath = "Assets/Scenes/DicomViewer.unity";
    // <repo>/build/: next to unity/ and backend/, so the app finds ../backend/out/latest.txt (VolumeLoader.LatestListPath).
    private static string OutputExe =>
        Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "build", "DICOM 3D Viewer.exe"));

    private static readonly string[] RuntimeShaders =
    {
        "VolumeRendering/URP/VolumeRendering",
        "VolumeRendering/URP/CrossSectionPlane",
        "DicomViewer/PhotoBody",       // Anatomy Lab
        "DicomViewer/BloodDrop",
        "DicomViewer/LivingEyeSclera",
        "DicomViewer/LivingEyeIris",
        "DicomViewer/LivingEyeCornea",
        "DicomViewer/BloodFluidDrops",
        "DicomViewer/BloodFluidBlur",
        "DicomViewer/BloodFluidComposite",
        "DicomViewer/LabInstrument",
        "DicomViewer/TissueSheet",
    };

    [MenuItem("DICOM Viewer/Set Up Scene")]
    public static void SetUpScene()
    {
        if (EditorSceneManager.GetActiveScene().path != ScenePath)
            EditorSceneManager.OpenScene(ScenePath);
        var loader = Object.FindFirstObjectByType<VolumeLoader>();
        if (loader == null)
        {
            Debug.LogError("No VolumeLoader in the scene");
            return;
        }
        var go = loader.gameObject;
        foreach (var type in new[] { typeof(VolumeOrbitController), typeof(ClippingPlaneController), typeof(FpsOverlay),
                     typeof(MarkerCheck), typeof(SliceViewPanel), typeof(OrganPanel), typeof(MaskVolume), typeof(CutTool),
                     typeof(ScalpelTool), typeof(KnifeTool), typeof(InspectPanel),
                     typeof(ViewerToolbar) })
            if (go.GetComponent(type) == null)
            {
                Undo.AddComponent(go, type);
                Debug.Log($"Added {type.Name} to {go.name}");
            }
        EditorSceneManager.MarkSceneDirty(go.scene);
        EditorSceneManager.SaveScene(go.scene);
    }

    [MenuItem("DICOM Viewer/Build Windows App")]
    public static void Build()
    {
        SetUpScene();
        IncludeShaders();
        DicomViewer.AnatomyLab.EditorTools.BloodFluidDemo.EnsureRendererFeature();   // liquid blood in the Anatomy Lab

        PlayerSettings.productName = "DICOM 3D Viewer";
        PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        PlayerSettings.defaultScreenWidth = 1600;
        PlayerSettings.defaultScreenHeight = 900;
        PlayerSettings.resizableWindow = true;
        PlayerSettings.runInBackground = true;
        PlayerSettings.SplashScreen.show = false;

        Directory.CreateDirectory(Path.GetDirectoryName(OutputExe));
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = OutputExe,
            target = BuildTarget.StandaloneWindows64,
            options = BuildOptions.None,
        });
        if (report.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded)
        {
            Debug.Log($"Built {OutputExe} ({report.summary.totalSize / 1e6:F0} MB) in {report.summary.totalTime}");
            EditorUtility.RevealInFinder(OutputExe);
        }
        else Debug.LogError($"Build {report.summary.result}: see the Console for errors");
    }

    private static void IncludeShaders()
    {
        var settings = AssetDatabase.LoadAssetAtPath<GraphicsSettings>("ProjectSettings/GraphicsSettings.asset");
        var so = new SerializedObject(settings);
        var list = so.FindProperty("m_AlwaysIncludedShaders");
        foreach (var name in RuntimeShaders)
        {
            var shader = Shader.Find(name);
            if (shader == null)
            {
                Debug.LogError($"Shader not found: {name}");
                continue;
            }
            bool present = false;
            for (int i = 0; i < list.arraySize; i++)
                present |= list.GetArrayElementAtIndex(i).objectReferenceValue == shader;
            if (present) continue;
            list.InsertArrayElementAtIndex(list.arraySize);
            list.GetArrayElementAtIndex(list.arraySize - 1).objectReferenceValue = shader;
            Debug.Log($"Always-included shader added: {name}");
        }
        so.ApplyModifiedProperties();
        AssetDatabase.SaveAssets();
    }
}

/// <summary>
/// The volume shader declares ~9000 multi_compile variants; this viewer never uses 2D transfer functions,
/// shadows, the scene's main light, MIP/isosurface modes or segmentation "isolate" mode. Dropping those
/// variants cuts the shader compile of a build from very long to a few minutes.
/// </summary>
internal class StripUnusedVolumeVariants : IPreprocessShaders
{
    private static readonly string[] Unused = { "TF2D_ON", "SHADOWS_ON", "USE_MAIN_LIGHT", "MODE_MIP", "MODE_SURF", "MULTIVOLUME_ISOLATE" };

    public int callbackOrder => 0;

    public void OnProcessShader(Shader shader, ShaderSnippetData snippet, IList<ShaderCompilerData> data)
    {
        if (!shader.name.StartsWith("VolumeRendering/")) return;
        var keywords = new List<ShaderKeyword>();
        foreach (var name in Unused) keywords.Add(new ShaderKeyword(shader, name));
        for (int i = data.Count - 1; i >= 0; i--)
            foreach (var kw in keywords)
                if (data[i].shaderKeywordSet.IsEnabled(kw))
                {
                    data.RemoveAt(i);
                    break;
                }
    }
}
