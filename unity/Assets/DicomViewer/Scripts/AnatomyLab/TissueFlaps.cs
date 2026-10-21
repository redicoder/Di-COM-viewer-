using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// Skin flaps folded back beside scalpel cuts, evaluated exactly in the body shader (PhotoBody.shader, FlapSource)
    /// rather than baked into TissueWarp's displacement field: a flap moves tissue by centimetres right next to tissue
    /// that does not move, and a trilinearly filtered field blends those into displacements that point at random
    /// tissue (fragments sprayed around the flap). The flap geometry is TissueWarp's hinge: the tissue on one side of
    /// the cut, within the flap's width and down to its depth under the skin, rotates outward about a hinge line
    /// parallel to the cut; the space it left is empty, showing the tissue beneath.
    /// </summary>
    public class TissueFlaps : MonoBehaviour
    {
        public const int MaxFlaps = 4, MaxPoints = 32, CurveKnots = 8;

        [Tooltip("Fold angle when fully folded, degrees: 90 stands the flap up, 150-180 lays it back on the skin.")]
        [Range(10f, 180f)] public float maxFoldAngleDeg = 150f;

        private class Flap
        {
            public Vector3[] pointsMm;
            public Vector3 dir, outward, min, max;
            public float widthMm, depthMm, angle;
            public Vector3 t, nf, u;                                   // along the cut, fold direction, outward
            public readonly Vector2[] knots = new Vector2[CurveKnots];  // the cut's offset from its chord (u, nf)
        }

        private readonly List<Flap> flaps = new List<Flap>();
        private readonly Vector4[] ends0 = new Vector4[MaxFlaps], ends1 = new Vector4[MaxFlaps];
        private readonly Vector4[] info = new Vector4[MaxFlaps], dirs = new Vector4[MaxFlaps], outs = new Vector4[MaxFlaps],
            mins = new Vector4[MaxFlaps], maxs = new Vector4[MaxFlaps];
        private readonly Vector4[] curve = new Vector4[MaxFlaps * CurveKnots];
        private Material material;
        private Vector3 sizeMm;
        private bool dirty = true;

        public int Count => flaps.Count;

        public void Bind(Material m, Vector3 volumeSizeMm)
        {
            material = m;
            sizeMm = volumeSizeMm;
            dirty = true;
            Push();
        }

        /// <summary>
        /// A new flap beside a cut (texture coordinates), folding towards dirUvw (from the cut into the flap), flat
        /// for now. outwardMm: out of the body at the cut, in millimetre space. Returns its id, or -1 if MaxFlaps
        /// are already open.
        /// </summary>
        public int Begin(IReadOnlyList<Vector3> cutUvw, Vector3 dirUvw, Vector3 outwardMm, float widthMm, float depthMm)
        {
            if (flaps.Count >= MaxFlaps || cutUvw == null || cutUvw.Count < 2) return -1;
            int n = Mathf.Min(cutUvw.Count, MaxPoints);
            var p = new Vector3[n];
            for (int i = 0; i < n; i++)
            {
                int src = n == 1 ? 0 : Mathf.RoundToInt(i * (cutUvw.Count - 1) / (float)(n - 1));
                p[i] = Vector3.Scale(cutUvw[src], sizeMm);
            }
            Vector3 dir = Vector3.Scale(dirUvw, sizeMm);
            if (dir.sqrMagnitude < 1e-12f) return -1;
            var f = new Flap
            {
                pointsMm = p, dir = dir.normalized, outward = outwardMm.normalized, widthMm = widthMm, depthMm = depthMm,
                min = p[0], max = p[0],
            };
            foreach (Vector3 q in p)
            {
                f.min = Vector3.Min(f.min, q);
                f.max = Vector3.Max(f.max, q);
            }
            float reach = 2f * widthMm + depthMm + 2f;          // the folded flap can reach this far from the cut
            f.min -= Vector3.one * reach;
            f.max += Vector3.one * reach;
            Frame(f);
            flaps.Add(f);
            dirty = true;
            return flaps.Count - 1;
        }

        /// <summary>How far a flap is folded back, 0 (flat) .. 1 (maxFoldAngleDeg).</summary>
        public void SetFold(int id, float amount)
        {
            if (id < 0 || id >= flaps.Count) return;
            flaps[id].angle = Mathf.Clamp01(amount) * maxFoldAngleDeg * Mathf.Deg2Rad;
            dirty = true;
        }

        /// <summary>Removes a flap (one that was never folded, for instance).</summary>
        public void Remove(int id)
        {
            if (id < 0 || id >= flaps.Count) return;
            flaps.RemoveAt(id);
            dirty = true;
        }

        public void Clear()
        {
            flaps.Clear();
            dirty = true;
        }

        private void LateUpdate() => Push();

        private void Push()
        {
            if (!dirty || material == null) return;
            dirty = false;
            for (int i = 0; i < MaxFlaps; i++)
            {
                if (i >= flaps.Count)
                {
                    info[i] = Vector4.zero;
                    continue;
                }
                Flap f = flaps[i];
                ends0[i] = f.pointsMm[0];                       // the shader hinges each flap on its cut's two ends
                ends1[i] = f.pointsMm[f.pointsMm.Length - 1];
                info[i] = new Vector4(f.pointsMm.Length, f.widthMm, f.depthMm, f.angle);
                dirs[i] = f.dir;
                outs[i] = f.outward;
                mins[i] = f.min;
                maxs[i] = f.max;
                for (int k = 0; k < CurveKnots; k++) curve[i * CurveKnots + k] = f.knots[k];
            }
            material.SetVectorArray("_FlapA", ends0);
            material.SetVectorArray("_FlapB", ends1);
            material.SetVectorArray("_FlapInfo", info);
            material.SetVectorArray("_FlapDir", dirs);
            material.SetVectorArray("_FlapOut", outs);
            material.SetVectorArray("_FlapCurve", curve);
            material.SetFloat("_FlapCount", flaps.Count);
        }

        /// <summary>
        /// Where the tissue that was at uvw (before folding) is shown now: on a folded flap it has turned with it.
        /// For the Pull tool's hand, which holds the flap's edge.
        /// </summary>
        public Vector3 DisplayUvw(int id, Vector3 uvw)
        {
            if (id < 0 || id >= flaps.Count) return uvw;
            Flap f = flaps[id];
            Vector3 x = Vector3.Scale(uvw, sizeMm);
            Vector3 a = f.pointsMm[0], ab = f.pointsMm[f.pointsMm.Length - 1] - a;
            float s = Mathf.Clamp01(Vector3.Dot(x - a, ab) / Mathf.Max(ab.sqrMagnitude, 1e-6f));
            Vector2 bow = CurveAt(f, s);
            Vector3 hinge = a + ab * s + f.u * bow.x + f.nf * bow.y + f.nf * f.widthMm;
            Vector3 rel = x - hinge;
            float a2 = Vector3.Dot(rel, f.nf), b2 = Vector3.Dot(rel, f.u);
            float sn = Mathf.Sin(f.angle), cs = Mathf.Cos(f.angle);
            float ad = a2 * cs + b2 * sn, bd = -a2 * sn + b2 * cs;      // the fold (the shader undoes it)
            Vector3 xd = x + (ad - a2) * f.nf + (bd - b2) * f.u;
            return new Vector3(xd.x / sizeMm.x, xd.y / sizeMm.y, xd.z / sizeMm.z);
        }

        // The shader's frame (PhotoBody.shader, FlapSource) and the cut's offset from the straight line between its
        // ends at s = k/8 (k = 1..7): x along the outward direction U, y along the fold direction Nf.
        private static void Frame(Flap f)
        {
            Vector3[] p = f.pointsMm;
            Vector3 a = p[0], ab = p[p.Length - 1] - a;
            float len2 = Mathf.Max(ab.sqrMagnitude, 1e-6f);
            f.t = ab / Mathf.Sqrt(len2);
            Vector3 nf = f.dir - Vector3.Dot(f.dir, f.t) * f.t;
            f.nf = nf.sqrMagnitude > 1e-8f ? nf.normalized : Vector3.zero;
            f.u = Vector3.Cross(f.t, f.nf);
            if (Vector3.Dot(f.u, f.outward) < 0f) f.u = -f.u;
            for (int k = 0; k < CurveKnots; k++)
            {
                f.knots[k] = Vector2.zero;
                if (k == 0) continue;
                float sk = k / (float)CurveKnots;
                // The stroke point where the line's parameter reaches sk (strokes may wander back; take the first).
                for (int j = 0; j + 1 < p.Length; j++)
                {
                    float s0 = Vector3.Dot(p[j] - a, ab) / len2, s1 = Vector3.Dot(p[j + 1] - a, ab) / len2;
                    if ((sk - s0) * (sk - s1) > 0f || Mathf.Approximately(s0, s1)) continue;
                    Vector3 q = Vector3.Lerp(p[j], p[j + 1], (sk - s0) / (s1 - s0)) - (a + ab * sk);
                    f.knots[k] = new Vector2(Vector3.Dot(q, f.u), Vector3.Dot(q, f.nf));
                    break;
                }
            }
        }

        private static Vector2 CurveAt(Flap f, float s)
        {
            float u = Mathf.Clamp01(s) * CurveKnots;
            int k = Mathf.Min((int)u, CurveKnots - 1);
            Vector2 c0 = k == 0 ? Vector2.zero : f.knots[k];
            Vector2 c1 = k + 1 >= CurveKnots ? Vector2.zero : f.knots[k + 1];
            return Vector2.Lerp(c0, c1, u - k);
        }

        /// <summary>For editor snapshots, which have no LateUpdate.</summary>
        public void PushNow()
        {
            dirty = true;
            Push();
        }
    }
}
