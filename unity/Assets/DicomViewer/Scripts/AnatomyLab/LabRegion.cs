using System;
using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// Regions of the body at full detail: where the whole body's export (1.3 mm) names a finer export inside it
    /// (the head at 0.66 mm, placed by tools/transfer_eyes.py), that export is loaded as a body of its own, with
    /// its skin mesh, at its place inside the whole body, and the whole body's volume and mesh leave that box to
    /// it. Nothing is cut there in whole-body mode (the tools look away from the box): to dissect the face, the
    /// lab shows the head on its own. Display only, so the face a student looks at is the face at full detail.
    /// </summary>
    [RequireComponent(typeof(PhotoBody))]
    public class LabRegion : MonoBehaviour
    {
        /// <summary>The export was cut off (at the neck) and closed over the cut: nothing of it is drawn below this.</summary>
        public const float CutEndMm = 1.5f;

        private PhotoBody body;
        private readonly List<PhotoBody> regions = new List<PhotoBody>();
        private readonly List<Bounds> boxesMm = new List<Bounds>();

        public int Count => regions.Count;
        public IReadOnlyList<PhotoBody> Regions => regions;

        /// <summary>
        /// Loads the body's regions. `loader` loads an export into a PhotoBody synchronously (editor snapshots);
        /// null loads them in the background as the lab does.
        /// </summary>
        public void Attach(PhotoBody photoBody, Func<PhotoBody, BodyMeta> loader = null)
        {
            Clear();
            body = photoBody;
            if (body == null || !body.IsLoaded || body.Meta.regions == null) { Push(); return; }
            foreach (BodyRegion r in body.Meta.regions)
            {
                if (string.IsNullOrEmpty(r.folder) || r.centre_m == null || r.size_m == null) continue;
                var go = new GameObject("Region " + r.name) { hideFlags = HideFlags.DontSave };
                go.transform.SetParent(body.transform, false);                       // the body's metres, same axes
                go.transform.localPosition = new Vector3(r.centre_m[0], r.centre_m[1], r.centre_m[2]);
                var region = go.AddComponent<PhotoBody>();
                region.folder = AnatomyLab.BodyFolder(r.folder);
                var skin = go.AddComponent<SkinMesh>();
                regions.Add(region);
                Vector3 size = body.Space.SizeMm, half = new Vector3(r.size_m[0], r.size_m[1], r.size_m[2]) * 500f;
                Vector3 centreMm = new Vector3((r.centre_m[0] / body.SizeM.x + 0.5f) * size.x, (r.centre_m[1] / body.SizeM.y + 0.5f) * size.y,
                                               (r.centre_m[2] / body.SizeM.z + 0.5f) * size.z);
                // The body fills up to the region's cut end; the region draws from there up (CutEndMm).
                Bounds box = new Bounds(centreMm, half * 2f);
                box.SetMinMax(box.min + new Vector3(0f, CutEndMm, 0f), box.max);
                boxesMm.Add(box);
                if (loader != null)
                {
                    loader(region);
                    OnRegionLoaded(region, skin);
                }
                else
                {
                    region.Loaded += () => OnRegionLoaded(region, skin);
                    _ = region.LoadAsync();
                }
            }
            Push();
        }

        private void OnRegionLoaded(PhotoBody region, SkinMesh skin)
        {
            Material m = region.Material;
            if (m == null) return;
            m.SetFloat("_MaskEnabled", 0f);
            m.SetFloat("_StepScale", 0.5f);
            m.SetFloat("_ClipBelowMm", CutEndMm);
            BodyEye[] eyes = region.Meta.eyes;
            if (eyes != null && eyes.Length >= 2)
                for (int i = 0; i < 2; i++)
                {
                    BodyEye e = eyes[i];
                    m.SetVector(i == 0 ? "_Eye0" : "_Eye1", new Vector4(e.centre_m[0], e.lid_line_y_m, e.centre_m[2], e.radius_m));
                    m.SetVector(i == 0 ? "_EyeBall0" : "_EyeBall1", new Vector4(e.centre_m[0], e.centre_m[1], e.centre_m[2], e.radius_m + 0.0005f));
                }
            skin.Attach(region);
            if (skin.Material != null) skin.Material.SetFloat("_ClipBelowMm", CutEndMm);
            Sync();
        }

        // The body and its skin mesh leave the regions' boxes alone.
        private void Push()
        {
            if (body == null || body.Material == null) return;
            Material m = body.Material;
            bool on = boxesMm.Count > 0;
            m.SetFloat("_RegionOn", on ? 1f : 0f);
            if (on)
            {
                m.SetVector("_RegionMin", boxesMm[0].min);
                m.SetVector("_RegionMax", boxesMm[0].max);
            }
        }

        private void LateUpdate() => Sync();

        /// <summary>The eyes' opening and the step size follow the body's (LateUpdate; snapshots call it).</summary>
        public void Sync()
        {
            if (body == null || body.Material == null) return;
            Material src = body.Material;
            foreach (PhotoBody r in regions)
            {
                if (r == null || r.Material == null) continue;
                r.Material.SetFloat("_Open", src.GetFloat("_Open"));
                r.Material.SetFloat("_ModelEyes", src.GetFloat("_ModelEyes"));
                r.Material.SetFloat("_StepScale", src.GetFloat("_StepScale"));
                if (src.HasFloat("_SkinMode")) r.Material.SetFloat("_SkinMode", src.GetFloat("_SkinMode"));
                foreach (var sm in r.GetComponents<SkinMesh>()) sm.Sync();
            }
        }

        /// <summary>Is a world point inside a region's box (where the body is not cut)?</summary>
        public bool Contains(Vector3 world)
        {
            if (boxesMm.Count == 0 || body == null || body.Volume == null) return false;
            Vector3 mm = body.Space.UvwToMm(VolumeSpace.LocalToUvw(body.Volume.InverseTransformPoint(world)));
            foreach (Bounds b in boxesMm) if (b.Contains(mm)) return true;
            return false;
        }

        public void Clear()
        {
            foreach (PhotoBody r in regions) if (r != null) Kill(r.gameObject);
            regions.Clear();
            boxesMm.Clear();
            if (body != null && body.Material != null) body.Material.SetFloat("_RegionOn", 0f);
        }

        private void OnDestroy() => Clear();

        private static void Kill(UnityEngine.Object o)
        {
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
