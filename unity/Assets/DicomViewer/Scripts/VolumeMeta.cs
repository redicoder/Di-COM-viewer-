using System;

namespace DicomViewer
{
    /// <summary>Mirror of backend/app/volume.py -> volume.json (JsonUtility ignores fields it doesn't know, e.g. "axes").</summary>
    [Serializable]
    public class VolumeMeta
    {
        public string volume_id;
        public int dim_x, dim_y, dim_z;
        public float[] spacing_mm;   // per texture axis (x, y, z)
        public float[] size_mm;      // dim * spacing, per texture axis
        public string format;        // "int16"
        public string endianness;    // "little"
        public long byte_length;
        public int value_min, value_max;
        public bool is_hu;
        public string modality;
        public bool lungs_only;      // written by `app.export --lungs-only`; VolumeLoader then picks the Lungs preset
        public string[] warnings;

        public long VoxelCount => (long)dim_x * dim_y * dim_z;
    }

    /// <summary>One entry of labels.json (tools/segment_organs.py): label id in labels.raw, display name, RGB 0..1.</summary>
    [Serializable]
    public class OrganLabel
    {
        public int id;
        public string name;
        public float[] color;
        public float opacity = 1f;   // relative to VolumeLoader.organOpacity; the lungs use less so they stay see-through
        public bool visible = true;
    }

    [Serializable]
    public class OrganLabelFile
    {
        public OrganLabel[] labels;
    }
}
