// Skin and fat taken in hand (TissueSheets.cs): a mesh whose every vertex knows where its tissue came from (uv0, a
// texture coordinate in the photo volume), so a lifted flap or a loose piece shows the real photographed skin on
// top, the yellow fat under it and the layers of the skin on its cut walls (uv1.x = 1 on cut surfaces, drawn wet).
// Blood that ran over the skin before it was lifted stays on it (the stain is sampled where the tissue came from).
Shader "DicomViewer/TissueSheet"
{
    Properties
    {
        _ColorTex ("Photo colour (RGB) + tissue (A)", 3D) = "" {}
        _StainTex ("Blood stain", 3D) = "black" {}
        _ShowStain ("Show blood stains", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Name "TissueSheet"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            ZWrite On

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "LabSkin.hlsl"

            TEXTURE3D(_ColorTex);  SAMPLER(sampler_ColorTex);
            TEXTURE3D(_StainTex);  SAMPLER(sampler_StainTex);

            CBUFFER_START(UnityPerMaterial)
                float _ShowStain;
                float4 _SizeMm;            // the body's size, to carry a millimetre position with the tissue
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float3 uvw : TEXCOORD0; float2 flags : TEXCOORD1; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 uvw : TEXCOORD2;
                float cut : TEXCOORD3;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uvw = v.uvw;
                o.cut = v.flags.x;
                return o;
            }

            half4 Frag(Varyings i, bool front : SV_IsFrontFace) : SV_Target
            {
                float3 N = normalize(i.normalWS) * (front ? 1.0 : -1.0);
                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                float4 c = SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, i.uvw, 0);
                // Where the sample point slipped out of the tissue (a fold's thin edge), fall back to fat's colour.
                float3 albedo = lerp(float3(0.78, 0.66, 0.42), c.rgb, saturate(c.a * 2.0));
                float cut = saturate(i.cut);
                albedo = LabSkinGrade(albedo, 1.0 - cut);
                float stain = SAMPLE_TEXTURE3D_LOD(_StainTex, sampler_StainTex, i.uvw, 0).r * (1.0 - cut);
                float wet = max(smoothstep(0.04, 0.35, stain) * _ShowStain, 0.0);
                albedo = lerp(albedo, float3(0.13, 0.0018, 0.0025), wet * 0.92);

                Light light = GetMainLight();
                float3 lit = LabShadeSkin(albedo, N, V, light.direction, light.color, wet, 1.0 - cut, 1.0, 1.0, i.uvw * _SizeMm.xyz, LabPixelMm(i.positionWS));
                return half4(lit, 1.0);
            }
            ENDHLSL
        }
    }
}
