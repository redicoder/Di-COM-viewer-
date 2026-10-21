// Menu "DICOM Viewer/Living Eye Demo Scene": camera, one directional light, dark background, two eyes
// 64 mm apart looking at the camera, gaze following the mouse. Also puts the eye shaders in Always Included.
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab.EditorTools
{
    public static class LivingEyeDemo
    {
        private static readonly string[] k_Shaders =
        {
            "DicomViewer/LivingEyeSclera", "DicomViewer/LivingEyeIris", "DicomViewer/LivingEyeCornea",
        };

        [MenuItem("DICOM Viewer/Living Eye Demo Scene")]
        public static void CreateScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            EnsureAlwaysIncludedShaders();

            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.22f, 0.24f, 0.28f);
            RenderSettings.ambientEquatorColor = new Color(0.16f, 0.15f, 0.15f);
            RenderSettings.ambientGroundColor = new Color(0.06f, 0.05f, 0.05f);

            // The face looks toward -Z; the camera stands on -Z looking back at it.
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.05f, 0.05f, 0.06f);
            cam.nearClipPlane = 0.005f;
            cam.farClipPlane = 10f;
            cam.fieldOfView = 18f;   // the two eyes span most of the width at this distance
            camGo.transform.position = new Vector3(0f, 0f, -0.24f);
            camGo.transform.rotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
            camGo.AddComponent<AudioListener>();

            var lightGo = new GameObject("Directional Light");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.color = new Color(1f, 0.97f, 0.92f);
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.LookRotation(new Vector3(0.45f, -0.55f, 1f), Vector3.up);   // from the camera's upper left
            RenderSettings.sun = light;

            var head = new GameObject("Head");
            LivingEye leftEye = LivingEye.Create(head.transform, new Vector3(0.032f, 0f, 0f), 0.012f, Vector3.back);
            LivingEye rightEye = LivingEye.Create(head.transform, new Vector3(-0.032f, 0f, 0f), 0.012f, Vector3.back);
            leftEye.name = "LivingEye Left";
            rightEye.name = "LivingEye Right";
            rightEye.irisColor = leftEye.irisColor;

            var gaze = head.AddComponent<LivingEyeDemoGaze>();
            gaze.left = leftEye;
            gaze.right = rightEye;
            gaze.viewCamera = cam;

            Selection.activeGameObject = head;
            Debug.Log("Living Eye demo ready. Press Play and move the mouse; tune irisColor / pupil / wetness on each eye.");
        }

        private static void EnsureAlwaysIncludedShaders()
        {
            var so = new SerializedObject(GraphicsSettings.GetGraphicsSettings());
            SerializedProperty list = so.FindProperty("m_AlwaysIncludedShaders");
            if (list == null) return;
            foreach (string name in k_Shaders)
            {
                Shader shader = Shader.Find(name);
                if (shader == null) { Debug.LogError($"Living Eye: shader '{name}' not found."); continue; }
                bool present = false;
                for (int i = 0; i < list.arraySize && !present; i++)
                    present = list.GetArrayElementAtIndex(i).objectReferenceValue == shader;
                if (present) continue;
                list.arraySize++;
                list.GetArrayElementAtIndex(list.arraySize - 1).objectReferenceValue = shader;
            }
            so.ApplyModifiedProperties();
        }
    }
}
