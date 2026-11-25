using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// Which structure of the modelled body lies under a finger. The body is some five million triangles in 540
    /// meshes and has no colliders; so the meshes are drawn once more, each in its own number as a colour, into
    /// a few pixels round the touched one (LabModel.shader's "Pick" pass: at the place the mesh is drawn, with a
    /// lid open or the jaw turned), and the pixel in the middle is read. Done on a tap only.
    /// </summary>
    public static class ModelPick
    {
        /// <summary>Pixels square that are drawn; the touched pixel is the middle one.</summary>
        public const int Size = 5;

        private static readonly int PickColourId = Shader.PropertyToID("_LabPickColour");

        /// <summary>
        /// The whole picture in numbers: for each pixel of the camera's picture (row by row from the bottom, as
        /// Texture2D has them) the place in `renderers` of the mesh in front there, plus one; 0 where there is
        /// none. For asking of a view what shows in it (with the skin on: does anything show that is not skin?).
        /// </summary>
        public static int[] Map(Camera cam, IList<Renderer> renderers, out int width, out int height)
        {
            width = cam != null ? cam.pixelWidth : 0;
            height = cam != null ? cam.pixelHeight : 0;
            if (cam == null || renderers == null || width <= 0 || height <= 0) return new int[0];
            Color32[] read = Draw(cam, cam.projectionMatrix, renderers, width, height);
            var map = new int[width * height];
            // (the picture may come out upside down, as a camera's own picture into a texture does on some
            // graphics interfaces: told by drawing, which Draw does, and put right here)
            bool flipped = Flipped(cam);
            for (int y = 0; y < height; y++)
            {
                int from = (flipped ? height - 1 - y : y) * width, to = y * width;
                for (int x = 0; x < width; x++)
                {
                    Color32 c = read[from + x];
                    int id = c.a > 127 ? c.r | (c.g << 8) | (c.b << 16) : 0;
                    map[to + x] = id <= renderers.Count ? id : 0;
                }
            }
            return map;
        }

        private static bool? flippedKnown;

        /// <summary>Whether a picture drawn this way comes out upside down: found once, by drawing a mesh into the
        /// upper half of a small picture and seeing in which half it is read.</summary>
        private static bool Flipped(Camera cam)
        {
            if (flippedKnown.HasValue) return flippedKnown.Value;
            var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            quad.hideFlags = HideFlags.HideAndDontSave;
            var probe = new GameObject("pick probe") { hideFlags = HideFlags.HideAndDontSave }.AddComponent<Camera>();
            probe.enabled = false;
            probe.transform.SetPositionAndRotation(new Vector3(0f, -1000f, 0f), Quaternion.identity);
            probe.orthographic = true;
            probe.orthographicSize = 1f;
            probe.aspect = 1f;
            probe.nearClipPlane = 0.1f;
            probe.farClipPlane = 10f;
            quad.transform.position = probe.transform.position + new Vector3(0f, 0.5f, 2f);      // in the picture's upper half
            quad.transform.localScale = new Vector3(4f, 0.6f, 1f);
            Shader shader = Shader.Find("DicomViewer/LabModel");
            bool flipped = false;
            if (shader != null)
            {
                var material = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
                var r = quad.GetComponent<Renderer>();
                r.sharedMaterial = material;
                Color32[] read = Draw(probe, probe.projectionMatrix, new List<Renderer> { r }, 8, 8);
                flipped = read.Length == 64 && read[1 * 8 + 4].a > 127 && read[6 * 8 + 4].a <= 127;     // read in the lower half
                Object.DestroyImmediate(material);
            }
            Object.DestroyImmediate(quad);
            Object.DestroyImmediate(probe.gameObject);
            flippedKnown = flipped;
            return flipped;
        }

        /// <summary>
        /// The renderer that is in front at a screen pixel (origin bottom-left, as Input.mousePosition; of the
        /// camera's own picture), among those given; null where there is none. A renderer that is off, or whose
        /// material has no "Pick" pass (hair), is not drawn and cannot be touched.
        /// </summary>
        public static Renderer At(Camera cam, Vector2 pixel, IList<Renderer> renderers)
        {
            if (cam == null || renderers == null || renderers.Count == 0) return null;
            float w = Mathf.Max(1, cam.pixelWidth), h = Mathf.Max(1, cam.pixelHeight);
            if (pixel.x < 0f || pixel.y < 0f || pixel.x >= w || pixel.y >= h) return null;
            // The camera's projection narrowed to the few pixels round the touched one (in clip space: moved so that
            // the pixel's centre is the picture's middle, then widened).
            float cx = 2f * (Mathf.Floor(pixel.x) + 0.5f) / w - 1f, cy = 2f * (Mathf.Floor(pixel.y) + 0.5f) / h - 1f;
            Matrix4x4 narrow = Matrix4x4.Scale(new Vector3(w / Size, h / Size, 1f)) * Matrix4x4.Translate(new Vector3(-cx, -cy, 0f));
            Color32[] read = Draw(cam, narrow * cam.projectionMatrix, renderers, Size, Size);
            if (read.Length == 0) return null;
            Color32 c = read[(Size / 2) * Size + Size / 2];              // (the middle pixel is the middle pixel either way up)
            int found = c.a > 127 ? c.r | (c.g << 8) | (c.b << 16) : 0;
            return found > 0 && found <= renderers.Count ? renderers[found - 1] : null;
        }

        /// <summary>The renderers drawn in their numbers with this projection into a picture of this size; its pixels
        /// as read (an empty array where nothing could be drawn).</summary>
        private static Color32[] Draw(Camera cam, Matrix4x4 projection, IList<Renderer> renderers, int width, int height)
        {
            RenderTexture target = RenderTexture.GetTemporary(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            var cmd = new CommandBuffer { name = "ModelPick" };
            cmd.SetRenderTarget(target);
            cmd.ClearRenderTarget(true, true, Color.clear);
            cmd.SetViewProjectionMatrices(cam.worldToCameraMatrix, projection);
            int drawn = 0;
            for (int i = 0; i < renderers.Count; i++)
            {
                Renderer r = renderers[i];
                if (r == null || !r.enabled || !r.gameObject.activeInHierarchy) continue;
                Material m = r.sharedMaterial;
                int pass = m != null ? m.FindPass("Pick") : -1;
                if (pass < 0) continue;
                int id = i + 1;
                // (a vector, not a colour: a colour would be taken from sRGB to linear on its way)
                cmd.SetGlobalVector(PickColourId, new Vector4((id & 255) / 255f, ((id >> 8) & 255) / 255f, ((id >> 16) & 255) / 255f, 1f));
                cmd.DrawRenderer(r, m, 0, pass);
                drawn++;
            }
            Color32[] pixels = new Color32[0];
            if (drawn > 0)
            {
                Graphics.ExecuteCommandBuffer(cmd);
                RenderTexture before = RenderTexture.active;
                RenderTexture.active = target;
                var read = new Texture2D(width, height, TextureFormat.RGBA32, false, true);
                read.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                pixels = read.GetPixels32();
                RenderTexture.active = before;
                Object.DestroyImmediate(read);
            }
            cmd.Release();
            RenderTexture.ReleaseTemporary(target);
            return pixels;
        }
    }
}
