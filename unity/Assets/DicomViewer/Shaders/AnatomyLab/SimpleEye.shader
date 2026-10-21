// A living eye on a sphere (the Unity sphere primitive), looking along the object's -z like the face. Procedural
// iris (radial fibres, darker limbal ring), pupil, off-white sclera with fine veins near the corners, a sharp wet
// highlight. A stand-in until the full living-eye model (cornea refraction) is in.
Shader "DicomViewer/SimpleEye"
{
    Properties
    {
        _IrisColor ("Iris", Color) = (0.45, 0.28, 0.13, 1)
        _Pupil ("Pupil size", Range(0, 1)) = 0.35
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _IrisColor;
                float _Pupil;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 normalOS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionWS : TEXCOORD2;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.normalOS = v.normalOS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 n = normalize(i.normalOS);
                float a = acos(clamp(-n.z, -1.0, 1.0));            // angle from the line of sight
                float th = atan2(n.y, n.x);
                const float irisA = 0.55;
                float pupilA = lerp(0.12, 0.32, _Pupil);
                float r = a / irisA;
                float fib = 0.5 + 0.5 * sin(th * 58.0 + 5.0 * sin(th * 9.0) + r * 3.0);
                float3 iris = lerp(_IrisColor.rgb * 0.3, _IrisColor.rgb * 1.25, fib * 0.55 + 0.35 * r);
                iris *= 1.0 - 0.65 * smoothstep(0.82, 1.0, r);
                float vein = smoothstep(0.93, 1.0, sin(th * 21.0 + a * 13.0) * sin(th * 7.0 - a * 8.0)) * smoothstep(0.9, 1.6, a);
                float3 sclera = lerp(float3(0.86, 0.80, 0.73), float3(0.65, 0.22, 0.18), 0.25 * smoothstep(1.0, 1.7, a) + 0.6 * vein);
                float3 col = lerp(iris, sclera, smoothstep(irisA - 0.02, irisA + 0.03, a));
                col = lerp(float3(0.003, 0.003, 0.003), col, smoothstep(pupilA - 0.02, pupilA + 0.02, a));

                float3 N = normalize(i.normalWS);
                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                Light light = GetMainLight();
                float diff = 0.35 + 0.65 * saturate(dot(N, light.direction));
                float spec = pow(saturate(dot(reflect(-light.direction, N), V)), 160.0) * 1.4;
                float fresnel = pow(1.0 - saturate(dot(N, V)), 3.0) * 0.2;
                return half4(col * diff * light.color + (spec + fresnel) * light.color, 1.0);
            }
            ENDHLSL
        }
    }
}
