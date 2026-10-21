// The Anatomy Lab's instruments (LabInstruments.cs): a steel scalpel and gloved hands. Simple lit surfaces with a
// studio-style reflection (the lab has no environment for steel to mirror): a bright overhead softbox and a dark
// floor. _Ridges: grip grooves across a scalpel handle (object-space y from .x to .y, every .z mm, on when .w > 0).
Shader "DicomViewer/LabInstrument"
{
    Properties
    {
        _Color ("Colour", Color) = (0.7, 0.7, 0.72, 1)
        _Metallic ("Metallic", Range(0, 1)) = 1
        _Smoothness ("Smoothness", Range(0, 1)) = 0.8
        _Sheen ("Sheen (glove rim)", Range(0, 1)) = 0
        _Wrap ("Light wrap (soft material)", Range(0, 1)) = 0
        _Ridges ("Grip ridges: y0, y1, pitch, on", Vector) = (0, 0, 1, 0)
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Name "LabInstrument"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _Color;
                float _Metallic, _Smoothness, _Sheen, _Wrap;
                float4 _Ridges;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionOS : TEXCOORD2;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.positionOS = v.positionOS.xyz;
                return o;
            }

            // A photographer's studio: dark below, a soft grey sky, one big softbox up front and a strip light.
            float3 Studio(float3 r, float rough)
            {
                float3 c = lerp(float3(0.05, 0.05, 0.055), float3(0.55, 0.57, 0.6), smoothstep(-0.35, 0.65, r.y));
                float k = lerp(60.0, 6.0, rough);
                c += 2.2 * pow(saturate(dot(r, normalize(float3(-0.35, 0.75, -0.55)))), k);
                c += 0.9 * pow(saturate(dot(r, normalize(float3(0.8, 0.2, -0.3)))), k * 0.6);
                return c;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 N = normalize(i.normalWS);
                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                if (dot(N, V) < 0.0) N = -N;                       // thin blade: lit from either side
                float3 albedo = _Color.rgb;
                float smooth = _Smoothness;
                if (_Ridges.w > 0.0 && i.positionOS.y > _Ridges.x && i.positionOS.y < _Ridges.y)
                {
                    float g = abs(frac(i.positionOS.y / _Ridges.z) - 0.5) * 2.0;   // 0 in a groove
                    float groove = 1.0 - smoothstep(0.15, 0.4, g);
                    albedo *= 1.0 - 0.45 * groove;
                    smooth -= 0.3 * groove;
                }

                Light light = GetMainLight();
                float3 L = light.direction;
                float ndl = saturate((dot(N, L) + _Wrap) / (1.0 + _Wrap));
                float3 H = normalize(L + V);
                float rough = 1.0 - smooth;
                float specPow = exp2(11.0 * smooth + 1.0);
                float3 f0 = lerp(float3(0.04, 0.04, 0.04), albedo, _Metallic);
                float nv = saturate(dot(N, V));
                float3 F = f0 + (1.0 - f0) * pow(1.0 - nv, 5.0) * smooth;
                float3 spec = F * pow(saturate(dot(N, H)), specPow) * (specPow + 8.0) / 25.0 * ndl;
                float3 diffuse = albedo * (1.0 - _Metallic) * (light.color * ndl + max(SampleSH(N), 0.18));
                float3 refl = F * Studio(reflect(-V, N), rough) * lerp(0.35, 1.0, _Metallic);
                float3 sheen = _Sheen * pow(1.0 - nv, 3.0) * albedo * 0.8;
                return half4(diffuse + spec * light.color + refl + sheen, 1.0);
            }
            ENDHLSL
        }
    }
}
