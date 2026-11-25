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
            Matrix4x4 projection = narrow * cam.projectionMatrix;

            RenderTexture target = RenderTexture.GetTemporary(Size, Size, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
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
            int found = 0;
            if (drawn > 0)
            {
                Graphics.ExecuteCommandBuffer(cmd);
                RenderTexture before = RenderTexture.active;
                RenderTexture.active = target;
                var read = new Texture2D(Size, Size, TextureFormat.RGBA32, false, true);
                read.ReadPixels(new Rect(0, 0, Size, Size), 0, 0);
                Color32 c = read.GetPixel(Size / 2, Size / 2);
                RenderTexture.active = before;
                Object.DestroyImmediate(read);
                if (c.a > 127) found = c.r | (c.g << 8) | (c.b << 16);
            }
            cmd.Release();
            RenderTexture.ReleaseTemporary(target);
            return found > 0 && found <= renderers.Count ? renderers[found - 1] : null;
        }
    }
}
