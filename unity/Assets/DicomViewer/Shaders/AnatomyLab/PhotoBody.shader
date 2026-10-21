// The photographed body (DicomViewer.AnatomyLab.PhotoBody): ray-marches the colour photo volume in the unit cube and
// shades the first tissue it meets. Cut walls (from the dissection mask) show the photo's own colour; intact skin
// takes its colour from 1.5 mm under the surface (the photos' outermost pixels mix with the blue gelatin). Blood
// stains, eyelids that slide open, and modelled eyes in place of the real ones. Writes SV_Depth, so meshes and blood
// drops drawn after it are hidden behind tissue.
Shader "DicomViewer/PhotoBody"
{
    Properties
    {
        _ColorTex ("Photo colour (RGB) + tissue (A)", 3D) = "" {}
        _MaskTex ("Dissection mask", 3D) = "white" {}
        _StainTex ("Blood stain", 3D) = "black" {}
        _LidTex ("Eyelids (0.25 lower, 0.5 upper)", 3D) = "black" {}
        _OccTex ("Occupancy (tissue somewhere in this brick)", 3D) = "white" {}
        _ShowStain ("Show blood stains", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Name "PhotoBody"
            Tags { "LightMode" = "UniversalForward" }
            Cull Front
            ZWrite On
            ZTest LEqual

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            #define BRICK 8.0

            TEXTURE3D(_ColorTex);  SAMPLER(sampler_ColorTex);
            TEXTURE3D(_MaskTex);   SAMPLER(sampler_MaskTex);
            TEXTURE3D(_StainTex);  SAMPLER(sampler_StainTex);
            TEXTURE3D(_LidTex);    SAMPLER(sampler_LidTex);
            TEXTURE3D(_OccTex);    SAMPLER(sampler_point_clamp);

            CBUFFER_START(UnityPerMaterial)
                float4 _Dims;              // voxels per axis
                float4 _SizeM;             // body size in metres (x left, y up, z back)
                float _MaskEnabled;
                float _HasLids;
                float _Open;               // eyelids: 0 shut .. 1 open
                float _ModelEyes;          // 1: the real eyeballs are hidden, modelled eyes sit in their place
                float _StepScale;          // ray step in voxels: 0.5 at rest, 1 while the body moves
                float _ShowStain;          // 0: blood hidden (dry dissection)
                float4 _Eye0, _Eye1;       // per eye: x, lid line y, eyeball centre z, radius (metres)
                float4 _EyeBall0, _EyeBall1;   // the real eyeballs (centre xyz, radius), hidden when _ModelEyes
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 objPos : TEXCOORD0; };
            struct FragOut { half4 color : SV_Target; float depth : SV_Depth; };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.objPos = v.positionOS.xyz;
                return o;
            }

            // Tissue density (0..1) at object-space p after cuts, eyelid movement and the eyeball swap; colour via rgb.
            float Tissue(float3 p, out float3 rgb)
            {
                float3 uvw = p + 0.5;
                float4 c = SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, uvw, 0);
                float m = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvw, 0).r : 1.0;
                float3 w = p * _SizeM.xyz;
                bool lidsMove = _HasLids > 0.5 && _Open > 0.001;
                float keep = 1.0;
                if (lidsMove && SAMPLE_TEXTURE3D_LOD(_LidTex, sampler_LidTex, uvw, 0).r > 0.12) keep = 0.0;
                if (_ModelEyes > 0.5 && (distance(w, _EyeBall0.xyz) < _EyeBall0.w || distance(w, _EyeBall1.xyz) < _EyeBall1.w))
                    keep = 0.0;
                float d = c.a * m * keep;
                rgb = c.rgb;
                if (lidsMove)
                {
                    // Each lid folds towards its attachment: the upper lid is squeezed upwards, the lower downwards,
                    // so the gap between them opens over the eyeball.
                    [unroll] for (int e = 0; e < 2; e++)
                    {
                        float4 E = e == 0 ? _Eye0 : _Eye1;
                        float R = E.w, dx = w.x - E.x;
                        if (abs(dx) >= R || w.z > E.z) continue;       // only in front of the eyeball (the face looks to -z)
                        float s = 1.0 - (dx / R) * (dx / R);
                        float dy = w.y - E.y, ys;
                        bool upper = dy >= 0.0;
                        if (upper) { float hu = _Open * 0.85 * R * s; if (dy > R || dy < hu) continue; ys = (dy - hu) * R / (R - hu); }
                        else       { float hl = _Open * 0.45 * R * s; if (dy < -R || dy > -hl) continue; ys = (dy + hl) * R / (R - hl); }
                        float3 uvs = float3(w.x, E.y + ys, w.z) / _SizeM.xyz + 0.5;
                        float lid = SAMPLE_TEXTURE3D_LOD(_LidTex, sampler_LidTex, uvs, 0).r;
                        if (upper ? lid < 0.37 : (lid < 0.12 || lid > 0.37)) continue;
                        float4 c2 = SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, uvs, 0);
                        float m2 = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvs, 0).r : 1.0;
                        float d2 = c2.a * m2;
                        if (d2 > d) { d = d2; rgb = c2.rgb; }
                    }
                }
                return d;
            }

            float Density(float3 p)
            {
                float3 c;
                return Tissue(p, c);
            }

            FragOut Frag(Varyings i)
            {
                float3 o = TransformWorldToObject(_WorldSpaceCameraPos);
                float3 d = normalize(i.objPos - o);
                float3 inv = 1.0 / d;
                float3 t0 = (-0.5 - o) * inv, t1 = (0.5 - o) * inv;
                float3 tmin = min(t0, t1), tmax = max(t0, t1);
                float tNear = max(max(max(tmin.x, tmin.y), tmin.z), 0.0);
                float tFar = min(min(tmax.x, tmax.y), tmax.z);
                if (tNear >= tFar) discard;

                float maxDim = max(_Dims.x, max(_Dims.y, _Dims.z));
                float fine = max(_StepScale, 0.25) / maxDim;
                float coarse = 0.5 * BRICK / maxDim;                 // half a brick: empty bricks are grown by one
                float t = tNear + fine * 0.5;
                bool hit = false, first = true;
                [loop] for (int k = 0; k < 4096; k++)
                {
                    if (t > tFar) break;
                    float3 p = o + d * t;
                    if (SAMPLE_TEXTURE3D_LOD(_OccTex, sampler_point_clamp, p + 0.5, 0).r < 0.5) { t += coarse; first = false; continue; }
                    if (Density(p) > 0.5) { hit = true; break; }
                    first = false;
                    t += fine;
                }
                if (!hit) discard;

                float a = t - fine, b = t;
                if (!first)
                {
                    [unroll] for (int r = 0; r < 6; r++) { float mid = 0.5 * (a + b); if (Density(o + d * mid) > 0.5) b = mid; else a = mid; }
                }
                float3 p = o + d * b;

                // Gradient in object space; the tissue grows inwards, so the outward normal is -g.
                float3 e = 1.0 / _Dims.xyz;
                float3 g = float3(Density(p + float3(e.x, 0, 0)) - Density(p - float3(e.x, 0, 0)),
                                  Density(p + float3(0, e.y, 0)) - Density(p - float3(0, e.y, 0)),
                                  Density(p + float3(0, 0, e.z)) - Density(p - float3(0, 0, e.z))) / (2.0 * e);
                float3 gm = g / _SizeM.xyz;                             // per metre of body
                bool flat = first || dot(gm, gm) < 1e-6;                // the specimen's own cut edge
                float3 inwardM = flat ? float3(0, 0, 1) : normalize(gm);
                float3 N = flat ? -normalize(TransformObjectToWorldDir(d)) : normalize(TransformObjectToWorldNormal(-g));

                float m0 = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, p + 0.5, 0).r : 1.0;
                float skin = smoothstep(0.8, 1.0, m0);                  // 1 on intact skin, 0 on a cut wall
                float depthM = flat ? 0.0 : lerp(0.0003, 0.0015, skin);
                float3 pc = p + inwardM * depthM / _SizeM.xyz;
                float3 up = float3(0, 1.0 / _Dims.y, 0);                // one photo slice
                float3 c0, c1, c2;
                Tissue(pc - up, c0);
                Tissue(pc, c1);
                Tissue(pc + up, c2);
                float3 albedo = 0.25 * c0 + 0.5 * c1 + 0.25 * c2;      // softens the 1 mm steps between photos

                float stain = max(SAMPLE_TEXTURE3D_LOD(_StainTex, sampler_StainTex, p + 0.5, 0).r,
                                  SAMPLE_TEXTURE3D_LOD(_StainTex, sampler_StainTex, p + 0.5 + inwardM * 0.0006 / _SizeM.xyz, 0).r);
                float wet = smoothstep(0.04, 0.35, stain) * _ShowStain;
                albedo = lerp(albedo, float3(0.13, 0.0018, 0.0025), wet * 0.92);

                float3 wpos = TransformObjectToWorld(p);
                float3 V = normalize(_WorldSpaceCameraPos - wpos);
                Light light = GetMainLight();
                float3 L = light.direction;
                float wrap = saturate((dot(N, L) + 0.35) / 1.35);
                float3 H = normalize(L + V);
                float glisten = max(wet, 1.0 - skin);                    // blood and fresh cut tissue are wet
                float spec = pow(saturate(dot(N, H)), lerp(36.0, 90.0, glisten)) * lerp(0.06, 0.45, glisten);
                float occ = 0.0;
                if (!flat)
                {
                    float3 outM = -inwardM;
                    occ = Density(p + outM * 0.0012 / _SizeM.xyz) + Density(p + outM * 0.0025 / _SizeM.xyz)
                        + Density(p + outM * 0.0045 / _SizeM.xyz);
                }
                float ao = 1.0 - 0.45 * saturate(occ / 3.0) * lerp(0.3, 1.0, skin);
                float3 ambient = max(SampleSH(N), 0.22);
                float3 lit = albedo * (ambient + light.color * wrap * 0.95) * ao + light.color * spec * ao;

                FragOut f;
                f.color = half4(lit, 1.0);
                float4 cs = TransformObjectToHClip(p);
                f.depth = cs.z / cs.w;
                return f;
            }
            ENDHLSL
        }
    }
}
