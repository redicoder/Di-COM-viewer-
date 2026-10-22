using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// One frame of a TissueSheet's physics, compiled by Burst: for each substep, gravity and damping, the hand, the
    /// XPBD distance constraints, shape matching of freed tissue, the fat's hold, and contacts with the body and the
    /// tray (inelastic, Coulomb friction). TissueSheet.cs explains the model; this is the arithmetic.
    /// </summary>
    [BurstCompile(CompileSynchronously = true)]
    public struct TissueSheetJob : IJob
    {
        public NativeArray<float3> X, Vel, Prev, ContactN;
        public NativeArray<float> JunctionLift, JunctionSlide;   // per node: the most its junction was strained this frame
        [ReadOnly] public NativeArray<float> W, Ramp;
        [ReadOnly] public NativeArray<int> Moving, Adhered, Colliding;
        [ReadOnly] public NativeArray<int> CA, CB;
        [ReadOnly] public NativeArray<float> CRest, CAlpha;
        public int CCount;
        [ReadOnly] public NativeArray<int> ClStart, ClMembers;
        [ReadOnly] public NativeArray<float3> ClRest;
        public NativeArray<quaternion> ClRot;
        public int ClCount;
        [ReadOnly] public NativeArray<float3> RestTop, RestBot, RestN;
        [ReadOnly] public NativeArray<int> Held;
        [ReadOnly] public NativeArray<float3> HeldTarget;
        public int HeldCount;
        [ReadOnly] public NativeArray<byte> Hidden;
        [ReadOnly] public NativeArray<float> RestHeight;
        [ReadOnly] public NativeArray<ushort> Depth;
        public int3 Dims;
        public float3 Spacing;
        public float3 Origin, E1, E2, E3;
        public int GridN;
        public float H, T;
        public float TrayY;
        public float2 TrayMin, TrayMax;
        public float3 Gravity;
        public float Dt;
        public int Substeps, Iterations;
        public float Damping, Retraction, ShapeStiffness, AdhesionNormalCompliance, AdhesionShearCompliance, Friction, MaxSpeed;

        public void Execute()
        {
            float h = Dt / Substeps, invH = 1f / h, invH2 = invH * invH;
            float keep = math.exp(-Damping * h);
            for (int s = 0; s < Substeps; s++)
            {
                for (int i = 0; i < Moving.Length; i++)
                    for (int k = 0; k < 2; k++)
                    {
                        int p = 2 * Moving[i] + k;
                        float3 v = (Vel[p] + Gravity * h) * keep;
                        Vel[p] = v;
                        Prev[p] = X[p];
                        X[p] += v * h;
                    }
                PlaceHeld();
                // Several passes: a chain of stiff dermis links converges slowly, one pass per substep would leave
                // the skin far softer than its modulus says.
                for (int it = 0; it < Iterations; it++) Distances(invH2);
                ShapeMatch();
                Adhesion(invH2);
                PlaceHeld();
                Collide();
                for (int i = 0; i < Moving.Length; i++)
                    for (int k = 0; k < 2; k++)
                    {
                        int p = 2 * Moving[i] + k;
                        float3 v = (X[p] - Prev[p]) * invH;
                        // Contacts are inelastic: being pushed out of a surface does not throw tissue off it.
                        float3 cn = ContactN[p];
                        float vn = math.dot(v, cn);
                        if (vn > 0f) v -= cn * vn;
                        float speed = math.length(v);
                        if (speed > MaxSpeed) v *= MaxSpeed / speed;
                        Vel[p] = v;
                    }
            }
        }

        private void PlaceHeld()
        {
            for (int i = 0; i < HeldCount; i++) X[Held[i]] = HeldTarget[i];
        }

        private void Distances(float invH2)
        {
            for (int c = 0; c < CCount; c++)
            {
                int a = CA[c], b = CB[c];
                float wa = W[a], wb = W[b], ws = wa + wb;
                if (ws <= 0f) continue;
                float3 d = X[a] - X[b];
                float len = math.length(d);
                if (len < 1e-6f) continue;
                float rest = CRest[c] * (1f - Retraction * math.min(Ramp[a >> 1], Ramp[b >> 1]));   // freed tissue shrinks
                float k = -(len - rest) / ((ws + CAlpha[c] * invH2) * len);
                X[a] += d * (k * wa);
                X[b] -= d * (k * wb);
            }
        }

        private void ShapeMatch()
        {
            for (int k = 0; k < ClCount; k++)
            {
                int a = ClStart[k], b = ClStart[k + 1];
                float3 c = 0f;
                for (int m = a; m < b; m++) c += X[ClMembers[m]];
                c /= b - a;
                float3x3 A = float3x3.zero;
                for (int m = a; m < b; m++)
                {
                    int p = ClMembers[m];
                    float3 q = ClRest[m] * (1f - Retraction * Ramp[p >> 1]);
                    float3 d = X[p] - c;
                    A.c0 += d * q.x;
                    A.c1 += d * q.y;
                    A.c2 += d * q.z;
                }
                quaternion rot = ExtractRotation(A, ClRot[k]);
                ClRot[k] = rot;
                float3x3 R = new float3x3(rot);
                for (int m = a; m < b; m++)
                {
                    int p = ClMembers[m];
                    if (W[p] <= 0f) continue;
                    float3 q = ClRest[m] * (1f - Retraction * Ramp[p >> 1]);
                    X[p] += (c + math.mul(R, q) - X[p]) * ShapeStiffness;
                }
            }
        }

        // Mueller et al. 2016, "A robust method to extract the rotational part of deformations", warm-started.
        private static quaternion ExtractRotation(float3x3 A, quaternion q)
        {
            for (int it = 0; it < 4; it++)
            {
                float3x3 R = new float3x3(q);
                float3 omega = math.cross(R.c0, A.c0) + math.cross(R.c1, A.c1) + math.cross(R.c2, A.c2);
                omega /= math.abs(math.dot(R.c0, A.c0) + math.dot(R.c1, A.c1) + math.dot(R.c2, A.c2)) + 1e-9f;
                float w = math.length(omega);
                if (w < 1e-7f) break;
                q = math.normalize(math.mul(quaternion.AxisAngle(omega / w, w), q));
            }
            return q;
        }

        // The junction's hold on each adhered node's fat: stiff against lifting off the fascia, soft along it.
        private void Adhesion(float invH2)
        {
            float alphaN = AdhesionNormalCompliance * invH2, alphaT = AdhesionShearCompliance * invH2;
            for (int i = 0; i < Adhered.Length; i++)
            {
                int n = Adhered[i], p = 2 * n + 1;
                float wp = W[p];
                if (wp <= 0f) continue;
                float3 d = X[p] - RestBot[n], nrm = RestN[n];
                float lift = math.dot(d, nrm);
                float3 dn = nrm * lift, dt = d - dn;
                // The strain the junction is asked to take, before it pulls the fat back: in XPBD that is the
                // constraint's violation, the measure of the force through it (TissueSheet judges tearing on it).
                JunctionLift[n] = math.max(JunctionLift[n], lift);
                JunctionSlide[n] = math.max(JunctionSlide[n], math.length(dt));
                X[p] -= dn * (wp / (wp + alphaN)) + dt * (wp / (wp + alphaT));
            }
        }

        private void Collide()
        {
            for (int i = 0; i < Colliding.Length; i++)
            {
                int n = Colliding[i];
                for (int k = 0; k < 2; k++)
                {
                    int p = 2 * n + k;
                    float3 x = X[p];
                    float3 normal = new float3(0f, 1f, 0f);
                    float push = 0f;
                    ContactN[p] = 0f;
                    float depth = SkinDepthGrid.Sample(Depth, Dims, Spacing, x);
                    // Where skin has been lifted the solid is its wound bed, T deeper: under this particle's own
                    // place always (its bottom lies off the grid point it belongs to), elsewhere where the sheet lifted.
                    float3 home = k == 0 ? RestTop[n] : RestBot[n];
                    if (depth > 0f && (math.lengthsq(x - home) < 4f * H * H || HiddenAt(x))) depth -= T;
                    if (depth > 0.05f)
                    {
                        normal = Outward(x);
                        push = math.min(depth, 1f);                          // deep in: climb out over a few substeps
                        x += normal * push;
                    }
                    if (x.y < TrayY && x.y > TrayY - 40f && x.x > TrayMin.x && x.x < TrayMax.x && x.z > TrayMin.y && x.z < TrayMax.y)
                    {
                        push = TrayY - x.y;
                        x.y = TrayY;
                        normal = new float3(0f, 1f, 0f);
                    }
                    if (push > 0f)
                    {
                        // Coulomb friction: the sliding it can stop is limited by how hard the surface pushes back.
                        float3 move = x - Prev[p];
                        float3 along = move - math.dot(move, normal) * normal;
                        float slide = math.length(along), hold = Friction * push;
                        x -= slide <= hold ? along : along * (hold / slide);
                        ContactN[p] = normal;
                    }
                    X[p] = x;
                }
            }
        }

        private bool HiddenAt(float3 mm)
        {
            float3 d = mm - Origin;
            int i = (int)math.round(math.dot(d, E1) / H), j = (int)math.round(math.dot(d, E2) / H);
            if (i < 0 || j < 0 || i >= GridN || j >= GridN) return false;
            int n = j * GridN + i;
            if (Hidden[n] == 0) return false;
            float hz = math.dot(d, E3);
            return hz <= RestHeight[n] + 1f && hz >= RestHeight[n] - T - 1f;
        }

        private float3 Outward(float3 p)
        {
            const float e = 0.7f;
            float3 g = new float3(
                SkinDepthGrid.Sample(Depth, Dims, Spacing, p + new float3(e, 0, 0)) - SkinDepthGrid.Sample(Depth, Dims, Spacing, p - new float3(e, 0, 0)),
                SkinDepthGrid.Sample(Depth, Dims, Spacing, p + new float3(0, e, 0)) - SkinDepthGrid.Sample(Depth, Dims, Spacing, p - new float3(0, e, 0)),
                SkinDepthGrid.Sample(Depth, Dims, Spacing, p + new float3(0, 0, e)) - SkinDepthGrid.Sample(Depth, Dims, Spacing, p - new float3(0, 0, e)));
            float l = math.length(g);
            return l > 1e-5f ? -g / l : E3;
        }
    }
}
