// Sclera: off-white, faintly blue-grey near the limbus and pink toward the corners, with veins from a
// runtime-generated polar texture (u = angle around the look axis, v = angle from the limbus). The eye's
// look axis is object-space +Z, so the tint and vein density are driven by the object-space direction.
Shader "DicomViewer/LivingEyeSclera"
{
    Properties
    {
        _Wetness ("Wetness", Range(0, 1)) = 1
        _VeinStrength ("Vein strength", Range(0, 2)) = 0.7
        _VeinColor ("Vein colour", Color) = (0.62, 0.10, 0.09, 1)
        _TintFront ("Tint near limbus", Color) = (0.90, 0.93, 0.97, 1)
        _TintBack ("Tint toward corners", Color) = (0.97, 0.89, 0.86, 1)
        _SSSColor ("Scatter colour", Color) = (0.95, 0.35, 0.28, 1)
        _EyeGeom ("Geometry: radius, cos(limbus), -, -", Vector) = (0.012, 0.873, 0, 0)
        _VeinTex ("Vein texture (generated)", 2D) = "black" {}
    }

    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Opaque" "Queue" = "Geometry" }

        HLSLINCLUDE
        #pragma target 4.5
        #pragma exclude_renderers gles

        #include "LivingEyeCommon.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float  _Wetness;
            float  _VeinStrength;
            float4 _VeinColor;
            float4 _TintFront;
            float4 _TintBack;
            float4 _SSSColor;
            float4 _EyeGeom;
            float4 _VeinTex_ST;
        CBUFFER_END

        TEXTURE2D(_VeinTex);
        SAMPLER(sampler_VeinTex);
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite On
            ZTest LEqual

            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BLENDING
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_ATLAS

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS   : TEXCOORD1;
                float3 positionOS : TEXCOORD2;
            };

            Varyings Vert(EyeAttributes i)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(i.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(i.normalOS);
                o.positionOS = i.positionOS.xyz;
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 n = normalize(i.normalWS);
                float3 v = GetWorldSpaceNormalizeViewDir(i.positionWS);
                float3 dOS = normalize(i.positionOS);
                float cosA = dOS.z;                                      // 1 = look axis, -1 = back pole

                // 0 at the limbus, 1 well behind the equator: drives tint and vein density.
                float edge = saturate((_EyeGeom.y - cosA) / 1.3);
                edge = edge * edge * (3.0 - 2.0 * edge);

                float2 uv = float2(atan2(dOS.y, dOS.x) * INV_TWO_PI + 0.5, acos(clamp(cosA, -1.0, 1.0)) * INV_PI);
                float4 vt = SAMPLE_TEXTURE2D(_VeinTex, sampler_VeinTex, uv);   // r = veins, g = mottling

                float3 albedo = lerp(_TintFront.rgb, _TintBack.rgb, edge);
                albedo *= 1.0 - 0.06 * vt.g;
                float veins = saturate(vt.r * _VeinStrength * (0.35 + 0.65 * edge));
                albedo = lerp(albedo, _VeinColor.rgb, veins);

                Light mainLight = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                float3 radiance = mainLight.color * (mainLight.shadowAttenuation * mainLight.distanceAttenuation);
                const float wrap = 0.35;
                float NoL = dot(n, mainLight.direction);
                float3 color = albedo * (radiance * EyeWrapDiffuse(NoL, wrap) + SampleSHPixel(half3(0, 0, 0), n));
                // Thin, blood-fed tissue: the shadow side glows faintly warm instead of going grey.
                color += albedo * _SSSColor.rgb * radiance * saturate(0.5 - 0.5 * NoL) * 0.3;

                float rough = lerp(0.35, 0.10, _Wetness);
                const float f0 = 0.03;
                float3 spec = EyeSpecular(n, v, mainLight.direction, rough, f0) * radiance;

                InputData inputData = (InputData)0;
                inputData.positionWS = i.positionWS;
                inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
            #if defined(_ADDITIONAL_LIGHTS)
                uint lightCount = GetAdditionalLightsCount();
                LIGHT_LOOP_BEGIN(lightCount)
                    Light l = GetAdditionalLight(lightIndex, i.positionWS, half4(1, 1, 1, 1));
                    float3 rad = l.color * (l.distanceAttenuation * l.shadowAttenuation);
                    color += albedo * rad * EyeWrapDiffuse(dot(n, l.direction), wrap);
                    spec += EyeSpecular(n, v, l.direction, rough, f0) * rad;
                LIGHT_LOOP_END
            #endif

                float3 refl = GlossyEnvironmentReflection(reflect(-v, n), i.positionWS, rough, 1.0, inputData.normalizedScreenSpaceUV);
                color += spec * lerp(0.4, 1.0, _Wetness) + refl * EyeFresnel(dot(n, v), f0) * lerp(0.3, 1.0, _Wetness);
                return half4(color, 1.0);
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            Cull Back
            ZWrite On
            ColorMask R
            HLSLPROGRAM
            #pragma vertex EyeDepthVert
            #pragma fragment EyeDepthOnlyFrag
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            Cull Back
            ZWrite On
            HLSLPROGRAM
            #pragma vertex EyeDepthVert
            #pragma fragment EyeDepthNormalsFrag
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            Cull Back
            ZWrite On
            ZTest LEqual
            ColorMask 0
            HLSLPROGRAM
            #pragma vertex EyeShadowVert
            #pragma fragment EyeShadowFrag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            ENDHLSL
        }
    }
    Fallback Off
}
