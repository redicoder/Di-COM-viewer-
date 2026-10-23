// The dissection table and floor (LabRoom.cs): lit steel or matt paint, with the body's shadow on them. The body is
// a ray-marched volume, so it casts no ordinary shadow; this shader marches the photo volume's tissue from each
// point of the table towards the light (a soft shadow that widens with distance, as a lamp's does) and along the
// table's normal (the dark seam where he touches it). Vertices are in body millimetres (LabRoom's root).
Shader "DicomViewer/LabTable"
{
    Properties
    {
        _Color ("Colour", Color) = (0.6, 0.62, 0.64, 1)
        _Metallic ("Metallic", Range(0, 1)) = 1
        _Smoothness ("Smoothness", Range(0, 1)) = 0.5
        _BodyTex ("Body (alpha = tissue)", 3D) = "black" {}
        _LabelTex ("Object labels (BodyLabels)", 3D) = "black" {}
        _LabelHideTex ("Hidden labels, 256 x 1", 2D) = "black" {}
        _SizeMm ("Body size, mm", Vector) = (1, 1, 1, 0)
        _LightDirBody ("Towards the light, body mm axes", Vector) = (0, 0, -1, 0)
        _NormalBody ("Table normal, body mm axes", Vector) = (0, 1, 0, 0)
        _ShadowRange ("Shadow march length, mm", Float) = 700
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Name "LabTable"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE3D(_BodyTex); SAMPLER(sampler_BodyTex);
            TEXTURE3D(_LabelTex); SAMPLER(sampler_LabelTex);       // what the student took away casts no shadow
            TEXTURE2D(_LabelHideTex); SAMPLER(sampler_LabelHideTex);
            SamplerState lab_point_clamp_sampler;
            float _LayersOn;

            CBUFFER_START(UnityPerMaterial)
                float4 _Color;
                float _Metallic, _Smoothness;
                float4 _SizeMm, _LightDirBody, _NormalBody;
                float _ShadowRange;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionMm : TEXCOORD2;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.positionMm = v.positionOS.xyz;
                return o;
            }

            float Tissue(float3 mm)
            {
                float3 uvw = mm / _SizeMm.xyz;
                if (any(uvw < 0.0) || any(uvw > 1.0)) return 0.0;
                float a = SAMPLE_TEXTURE3D_LOD(_BodyTex, sampler_BodyTex, uvw, 0).a;
                if (a > 0.0 && _LayersOn > 0.5)
                {
                    float li = round(SAMPLE_TEXTURE3D_LOD(_LabelTex, sampler_LabelTex, uvw, 0).r * 255.0);
                    if (li < 0.5) return SAMPLE_TEXTURE3D_LOD(_BodyTex, lab_point_clamp_sampler, uvw, 0).a <= 0.0 ? 0.0 : a;
                    if (SAMPLE_TEXTURE2D_LOD(_LabelHideTex, sampler_LabelHideTex, float2((li + 0.5) / 256.0, 0.5), 0).r > 0.5) return 0.0;
                }
                return a;
            }

            // How much of the light the body blocks on its way to this point: a soft shadow, sharp near a contact
            // and spreading further away, as a lamp's shadow does.
            float Shadow(float3 p)
            {
                float3 L = normalize(_LightDirBody.xyz);
                float sh = 0.0;
                [loop] for (int i = 1; i <= 28; i++)
                {
                    float f = i / 28.0;
                    float t = f * f * _ShadowRange;                  // fine steps near the table
                    float a = Tissue(p + L * t);
                    sh = max(sh, a * (1.0 - 0.55 * f));
                }
                return sh;
            }

            // The dark seam where he lies on the table.
            float Contact(float3 p)
            {
                float3 N = normalize(_NormalBody.xyz);
                float occ = 0.0;
                [unroll] for (int i = 1; i <= 8; i++)
                {
                    float t = i * 7.0;
                    occ = max(occ, Tissue(p + N * t) * (1.0 - t / 60.0));
                }
                return occ;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 N = normalize(i.normalWS);
                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                Light light = GetMainLight();
                float3 L = light.direction;
                float shade = 1.0 - 0.78 * Shadow(i.positionMm);
                float contact = 1.0 - 0.6 * Contact(i.positionMm);
                float ndl = saturate(dot(N, L));
                float3 H = normalize(L + V);
                float rough = 1.0 - _Smoothness;
                float specPow = exp2(10.0 * _Smoothness + 1.0);
                float3 f0 = lerp(float3(0.04, 0.04, 0.04), _Color.rgb, _Metallic);
                float nv = saturate(dot(N, V));
                float3 F = f0 + (1.0 - f0) * pow(1.0 - nv, 5.0) * _Smoothness;
                float3 spec = F * pow(saturate(dot(N, H)), specPow) * (specPow + 8.0) / 25.0 * ndl * shade;
                float3 ambient = lerp(float3(0.10, 0.10, 0.11), float3(0.38, 0.39, 0.42), N.y * 0.5 + 0.5);
                // Steel mirrors a dim room: a soft sheen rather than a true reflection.
                float3 sheen = F * lerp(float3(0.16, 0.16, 0.17), float3(0.55, 0.56, 0.60), saturate(reflect(-V, N).y * 0.5 + 0.5)) * (0.5 + 0.5 * rough);
                float3 diffuse = _Color.rgb * (1.0 - _Metallic) * (light.color * ndl * shade + ambient);
                float3 color = (diffuse + light.color * spec + sheen) * contact;
                return half4(color, 1.0);
            }
            ENDHLSL
        }
    }
}
