// Menu "DICOM Viewer/Blood Fluid Demo Scene": a sphere with ~3000 animated drops, the renderer feature
// added to the default URP renderer if missing, and the blood shaders added to Always Included Shaders.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace DicomViewer.AnatomyLab.EditorTools
{
    public static class BloodFluidDemo
    {
        private static readonly string[] k_Shaders =
        {
            "DicomViewer/BloodFluidDrops", "DicomViewer/BloodFluidBlur", "DicomViewer/BloodFluidComposite",
        };

        [MenuItem("DICOM Viewer/Blood Fluid Demo Scene")]
        public static void CreateScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.08f, 0.08f, 0.09f);
            cam.nearClipPlane = 0.01f;
            cam.farClipPlane = 20f;
            cam.fieldOfView = 30f;   // close-up: a 1 mm drop is ~6 px, so the film and rivulets are readable
            camGo.transform.position = new Vector3(0f, 0.32f, -0.78f);
            camGo.transform.LookAt(new Vector3(0f, 0.22f, -0.40f));
            camGo.AddComponent<AudioListener>();

            var lightGo = new GameObject("Directional Light");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.6f;
            light.color = new Color(1f, 0.96f, 0.9f);
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.Euler(38f, -35f, 0f);

            var body = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            body.name = "Body";
            var skin = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            skin.SetColor("_BaseColor", new Color(0.86f, 0.66f, 0.56f));
            skin.SetFloat("_Smoothness", 0.35f);
            body.GetComponent<Renderer>().sharedMaterial = skin;
            body.AddComponent<BloodFluidDemoDrops>();

            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "Floor";
            floor.transform.position = new Vector3(0f, -0.5f, 0f);
            var floorMat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            floorMat.SetColor("_BaseColor", new Color(0.35f, 0.36f, 0.38f));
            floor.GetComponent<Renderer>().sharedMaterial = floorMat;

            EnsureAlwaysIncludedShaders();
            EnsureRendererFeature();

            Selection.activeGameObject = body;
            Debug.Log("Blood Fluid demo scene ready. Press Play. Tune settings on the Blood Fluid Feature of the URP renderer.");
        }

        public static void EnsureAlwaysIncludedShaders()
        {
            var so = new SerializedObject(GraphicsSettings.GetGraphicsSettings());
            SerializedProperty list = so.FindProperty("m_AlwaysIncludedShaders");
            if (list == null) return;
            foreach (string name in k_Shaders)
            {
                Shader shader = Shader.Find(name);
                if (shader == null) { Debug.LogError($"Blood Fluid: shader '{name}' not found."); continue; }
                bool present = false;
                for (int i = 0; i < list.arraySize && !present; i++)
                    present = list.GetArrayElementAtIndex(i).objectReferenceValue == shader;
                if (present) continue;
                list.arraySize++;
                list.GetArrayElementAtIndex(list.arraySize - 1).objectReferenceValue = shader;
            }
            so.ApplyModifiedProperties();
        }

        [MenuItem("DICOM Viewer/Install Blood Fluid Feature")]
        public static void Install()
        {
            EnsureAlwaysIncludedShaders();
            EnsureRendererFeature();
        }

        // Mirrors ScriptableRendererDataEditor.AddComponent: sub-asset + m_RendererFeatures + m_RendererFeatureMap.
        public static void EnsureRendererFeature()
        {
            var asset = UniversalRenderPipeline.asset;
            if (asset == null) { Debug.LogWarning("Blood Fluid: no URP asset is active; add the feature to your renderer by hand."); return; }

            var assetSo = new SerializedObject(asset);
            SerializedProperty renderers = assetSo.FindProperty("m_RendererDataList");
            if (renderers == null || renderers.arraySize == 0) return;
            var data = renderers.GetArrayElementAtIndex(0).objectReferenceValue as ScriptableRendererData;
            if (data == null) return;

            foreach (ScriptableRendererFeature f in data.rendererFeatures)
                if (f is BloodFluidFeature) return;

            var feature = ScriptableObject.CreateInstance<BloodFluidFeature>();
            feature.name = nameof(BloodFluidFeature);
            feature.hideFlags |= HideFlags.HideInHierarchy;
            if (EditorUtility.IsPersistent(data)) AssetDatabase.AddObjectToAsset(feature, data);
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(feature, out _, out long localId);

            var so = new SerializedObject(data);
            SerializedProperty features = so.FindProperty("m_RendererFeatures");
            SerializedProperty map = so.FindProperty("m_RendererFeatureMap");
            if (features == null || map == null) { Debug.LogWarning("Blood Fluid: could not edit the renderer asset; add the feature by hand."); return; }
            features.arraySize++;
            features.GetArrayElementAtIndex(features.arraySize - 1).objectReferenceValue = feature;
            map.arraySize++;
            map.GetArrayElementAtIndex(map.arraySize - 1).longValue = localId;
            so.ApplyModifiedProperties();
            EditorUtility.SetDirty(data);
            AssetDatabase.SaveAssets();
            Debug.Log($"Blood Fluid: feature added to renderer '{data.name}'.");
        }
    }
}
