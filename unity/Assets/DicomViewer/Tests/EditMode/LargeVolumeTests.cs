using NUnit.Framework;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

namespace DicomViewer.Tests
{
    /// <summary>A whole body at 1.3 mm is a 460 MB colour volume: does it reach the GPU whole?</summary>
    public class LargeVolumeTests
    {
        private static Vector4[] Probe(Texture tex, Vector3[] uvw)
        {
            var cs = Resources.Load<ComputeShader>("Probe3D");
            Assert.That(cs, Is.Not.Null);
            int k = cs.FindKernel("Probe");
            var inBuf = new ComputeBuffer(uvw.Length, 12);
            var outBuf = new ComputeBuffer(uvw.Length, 16);
            inBuf.SetData(uvw);
            cs.SetTexture(k, "_Tex", tex);
            cs.SetBuffer(k, "_Uvw", inBuf);
            cs.SetBuffer(k, "_Out", outBuf);
            cs.Dispatch(k, uvw.Length, 1, 1);
            var result = new Vector4[uvw.Length];
            outBuf.GetData(result);
            inBuf.Release();
            outBuf.Release();
            return result;
        }

        [TestCase(290, 939, 167, false)]   // the 2 mm body, 182 MB
        [TestCase(436, 939, 282, false)]   // the 1.3 mm body, 462 MB
        [TestCase(436, 939, 282, true)]    // as the photographs are stored: sRGB
        [TestCase(282, 225, 366, true)]    // the head, sRGB
        public void VolumeUploadsWhole(int w, int h, int d, bool srgb)
        {
            var data = new byte[w * h * d * 4];
            for (int z = 0; z < d; z++)
            {
                byte v = (byte)(20 + (z * 7) % 200);               // a value that tells the depth apart
                int from = z * h * w * 4, to = from + h * w * 4;
                for (int i = from; i < to; i += 4) { data[i] = v; data[i + 1] = 255; data[i + 2] = 0; data[i + 3] = 255; }
            }
            var tex = new Texture3D(w, h, d, srgb ? GraphicsFormat.R8G8B8A8_SRGB : GraphicsFormat.R8G8B8A8_UNorm, TextureCreationFlags.None) { filterMode = FilterMode.Point };
            try
            {
                tex.SetPixelData(data, 0);
                tex.Apply(false, true);
                // A grid of probes through the whole volume, not just one line.
                const int G = 7;
                var uvw = new Vector3[G * G * G];
                var zs = new int[G * G * G];
                for (int i = 0; i < uvw.Length; i++)
                {
                    int a = i % G, b = (i / G) % G, c = i / (G * G);
                    zs[i] = Mathf.Clamp(Mathf.RoundToInt((c + 0.5f) / G * d), 0, d - 1);
                    uvw[i] = new Vector3((a + 0.5f) / G, (b + 0.5f) / G, (zs[i] + 0.5f) / d);
                }
                Vector4[] got = Probe(tex, uvw);
                int wrong = 0;
                string first = "";
                for (int i = 0; i < uvw.Length; i++)
                {
                    float want = (20 + (zs[i] * 7) % 200) / 255f;
                    if (srgb) want = Mathf.GammaToLinearSpace(want);
                    if (Mathf.Abs(got[i].x - want) > 0.01f || Mathf.Abs(got[i].y - 1f) > 0.01f)
                    {
                        wrong++;
                        if (first == "") first = $"at {uvw[i]} (z {zs[i]} of {d}) got {got[i]}, wanted x {want:F3}";
                    }
                }
                Assert.That(wrong, Is.EqualTo(0), $"{wrong} of {uvw.Length} probes wrong in a {w * h * d * 4 / 1048576} MB volume; first {first}");
            }
            finally
            {
                Object.DestroyImmediate(tex);
            }
        }
    }
}
