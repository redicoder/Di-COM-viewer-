// A structure taken out of the body as a piece (OrganPiece.cs): its surface coloured from the photographs where
// it came from (each vertex keeps its volume coordinate), lit as wet cut tissue (LabSkin.hlsl), casting and
// receiving the main light's shadow.
Shader "DicomViewer/LabOrganPiece"
{
    Properties
    {
        _ColorTex ("Photo colour (RGB) + tissue (A)", 3D) = "" {}
        _Wet ("Wetness of the surface", Range(0, 1)) = 0.35
        _SkinAmount ("Skin (1) or cut tissue (0)", Range(0, 1)) = 0
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }

        Pass
        {
            Name "LabOrganPiece"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "LabSkin.hlsl"

            TEXTURE3D(_ColorTex);  SAMPLER(sampler_ColorTex);
            CBUFFER_START(UnityPerMaterial)
                float4 _SizeMm;
                float _Wet, _SkinAmount;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float3 uvw : TEXCOORD0; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 uvw : TEXCOORD2;
                float3 normalOS : TEXCOORD3;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uvw = v.uvw;
                o.normalOS = v.normalOS;
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 N = normalize(i.normalWS);
                // The colour a little inside the surface (the boundary voxels mix with the neighbour's tissue).
                float3 inward = -normalize(i.normalOS) * 0.8 / _SizeMm.xyz;
                float3 c = 0.0;
                c += SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, i.uvw + inward, 0).rgb;
                c += SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, i.uvw + inward * 2.0, 0).rgb;
                float3 albedo = LabSkinGrade(c * 0.5, 0.0);
                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                Light light = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                float3 lit = LabShadeSkin(albedo, N, V, light.direction, light.color, _Wet, _SkinAmount, 1.0, light.shadowAttenuation,
                                          i.uvw * _SizeMm.xyz, LabPixelMm(i.positionWS));
                lit = min(max(lit, 0.0), 8.0);                                           // finite, whatever happens
                return half4(lit, 1.0);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Back

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings { float4 positionCS : SV_POSITION; };

            Varyings ShadowVert(Attributes v)
            {
                Varyings o;
                float3 positionWS = TransformObjectToWorld(v.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - positionWS);
            #else
                float3 lightDir = _LightDirection;
            #endif
                float4 positionCS = TransformWorldToHClip(ApplyShadowBias(positionWS, normalWS, lightDir));
            #if UNITY_REVERSED_Z
                positionCS.z = min(positionCS.z, UNITY_NEAR_CLIP_VALUE);
            #else
                positionCS.z = max(positionCS.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                o.positionCS = positionCS;
                return o;
            }

            half4 ShadowFrag(Varyings i) : SV_Target { return 0; }
            ENDHLSL
        }
    }
}
