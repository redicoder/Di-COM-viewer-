// Cornea: a clear dome that adds only what a wet transparent surface adds, specular highlights and a
// Fresnel-weighted environment reflection, and removes the same energy from what is behind it
// (premultiplied blend with alpha = Fresnel). Drawn after opaques, depth-tested, no depth write.
Shader "DicomViewer/LivingEyeCornea"
{
    Properties
    {
        _Wetness ("Wetness", Range(0, 1)) = 1
        _SpecularBoost ("Highlight boost", Range(0.5, 3)) = 1.4
        _EyeGeom ("Geometry: limbus r, cornea r, cornea centre z, iris z", Vector) = (0.00585, 0.0078, 0.00532, 0.0106)
    }

    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Transparent" "Queue" = "Transparent" }

        Pass
        {
            Name "Cornea"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite Off
            ZTest LEqual
            Blend One OneMinusSrcAlpha

            HLSLPROGRAM
            #pragma target 4.5
            #pragma exclude_renderers gles
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

            #include "LivingEyeCommon.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float  _Wetness;
                float  _SpecularBoost;
                float4 _EyeGeom;
            CBUFFER_END


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
                const float f0 = 0.025;                                    // n = 1.376
                float F = EyeFresnel(dot(n, v), f0);
                float rough = lerp(0.09, 0.03, _Wetness);

                Light mainLight = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                float3 radiance = mainLight.color * (mainLight.shadowAttenuation * mainLight.distanceAttenuation);
                float3 spec = EyeSpecular(n, v, mainLight.direction, rough, f0) * radiance;

                InputData inputData = (InputData)0;
                inputData.positionWS = i.positionWS;
                inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
            #if defined(_ADDITIONAL_LIGHTS)
                uint lightCount = GetAdditionalLightsCount();
                LIGHT_LOOP_BEGIN(lightCount)
                    Light l = GetAdditionalLight(lightIndex, i.positionWS, half4(1, 1, 1, 1));
                    spec += EyeSpecular(n, v, l.direction, rough, f0) * l.color * (l.distanceAttenuation * l.shadowAttenuation);
                LIGHT_LOOP_END
            #endif

                float3 refl = GlossyEnvironmentReflection(reflect(-v, n), i.positionWS, rough, 1.0, inputData.normalizedScreenSpaceUV) * F;

                // The tear film pools at the limbus: a faint extra sheen on the outer ring.
                float rN = length(i.positionOS.xy) / _EyeGeom.x;
                float meniscus = smoothstep(0.80, 1.0, rN) * 0.08;

                float3 color = (spec * _SpecularBoost + refl) * lerp(0.6, 1.0, _Wetness) + meniscus * F;
                return half4(color, F);                                    // premultiplied: iris behind loses what the film reflects
            }
            ENDHLSL
        }
    }
    Fallback Off
}
