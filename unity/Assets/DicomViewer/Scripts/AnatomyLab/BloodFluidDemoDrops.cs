// CPU-animated stand-in for the GPU blood simulation: drops run down the outside of a sphere.
// Fills BloodDrops.Buffer so BloodFluidFeature has something to draw in the demo scene.
using System.Runtime.InteropServices;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    [DisallowMultipleComponent]
    public sealed class BloodFluidDemoDrops : MonoBehaviour
    {
        [Tooltip("Number of drop slots. The feature's budget target is 10,000.")]
        public int count = 3000;
        [Tooltip("Sphere radius in this object's local space (Unity's primitive sphere is 0.5).")]
        public float sphereRadius = 0.5f;
        public Vector2 radiusRange = new Vector2(0.0008f, 0.0015f);
        [Tooltip("Polar speed in radians per second (how fast drops run down).")]
        public float speed = 0.35f;
        [Tooltip("Side-to-side wobble of the rivulets.")]
        public float wobble = 0.12f;
        [Tooltip("Fraction of slots that are alive at any time.")]
        [Range(0f, 1f)] public float fill = 0.85f;
        public int seed = 12345;

        private BloodDrop[] m_Drops;
        private Vector4[] m_State;        // x = polar angle, y = azimuth, z = speed factor, w = wobble phase
        private ComputeBuffer m_Buffer;

        private void OnEnable()
        {
            count = Mathf.Max(1, count);
            m_Drops = new BloodDrop[count];
            m_State = new Vector4[count];
            var rng = new System.Random(seed);
            for (int i = 0; i < count; i++)
            {
                m_State[i] = new Vector4(
                    (float)rng.NextDouble() * Mathf.PI,
                    (float)rng.NextDouble() * Mathf.PI * 2f,
                    0.6f + 0.8f * (float)rng.NextDouble(),
                    (float)rng.NextDouble() * Mathf.PI * 2f);
                m_Drops[i].radius = Mathf.Lerp(radiusRange.x, radiusRange.y, (float)rng.NextDouble());
                m_Drops[i].alive = (uint)(rng.NextDouble() < fill ? 1 : 0);
            }

            m_Buffer = new ComputeBuffer(count, Marshal.SizeOf<BloodDrop>(), ComputeBufferType.Structured);
            BloodDrops.Buffer = m_Buffer;
            BloodDrops.Capacity = count;
            BloodDrops.Body = transform;
            Step(0f);
        }

        private void OnDisable()
        {
            if (BloodDrops.Buffer == m_Buffer)
            {
                BloodDrops.Buffer = null;
                BloodDrops.Capacity = 0;
                BloodDrops.Body = null;
            }
            m_Buffer?.Release();
            m_Buffer = null;
        }

        private void Update() => Step(Time.deltaTime);

        private void Step(float dt)
        {
            float time = Time.time;
            for (int i = 0; i < count; i++)
            {
                Vector4 st = m_State[i];
                if (m_Drops[i].alive == 1)
                {
                    st.x += speed * st.z * dt;                 // run from the pole downwards
                    if (st.x > Mathf.PI * 0.98f) st.x = 0.05f; // drip off the bottom, respawn at the top
                }
                float az = st.y + Mathf.Sin(time * 1.7f + st.w) * wobble * Mathf.Sin(st.x);
                Vector3 n = new Vector3(Mathf.Sin(st.x) * Mathf.Cos(az), Mathf.Cos(st.x), Mathf.Sin(st.x) * Mathf.Sin(az));
                m_Drops[i].position = n * (sphereRadius + m_Drops[i].radius * 0.6f);   // sits on the surface, slightly sunk
                m_Drops[i].normal = n;
                m_State[i] = st;
            }
            m_Buffer.SetData(m_Drops);   // no allocation: same managed array every frame
        }
    }
}
