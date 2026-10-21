// LivingEye — a procedural human eye for URP (Unity 6).
// Geometry (eye-local, +Z = look axis) for a 12 mm eye, scaled with `radius`:
//   globe r 12.0 mm · limbus r 5.85 mm · cornea radius of curvature 7.8 mm, apex 2.6 mm in front of the
//   limbus plane · iris plane 2.5 mm behind the cornea apex, bowing slightly forward toward the pupil.
// The sclera mesh is the globe with the corneal cap cut out; the cornea cap closes that hole exactly.
using UnityEngine;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    [DisallowMultipleComponent]
    public sealed class LivingEye : MonoBehaviour
    {
        [Tooltip("Stroma colour. Natural range: brown (0.36,0.22,0.12), hazel (0.45,0.33,0.16), green (0.30,0.40,0.24), blue (0.35,0.50,0.62).")]
        public Color irisColor = new Color(0.36f, 0.22f, 0.12f, 1f);
        [Tooltip("0 = pin-point (1 mm radius), 1 = fully dilated (4 mm radius).")]
        [Range(0f, 1f)] public float pupil = 0.35f;
        [Tooltip("Tear film: highlight sharpness and reflection strength on sclera and cornea.")]
        [Range(0f, 1f)] public float wetness = 1f;
        [Tooltip("Small involuntary jumps and drift so the eye never sits perfectly still.")]
        public bool autoSaccades = true;
        [Tooltip("Pupil slowly constricts in bright main light and dilates in dim light, around the `pupil` value.")]
        public bool pupilReactsToLight = true;
        [Range(0f, 1f)] public float pupilLightInfluence = 0.6f;
        [Tooltip("Degrees per second for LookAt tracking (smooth pursuit).")]
        public float gazeSpeed = 240f;
        public const float MaxGazeAngle = 30f;

        public float Radius => m_Radius;
        public Vector3 LocalForward => m_LocalForward;

        // Serialized so an eye created in the editor rebuilds its (non-serialized) meshes and materials
        // after a scene reload or entering Play mode.
        [SerializeField, HideInInspector] private float m_Radius;
        [SerializeField, HideInInspector] private Vector3 m_LocalForward = Vector3.back;
        [SerializeField, HideInInspector] private bool m_Built;

        private Transform m_Parent;
        private Vector3 m_Up;
        private Quaternion m_RestRotation, m_DesiredGaze, m_CurrentGaze;
        private Vector2 m_SaccadeTarget, m_SaccadeCurrent;
        private float m_NextSaccadeTime;
        private float m_PupilCurrent, m_PupilApplied = -1f, m_WetnessApplied = -1f;
        private Color m_IrisApplied;
        private Light m_Sun;

        private Material m_ScleraMat, m_IrisMat, m_CorneaMat;
        private Mesh m_ScleraMesh, m_CorneaMesh, m_IrisMesh;
        private float m_LimbusRadius, m_CorneaRadius, m_CorneaCentreZ, m_IrisZ;

        private static readonly int s_IrisColor = Shader.PropertyToID("_IrisColor");
        private static readonly int s_EyeGeom = Shader.PropertyToID("_EyeGeom");
        private static readonly int s_EyeGeom2 = Shader.PropertyToID("_EyeGeom2");
        private static readonly int s_Wetness = Shader.PropertyToID("_Wetness");
        private static readonly int s_VeinTex = Shader.PropertyToID("_VeinTex");
        private static readonly int s_IrisTex = Shader.PropertyToID("_IrisTex");

        private static Texture2D s_IrisTexture, s_ScleraTexture;   // shared by every eye; colour is applied in the shader

        // ------------------------------------------------------------------------------------------ API

        public static LivingEye Create(Transform parent, Vector3 localCentre, float radius, Vector3 localForward)
        {
            var go = new GameObject("LivingEye");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localCentre;
            var eye = go.AddComponent<LivingEye>();
            eye.Build(parent, radius, localForward);
            return eye;
        }

        /// <summary>Turns the eye toward a world point, limited to MaxGazeAngle from the rest direction.</summary>
        public void LookAt(Vector3 worldTarget)
        {
            Vector3 dirWorld = worldTarget - transform.position;
            if (dirWorld.sqrMagnitude < 1e-12f) return;
            Vector3 dirParent = m_Parent != null ? m_Parent.InverseTransformDirection(dirWorld.normalized) : dirWorld.normalized;
            Vector3 clamped = Vector3.RotateTowards(LocalForward, dirParent, MaxGazeAngle * Mathf.Deg2Rad, 0f);
            m_DesiredGaze = Quaternion.LookRotation(clamped, m_Up);
        }

        /// <summary>Back to looking straight along localForward.</summary>
        public void LookForward() => m_DesiredGaze = m_RestRotation;

        // ---------------------------------------------------------------------------------------- build

        private void Awake()
        {
            if (m_Built && m_ScleraMat == null) Rebuild();
        }

        private void Rebuild()
        {
            for (int i = transform.childCount - 1; i >= 0; i--)
            {
                Transform c = transform.GetChild(i);
                if (c.name == "Sclera" || c.name == "Iris" || c.name == "Cornea") DestroyImmediate(c.gameObject);
            }
            Build(transform.parent, m_Radius, m_LocalForward);
        }

        private void Build(Transform parent, float radius, Vector3 localForward)
        {
            m_Parent = parent;
            m_Radius = radius;
            m_LocalForward = localForward.sqrMagnitude > 1e-12f ? localForward.normalized : Vector3.back;
            m_Built = true;
            m_Up = Mathf.Abs(Vector3.Dot(LocalForward, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up;
            m_RestRotation = Quaternion.LookRotation(LocalForward, m_Up);
            m_DesiredGaze = m_CurrentGaze = m_RestRotation;
            transform.localRotation = m_RestRotation;

            float s = radius / 0.012f;
            m_LimbusRadius = 0.00585f * s;
            m_CorneaRadius = 0.0078f * s;
            float limbusZ = Mathf.Sqrt(radius * radius - m_LimbusRadius * m_LimbusRadius);
            float capHeight = m_CorneaRadius - Mathf.Sqrt(m_CorneaRadius * m_CorneaRadius - m_LimbusRadius * m_LimbusRadius);   // ~2.6 mm
            m_CorneaCentreZ = limbusZ + capHeight - m_CorneaRadius;
            float apexZ = m_CorneaCentreZ + m_CorneaRadius;
            m_IrisZ = apexZ - 0.0025f * s;

            EnsureTextures();

            m_ScleraMesh = BuildSclera(radius, m_LimbusRadius, limbusZ, 64, 40);
            m_CorneaMesh = BuildCorneaCap(m_CorneaRadius, m_CorneaCentreZ, m_LimbusRadius, 64, 20);
            m_IrisMesh = BuildIris(m_LimbusRadius, m_IrisZ + 0.0004f * s, m_IrisZ - 0.0003f * s, 64, 16);

            m_ScleraMat = MakeMaterial("DicomViewer/LivingEyeSclera");
            m_IrisMat = MakeMaterial("DicomViewer/LivingEyeIris");
            m_CorneaMat = MakeMaterial("DicomViewer/LivingEyeCornea");

            Vector4 geom = new Vector4(m_LimbusRadius, m_CorneaRadius, m_CorneaCentreZ, m_IrisZ);
            if (m_ScleraMat != null)
            {
                m_ScleraMat.SetVector(s_EyeGeom, new Vector4(radius, limbusZ / radius, 0f, 0f));
                m_ScleraMat.SetTexture(s_VeinTex, s_ScleraTexture);
            }
            if (m_IrisMat != null)
            {
                m_IrisMat.SetVector(s_EyeGeom, geom);
                m_IrisMat.SetTexture(s_IrisTex, s_IrisTexture);
            }
            if (m_CorneaMat != null) m_CorneaMat.SetVector(s_EyeGeom, geom);

            MakeChild("Sclera", m_ScleraMesh, m_ScleraMat, ShadowCastingMode.On);
            MakeChild("Iris", m_IrisMesh, m_IrisMat, ShadowCastingMode.Off);
            MakeChild("Cornea", m_CorneaMesh, m_CorneaMat, ShadowCastingMode.Off);

            m_PupilCurrent = pupil;
            m_Sun = RenderSettings.sun;
            if (m_Sun == null)
            {
                Light[] lights = FindObjectsByType<Light>(FindObjectsSortMode.None);   // once, at build time
                for (int i = 0; i < lights.Length; i++)
                    if (lights[i].type == LightType.Directional) { m_Sun = lights[i]; break; }
            }
            ApplyDynamicProperties(true);
        }

        private static Material MakeMaterial(string shaderName)
        {
            Shader shader = Shader.Find(shaderName);
            if (shader == null)
            {
                Debug.LogError($"LivingEye: shader '{shaderName}' not found. Add it to Always Included Shaders.");
                return null;
            }
            return new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
        }

        private void MakeChild(string name, Mesh mesh, Material material, ShadowCastingMode shadows)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = material;
            mr.shadowCastingMode = shadows;
            mr.receiveShadows = true;
            mr.lightProbeUsage = LightProbeUsage.BlendProbes;
            mr.reflectionProbeUsage = ReflectionProbeUsage.BlendProbes;
        }

        private void OnDestroy()
        {
            Kill(m_ScleraMat); Kill(m_IrisMat); Kill(m_CorneaMat);
            Kill(m_ScleraMesh); Kill(m_CorneaMesh); Kill(m_IrisMesh);
        }

        // Eyes are also built outside Play mode (editor snapshots), where Destroy is not allowed.
        private static void Kill(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }

        // --------------------------------------------------------------------------------------- update

        private void Update()
        {
            float dt = Time.deltaTime;

            // Smooth pursuit toward the requested gaze.
            m_CurrentGaze = Quaternion.RotateTowards(m_CurrentGaze, m_DesiredGaze, gazeSpeed * dt);

            // Saccades: a quick jump every 0.4–2.8 s, held with a slow drift. Real saccades run 300–500 °/s.
            if (autoSaccades)
            {
                if (Time.time >= m_NextSaccadeTime)
                {
                    float amplitude = Random.Range(0.4f, 2.5f);
                    m_SaccadeTarget = new Vector2(Random.Range(-1f, 1f), Random.Range(-0.6f, 0.6f)) * amplitude;
                    m_NextSaccadeTime = Time.time + Random.Range(0.4f, 2.8f);
                }
            }
            else m_SaccadeTarget = Vector2.zero;
            m_SaccadeCurrent = Vector2.MoveTowards(m_SaccadeCurrent, m_SaccadeTarget, 450f * dt);
            float t = Time.time;
            Vector2 drift = autoSaccades ? new Vector2(Mathf.Sin(t * 1.3f) * 0.08f, Mathf.Sin(t * 0.9f + 1.7f) * 0.06f) : Vector2.zero;
            Vector2 off = m_SaccadeCurrent + drift;
            transform.localRotation = m_CurrentGaze * Quaternion.Euler(off.y, off.x, 0f);

            // Pupil: constriction is faster than dilation.
            float target = pupil;
            if (pupilReactsToLight && m_Sun != null)
            {
                float facing = Mathf.Clamp01(Vector3.Dot(-m_Sun.transform.forward, transform.forward) * 0.5f + 0.5f);
                float brightness = m_Sun.intensity * (0.2126f * m_Sun.color.r + 0.7152f * m_Sun.color.g + 0.0722f * m_Sun.color.b) * facing;
                float lightPupil = Mathf.Lerp(0.65f, 0.12f, Mathf.Clamp01(brightness / 2f));
                target = Mathf.Lerp(pupil, lightPupil, pupilLightInfluence);
            }
            float tau = target < m_PupilCurrent ? 0.45f : 1.5f;
            m_PupilCurrent = Mathf.Lerp(m_PupilCurrent, target, 1f - Mathf.Exp(-dt / tau));

            ApplyDynamicProperties(false);
        }

        private void ApplyDynamicProperties(bool force)
        {
            float p = Mathf.Clamp01(m_PupilCurrent);
            if (m_IrisMat != null && (force || !Mathf.Approximately(p, m_PupilApplied) || irisColor != m_IrisApplied))
            {
                float pupilRadius = Mathf.Lerp(0.0010f, 0.0040f, p) * (Radius / 0.012f);
                m_IrisMat.SetVector(s_EyeGeom2, new Vector4(Radius, pupilRadius, 0.25f, 1f / 1.376f));
                m_IrisMat.SetColor(s_IrisColor, irisColor);
                m_PupilApplied = p;
                m_IrisApplied = irisColor;
            }
            float w = Mathf.Clamp01(wetness);
            if (force || !Mathf.Approximately(w, m_WetnessApplied))
            {
                if (m_ScleraMat != null) m_ScleraMat.SetFloat(s_Wetness, w);
                if (m_CorneaMat != null) m_CorneaMat.SetFloat(s_Wetness, w);
                m_WetnessApplied = w;
            }
        }

        // --------------------------------------------------------------------------------------- meshes

        // Globe from the limbus ring back to the rear pole; the front cap is left open for the cornea.
        private static Mesh BuildSclera(float r, float limbusRadius, float limbusZ, int segments, int rings)
        {
            float thetaStart = Mathf.Acos(limbusZ / r);
            var b = new MeshBuilder(segments, rings);
            for (int i = 0; i <= rings; i++)
            {
                float theta = Mathf.Lerp(thetaStart, Mathf.PI, (float)i / rings);
                float st = Mathf.Sin(theta), ct = Mathf.Cos(theta);
                for (int j = 0; j <= segments; j++)
                {
                    float phi = (float)j / segments * Mathf.PI * 2f;
                    var n = new Vector3(st * Mathf.Cos(phi), st * Mathf.Sin(phi), ct);
                    b.Set(i, j, n * r, n, new Vector2((float)j / segments, theta / Mathf.PI));
                }
            }
            return b.Finish("Sclera");
        }

        // Spherical cap of the cornea sphere, from the apex to the limbus ring (shared edge with the sclera).
        private static Mesh BuildCorneaCap(float rc, float centreZ, float limbusRadius, int segments, int rings)
        {
            float psiEnd = Mathf.Asin(Mathf.Clamp01(limbusRadius / rc));
            var b = new MeshBuilder(segments, rings);
            for (int i = 0; i <= rings; i++)
            {
                float psi = psiEnd * i / rings;
                float sp = Mathf.Sin(psi), cp = Mathf.Cos(psi);
                for (int j = 0; j <= segments; j++)
                {
                    float phi = (float)j / segments * Mathf.PI * 2f;
                    var n = new Vector3(sp * Mathf.Cos(phi), sp * Mathf.Sin(phi), cp);
                    b.Set(i, j, new Vector3(0f, 0f, centreZ) + n * rc, n, new Vector2((float)j / segments, (float)i / rings));
                }
            }
            return b.Finish("Cornea");
        }

        // Shallow cone: centre slightly in front of the root, so the iris bows forward like the real one.
        private static Mesh BuildIris(float limbusRadius, float zCentre, float zRoot, int segments, int rings)
        {
            float slope = (zRoot - zCentre) / limbusRadius;    // dz/dr, negative
            var b = new MeshBuilder(segments, rings);
            for (int i = 0; i <= rings; i++)
            {
                float f = (float)i / rings;
                float rad = limbusRadius * f;
                float z = Mathf.Lerp(zCentre, zRoot, f);
                for (int j = 0; j <= segments; j++)
                {
                    float phi = (float)j / segments * Mathf.PI * 2f;
                    var radial = new Vector3(Mathf.Cos(phi), Mathf.Sin(phi), 0f);
                    var n = (new Vector3(-slope * radial.x, -slope * radial.y, 1f)).normalized;
                    b.Set(i, j, radial * rad + new Vector3(0f, 0f, z), n, new Vector2((float)j / segments, f));
                }
            }
            return b.Finish("Iris");
        }

        // Grid of (rings+1) x (segments+1) vertices; triangles oriented so face normals follow vertex normals,
        // which keeps the winding correct without reasoning about handedness per surface.
        private sealed class MeshBuilder
        {
            private readonly int m_Seg, m_Rings;
            private readonly Vector3[] m_Pos, m_Nrm;
            private readonly Vector2[] m_Uv;

            public MeshBuilder(int segments, int rings)
            {
                m_Seg = segments; m_Rings = rings;
                int n = (segments + 1) * (rings + 1);
                m_Pos = new Vector3[n]; m_Nrm = new Vector3[n]; m_Uv = new Vector2[n];
            }

            public void Set(int ring, int seg, Vector3 p, Vector3 n, Vector2 uv)
            {
                int k = ring * (m_Seg + 1) + seg;
                m_Pos[k] = p; m_Nrm[k] = n; m_Uv[k] = uv;
            }

            public Mesh Finish(string name)
            {
                var tris = new int[m_Rings * m_Seg * 6];
                int t = 0;
                for (int i = 0; i < m_Rings; i++)
                for (int j = 0; j < m_Seg; j++)
                {
                    int a = i * (m_Seg + 1) + j, bIdx = a + 1, c = a + m_Seg + 1, d = c + 1;
                    t = AddTri(tris, t, a, c, bIdx);
                    t = AddTri(tris, t, bIdx, c, d);
                }
                var mesh = new Mesh { name = name, hideFlags = HideFlags.HideAndDontSave };
                mesh.SetVertices(m_Pos);
                mesh.SetNormals(m_Nrm);
                mesh.SetUVs(0, m_Uv);
                mesh.SetTriangles(tris, 0);
                mesh.RecalculateBounds();
                return mesh;
            }

            private int AddTri(int[] tris, int t, int i0, int i1, int i2)
            {
                Vector3 face = Vector3.Cross(m_Pos[i1] - m_Pos[i0], m_Pos[i2] - m_Pos[i0]);
                Vector3 n = m_Nrm[i0] + m_Nrm[i1] + m_Nrm[i2];
                bool flip = Vector3.Dot(face, n) < 0f;
                tris[t++] = i0;
                tris[t++] = flip ? i2 : i1;
                tris[t++] = flip ? i1 : i2;
                return t;
            }
        }

        // ------------------------------------------------------------------------------------- textures

        private static void EnsureTextures()
        {
            if (s_IrisTexture == null) s_IrisTexture = BuildIrisTexture(512, 256);
            if (s_ScleraTexture == null) s_ScleraTexture = BuildScleraTexture(512, 256);
        }

        // Polar: u = angle (tiles), v = radius 0..1. r = fibres, g = crypts, b = fine detail.
        private static Texture2D BuildIrisTexture(int w, int h)
        {
            var px = new Color32[w * h];
            for (int y = 0; y < h; y++)
            {
                float v = (y + 0.5f) / h;
                for (int x = 0; x < w; x++)
                {
                    float u = (x + 0.5f) / w;

                    // Radial fibres: much higher frequency around than along the radius, ridged.
                    float fib = 0f, amp = 0.5f, fu = 64f, fv = 3f;
                    for (int o = 0; o < 4; o++)
                    {
                        float nv = Noise(u * fu, v * fv + o * 3.1f, (int)fu, 11 + o);
                        fib += (1f - Mathf.Abs(2f * nv - 1f)) * amp;
                        amp *= 0.5f; fu *= 2f; fv *= 1.7f;
                    }
                    fib = Mathf.Clamp01(fib * 1.1f);
                    fib *= 1f + 0.10f * Mathf.Sin(v * 70f + Noise(u * 16f, v * 4f, 16, 5) * 4f);   // contraction furrows

                    // Crypts: low-frequency blobs, mostly in the ciliary zone.
                    float c = Fbm(u * 12f, v * 5f, 12, 3, 21);
                    float crypt = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.58f, 0.70f, c)) * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.35f, 0.55f, v));

                    float detail = Fbm(u * 30f, v * 14f, 30, 3, 33);

                    px[y * w + x] = new Color32(ToByte(fib), ToByte(crypt), ToByte(detail), 255);
                }
            }
            return Finish(px, w, h, "LivingEye Iris", TextureWrapMode.Repeat, TextureWrapMode.Clamp);
        }

        // Polar around the look axis: u = angle (tiles), v = angle from the limbus / pi. r = veins, g = mottling.
        private static Texture2D BuildScleraTexture(int w, int h)
        {
            var px = new Color32[w * h];
            for (int y = 0; y < h; y++)
            {
                float v = (y + 0.5f) / h;
                float thick = 0.5f + 1.6f * v;                       // vessels widen away from the limbus
                float density = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.05f, 0.45f, v));
                for (int x = 0; x < w; x++)
                {
                    float u = (x + 0.5f) / w;
                    // Ridges of a noise field stretched along v give branching, radially oriented vessels.
                    float n1 = Fbm(u * 10f, v * 2.2f, 10, 3, 41);
                    float l1 = 1f - Mathf.SmoothStep(0f, 1f, Mathf.Abs(n1 - 0.5f) / (0.012f * thick));
                    float n2 = Fbm(u * 22f + 0.37f, v * 5f + 0.61f, 22, 3, 52);
                    float l2 = 1f - Mathf.SmoothStep(0f, 1f, Mathf.Abs(n2 - 0.5f) / (0.008f * thick));
                    float n3 = Fbm(u * 40f + 0.8f, v * 9f, 40, 2, 63);
                    float l3 = 1f - Mathf.SmoothStep(0f, 1f, Mathf.Abs(n3 - 0.5f) / (0.006f * thick));
                    float veins = Mathf.Clamp01(l1 * 0.9f + l2 * 0.6f + l3 * 0.35f) * density;
                    float mottle = Fbm(u * 4f, v * 2f, 4, 3, 71);
                    px[y * w + x] = new Color32(ToByte(veins), ToByte(mottle), 0, 255);
                }
            }
            return Finish(px, w, h, "LivingEye Sclera", TextureWrapMode.Repeat, TextureWrapMode.Clamp);
        }

        private static Texture2D Finish(Color32[] px, int w, int h, string name, TextureWrapMode wrapU, TextureWrapMode wrapV)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, true, true)
            {
                name = name, hideFlags = HideFlags.HideAndDontSave, wrapModeU = wrapU, wrapModeV = wrapV,
                filterMode = FilterMode.Trilinear, anisoLevel = 8,
            };
            tex.SetPixels32(px);
            tex.Apply(true, true);
            return tex;
        }

        private static byte ToByte(float f) => (byte)Mathf.RoundToInt(Mathf.Clamp01(f) * 255f);

        private static float Fbm(float x, float y, int periodX, int octaves, int seed)
        {
            float sum = 0f, amp = 0.5f, norm = 0f;
            for (int o = 0; o < octaves; o++)
            {
                sum += Noise(x, y, periodX, seed + o) * amp;
                norm += amp;
                amp *= 0.5f; x *= 2f; y *= 2f; periodX *= 2;
            }
            return sum / norm;
        }

        // Value noise, tileable in x with integer period, smooth interpolation.
        private static float Noise(float x, float y, int periodX, int seed)
        {
            int xi = Mathf.FloorToInt(x), yi = Mathf.FloorToInt(y);
            float fx = x - xi, fy = y - yi;
            fx = fx * fx * (3f - 2f * fx);
            fy = fy * fy * (3f - 2f * fy);
            int x0 = Mod(xi, periodX), x1 = Mod(xi + 1, periodX);
            float a = Hash(x0, yi, seed), b = Hash(x1, yi, seed), c = Hash(x0, yi + 1, seed), d = Hash(x1, yi + 1, seed);
            return Mathf.Lerp(Mathf.Lerp(a, b, fx), Mathf.Lerp(c, d, fx), fy);
        }

        private static int Mod(int a, int m) => (a % m + m) % m;

        private static float Hash(int x, int y, int seed)
        {
            uint h = (uint)(x * 374761393) + (uint)(y * 668265263) + (uint)(seed * 1442695041);
            h = (h ^ (h >> 13)) * 1274126177u;
            h ^= h >> 16;
            return (h & 0xFFFFFF) / 16777215f;
        }
    }
}
