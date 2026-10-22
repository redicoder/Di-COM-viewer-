using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// A gloved right hand as one smooth surface: fingers, thumb, palm and wrist are signed-distance primitives
    /// joined with a soft union (so knuckles swell and the webbing between the fingers is continuous), meshed with
    /// surface nets on a 1.5 mm grid. Metres; the pinch (between thumb and index tip) is at the origin, x towards
    /// the little finger, y the back of the hand, z where the fingers point. Built once per pose at start.
    /// </summary>
    public static class HandMesh
    {
        private struct Cap { public Vector3 a, b; public float ra, rb; }

        private static readonly List<Cap> caps = new List<Cap>();
        private static Vector3 palmCentre, palmHalf, thenarCentre, thenarHalf;
        private static Quaternion palmRot, thenarRot;

        /// <summary>
        /// The glove's surface for a pinch `sep` metres wide: vertices and triangles (shared vertices, so the normals
        /// come out smooth), the pinch point it was built round, and capsules for its shadow on the body.
        /// </summary>
        public static void Glove(float sep, List<Vector3> vertices, List<int> triangles, out Vector3 pinch,
            out List<(Vector3 a, Vector3 b, float r)> shadow)
        {
            caps.Clear();
            var chains = new List<Vector3[]>();
            var radii = new List<float[]>();

            // Fingers: knuckle, spread (deg about y), segment lengths, flexion of each joint (deg), radii (gloved).
            void Finger(Vector3 mcp, float spread, Vector3 len, Vector3 flex, Vector4 r)
            {
                var pts = new Vector3[4];
                pts[0] = mcp;
                Quaternion q = Quaternion.Euler(0f, spread, 0f);
                float bend = 0f;
                for (int i = 0; i < 3; i++)
                {
                    bend += flex[i];
                    pts[i + 1] = pts[i] + q * (Quaternion.Euler(bend, 0f, 0f) * Vector3.forward) * len[i];
                }
                chains.Add(pts);
                r *= 0.86f;
                radii.Add(new[] { r.x, r.y, r.z, r.w });
            }
            Finger(new Vector3(-0.024f, 0f, 0.088f), -6f, new Vector3(0.040f, 0.024f, 0.019f), new Vector3(42f, 33f, 15f), new Vector4(0.0098f, 0.0088f, 0.0080f, 0.0074f));
            Finger(new Vector3(-0.004f, 0.003f, 0.092f), 0f, new Vector3(0.044f, 0.028f, 0.020f), new Vector3(58f, 72f, 40f), new Vector4(0.0100f, 0.0090f, 0.0082f, 0.0076f));
            Finger(new Vector3(0.014f, 0.001f, 0.087f), 5f, new Vector3(0.041f, 0.026f, 0.019f), new Vector3(64f, 80f, 45f), new Vector4(0.0095f, 0.0086f, 0.0078f, 0.0072f));
            Finger(new Vector3(0.029f, -0.004f, 0.076f), 11f, new Vector3(0.032f, 0.019f, 0.017f), new Vector3(68f, 85f, 45f), new Vector4(0.0086f, 0.0077f, 0.0070f, 0.0065f));

            // Thumb: metacarpal from the wrist, then two bones reaching (two-bone IK) to face the index tip.
            Vector3 indexTip = chains[0][3];
            Vector3 cmc = new Vector3(-0.020f, -0.010f, 0.020f);
            Vector3 m1 = cmc + new Vector3(-0.35f, -0.55f, 0.75f).normalized * 0.045f;
            Vector3 target = indexTip + new Vector3(-0.003f, 0f, -sep);
            Vector3 joint = TwoBone(m1, target, 0.037f, 0.031f, new Vector3(-1f, 0.6f, 0f));
            Vector3 thumbTip = joint + (target - joint).normalized * 0.031f;
            chains.Add(new[] { cmc, m1, joint, thumbTip });
            radii.Add(new[] { 0.0112f, 0.0094f, 0.0086f, 0.0078f });

            pinch = (indexTip + thumbTip) * 0.5f;
            for (int c = 0; c < chains.Count; c++)
                for (int i = 0; i < 3; i++)
                    caps.Add(new Cap { a = chains[c][i] - pinch, b = chains[c][i + 1] - pinch, ra = radii[c][i], rb = radii[c][i + 1] });
            // Wrist and the knuckle row.
            caps.Add(new Cap { a = new Vector3(0.003f, 0f, 0.012f) - pinch, b = new Vector3(0.003f, 0.004f, -0.065f) - pinch, ra = 0.027f, rb = 0.031f });
            caps.Add(new Cap { a = chains[0][0] - pinch, b = chains[3][0] - pinch, ra = 0.0105f, rb = 0.0095f });
            palmCentre = new Vector3(0.003f, -0.001f, 0.050f) - pinch;
            palmHalf = new Vector3(0.034f, 0.009f, 0.040f);
            palmRot = Quaternion.Inverse(Quaternion.Euler(0f, 0f, -6f));
            thenarCentre = new Vector3(-0.022f, -0.009f, 0.036f) - pinch;
            thenarHalf = new Vector3(0.012f, 0.011f, 0.026f);
            thenarRot = Quaternion.Inverse(Quaternion.Euler(-20f, -30f, 0f));

            shadow = new List<(Vector3, Vector3, float)>
            {
                (new Vector3(0.003f, 0f, 0f) - pinch, new Vector3(0f, 0.03f, -0.30f) - pinch, 0.035f),
                (new Vector3(0.003f, 0f, 0.02f) - pinch, chains[1][0] - pinch, 0.03f),
                (chains[0][0] - pinch, chains[0][3] - pinch, 0.009f),
                (chains[4][1] - pinch, chains[4][3] - pinch, 0.0095f),
                (chains[1][0] - pinch, chains[1][2] - pinch, 0.0095f),
                (chains[2][0] - pinch, chains[3][2] - pinch, 0.0095f),
            };

            // Mesh the surface: a grid round everything, 1.5 mm cells.
            Vector3 lo = new Vector3(float.MaxValue, float.MaxValue, float.MaxValue), hi = -lo;
            foreach (Cap c in caps)
            {
                float r = Mathf.Max(c.ra, c.rb) + 0.012f;
                lo = Vector3.Min(lo, Vector3.Min(c.a, c.b) - Vector3.one * r);
                hi = Vector3.Max(hi, Vector3.Max(c.a, c.b) + Vector3.one * r);
            }
            lo.z = Mathf.Max(lo.z, -0.075f - pinch.z);                      // the sleeve takes over at the wrist
            SurfaceNets(lo, hi, 0.0015f, vertices, triangles);
        }

        // ------------------------------------------------------------------------------------------- the distance

        private static float Distance(Vector3 p)
        {
            const float k = 0.0065f;                                        // how softly the parts blend
            float d = float.MaxValue;
            foreach (Cap c in caps) d = SmoothMin(d, RoundCone(p, c), k);
            d = SmoothMin(d, RoundBox(palmRot * (p - palmCentre), palmHalf, 0.012f), k);
            d = SmoothMin(d, Ellipsoid(thenarRot * (p - thenarCentre), thenarHalf), k);
            return d;
        }

        private static float SmoothMin(float a, float b, float k)
        {
            float h = Mathf.Clamp01(0.5f + 0.5f * (b - a) / k);
            return Mathf.Lerp(b, a, h) - k * h * (1f - h);
        }

        // A capsule whose radius runs from ra at a to rb at b.
        private static float RoundCone(Vector3 p, Cap c)
        {
            Vector3 ab = c.b - c.a;
            float t = Mathf.Clamp01(Vector3.Dot(p - c.a, ab) / Mathf.Max(ab.sqrMagnitude, 1e-12f));
            return Vector3.Distance(p, c.a + ab * t) - Mathf.Lerp(c.ra, c.rb, t);
        }

        private static float RoundBox(Vector3 p, Vector3 half, float r)
        {
            Vector3 q = new Vector3(Mathf.Abs(p.x), Mathf.Abs(p.y), Mathf.Abs(p.z)) - half + Vector3.one * r;
            Vector3 m = Vector3.Max(q, Vector3.zero);
            return m.magnitude + Mathf.Min(Mathf.Max(q.x, Mathf.Max(q.y, q.z)), 0f) - r;
        }

        private static float Ellipsoid(Vector3 p, Vector3 half)
        {
            Vector3 q = new Vector3(p.x / half.x, p.y / half.y, p.z / half.z);
            float k0 = q.magnitude;
            float k1 = new Vector3(p.x / (half.x * half.x), p.y / (half.y * half.y), p.z / (half.z * half.z)).magnitude;
            return k1 > 1e-9f ? k0 * (k0 - 1f) / k1 : -Mathf.Min(half.x, Mathf.Min(half.y, half.z));
        }

        private static Vector3 TwoBone(Vector3 a, Vector3 b, float l1, float l2, Vector3 pole)
        {
            Vector3 ab = b - a;
            float d = Mathf.Clamp(ab.magnitude, Mathf.Abs(l1 - l2) + 1e-4f, (l1 + l2) * 0.999f);
            Vector3 dir = ab.normalized;
            float along = (l1 * l1 - l2 * l2 + d * d) / (2f * d);
            float h = Mathf.Sqrt(Mathf.Max(l1 * l1 - along * along, 0f));
            Vector3 side = pole - Vector3.Dot(pole, dir) * dir;
            side = side.sqrMagnitude > 1e-8f ? side.normalized : Vector3.Cross(dir, Vector3.right).normalized;
            return a + dir * along + side * h;
        }

        // ------------------------------------------------------------------------------------------- surface nets

        /// <summary>
        /// Naive surface nets: one vertex per grid cell the surface crosses (at the mean of its edge crossings), a
        /// quad across every grid edge whose ends have different signs. Smooth, watertight, no lookup tables.
        /// </summary>
        private static void SurfaceNets(Vector3 lo, Vector3 hi, float cell, List<Vector3> vertices, List<int> triangles)
        {
            int nx = Mathf.CeilToInt((hi.x - lo.x) / cell) + 1, ny = Mathf.CeilToInt((hi.y - lo.y) / cell) + 1, nz = Mathf.CeilToInt((hi.z - lo.z) / cell) + 1;
            var f = new float[nx * ny * nz];
            int I(int x, int y, int z) => (z * ny + y) * nx + x;
            for (int z = 0; z < nz; z++)
            for (int y = 0; y < ny; y++)
            for (int x = 0; x < nx; x++)
                f[I(x, y, z)] = Distance(lo + new Vector3(x, y, z) * cell);

            // A vertex for every cell the surface passes through.
            var cellVertex = new int[(nx - 1) * (ny - 1) * (nz - 1)];
            int C(int x, int y, int z) => (z * (ny - 1) + y) * (nx - 1) + x;
            int[,] edges =
            {
                { 0, 1 }, { 2, 3 }, { 4, 5 }, { 6, 7 }, { 0, 2 }, { 1, 3 }, { 4, 6 }, { 5, 7 }, { 0, 4 }, { 1, 5 }, { 2, 6 }, { 3, 7 },
            };
            var corner = new Vector3Int[8];
            for (int i = 0; i < 8; i++) corner[i] = new Vector3Int(i & 1, (i >> 1) & 1, (i >> 2) & 1);
            for (int z = 0; z < nz - 1; z++)
            for (int y = 0; y < ny - 1; y++)
            for (int x = 0; x < nx - 1; x++)
            {
                Vector3 sum = Vector3.zero;
                int count = 0;
                for (int e = 0; e < 12; e++)
                {
                    Vector3Int a = corner[edges[e, 0]], b = corner[edges[e, 1]];
                    float fa = f[I(x + a.x, y + a.y, z + a.z)], fb = f[I(x + b.x, y + b.y, z + b.z)];
                    if ((fa < 0f) == (fb < 0f)) continue;
                    float t = fa / (fa - fb);
                    sum += (Vector3)a + ((Vector3)(b - a)) * t;
                    count++;
                }
                if (count == 0) { cellVertex[C(x, y, z)] = -1; continue; }
                cellVertex[C(x, y, z)] = vertices.Count;
                vertices.Add(lo + (new Vector3(x, y, z) + sum / count) * cell);
            }

            // A quad round every grid edge the surface crosses, wound to face outward (from inside to outside).
            void Quad(int c0, int c1, int c2, int c3, bool flip)
            {
                if (c0 < 0 || c1 < 0 || c2 < 0 || c3 < 0) return;
                if (flip) { triangles.Add(c0); triangles.Add(c2); triangles.Add(c1); triangles.Add(c0); triangles.Add(c3); triangles.Add(c2); }
                else { triangles.Add(c0); triangles.Add(c1); triangles.Add(c2); triangles.Add(c0); triangles.Add(c2); triangles.Add(c3); }
            }
            for (int z = 1; z < nz - 1; z++)
            for (int y = 1; y < ny - 1; y++)
            for (int x = 1; x < nx - 1; x++)
            {
                float f0 = f[I(x, y, z)];
                bool inside = f0 < 0f;
                if (x + 1 < nx && (f[I(x + 1, y, z)] < 0f) != inside)               // edge along x: cells round it differ in y, z
                    Quad(cellVertex[C(x, y - 1, z - 1)], cellVertex[C(x, y, z - 1)], cellVertex[C(x, y, z)], cellVertex[C(x, y - 1, z)], inside);
                if (y + 1 < ny && (f[I(x, y + 1, z)] < 0f) != inside)
                    Quad(cellVertex[C(x - 1, y, z - 1)], cellVertex[C(x - 1, y, z)], cellVertex[C(x, y, z)], cellVertex[C(x, y, z - 1)], inside);
                if (z + 1 < nz && (f[I(x, y, z + 1)] < 0f) != inside)
                    Quad(cellVertex[C(x - 1, y - 1, z)], cellVertex[C(x, y - 1, z)], cellVertex[C(x, y, z)], cellVertex[C(x - 1, y, z)], inside);
            }
        }
    }
}
