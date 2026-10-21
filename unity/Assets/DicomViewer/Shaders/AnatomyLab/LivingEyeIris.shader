// Iris disc behind the cornea. The cornea is a known sphere (centre on the look axis, radius _EyeGeom.y),
// so each fragment traces its view ray back to the cornea surface, refracts it (air -> cornea, n = 1.376)
// and samples the iris pattern where the refracted ray meets the iris plane. That gives real depth and
// magnification under the dome without any screen-space tricks. Everything is in object space, +Z = look axis.
Shader "DicomViewer/LivingEyeIris"
{
    Properties
    {
        _IrisColor ("Iris colour", Color) = (0.36, 0.22, 0.12, 1)
        _EyeGeom ("Geometry: limbus r, cornea r, cornea centre z, iris z", Vector) = (0.00585, 0.0078, 0.00532, 0.0106)
        _EyeGeom2 ("Geometry: eye r, pupil r, concavity, 1/IOR", Vector) = (0.012, 0.002, 0.25, 0.7267)
        _Caustic ("Caustic strength", Range(0, 1)) = 0.35
        _LimbalRing ("Limbal ring darkness", Range(0, 1)) = 0.8
        _IrisTex ("Iris texture (generated)", 2D) = "gray" {}
    }

    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Opaque" "Queue" = "Geometry" }

        HLSLINCLUDE
        #pragma target 4.5
        #pragma exclude_renderers gles

        #include "LivingEyeCommon.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _IrisColor;
            float4 _EyeGeom;
            float4 _EyeGeom2;
            float  _Caustic;
            float  _LimbalRing;
            float4 _IrisTex_ST;
        CBUFFER_END

        TEXTURE2D(_IrisTex);
        SAMPLER(sampler_IrisTex);
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

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 positionOS : TEXCOORD1;
            };

            Varyings Vert(EyeAttributes i)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(i.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.positionOS = i.positionOS.xyz;
                return o;
            }

            // Where on the iris plane does the light reaching this pixel actually come from?
            float2 RefractedIrisPoint(float3 pOS)
            {
                float3 toCam = IsPerspectiveProjection()
                    ? normalize(TransformWorldToObject(GetCameraPositionWS()) - pOS)
                    : TransformWorldToObjectDir(-GetViewForwardDir());

                float3 c = float3(0.0, 0.0, _EyeGeom.z);
                float rc = _EyeGeom.y;
                float3 oc = pOS - c;
                float b = dot(toCam, oc);
                float h = max(b * b - (dot(oc, oc) - rc * rc), 0.0);
                float3 hit = pOS + toCam * (-b + sqrt(h));              // iris is inside the cornea sphere: take the exit
                float3 nC = normalize(hit - c);
                float3 refr = refract(-toCam, nC, _EyeGeom2.w);
                if (refr.z >= -1e-4) return pOS.xy;                     // grazing/degenerate: fall back to no refraction
                float u = (_EyeGeom.w - hit.z) / refr.z;
                return (hit + refr * u).xy;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 pOS = i.positionOS;
                float2 sxy = RefractedIrisPoint(pOS);
                float rl = _EyeGeom.x;
                float r = length(sxy) / rl;                              // 0 = pupil centre, 1 = limbus
                float ang = atan2(sxy.y, sxy.x) * INV_TWO_PI + 0.5;
                float4 tex = SAMPLE_TEXTURE2D(_IrisTex, sampler_IrisTex, float2(ang, r));   // r fibres, g crypts, b detail

                float rp = _EyeGeom2.y / rl;
                float rCollar = lerp(rp, 1.0, 0.36);

                // Stroma: light and dark radial fibres around the base colour, warmer and denser inside the collarette.
                float3 baseCol = _IrisColor.rgb;
                float3 col = lerp(baseCol * 0.55, baseCol * 1.35 + 0.04, tex.r);
                col *= 1.0 + 0.30 * (tex.b - 0.5);
                float collar = exp(-pow((r - rCollar) / 0.05, 2.0));
                col *= 1.0 + 0.30 * collar;
                col = lerp(col, col * float3(1.10, 0.95, 0.82), saturate((rCollar - r) / 0.08));
                col *= 1.0 - 0.65 * tex.g;                                   // crypts
                col *= 1.0 - _LimbalRing * smoothstep(0.78, 1.02, r);        // limbal ring
                col *= 1.0 - 0.35 * exp(-pow((r - rp - 0.02) / 0.015, 2.0)); // pupillary ruff

                // Pupil: near-black with a soft, slightly blurred edge.
                float pupilMask = 1.0 - smoothstep(rp - 0.015, rp + 0.012, r);
                col = lerp(col, float3(0.012, 0.006, 0.006), pupilMask);

                // Lighting: a shallow dish normal plus a caustic so the side away from the light brightens,
                // the way light focused by the cornea lands on the far side of a real iris.
                float3 nOS = normalize(float3(-pOS.xy / rl * _EyeGeom2.z, 1.0));
                float3 n = TransformObjectToWorldNormal(nOS);
                Light mainLight = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                float3 radiance = mainLight.color * (mainLight.shadowAttenuation * mainLight.distanceAttenuation);
                float3 lOS = TransformWorldToObjectDir(mainLight.direction);
                float2 toCentre = -pOS.xy;
                float caus = dot(toCentre, lOS.xy) / max(length(toCentre) * length(lOS.xy), 1e-5);
                float caustic = 1.0 + _Caustic * saturate(caus) * (1.0 - pupilMask) * saturate(lOS.z + 0.2);

                float3 color = col * (radiance * EyeWrapDiffuse(dot(n, mainLight.direction), 0.25) * caustic
                                      + SampleSHPixel(half3(0, 0, 0), n));

                InputData inputData = (InputData)0;
                inputData.positionWS = i.positionWS;
                inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
            #if defined(_ADDITIONAL_LIGHTS)
                uint lightCount = GetAdditionalLightsCount();
                LIGHT_LOOP_BEGIN(lightCount)
                    Light l = GetAdditionalLight(lightIndex, i.positionWS, half4(1, 1, 1, 1));
                    color += col * l.color * (l.distanceAttenuation * l.shadowAttenuation) * EyeWrapDiffuse(dot(n, l.direction), 0.25);
                LIGHT_LOOP_END
            #endif
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
    }
    Fallback Off
}
