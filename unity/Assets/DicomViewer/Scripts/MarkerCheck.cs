using UnityEngine;
using UnityVolumeRendering;
// Unity 6.x added UnityEngine.TransferFunction; pin the plugin's type.
using TransferFunction = UnityVolumeRendering.TransferFunction;

namespace DicomViewer
{
    /// <summary>
    /// Press B to swap between the clinical transfer function and a bone-only one that hides
    /// everything below boneThresholdHU. Used to verify patient orientation against the phantom's
    /// three bone markers, and useful later for a quick skeleton view on real CT.
    ///
    /// Phantom: markers are 1200 HU, spine 900 HU, so a threshold of 1000 isolates the markers.
    /// Real CT: use ~300 (all bone) or ~700 (cortical bone only).
    /// </summary>
    [RequireComponent(typeof(VolumeLoader))]
    public class MarkerCheck : MonoBehaviour
    {
        [Tooltip("Voxels below this HU become fully transparent in bone-only mode. Live in Play mode.")]
        [Range(-200f, 1500f)] public float boneThresholdHU = 1000f;

        private VolumeLoader loader;
        private TransferFunction boneTF;
        private bool boneMode;

        private void Awake()
        {
            loader = GetComponent<VolumeLoader>();
            loader.Loaded += _ =>
            {
                // A (re)load clears the loader's override, so a new volume always starts in the clinical view.
                boneMode = false;
                if (boneTF == null) boneTF = ScriptableObject.CreateInstance<TransferFunction>();
                FillBoneOnly(boneTF, loader.Meta, boneThresholdHU);
            };
        }

        // Threshold edits during Play take effect immediately.
        private void OnValidate()
        {
            if (!Application.isPlaying || boneTF == null || loader == null) return;
            FillBoneOnly(boneTF, loader.Meta, boneThresholdHU);
            if (boneMode) loader.ApplyTransferFunction();
        }

        private void Update()
        {
            if (boneTF != null && !ViewerUi.ModalOpen && Input.GetKeyDown(KeyCode.B)) ToggleBones();
        }

        public bool BoneMode => boneMode;

        /// <summary>B key and the toolbar's Bones button.</summary>
        public void ToggleBones()
        {
            if (boneTF == null) return;
            boneMode = !boneMode;
            // The loader owns the clinical TF (and its live sliders); we only override it.
            loader.OverrideTransferFunction = boneMode ? boneTF : null;
            loader.ApplyTransferFunction();
            Debug.Log(boneMode
                ? $"Bone-only view (>{boneThresholdHU:F0} HU)"
                : "Clinical transfer function");
        }

        private static void FillBoneOnly(TransferFunction tf, VolumeMeta meta, float thresholdHU)
        {
            tf.colourControlPoints.Clear();
            tf.alphaControlPoints.Clear();
            float lo = meta.value_min, hi = meta.value_max;
            float T(float v) => Mathf.Clamp01((v - lo) / Mathf.Max(1f, hi - lo));

            tf.AddControlPoint(new TFColourControlPoint(0f, Color.white));
            tf.AddControlPoint(new TFColourControlPoint(1f, Color.white));

            // The plugin adds alpha 0 at position 0 itself; adding it here too would duplicate it
            // whenever the threshold sits below the data minimum.
            tf.AddControlPoint(new TFAlphaControlPoint(T(thresholdHU), 0f));
            tf.AddControlPoint(new TFAlphaControlPoint(T(thresholdHU + 100f), 1f));
            tf.AddControlPoint(new TFAlphaControlPoint(1f, 1f));

            tf.GenerateTexture();
        }
    }
}
