using System;
using System.Collections.Generic;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>What a skin sheet needs to know about the body it lies on, in body millimetres (texture axes).</summary>
    public interface ITissueField
    {
        /// <summary>Tissue, 0..1 (trilinear).</summary>
        float Alpha(Vector3 mm);

        /// <summary>Depth below the outer skin, mm; 0 outside the body.</summary>
        float SkinDepth(Vector3 mm);

        /// <summary>The same depth on its voxel grid, for the physics job.</summary>
        SkinDepthGrid Grid { get; }
    }

    /// <summary>
    /// A patch of skin with the fat under it, simulated as a thick elastic sheet: what a real body does when it is
    /// cut and pulled. Two layers of particles (the skin's surface and the bottom of the fat) on a 64 x 64 grid over
    /// the body, joined by XPBD distance constraints whose stiffness comes from the tissue's elastic modulus
    /// (k = E A / L): stiff dermis in tension (~1 MPa) over soft fat (~3 kPa); freed tissue keeps its shape by shape
    /// matching (Mueller et al. 2005) so it bends like skin rather than folding up like cloth. The loose tissue under
    /// the fat holds the sheet to the fascia: it slides a little, but lifted off it tears, so pulling peels the skin
    /// off progressively.
    ///
    /// Scalpel cuts split the sheet: an edge of the grid that the blade crossed carries no force, and the cells on
    /// it vanish (they are the incision). So a single cut only lets its edge be lifted (the skin beyond the cut's ends
    /// holds it); a U-shaped cut lets a flap fold back about its uncut base; a closed cut frees an island that, once its
    /// fat has let go, comes away in the hand and falls under gravity, onto the face, off it and onto the tray. Freed
    /// skin shrinks back a little (it lived stretched: an excised piece is smaller than its wound). Units are mm, g and
    /// s, so 1 Pa = 1 g/(mm s^2), and gravity is 9810 mm/s^2.
    ///
    /// Nodes far from anything happening are pinned to their place (no cost); nodes near movement wake up held by
    /// their fat (Adhered), and those whose fat has torn are free (Peeled). The body hides its own tissue wherever the
    /// sheet has woken up (PhotoBody.shader reads HiddenMap) and the sheet draws it instead, coloured from the photos
    /// at the place each bit of tissue came from.
    /// </summary>
    public sealed class TissueSheet : IDisposable
    {
        public const int N = 64;
        public enum Node : byte { Invalid, Pinned, Adhered, Peeled, Gone }

        // ------------------------------------------------------------------------------------------- material
        public float skinModulus = 1.0e6f;        // Pa: dermis in tension
        // Pa: the fat under the dermis and the links through it. Skin's stress-strain curve is J-shaped: stiff when
        // pulled taut (the dermis above), soft at the small strains of bending (~0.1-0.2 MPa), so a flap droops about
        // its base. What keeps a freed piece from folding up like cloth is shape matching (below), not this.
        public float deepModulus = 3.0e3f;
        // The loose areolar tissue holding the fat to the fascia beneath: the weakest layer, where a dissection plane
        // opens. It is anisotropic. Along the fascia it is soft and lets skin slide (you can move the skin of a
        // forehead a centimetre) until it tears at tearMm; it cannot be lifted off the fascia without tearing, so
        // its normal hold is stiff and gives at liftMm. Pa, effective, and mm.
        public float adhesionNormalModulus = 1.0e4f;
        public float adhesionShearModulus = 1.0e3f;
        public float liftMm = 1.5f;
        public float shearTearMm = 4.5f;          // the fat itself tears sheared this far through its thickness (strain ~0.9)
        public bool rePin = true;                 // adhered skin that stays still goes back to sleep
        // s^2/g, the dermis's resistance to bending (D = E t^3 / 12 ~ 7e-4 N m per m for 2 mm of dermis): a 2 cm
        // flap droops under its own weight, so this is soft; freed tissue keeps its shape by shape matching instead.
        public float skinBendCompliance = 6e-4f;
        public float shapeStiffness = 0.12f;      // per substep: how firmly freed tissue keeps its shape
        public float maxSpeed = 3000f;            // mm/s: far above anything dropped tissue reaches
        public float density = 1.0e-3f;           // g/mm^3 (tissue ~ water)
        public float skinThicknessMm = 2f;
        public float tearMm = 3f;                 // the fat's attachment tears once slid this far along the fascia
        public float retraction = 0.06f;          // freed skin shrinks back by this fraction (it lived stretched)
        public float retractSeconds = 0.5f;
        public float friction = 0.6f;
        public float damping = 3f;                // per second: tissue is viscous
        public float maxHandSpeed = 600f;         // mm/s: how fast held tissue can follow the finger
        public int substeps = 8;
        public int iterations = 3;                // constraint passes per substep

        // ------------------------------------------------------------------------------------------- geometry
        public readonly float H, T;                     // node spacing, thickness (mm)
        public readonly Vector3 Origin, E1, E2, E3;     // node (i, j) lies over Origin + E1 i H + E2 j H; E3 out of the skin
        public readonly Node[] State = new Node[N * N];
        public readonly float[] RestHeight = new float[N * N];
        private readonly Vector3[] restTop = new Vector3[N * N], restBot = new Vector3[N * N], restN = new Vector3[N * N];
        private readonly bool[] border = new bool[N * N];
        private readonly float[] ramp = new float[N * N];          // 0..1: how far a peeled node has shrunk back
        private readonly float[] calm = new float[N * N];          // seconds an adhered node has been still

        // Particles: node * 2 (skin surface) and node * 2 + 1 (bottom of the fat).
        public readonly Vector3[] X = new Vector3[2 * N * N];
        private readonly Vector3[] vel = new Vector3[2 * N * N];
        private readonly float[] w = new float[2 * N * N];
        private readonly float mass;

        // Grid edges: horizontal (i,j)-(i+1,j), vertical (i,j)-(i,j+1), one diagonal per cell (alternating).
        private const int HCount = (N - 1) * N, VCount = N * (N - 1), DCount = (N - 1) * (N - 1);
        private const int EdgeCount = HCount + VCount + DCount;
        private readonly int[] ea = new int[EdgeCount], eb = new int[EdgeCount];
        private readonly bool[] edgeCut = new bool[EdgeCount], edgeBad = new bool[EdgeCount];
        private readonly byte[] edgeTris = new byte[EdgeCount];     // existing triangles on this edge (0..2)

        // Two triangles per cell.
        private const int TriCount = 2 * (N - 1) * (N - 1);
        private readonly int[] ta = new int[TriCount], tb = new int[TriCount], tc = new int[TriCount];
        private readonly int[] te0 = new int[TriCount], te1 = new int[TriCount], te2 = new int[TriCount];
        private readonly bool[] triExists = new bool[TriCount], triShown = new bool[TriCount], triFlip = new bool[TriCount];

        // Constraints, rebuilt when the topology or the set of moving nodes changes.
        private int[] ca = new int[4096], cb = new int[4096];
        private float[] crest = new float[4096], calpha = new float[4096];
        private int ccount;
        private readonly List<int> adhered = new List<int>(), moving = new List<int>();

        // Shape matching (Mueller et al. 2005): overlapping regions of freed tissue, two nodes around every other node,
        // joined only through intact skin. Each keeps its rest shape up to a rotation: the dermis's bending stiffness,
        // which distance constraints alone only reach after many iterations. Where the freed tissue meets skin still
        // held by its fat, only distance constraints join them, so a flap turns about its base.
        private readonly List<int> clStart = new List<int>(), clMembers = new List<int>();
        private readonly List<Vector3> clRest = new List<Vector3>();
        private readonly List<Quaternion> clRot = new List<Quaternion>();
        private int[] clStartA = new int[1], clMembersA = new int[0];
        private readonly List<int> clCentre = new List<int>();
        private readonly quaternion[] nodeRot = new quaternion[N * N];    // each region's last rotation, by its centre
        private Vector3[] clRestA = new Vector3[0];

        // The hand: held particles and where they are going.
        private readonly List<int> held = new List<int>();
        private readonly List<Vector3> heldOffset = new List<Vector3>();
        private Vector3 handGoal, handNow;
        private int heldCentre = -1;

        private readonly int[] island = new int[N * N];
        private bool dirty = true;
        private float quiet;
        private Vector3 sleepGravity;

        public bool Asleep { get; private set; }
        public bool TopologyChanged { get; private set; } = true;   // the mesh's triangles and walls need rebuilding
        public bool HiddenChanged { get; private set; } = true;     // HiddenMap changed
        public int HeldNode => heldCentre;
        public bool Holding => held.Count > 0;

        /// <summary>
        /// The table or tray the body lies on, a plane in body mm: xyz its unit normal (out of the table, towards the
        /// body), w its offset (dot(x, xyz) = w on its surface). w = -infinity: no table.
        /// </summary>
        public Vector4 Table = new Vector4(0f, 1f, 0f, float.NegativeInfinity);

        /// <summary>Whether the body's own tissue at a point has been taken over by a sheet (this or another).</summary>
        public Func<Vector3, bool> HiddenAt;

        private readonly ITissueField field;

        private TissueSheet(ITissueField field, Vector3 origin, Vector3 e1, Vector3 e2, Vector3 e3, float h, float t)
        {
            this.field = field;
            Origin = origin; E1 = e1; E2 = e2; E3 = e3; H = h; T = t;
            mass = density * h * h * t * 0.5f;
            HiddenAt = p => HiddenHere(p);
            for (int j = 0; j < N; j++)
            for (int i = 0; i < N; i++)
            {
                int n = j * N + i;
                if (i < N - 1) { int e = j * (N - 1) + i; ea[e] = n; eb[e] = n + 1; }
                if (j < N - 1) { int e = HCount + j * N + i; ea[e] = n; eb[e] = n + N; }
                if (i < N - 1 && j < N - 1)
                {
                    int e = HCount + VCount + j * (N - 1) + i;
                    bool even = ((i + j) & 1) == 0;
                    ea[e] = even ? n : n + 1;
                    eb[e] = even ? n + N + 1 : n + N;
                    int c = (j * (N - 1) + i) * 2;
                    int h0 = j * (N - 1) + i, h1 = (j + 1) * (N - 1) + i, v0 = HCount + j * N + i, v1 = HCount + j * N + i + 1;
                    if (even)
                    {
                        SetTri(c, n, n + 1, n + N + 1, h0, v1, e);
                        SetTri(c + 1, n, n + N + 1, n + N, e, h1, v0);
                    }
                    else
                    {
                        SetTri(c, n, n + 1, n + N, h0, e, v0);
                        SetTri(c + 1, n + 1, n + N + 1, n + N, v1, h1, e);
                    }
                }
                border[n] = i == 0 || j == 0 || i == N - 1 || j == N - 1;
            }
        }

        private void SetTri(int t, int a, int b, int c, int e0, int e1, int e2)
        {
            ta[t] = a; tb[t] = b; tc[t] = c; te0[t] = e0; te1[t] = e1; te2[t] = e2;
        }

        /// <summary>
        /// A sheet centred on a point of the skin (body mm) with its outward normal: each node finds the skin by
        /// looking down the normal. Nodes where `excluded` says another sheet already owns the skin are left out.
        /// </summary>
        public static TissueSheet Create(ITissueField field, Vector3 centreMm, Vector3 normalMm, float spacingMm,
            float thicknessMm, Func<Vector3, bool> excluded = null)
        {
            Vector3 e3 = normalMm.normalized;
            Vector3 e1 = Vector3.right - Vector3.Dot(Vector3.right, e3) * e3;
            if (e1.sqrMagnitude < 0.1f) e1 = Vector3.up - Vector3.Dot(Vector3.up, e3) * e3;
            e1.Normalize();
            Vector3 e2 = Vector3.Cross(e3, e1).normalized;
            Vector3 origin = centreMm - (e1 + e2) * ((N - 1) * 0.5f * spacingMm);
            var s = new TissueSheet(field, origin, e1, e2, e3, spacingMm, thicknessMm);
            s.FindSkin(excluded);
            return s;
        }

        private void FindSkin(Func<Vector3, bool> excluded)
        {
            const float above = 30f, below = 45f, step = 0.8f;
            for (int n = 0; n < N * N; n++)
            {
                State[n] = Node.Invalid;
                Vector3 b = Origin + E1 * ((n % N) * H) + E2 * ((n / N) * H);
                Vector3 outside = b + E3 * above, inside = outside;
                bool found = false;
                for (float s = 0f; s <= above + below; s += step)
                {
                    inside = b + E3 * (above - s);
                    if (field.Alpha(inside) > 0.5f) { found = true; break; }
                    outside = inside;
                }
                if (!found) continue;
                for (int k = 0; k < 7; k++)
                {
                    Vector3 m = (outside + inside) * 0.5f;
                    if (field.Alpha(m) > 0.5f) inside = m; else outside = m;
                }
                Vector3 p = inside;
                Vector3 nrm = Outward(p);
                if (Vector3.Dot(nrm, E3) < 0.25f) continue;          // too steep to lie over the grid
                if (excluded != null && excluded(p)) continue;
                restTop[n] = p;
                restN[n] = nrm;
                restBot[n] = p - nrm * T;
                RestHeight[n] = Vector3.Dot(p - Origin, E3);
                State[n] = Node.Pinned;
                X[2 * n] = p;
                X[2 * n + 1] = restBot[n];
            }
            for (int e = 0; e < EdgeCount; e++)
            {
                int a = ea[e], b = eb[e];
                if (a == b) continue;
                // Skin that is not one surface over the grid (a step, the nose's side) is not joined.
                edgeBad[e] = State[a] == Node.Invalid || State[b] == Node.Invalid || Mathf.Abs(RestHeight[a] - RestHeight[b]) > 2.5f * H;
            }
            dirty = true;
        }

        // Outward normal of the body at p, from the tissue's gradient.
        private Vector3 Outward(Vector3 p)
        {
            const float e = 0.7f;
            var g = new Vector3(field.Alpha(p + Vector3.right * e) - field.Alpha(p - Vector3.right * e),
                                field.Alpha(p + Vector3.up * e) - field.Alpha(p - Vector3.up * e),
                                field.Alpha(p + Vector3.forward * e) - field.Alpha(p - Vector3.forward * e));
            return g.sqrMagnitude > 1e-10f ? -g.normalized : E3;
        }

        // ------------------------------------------------------------------------------------------ queries

        public Vector2 GridOf(Vector3 mm) => new Vector2(Vector3.Dot(mm - Origin, E1) / H, Vector3.Dot(mm - Origin, E2) / H);

        /// <summary>The node whose rest place is nearest a point, or -1.</summary>
        public int NearestNode(Vector3 mm, float maxMm = 4f)
        {
            Vector2 g = GridOf(mm);
            int best = -1;
            float bestD = maxMm * maxMm;
            for (int dj = -2; dj <= 3; dj++)
            for (int di = -2; di <= 3; di++)
            {
                int i = Mathf.FloorToInt(g.x) + di, j = Mathf.FloorToInt(g.y) + dj;
                if (i < 0 || j < 0 || i >= N || j >= N) continue;
                int n = j * N + i;
                if (State[n] == Node.Invalid || State[n] == Node.Gone) continue;
                float d = (restTop[n] - mm).sqrMagnitude;
                if (d < bestD) { bestD = d; best = n; }
            }
            return best;
        }

        /// <summary>Does the point lie over this sheet's skin (grid and height), within its thickness of the surface?</summary>
        public bool Covers(Vector3 mm, float marginNodes = 2f)
        {
            Vector2 g = GridOf(mm);
            if (g.x < marginNodes || g.y < marginNodes || g.x > N - 1 - marginNodes || g.y > N - 1 - marginNodes) return false;
            int n = Mathf.RoundToInt(g.y) * N + Mathf.RoundToInt(g.x);
            if (State[n] == Node.Invalid) return false;
            float hz = Vector3.Dot(mm - Origin, E3);
            return hz <= RestHeight[n] + 2f && hz >= RestHeight[n] - T - 3f;
        }

        /// <summary>Is the body's tissue at this point (body mm) taken over by this sheet?</summary>
        public bool HiddenHere(Vector3 mm)
        {
            Vector2 g = GridOf(mm);
            int i = Mathf.RoundToInt(g.x), j = Mathf.RoundToInt(g.y);
            if (i < 0 || j < 0 || i >= N || j >= N) return false;
            int n = j * N + i;
            if (State[n] == Node.Invalid || State[n] == Node.Pinned) return false;
            float hz = Vector3.Dot(mm - Origin, E3);
            return hz <= RestHeight[n] + 1f && hz >= RestHeight[n] - T - 1f;
        }

        /// <summary>Per node: hidden (1 where the sheet has taken over the body's tissue) and the skin's rest height.</summary>
        public void FillHiddenMap(ushort[] rg)
        {
            for (int n = 0; n < N * N; n++)
            {
                bool hidden = State[n] == Node.Adhered || State[n] == Node.Peeled || State[n] == Node.Gone;
                rg[2 * n] = Mathf.FloatToHalf(hidden ? 1f : 0f);
                rg[2 * n + 1] = Mathf.FloatToHalf(RestHeight[n]);
            }
            HiddenChanged = false;
        }

        /// <summary>Is any node of this sheet near a free edge (a cut or the end of the skin) within `rings` steps?</summary>
        public bool NearFreeEdge(int node, int rings)
        {
            RebuildIfDirty();
            var seen = new HashSet<int> { node };
            var front = new List<int> { node };
            for (int r = 0; r <= rings && front.Count > 0; r++)
            {
                var next = new List<int>();
                foreach (int n in front)
                    foreach (int e in EdgesOf(n))
                    {
                        if (edgeCut[e]) return true;
                        if (edgeTris[e] == 0) continue;
                        int o = ea[e] == n ? eb[e] : ea[e];
                        if (seen.Add(o)) next.Add(o);
                    }
                front = next;
            }
            return false;
        }

        private IEnumerable<int> EdgesOf(int n)
        {
            int i = n % N, j = n / N;
            if (i < N - 1) yield return j * (N - 1) + i;
            if (i > 0) yield return j * (N - 1) + i - 1;
            if (j < N - 1) yield return HCount + j * N + i;
            if (j > 0) yield return HCount + (j - 1) * N + i;
            for (int dj = -1; dj <= 0; dj++)
            for (int di = -1; di <= 0; di++)
            {
                int ci = i + di, cj = j + dj;
                if (ci < 0 || cj < 0 || ci >= N - 1 || cj >= N - 1) continue;
                int e = HCount + VCount + cj * (N - 1) + ci;
                if (ea[e] == n || eb[e] == n) yield return e;
            }
        }

        /// <summary>The skin's outward normal at a node now (from its neighbours).</summary>
        public Vector3 NormalAt(int n)
        {
            int i = n % N, j = n / N;
            Vector3 c = X[2 * n];
            Vector3 dx = i < N - 1 && State[n + 1] != Node.Invalid ? X[2 * (n + 1)] - c : c - X[2 * (n - 1)];
            Vector3 dy = j < N - 1 && State[n + N] != Node.Invalid ? X[2 * (n + N)] - c : c - X[2 * (n - N)];
            Vector3 nrm = Vector3.Cross(dy, dx);
            if (Vector3.Dot(nrm, X[2 * n] - X[2 * n + 1]) < 0f) nrm = -nrm;
            return nrm.sqrMagnitude > 1e-10f ? nrm.normalized : E3;
        }

        // ------------------------------------------------------------------------------------------- cutting

        /// <summary>
        /// A scalpel capsule on the body (mm): every edge of the grid whose skin, 1 mm down, passes within its radius
        /// is cut through. Used for incisions on skin the sheet still holds in place.
        /// </summary>
        public bool CutCapsule(Vector3 a, Vector3 b, float radius)
        {
            Vector2 ga = GridOf(a), gb = GridOf(b);
            float pad = radius / H + 2f;
            int i0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(ga.x, gb.x) - pad)), i1 = Mathf.Min(N - 1, Mathf.CeilToInt(Mathf.Max(ga.x, gb.x) + pad));
            int j0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(ga.y, gb.y) - pad)), j1 = Mathf.Min(N - 1, Mathf.CeilToInt(Mathf.Max(ga.y, gb.y) + pad));
            bool any = false;
            for (int j = j0; j <= j1; j++)
            for (int i = i0; i <= i1; i++)
                foreach (int e in EdgesOf(j * N + i))
                {
                    if (edgeCut[e] || edgeBad[e] || ea[e] != j * N + i) continue;
                    int p = ea[e], q = eb[e];
                    Vector3 pa = restTop[p] - restN[p], qa = restTop[q] - restN[q];
                    if (SegmentDistance(pa, qa, a, b) > radius) continue;
                    edgeCut[e] = true;
                    any = true;
                }
            if (any) Changed();
            return any;
        }

        /// <summary>A cut drawn on the sheet itself (grid coordinates, as from Raycast): lifted tissue cut in the air.</summary>
        public bool CutGrid(Vector2 a, Vector2 b)
        {
            int i0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(a.x, b.x)) - 1), i1 = Mathf.Min(N - 1, Mathf.CeilToInt(Mathf.Max(a.x, b.x)) + 1);
            int j0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(a.y, b.y)) - 1), j1 = Mathf.Min(N - 1, Mathf.CeilToInt(Mathf.Max(a.y, b.y)) + 1);
            bool any = false;
            for (int j = j0; j <= j1; j++)
            for (int i = i0; i <= i1; i++)
                foreach (int e in EdgesOf(j * N + i))
                {
                    if (edgeCut[e] || ea[e] != j * N + i) continue;
                    var p = new Vector2(ea[e] % N, ea[e] / N);
                    var q = new Vector2(eb[e] % N, eb[e] / N);
                    if (!SegmentsCross(a, b, p, q)) continue;
                    edgeCut[e] = true;
                    any = true;
                }
            if (any) Changed();
            return any;
        }

        private void Changed()
        {
            dirty = true;
            Wake();
        }

        public void Wake()
        {
            Asleep = false;
            quiet = 0f;
        }

        // ------------------------------------------------------------------------------------------- the hand

        /// <summary>Pinches the tissue around a node (within 2.5 mm, on its side of any cut): it lets go of the body.</summary>
        public void Grab(int node)
        {
            RebuildIfDirty();
            Release();
            var seen = new HashSet<int> { node };
            var front = new List<int> { node };
            while (front.Count > 0)
            {
                var next = new List<int>();
                foreach (int n in front)
                    foreach (int e in EdgesOf(n))
                    {
                        if (edgeTris[e] == 0) continue;
                        int o = ea[e] == n ? eb[e] : ea[e];
                        if ((restTop[o] - restTop[node]).sqrMagnitude <= 2.5f * 2.5f && seen.Add(o)) next.Add(o);
                    }
                front = next;
            }
            heldCentre = node;
            handGoal = handNow = X[2 * node];
            foreach (int n in seen)
            {
                if (border[n]) continue;
                if (State[n] == Node.Pinned || State[n] == Node.Adhered) { State[n] = Node.Peeled; dirty = true; HiddenChanged = true; }
                held.Add(2 * n);
                heldOffset.Add(X[2 * n] - handNow);
            }
            Wake();
        }

        /// <summary>Where the hand is taking the held tissue (body mm).</summary>
        public void MoveHand(Vector3 goalMm)
        {
            handGoal = goalMm;
            Wake();
        }

        public void Release()
        {
            held.Clear();
            heldOffset.Clear();
            heldCentre = -1;
            dirty = true;                                  // held particles get their mass back
            Wake();
        }

        // ------------------------------------------------------------------------------------------- physics

        public static readonly System.Diagnostics.Stopwatch[] Prof =
            { new System.Diagnostics.Stopwatch(), new System.Diagnostics.Stopwatch(), new System.Diagnostics.Stopwatch(), new System.Diagnostics.Stopwatch() };
        public string ProfCounts => $"moving {moving.Count} constraints {ccount} clusters {clStart.Count - 1} members {clMembers.Count}";

        /// <summary>Advances the sheet by dt seconds under gravity (body mm/s^2).</summary>
        public void Step(float dt, Vector3 gravity)
        {
            if (Asleep)
            {
                if (Vector3.Angle(gravity, sleepGravity) < 0.5f) return;
                Wake();
            }
            Prof[0].Start();
            RebuildIfDirty();
            Prof[0].Stop();
            dt = Mathf.Min(dt, 1f / 30f);
            if (moving.Count == 0 || field.Grid == null || !field.Grid.IsCreated) return;

            // The hand moves no faster than tissue can follow.
            Vector3 toGoal = handGoal - handNow;
            float maxMove = maxHandSpeed * dt;
            handNow += toGoal.magnitude > maxMove ? toGoal.normalized * maxMove : toGoal;

            Prof[1].Start();
            RunJob(dt, gravity);
            Prof[1].Stop();
            Prof[2].Start();
            AfterStep(dt, gravity);
            Prof[2].Stop();
        }

        // ------------------------------------------------------------------------------------------- the job

        private NativeArray<Vector3> nX, nVel, nPrev, nContact, nRestTop, nRestBot, nRestN, nHeldTarget, nClRest;
        private NativeArray<float> nW, nRamp, nRestHeight, nRest, nAlpha, nLift, nSlide;
        private NativeArray<int> nMoving, nAdhered, nColliding, nCA, nCB, nClStart, nClMembers, nHeld;
        private NativeArray<byte> nHidden;
        private NativeArray<quaternion> nRot;
        private bool nativeTopology = true;

        private void EnsureNative()
        {
            if (nX.IsCreated) return;
            const Allocator a = Allocator.Persistent;
            nX = new NativeArray<Vector3>(2 * N * N, a);
            nVel = new NativeArray<Vector3>(2 * N * N, a);
            nPrev = new NativeArray<Vector3>(2 * N * N, a);
            nContact = new NativeArray<Vector3>(2 * N * N, a);
            nRestTop = new NativeArray<Vector3>(restTop, a);
            nRestBot = new NativeArray<Vector3>(restBot, a);
            nRestN = new NativeArray<Vector3>(restN, a);
            nRestHeight = new NativeArray<float>(RestHeight, a);
            nW = new NativeArray<float>(2 * N * N, a);
            nRamp = new NativeArray<float>(N * N, a);
            nLift = new NativeArray<float>(N * N, a);
            nSlide = new NativeArray<float>(N * N, a);
            nHidden = new NativeArray<byte>(N * N, a);
            nHeld = new NativeArray<int>(256, a);
            nHeldTarget = new NativeArray<Vector3>(256, a);
            nativeTopology = true;
        }

        private static void Renew<T>(ref NativeArray<T> array, T[] source, int count) where T : struct
        {
            if (array.IsCreated) array.Dispose();
            array = new NativeArray<T>(Math.Max(count, 1), Allocator.Persistent);
            if (count > 0) NativeArray<T>.Copy(source, array, count);
        }

        // After the topology or the set of moving nodes changed: the constraints, regions and lists to the job.
        private void UploadTopology()
        {
            nativeTopology = false;
            Renew(ref nMoving, moving.ToArray(), moving.Count);
            Renew(ref nAdhered, adhered.ToArray(), adhered.Count);
            var colliding = new List<int>();
            foreach (int n in moving) if (State[n] == Node.Peeled) colliding.Add(n);
            collidingCount = colliding.Count;
            Renew(ref nColliding, colliding.ToArray(), colliding.Count);
            Renew(ref nCA, ca, ccount);
            Renew(ref nCB, cb, ccount);
            Renew(ref nRest, crest, ccount);
            Renew(ref nAlpha, calpha, ccount);
            Renew(ref nClStart, clStartA, clStartA.Length);
            Renew(ref nClMembers, clMembersA, clMembersA.Length);
            Renew(ref nClRest, clRestA, clRestA.Length);
            var rot = new quaternion[Math.Max(clStartA.Length - 1, 0)];
            for (int i = 0; i < rot.Length; i++)
            {
                quaternion q = nodeRot[clCentre[i]];
                rot[i] = math.lengthsq(q.value) > 0.5f ? q : quaternion.identity;     // carry on from where it was
            }
            Renew(ref nRot, rot, rot.Length);
            NativeArray<float>.Copy(w, nW);
            for (int n = 0; n < N * N; n++)
                nHidden[n] = (byte)(State[n] == Node.Adhered || State[n] == Node.Peeled || State[n] == Node.Gone ? 1 : 0);
        }

        private int collidingCount;

        private void RunJob(float dt, Vector3 gravity)
        {
            EnsureNative();
            if (nativeTopology) UploadTopology();
            nX.CopyFrom(X);
            nVel.CopyFrom(vel);
            NativeArray<float>.Copy(ramp, nRamp);
            foreach (int n in adhered)
            {
                nLift[n] = 0f;
                nSlide[n] = 0f;
            }
            int heldCount = Mathf.Min(held.Count, nHeld.Length);
            for (int k = 0; k < heldCount; k++)
            {
                nHeld[k] = held[k];
                nHeldTarget[k] = handNow + heldOffset[k];
            }
            SkinDepthGrid grid = field.Grid;
            var job = new TissueSheetJob
            {
                X = nX.Reinterpret<float3>(), Vel = nVel.Reinterpret<float3>(), Prev = nPrev.Reinterpret<float3>(),
                ContactN = nContact.Reinterpret<float3>(), W = nW, Ramp = nRamp, JunctionLift = nLift, JunctionSlide = nSlide,
                Moving = nMoving.GetSubArray(0, moving.Count), Adhered = nAdhered.GetSubArray(0, adhered.Count),
                Colliding = nColliding.GetSubArray(0, collidingCount),
                CA = nCA, CB = nCB, CRest = nRest, CAlpha = nAlpha, CCount = ccount,
                ClStart = nClStart, ClMembers = nClMembers, ClRest = nClRest.Reinterpret<float3>(), ClRot = nRot,
                ClCount = Math.Max(clStartA.Length - 1, 0),
                RestTop = nRestTop.Reinterpret<float3>(), RestBot = nRestBot.Reinterpret<float3>(), RestN = nRestN.Reinterpret<float3>(),
                Held = nHeld, HeldTarget = nHeldTarget.Reinterpret<float3>(), HeldCount = heldCount,
                Hidden = nHidden, RestHeight = nRestHeight,
                Depth = grid.Data, Dims = new int3(grid.Dims.x, grid.Dims.y, grid.Dims.z), Spacing = grid.SpacingMm,
                Origin = Origin, E1 = E1, E2 = E2, E3 = E3, GridN = N, H = H, T = T,
                Table = Table,
                Gravity = gravity, Dt = dt, Substeps = substeps, Iterations = iterations,
                Damping = damping, Retraction = retraction, ShapeStiffness = shapeStiffness,
                AdhesionNormalCompliance = 1f / (adhesionNormalModulus * H * H / 2f),
                AdhesionShearCompliance = 1f / (adhesionShearModulus * H * H / 2f), Friction = friction, MaxSpeed = maxSpeed,
            };
            job.Run();
            nX.CopyTo(X);
            nVel.CopyTo(vel);
            for (int i = 0; i < clCentre.Count; i++) nodeRot[clCentre[i]] = nRot[i];
        }

        /// <summary>Frees the sheet's native memory (TissueSheets does it when a sheet goes).</summary>
        public void Dispose()
        {
            Free(ref nX); Free(ref nVel); Free(ref nPrev); Free(ref nContact); Free(ref nRestTop); Free(ref nRestBot);
            Free(ref nHeldTarget); Free(ref nClRest); Free(ref nRestN); Free(ref nW); Free(ref nRamp); Free(ref nRestHeight); Free(ref nRest);
            Free(ref nAlpha); Free(ref nLift); Free(ref nSlide); Free(ref nMoving); Free(ref nAdhered); Free(ref nColliding); Free(ref nCA); Free(ref nCB);
            Free(ref nClStart); Free(ref nClMembers); Free(ref nHeld); Free(ref nHidden); Free(ref nRot);
        }

        private static void Free<T>(ref NativeArray<T> a) where T : struct
        {
            if (a.IsCreated) a.Dispose();
        }

        private void AfterStep(float dt, Vector3 gravity)
        {
            bool changed = false;
            float maxSpeed = 0f;
            foreach (int n in moving)
            {
                maxSpeed = Mathf.Max(maxSpeed, vel[2 * n].sqrMagnitude, vel[2 * n + 1].sqrMagnitude);
                if (State[n] == Node.Peeled)
                {
                    ramp[n] = Mathf.Min(1f, ramp[n] + dt / retractSeconds);
                    continue;
                }
                // The node comes free once its junction is asked to lift off the fascia by liftMm or to slide along
                // it by tearMm (the job records what it was asked before it pulled the fat back), or its fat is
                // sheared through its own thickness by shearTearMm (the skin dragged sideways over fat that stays).
                Vector3 column = (X[2 * n] - X[2 * n + 1]) - (restTop[n] - restBot[n]);
                float shear = (column - restN[n] * Vector3.Dot(column, restN[n])).magnitude;
                if ((nLift.IsCreated && (nLift[n] > liftMm || nSlide[n] > tearMm)) || shear > shearTearMm)
                {
                    State[n] = Node.Peeled;
                    changed = true;
                }
            }
            // Skin held by its fat that has been still for a while goes back to sleep in its place.
            foreach (int n in moving)
            {
                if (!rePin || State[n] != Node.Adhered) continue;
                bool still = (X[2 * n] - restTop[n]).sqrMagnitude < 0.01f && (X[2 * n + 1] - restBot[n]).sqrMagnitude < 0.01f &&
                             vel[2 * n].sqrMagnitude < 1f && !PeeledNear(n);
                calm[n] = still ? calm[n] + dt : 0f;
                if (calm[n] < 0.5f) continue;
                State[n] = Node.Pinned;
                calm[n] = 0f;
                changed = true;
            }
            // Skin near anything moving wakes up, held by its fat.
            foreach (int n in moving)
            {
                if (State[n] != Node.Peeled && (X[2 * n] - restTop[n]).sqrMagnitude < 0.3f * 0.3f) continue;
                int i = n % N, j = n / N;
                for (int dj = -2; dj <= 2; dj++)
                for (int di = -2; di <= 2; di++)
                {
                    int a = i + di, b = j + dj;
                    if (a < 0 || b < 0 || a >= N || b >= N) continue;
                    int m = b * N + a;
                    if (State[m] != Node.Pinned || border[m]) continue;
                    State[m] = Node.Adhered;
                    changed = true;
                }
            }
            if (changed)
            {
                dirty = true;
                HiddenChanged = true;
            }

            // Loose pieces that fell past the tray are gone.
            Vector3 down = gravity.sqrMagnitude > 1e-6f ? gravity.normalized : Vector3.down;
            float floor = Vector3.Dot(new Vector3(Table.x, Table.y, Table.z) * Table.w, down) + 400f;
            if (Table.w > -1e30f)
            {
                var fallen = new Dictionary<int, (float sum, int count, bool anchored)>();
                foreach (int n in moving)
                {
                    int k = island[n];
                    fallen.TryGetValue(k, out var f);
                    fallen[k] = (f.sum + Vector3.Dot(X[2 * n], down), f.count + 1, f.anchored);
                }
                foreach (var kv in fallen)
                {
                    if (IslandAnchored(kv.Key) || kv.Value.sum / kv.Value.count < floor) continue;
                    for (int n = 0; n < N * N; n++)
                        if (island[n] == kv.Key && State[n] != Node.Invalid) State[n] = Node.Gone;
                    dirty = true;
                    HiddenChanged = true;
                }
            }

            if (held.Count == 0 && maxSpeed < 1.5f * 1.5f) quiet += dt; else quiet = 0f;
            if (quiet > 0.8f)
            {
                Asleep = true;
                sleepGravity = gravity;
            }
        }

        private bool PeeledNear(int n)
        {
            int i = n % N, j = n / N;
            for (int b = Mathf.Max(0, j - 2); b <= Mathf.Min(N - 1, j + 2); b++)
            for (int a = Mathf.Max(0, i - 2); a <= Mathf.Min(N - 1, i + 2); a++)
                if (State[b * N + a] == Node.Peeled || held.Contains(2 * (b * N + a))) return true;
            return false;
        }

        private readonly HashSet<int> anchoredIslands = new HashSet<int>();

        /// <summary>Every piece of the sheet: its nodes, whether it is held to the body, its centre and fastest particle.</summary>
        public List<(int nodes, bool anchored, Vector3 centre, float maxSpeed, Vector3 size, Vector3 restSize)> Pieces()
        {
            RebuildIfDirty();
            var map = new Dictionary<int, (int nodes, Vector3 sum, float speed, Bounds now, Bounds rest)>();
            for (int n = 0; n < N * N; n++)
            {
                if (!Alive(n) || State[n] == Node.Pinned) continue;
                if (!map.TryGetValue(island[n], out var p)) p = (0, Vector3.zero, 0f, new Bounds(X[2 * n], Vector3.zero), new Bounds(restTop[n], Vector3.zero));
                p.now.Encapsulate(X[2 * n]);
                p.rest.Encapsulate(restTop[n]);
                map[island[n]] = (p.nodes + 1, p.sum + X[2 * n], Mathf.Max(p.speed, vel[2 * n].magnitude), p.now, p.rest);
            }
            var list = new List<(int, bool, Vector3, float, Vector3, Vector3)>();
            foreach (var kv in map)
                list.Add((kv.Value.nodes, IslandAnchored(kv.Key), kv.Value.sum / kv.Value.nodes, kv.Value.speed, kv.Value.now.size, kv.Value.rest.size));
            return list;
        }

        /// <summary>Is this node's piece still held to the body by any node (pinned or by its fat)?</summary>
        public bool IsAnchored(int node) => node >= 0 && IslandAnchored(island[node]);

        private bool IslandAnchored(int id) => anchoredIslands.Contains(id);

        // ------------------------------------------------------------------------------------------- topology

        private void RebuildIfDirty()
        {
            if (!dirty) return;
            dirty = false;
            TopologyChanged = true;

            Array.Clear(edgeTris, 0, EdgeCount);
            for (int t = 0; t < TriCount; t++)
            {
                bool ok = Alive(ta[t]) && Alive(tb[t]) && Alive(tc[t]) && Intact(te0[t]) && Intact(te1[t]) && Intact(te2[t]);
                triExists[t] = ok;
                if (!ok) continue;
                edgeTris[te0[t]]++; edgeTris[te1[t]]++; edgeTris[te2[t]]++;
                triShown[t] = State[ta[t]] != Node.Pinned || State[tb[t]] != Node.Pinned || State[tc[t]] != Node.Pinned;
                Vector3 nrm = Vector3.Cross(restTop[tb[t]] - restTop[ta[t]], restTop[tc[t]] - restTop[ta[t]]);
                triFlip[t] = Vector3.Dot(nrm, E3) < 0f;
            }

            // Free nodes left on no triangle are slivers inside a cut: nothing to draw or hold, gone with the incision.
            var onTri = new bool[N * N];
            for (int t = 0; t < TriCount; t++)
                if (triExists[t]) onTri[ta[t]] = onTri[tb[t]] = onTri[tc[t]] = true;
            for (int n = 0; n < N * N; n++)
                if (!onTri[n] && (State[n] == Node.Adhered || State[n] == Node.Peeled))
                {
                    State[n] = Node.Gone;
                    HiddenChanged = true;
                }

            // Particles that move, their mass; who is held by fat.
            moving.Clear();
            adhered.Clear();
            for (int n = 0; n < N * N; n++)
            {
                bool m = State[n] == Node.Adhered || State[n] == Node.Peeled;
                float inv = m ? 1f / mass : 0f;
                w[2 * n] = w[2 * n + 1] = inv;
                if (!m)
                {
                    if (State[n] == Node.Pinned)
                    {
                        X[2 * n] = restTop[n];
                        X[2 * n + 1] = restBot[n];
                    }
                    vel[2 * n] = vel[2 * n + 1] = Vector3.zero;
                    continue;
                }
                moving.Add(n);
                if (State[n] == Node.Adhered) adhered.Add(n);
            }
            foreach (int p in held) w[p] = 0f;                // the hand is immovable to the tissue

            // Constraints between particles where at least one moves.
            ccount = 0;
            float skinA = H * skinThicknessMm, fatA = H * Mathf.Max(T - skinThicknessMm, 0.5f) * 0.5f;
            for (int e = 0; e < EdgeCount; e++)
            {
                if (edgeTris[e] == 0) continue;
                int a = ea[e], b = eb[e];
                if (w[2 * a] == 0f && w[2 * b] == 0f) continue;
                float lt = (restTop[a] - restTop[b]).magnitude, lb = (restBot[a] - restBot[b]).magnitude;
                Add(2 * a, 2 * b, lt, lt / (skinModulus * skinA));
                Add(2 * a + 1, 2 * b + 1, lb, lb / (deepModulus * fatA));
                float lx = (restTop[a] - restBot[b]).magnitude, ly = (restBot[a] - restTop[b]).magnitude;
                Add(2 * a, 2 * b + 1, lx, lx / (deepModulus * H * H * 0.5f));
                Add(2 * a + 1, 2 * b, ly, ly / (deepModulus * H * H * 0.5f));
            }
            // Through the thickness the fat is confined by the dermis above and the fascia below, so it is far stiffer
            // than in shear: this link must be well above the junction's hold (adhesionModulus) for the junction to
            // give first when the skin is pulled.
            foreach (int n in moving) Add(2 * n, 2 * n + 1, T, T / (deepModulus * H * H * 20f));
            // The dermis's bending: skin two nodes apart along rows and columns, across intact edges.
            for (int j = 0; j < N; j++)
            for (int i = 0; i < N; i++)
            {
                int n = j * N + i;
                if (i + 2 < N && edgeTris[j * (N - 1) + i] > 0 && edgeTris[j * (N - 1) + i + 1] > 0 && (w[2 * n] > 0f || w[2 * (n + 2)] > 0f))
                    Add(2 * n, 2 * (n + 2), (restTop[n] - restTop[n + 2]).magnitude, skinBendCompliance);
                if (j + 2 < N && edgeTris[HCount + j * N + i] > 0 && edgeTris[HCount + (j + 1) * N + i] > 0 && (w[2 * n] > 0f || w[2 * (n + 2 * N)] > 0f))
                    Add(2 * n, 2 * (n + 2 * N), (restTop[n] - restTop[n + 2 * N]).magnitude, skinBendCompliance);
            }

            BuildClusters();
            nativeTopology = true;

            // Pieces: connected through intact edges. A piece is anchored while any of it is pinned or held by fat.
            for (int n = 0; n < N * N; n++) island[n] = n;
            for (int e = 0; e < EdgeCount; e++)
                if (edgeTris[e] > 0) Union(ea[e], eb[e]);
            anchoredIslands.Clear();
            for (int n = 0; n < N * N; n++)
            {
                island[n] = Find(n);
                if (State[n] == Node.Pinned || State[n] == Node.Adhered) anchoredIslands.Add(island[n]);
            }
        }

        private void BuildClusters()
        {
            clStart.Clear();
            clMembers.Clear();
            clRest.Clear();
            clRot.Clear();
            clCentre.Clear();
            var seen = new HashSet<int>();
            var front = new List<int>();
            var next = new List<int>();
            foreach (int c in moving)
            {
                int ci = c % N, cj = c / N;
                if ((ci & 1) != 0 || (cj & 1) != 0 || State[c] != Node.Peeled) continue;
                seen.Clear();
                seen.Add(c);
                front.Clear();
                front.Add(c);
                for (int r = 0; r < 2; r++)
                {
                    next.Clear();
                    foreach (int n in front)
                        foreach (int e in EdgesOf(n))
                        {
                            if (edgeTris[e] == 0) continue;
                            int o = ea[e] == n ? eb[e] : ea[e];
                            if (State[o] == Node.Peeled && seen.Add(o)) next.Add(o);   // freed tissue only: the base bends freely
                        }
                    front.Clear();
                    front.AddRange(next);
                }
                if (seen.Count < 4) continue;
                Vector3 centre = Vector3.zero;
                foreach (int n in seen) centre += restTop[n] + restBot[n];
                centre /= 2 * seen.Count;
                clStart.Add(clMembers.Count);
                foreach (int n in seen)
                {
                    clMembers.Add(2 * n);
                    clRest.Add(restTop[n] - centre);
                    clMembers.Add(2 * n + 1);
                    clRest.Add(restBot[n] - centre);
                }
                clRot.Add(Quaternion.identity);
                clCentre.Add(c);
            }
            clStart.Add(clMembers.Count);
            clStartA = clStart.ToArray();
            clMembersA = clMembers.ToArray();
            clRestA = clRest.ToArray();
        }

        private bool Alive(int n) => State[n] != Node.Invalid && State[n] != Node.Gone;
        private bool Intact(int e) => !edgeCut[e] && !edgeBad[e];

        private int Find(int n)
        {
            while (island[n] != n) n = island[n] = island[island[n]];
            return n;
        }

        private void Union(int a, int b)
        {
            a = Find(a);
            b = Find(b);
            if (a != b) island[a] = b;
        }

        private void Add(int a, int b, float rest, float alpha)
        {
            if (ccount == ca.Length)
            {
                Array.Resize(ref ca, ccount * 2);
                Array.Resize(ref cb, ccount * 2);
                Array.Resize(ref crest, ccount * 2);
                Array.Resize(ref calpha, ccount * 2);
            }
            ca[ccount] = a; cb[ccount] = b; crest[ccount] = rest; calpha[ccount] = alpha;
            ccount++;
        }

        // ------------------------------------------------------------------------------------------- drawing

        private readonly List<Vector3> mv = new List<Vector3>(), muv = new List<Vector3>();
        private readonly List<Vector2> mflag = new List<Vector2>();
        private readonly List<int> mtri = new List<int>();
        private readonly List<(int e, int a, int b, bool flip)> walls = new List<(int, int, int, bool)>();

        /// <summary>
        /// The sheet as a mesh in body millimetres: the skin on top, the fat's underside, and walls where it was cut.
        /// Each vertex carries the texture coordinate of the tissue it shows (uv0) and 1 on cut surfaces (uv1.x).
        /// </summary>
        public void FillMesh(Mesh mesh, Vector3 sizeMm)
        {
            Prof[3].Start();
            try { FillMeshInner(mesh, sizeMm); } finally { Prof[3].Stop(); }
        }

        private void FillMeshInner(Mesh mesh, Vector3 sizeMm)
        {
            RebuildIfDirty();
            bool topo = TopologyChanged || mesh.vertexCount == 0;
            mv.Clear();
            for (int n = 0; n < N * N; n++) mv.Add(X[2 * n]);
            for (int n = 0; n < N * N; n++) mv.Add(X[2 * n + 1]);
            if (topo) CollectWalls();
            foreach (var wl in walls)
            {
                mv.Add(X[2 * wl.a]); mv.Add(X[2 * wl.b]); mv.Add(X[2 * wl.b + 1]); mv.Add(X[2 * wl.a + 1]);
            }
            if (topo)
            {
                mesh.Clear();
                mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            }
            mesh.SetVertices(mv);
            if (topo)
            {
                muv.Clear();
                mflag.Clear();
                Vector3 inv = new Vector3(1f / sizeMm.x, 1f / sizeMm.y, 1f / sizeMm.z);
                for (int n = 0; n < N * N; n++) { muv.Add(Vector3.Scale(restTop[n] - restN[n] * 1.5f, inv)); mflag.Add(Vector2.zero); }
                for (int n = 0; n < N * N; n++) { muv.Add(Vector3.Scale(restBot[n] + restN[n] * 0.4f, inv)); mflag.Add(Vector2.right); }
                foreach (var wl in walls)
                {
                    muv.Add(Vector3.Scale(restTop[wl.a] - restN[wl.a] * 0.5f, inv));
                    muv.Add(Vector3.Scale(restTop[wl.b] - restN[wl.b] * 0.5f, inv));
                    muv.Add(Vector3.Scale(restBot[wl.b] + restN[wl.b] * 0.3f, inv));
                    muv.Add(Vector3.Scale(restBot[wl.a] + restN[wl.a] * 0.3f, inv));
                    for (int k = 0; k < 4; k++) mflag.Add(Vector2.right);
                }
                mesh.SetUVs(0, muv);
                mesh.SetUVs(1, mflag);
                mtri.Clear();
                int nn = N * N;
                for (int t = 0; t < TriCount; t++)
                {
                    if (!triExists[t] || !triShown[t]) continue;
                    int a = ta[t], b = tb[t], c = tc[t];
                    if (triFlip[t]) (b, c) = (c, b);
                    mtri.Add(a); mtri.Add(b); mtri.Add(c);                       // skin, facing out
                    mtri.Add(nn + a); mtri.Add(nn + c); mtri.Add(nn + b);        // the fat's underside, facing in
                }
                int v = 2 * nn;
                foreach (var wl in walls)
                {
                    if (wl.flip) { mtri.Add(v); mtri.Add(v + 2); mtri.Add(v + 1); mtri.Add(v); mtri.Add(v + 3); mtri.Add(v + 2); }
                    else { mtri.Add(v); mtri.Add(v + 1); mtri.Add(v + 2); mtri.Add(v); mtri.Add(v + 2); mtri.Add(v + 3); }
                    v += 4;
                }
                mesh.SetTriangles(mtri, 0);
                TopologyChanged = false;
            }
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
        }

        // Walls on every edge of a drawn triangle that has no triangle on its other side (a cut, the skin's end).
        private void CollectWalls()
        {
            walls.Clear();
            for (int t = 0; t < TriCount; t++)
            {
                if (!triExists[t] || !triShown[t]) continue;
                int[] es = { te0[t], te1[t], te2[t] };
                foreach (int e in es)
                {
                    if (edgeTris[e] != 1) continue;
                    int a = ea[e], b = eb[e];
                    int c = ta[t] != a && ta[t] != b ? ta[t] : tb[t] != a && tb[t] != b ? tb[t] : tc[t];
                    // Outward: away from the triangle's third corner.
                    Vector3 outDir = (restTop[a] + restTop[b]) * 0.5f - restTop[c];
                    Vector3 nrm = Vector3.Cross(restTop[b] - restTop[a], restBot[a] - restTop[a]);
                    walls.Add((e, a, b, Vector3.Dot(nrm, outDir) < 0f));
                }
            }
        }

        /// <summary>
        /// The nearest drawn surface of the sheet along a ray (body mm; dir need not be unit): distance in units of
        /// dir, the grid coordinates of the tissue hit and the nearest node.
        /// </summary>
        public bool Raycast(Vector3 origin, Vector3 dir, out float t, out Vector2 grid, out int node)
        {
            RebuildIfDirty();
            t = float.MaxValue;
            grid = default;
            node = -1;
            for (int tri = 0; tri < TriCount; tri++)
            {
                if (!triExists[tri] || !triShown[tri]) continue;
                for (int layer = 0; layer < 2; layer++)
                {
                    int a = ta[tri], b = tb[tri], c = tc[tri];
                    if (!RayTriangle(origin, dir, X[2 * a + layer], X[2 * b + layer], X[2 * c + layer], out float d, out float u, out float v) || d >= t)
                        continue;
                    t = d;
                    var ga = new Vector2(a % N, a / N);
                    var gb = new Vector2(b % N, b / N);
                    var gc = new Vector2(c % N, c / N);
                    grid = ga * (1f - u - v) + gb * u + gc * v;
                    node = (1f - u - v) >= u && (1f - u - v) >= v ? a : u >= v ? b : c;
                }
            }
            return node >= 0;
        }

        /// <summary>Where the tissue at grid coordinates is now (skin surface, body mm).</summary>
        public Vector3 PositionAt(Vector2 grid)
        {
            int i = Mathf.Clamp(Mathf.FloorToInt(grid.x), 0, N - 2), j = Mathf.Clamp(Mathf.FloorToInt(grid.y), 0, N - 2);
            float fx = grid.x - i, fy = grid.y - j;
            int n = j * N + i;
            return Vector3.Lerp(Vector3.Lerp(X[2 * n], X[2 * (n + 1)], fx), Vector3.Lerp(X[2 * (n + N)], X[2 * (n + N + 1)], fx), fy);
        }

        // ------------------------------------------------------------------------------------------- maths

        private static bool RayTriangle(Vector3 o, Vector3 d, Vector3 a, Vector3 b, Vector3 c, out float t, out float u, out float v)
        {
            t = u = v = 0f;
            Vector3 e1 = b - a, e2 = c - a, p = Vector3.Cross(d, e2);
            float det = Vector3.Dot(e1, p);
            if (Mathf.Abs(det) < 1e-9f) return false;
            float inv = 1f / det;
            Vector3 s = o - a;
            u = Vector3.Dot(s, p) * inv;
            if (u < 0f || u > 1f) return false;
            Vector3 q = Vector3.Cross(s, e1);
            v = Vector3.Dot(d, q) * inv;
            if (v < 0f || u + v > 1f) return false;
            t = Vector3.Dot(e2, q) * inv;
            return t > 0f;
        }

        private static bool SegmentsCross(Vector2 a, Vector2 b, Vector2 c, Vector2 d)
        {
            float Cross(Vector2 p, Vector2 q) => p.x * q.y - p.y * q.x;
            Vector2 r = b - a, s = d - c;
            float den = Cross(r, s);
            if (Mathf.Abs(den) < 1e-9f) return false;
            float t = Cross(c - a, s) / den, u = Cross(c - a, r) / den;
            return t >= 0f && t <= 1f && u >= 0f && u <= 1f;
        }

        /// <summary>Shortest distance between segments p0-p1 and q0-q1.</summary>
        public static float SegmentDistance(Vector3 p0, Vector3 p1, Vector3 q0, Vector3 q1)
        {
            Vector3 d1 = p1 - p0, d2 = q1 - q0, r = p0 - q0;
            float a = Vector3.Dot(d1, d1), e = Vector3.Dot(d2, d2), f = Vector3.Dot(d2, r);
            float s, t;
            if (a <= 1e-9f && e <= 1e-9f) return r.magnitude;
            if (a <= 1e-9f) { s = 0f; t = Mathf.Clamp01(f / e); }
            else
            {
                float c = Vector3.Dot(d1, r);
                if (e <= 1e-9f) { t = 0f; s = Mathf.Clamp01(-c / a); }
                else
                {
                    float b = Vector3.Dot(d1, d2), den = a * e - b * b;
                    s = den > 1e-9f ? Mathf.Clamp01((b * f - c * e) / den) : 0f;
                    t = (b * s + f) / e;
                    if (t < 0f) { t = 0f; s = Mathf.Clamp01(-c / a); }
                    else if (t > 1f) { t = 1f; s = Mathf.Clamp01((b - c) / a); }
                }
            }
            return (p0 + d1 * s - (q0 + d2 * t)).magnitude;
        }
    }
}
