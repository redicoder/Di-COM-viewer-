using System.Collections.Generic;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>One blood drop on the GPU (32 bytes; the same layout in BloodSim.compute and the blood renderers).</summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct BloodDrop
    {
        public Vector3 position;    // metres, body local
        public float radius;        // metres
        public Vector3 normal;      // outward skin normal under the drop (body local); zero while falling
        public uint alive;          // 0 = free slot
    }

    /// <summary>Where renderers find the drops (the simple drops below, or a liquid-blood renderer feature).</summary>
    public static class BloodDrops
    {
        public static ComputeBuffer Buffer;
        public static int Capacity;
        public static Transform Body;
    }

    /// <summary>
    /// Bleeding, simulated on the GPU (Resources/BloodSim.compute). A wound first fills with blood; once full it
    /// spills over its lower edge at a few points and the blood runs down the skin in rivulets, in the direction of
    /// real gravity (turn the head and it runs another way), drying into stains (a 3D stain texture the body's shader
    /// reads). Drops walk on the photographed tissue itself, so they follow every fold of the real face.
    /// Bleeding is a simulation: a real dead body does not bleed.
    /// </summary>
    public class BloodSim : MonoBehaviour
    {
        public int capacity = 16384;
        [Tooltip("Pull along the skin, m/s^2. Lower than real gravity: thick blood creeps.")]
        public float gravity = 0.3f;
        public float dropRadiusMm = 1.1f;
        [Tooltip("Off when a liquid-blood renderer feature draws BloodDrops.Buffer instead.")]
        public bool drawSimpleDrops = true;
        [Tooltip("Drops per second per cm of wound, before the tissue's redness multiplies it.")]
        public float bleedRate = 25f;
        [Tooltip("Off: a dry dissection. Blood is hidden and paused, and new cuts do not bleed; on again shows it.")]
        public bool showBlood = true;

        [StructLayout(LayoutKind.Sequential)]
        private struct EmitRequest
        {
            public Vector3 position;
            public float radius;
            public Vector3 normal;
            public float pad;
        }

        private class Wound
        {
            public Vector3 a, b, n, lip;
            public float rate, age, acc;
            public bool leak;
        }

        private const int MaxEmitPerFrame = 512;
        private const float FillSeconds = 1.2f, LifeSeconds = 25f;

        private PhotoBody body;
        private MaskVolume mask;
        private ComputeShader cs;
        private int kEmit, kStep, kResolve, kClear;
        private ComputeBuffer drops, state, emitBuffer;
        private RenderTexture stainAccum, stain;
        private Vector3Int stainDims;
        private Material dropMaterial;
        private MaterialPropertyBlock dropProps;
        private readonly List<EmitRequest> pending = new List<EmitRequest>();
        private readonly List<Wound> wounds = new List<Wound>();
        private EmitRequest[] emitArray;
        private BloodDrop[] zeros;
        private int ring;
        private float clock, activeUntil;       // simulation time, so Advance() works outside Play mode too

        public bool Ready => drops != null;

        /// <summary>Which way is down, in the body's local axes (zero: the world's down, so turning the body turns it).</summary>
        public Vector3 downLocalOverride;

        private Vector3 LocalDown(Transform t) =>
            downLocalOverride.sqrMagnitude > 1e-6f ? downLocalOverride.normalized : t.InverseTransformDirection(Vector3.down);

        public void Attach(PhotoBody photoBody, MaskVolume dissectionMask)
        {
            Release();
            body = photoBody;
            mask = dissectionMask;
            cs = Resources.Load<ComputeShader>("BloodSim");
            if (cs == null || !SystemInfo.supportsComputeShaders)
            {
                Debug.LogWarning("Bleeding unavailable: compute shaders not supported or BloodSim.compute missing");
                return;
            }
            kEmit = cs.FindKernel("Emit");
            kStep = cs.FindKernel("Step");
            kResolve = cs.FindKernel("Resolve");
            kClear = cs.FindKernel("Clear");

            drops = new ComputeBuffer(capacity, Marshal.SizeOf<BloodDrop>());
            state = new ComputeBuffer(capacity, 32);
            emitBuffer = new ComputeBuffer(MaxEmitPerFrame, Marshal.SizeOf<EmitRequest>());
            emitArray = new EmitRequest[MaxEmitPerFrame];
            zeros = new BloodDrop[capacity];
            drops.SetData(zeros);
            state.SetData(new byte[capacity * 32]);

            Vector3Int d = body.Space.Dims;
            stainDims = new Vector3Int((d.x + 1) / 2, (d.y + 1) / 2, (d.z + 1) / 2);   // stains at half resolution
            stainAccum = Volume3D(GraphicsFormat.R32_UInt, FilterMode.Point, "Blood stain (sum)");
            stain = Volume3D(GraphicsFormat.R8_UNorm, FilterMode.Bilinear, "Blood stain");
            DispatchClear();
            body.Material.SetTexture("_StainTex", stain);

            Shader s = Shader.Find("DicomViewer/BloodDrop");
            if (s != null) dropMaterial = new Material(s) { name = "Blood drops" };
            dropProps = new MaterialPropertyBlock();
            Publish(false);
        }

        // Renderers see the drops only while blood is moving, so they cost nothing once it has dried.
        private void Publish(bool active)
        {
            BloodDrops.Buffer = active ? drops : null;
            BloodDrops.Capacity = capacity;
            BloodDrops.Body = body != null ? body.transform : null;
        }

        private RenderTexture Volume3D(GraphicsFormat format, FilterMode filter, string name)
        {
            var rt = new RenderTexture(new RenderTextureDescriptor(stainDims.x, stainDims.y, format, 0)
            {
                dimension = TextureDimension.Tex3D, volumeDepth = stainDims.z, enableRandomWrite = true, msaaSamples = 1,
            }) { filterMode = filter, wrapMode = TextureWrapMode.Clamp, name = name };
            rt.Create();
            return rt;
        }

        /// <summary>A new piece of wound (world space). redness 0..1: how much the tissue under it bleeds.</summary>
        public void AddWound(Vector3 aWorld, Vector3 bWorld, Vector3 normalWorld, float redness)
        {
            if (!Ready || !showBlood) return;
            Transform t = body.transform;
            var w = new Wound
            {
                a = t.InverseTransformPoint(aWorld),
                b = t.InverseTransformPoint(bWorld),
                n = t.InverseTransformDirection(normalWorld).normalized,
                leak = Random.value < 0.15f,          // a few strong rivulets, not a curtain
            };
            float lengthCm = Vector3.Distance(w.a, w.b) * 100f;
            w.rate = lengthCm * bleedRate * (1f + 7f * redness);
            // Where it spills once the wound is full: the skin just below the wound's lower edge.
            Vector3 down = LocalDown(t);
            Vector3 along = down - w.n * Vector3.Dot(down, w.n);
            w.lip = (w.a + w.b) * 0.5f + (along.sqrMagnitude > 0.05f ? along.normalized * 0.003f : Vector3.zero);
            wounds.Add(w);
            Emit(w, Mathf.RoundToInt(lengthCm * (6f + 40f * redness)));
            activeUntil = clock + 35f;
        }

        /// <summary>All blood gone (with Heal).</summary>
        public void Clear()
        {
            wounds.Clear();
            pending.Clear();
            if (!Ready) return;
            drops.SetData(zeros);
            DispatchClear();
        }

        private void Emit(Wound w, int count)
        {
            bool spill = w.age > FillSeconds;
            if (spill && !w.leak) return;
            float r = dropRadiusMm / 1000f;
            for (int i = 0; i < count && pending.Count < MaxEmitPerFrame; i++)
            {
                Vector3 p = spill
                    ? w.lip + Random.insideUnitSphere * 0.0004f
                    : Vector3.Lerp(w.a, w.b, Random.value) - w.n * 0.001f;     // inside the wound
                pending.Add(new EmitRequest { position = p, radius = r * Random.Range(0.8f, 1.2f), normal = w.n });
            }
        }

        private void Update()
        {
            if (body != null && body.Material != null) body.Material.SetFloat("_ShowStain", showBlood ? 1f : 0f);
            if (Ready && body != null && body.IsLoaded) Tick(Mathf.Min(Time.deltaTime, 0.05f));
        }

        /// <summary>Runs the bleeding for `seconds` at 60 steps a second (snapshots and tests, outside Play mode).</summary>
        public void Advance(float seconds)
        {
            if (!Ready) return;
            for (float t = 0f; t < seconds; t += 1f / 60f) Tick(1f / 60f);
        }

        private void Tick(float dt)
        {
            if (!showBlood)
            {
                Publish(false);                  // hidden and paused where it is
                return;
            }
            clock += dt;
            for (int i = wounds.Count - 1; i >= 0; i--)
            {
                Wound w = wounds[i];
                w.age += dt;
                w.acc += w.rate * (w.leak ? 4f : 1f) * Mathf.Exp(-w.age / 8f) * dt;
                int n = Mathf.FloorToInt(w.acc);
                if (n > 0)
                {
                    Emit(w, n);
                    w.acc -= n;
                }
                if (w.age > LifeSeconds) wounds.RemoveAt(i);
            }
            bool active = clock <= activeUntil || pending.Count > 0;
            Publish(active);
            if (!active) return;

            SetCommon(dt);
            if (pending.Count > 0)
            {
                pending.CopyTo(emitArray);
                emitBuffer.SetData(emitArray, 0, 0, pending.Count);
                cs.SetInt("_EmitCount", pending.Count);
                cs.SetInt("_EmitStart", ring);
                ring = (ring + pending.Count) % capacity;
                Bind(kEmit);
                cs.SetBuffer(kEmit, "_Emit", emitBuffer);
                cs.Dispatch(kEmit, (pending.Count + 63) / 64, 1, 1);
                pending.Clear();
                activeUntil = clock + 35f;
            }
            int sub = Mathf.Clamp(Mathf.CeilToInt(dt * 90f), 1, 4);
            cs.SetFloat("_Dt", dt / sub);
            Bind(kStep);
            for (int i = 0; i < sub; i++) cs.Dispatch(kStep, (capacity + 63) / 64, 1, 1);
            cs.SetTexture(kResolve, "_StainAccum", stainAccum);
            cs.SetTexture(kResolve, "_Stain", stain);
            cs.Dispatch(kResolve, (stainDims.x + 7) / 8, (stainDims.y + 7) / 8, (stainDims.z + 7) / 8);
        }

        private void LateUpdate()
        {
            if (!Ready || !drawSimpleDrops || dropMaterial == null || BloodDrops.Buffer != drops) return;
            if (Time.frameCount - BloodFluidFeature.LastQueuedFrame <= 2) return;     // the liquid renderer draws them
            dropProps.SetBuffer("_Drops", drops);
            dropProps.SetMatrix("_BodyToWorld", body.transform.localToWorldMatrix);
            dropProps.SetFloat("_BodyScale", body.transform.lossyScale.x);
            var rp = new RenderParams(dropMaterial)
            {
                worldBounds = new Bounds(body.transform.position, Vector3.one * 10f),
                matProps = dropProps,
                shadowCastingMode = ShadowCastingMode.Off,
                receiveShadows = false,
            };
            Graphics.RenderPrimitives(rp, MeshTopology.Triangles, 6, capacity);
        }

        private void SetCommon(float dt)
        {
            Vector3Int d = body.Space.Dims;
            Vector3 size = body.SizeM;
            cs.SetInt("_Capacity", capacity);
            cs.SetInts("_StainDims", stainDims.x, stainDims.y, stainDims.z);
            cs.SetVector("_SizeM", size);
            cs.SetVector("_VoxelM", new Vector3(size.x / d.x, size.y / d.y, size.z / d.z));
            cs.SetVector("_Gravity", LocalDown(body.transform) * gravity);
            cs.SetFloat("_Dt", dt);
            Texture m = mask != null ? mask.MaskTexture : null;
            cs.SetFloat("_MaskOn", m != null ? 1f : 0f);
        }

        private void Bind(int kernel)
        {
            cs.SetBuffer(kernel, "_Drops", drops);
            cs.SetBuffer(kernel, "_State", state);
            cs.SetTexture(kernel, "_ColorTex", body.ColourTexture);
            Texture m = mask != null ? mask.MaskTexture : null;
            cs.SetTexture(kernel, "_MaskTex", m != null ? m : body.ColourTexture);
            cs.SetTexture(kernel, "_StainAccum", stainAccum);
        }

        private void DispatchClear()
        {
            cs.SetInts("_StainDims", stainDims.x, stainDims.y, stainDims.z);
            cs.SetTexture(kClear, "_StainAccum", stainAccum);
            cs.SetTexture(kClear, "_Stain", stain);
            cs.Dispatch(kClear, (stainDims.x + 7) / 8, (stainDims.y + 7) / 8, (stainDims.z + 7) / 8);
        }

        private void Release()
        {
            drops?.Release();
            state?.Release();
            emitBuffer?.Release();
            drops = state = emitBuffer = null;
            if (stainAccum != null) stainAccum.Release();
            if (stain != null) stain.Release();
            stainAccum = stain = null;
            if (BloodDrops.Body == (body != null ? body.transform : null)) BloodDrops.Buffer = null;
        }

        private void OnDestroy() => Release();
    }
}
