// A layer of the modelled body (ModelBody: skin, muscles, skeleton; generated models with one colour texture),
// lit as the lab lights tissue (LabSkin.hlsl) with what ModelPolish bakes into the vertex colours: occlusion,
// the tissue behind the surface (light through ears and fingers) and curvature (pre-integrated scattering).
// The texture's own light and dark is read as relief (fibres of a muscle, the pits of a bone, creases of skin):
// a bump from the colour's brightness, by screen-space derivatives, so the model needs no tangents and no
// normal map. _Skin: how much the surface scatters as skin (1 skin, about 0.35 muscle, 0.2 bone). _Gloss: how
// wet and smooth it is (0.1 skin, 0.7 muscle, 0.05 bone). Casts and receives the key light's shadow.
Shader "DicomViewer/LabModel"
{
    Properties
    {
        _BaseTex ("Colour", 2D) = "white" {}
        _SkinDetail ("Skin's own unevenness: blotches, mottle, pores, follicles (0 for other tissue)", Range(0, 1)) = 0
        _VertexAlbedo ("Colour from the vertices (uv0.xy, uv1.x in sRGB; uv1.y extra; gloss in the bake's alpha)", Float) = 0
        _Tint ("Tint", Color) = (1, 1, 1, 1)
        _Saturation ("Saturation", Range(0, 2)) = 1
        _Skin ("Scatters as skin", Range(0, 1)) = 1
        _Gloss ("Wet and smooth", Range(0, 1)) = 0.1
        _Bump ("Relief from the colour, mm", Range(0, 4)) = 0.5
        _Grain ("Fine grain (bone), mm", Range(0, 1)) = 0
        _Occlusion ("Occlusion strength", Range(0, 1)) = 0.7
        _CavityTint ("Colour in the crevices", Color) = (0.8, 0.6, 0.55, 1)
        _SkinLut ("Pre-integrated skin", 2D) = "white" {}
        _SkinLutOn ("Use the lookup", Float) = 0
        _MmPerUnit ("Millimetres per mesh unit", Float) = 890
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }

        Pass
        {
            Name "LabModel"
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
            #include "LabLids.hlsl"

            TEXTURE2D(_BaseTex);  SAMPLER(sampler_BaseTex);
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseTex_ST;
                float4 _Tint;
                float4 _CavityTint;
                float _Saturation, _Skin, _Gloss, _Bump, _Grain, _Occlusion, _MmPerUnit, _VertexAlbedo, _SkinDetail;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; float2 uv2 : TEXCOORD1; float2 uv3 : TEXCOORD2; float4 color : COLOR; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float2 uv : TEXCOORD2;
                float3 positionMm : TEXCOORD3;
                float4 bake : TEXCOORD4;
                float4 data : TEXCOORD5;                                                 // the vertex's own colour (sRGB) and its extra value
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                float3 position = v.positionOS.xyz, normal = v.normalOS, unused = 0.0;
                LabLid(v.uv3, position, normal, unused);                                 // an eyelid, where it is opened
                o.positionWS = TransformObjectToWorld(position);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(normal);
                o.uv = v.uv;
                o.positionMm = v.positionOS.xyz * _MmPerUnit;
                o.bake = v.color;
                o.data = float4(v.uv.x, v.uv.y, v.uv2.x, v.uv2.y);
                return o;
            }

            float Height(float2 uv)
            {
                float3 c = SAMPLE_TEXTURE2D(_BaseTex, sampler_BaseTex, uv).rgb;
                return dot(c, float3(0.3, 0.59, 0.11));
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 N = normalize(i.normalWS);
                // The anatomy model carries its colour in the vertices (there is no UV map); a generated model in a texture.
                bool fromVertices = _VertexAlbedo > 0.5;
                float3 albedo = (fromVertices ? SRGBToLinear(saturate(i.data.rgb)) : SAMPLE_TEXTURE2D(_BaseTex, sampler_BaseTex, i.uv).rgb) * _Tint.rgb;
                float gloss = saturate(_Gloss * (fromVertices ? i.bake.a * 2.0 : 1.0));
                float pixelMm0 = LabPixelMm(i.positionWS);
                [branch] if (_SkinDetail > 0.0)
                {
                    // Skin is never one colour: blood shows in slow blotches a few centimetres across, in a finer mottle of a few
                    // millimetres, and every pore is a little darker. Where hair grows, each follicle is a dark dot.
                    float3 p = i.positionMm;
                    float blotch = LabNoise(p * 0.045) * 0.6 + LabNoise(p * 0.11 + 17.0) * 0.4 - 0.5;
                    float mottle = LabNoise(p * 0.55 + 5.0) - 0.5;
                    float3 redder = float3(1.0, 0.90, 0.88);
                    albedo *= lerp(float3(1, 1, 1), redder, saturate(blotch * 1.6 + mottle * 0.7 + 0.15) * 0.55 * _SkinDetail);
                    albedo *= 1.0 + (blotch * 0.10 + mottle * 0.05) * _SkinDetail;
                    float close = saturate(1.0 - (pixelMm0 - 0.15) / 0.5);              // only where a pixel is smaller than a pore
                    float pore = 1.0 - smoothstep(0.0, 0.30, LabCells(p * 2.1));
                    albedo *= 1.0 - 0.10 * pore * close * _SkinDetail;
                    float hairy = fromVertices ? saturate(i.data.a) : 0.0;
                    float follicle = 1.0 - smoothstep(0.10, 0.34, LabCells(p * 1.35 + 3.0));
                    albedo *= 1.0 - 0.45 * follicle * hairy * saturate(1.0 - (pixelMm0 - 0.2) / 0.8) * _SkinDetail;
                    gloss *= 1.0 - 0.35 * hairy;
                }
                float grey = dot(albedo, float3(0.3, 0.59, 0.11));
                albedo = max(0.0, lerp(grey.xxx, albedo, _Saturation));

                // Relief from the colour's brightness (Mikkelsen's surface gradient): brighter stands a little proud.
                float pixelMm = LabPixelMm(i.positionWS);
                float3 dpdx = ddx(i.positionWS), dpdy = ddy(i.positionWS);
                float2 duvdx = ddx(i.uv), duvdy = ddy(i.uv);
                float seam = max(dot(duvdx, duvdx), dot(duvdy, duvdy));                  // huge where the texture's islands meet
                [branch] if (_Bump > 0.0 && seam < 1e-3 && !fromVertices)
                {
                    float h0 = Height(i.uv);
                    float hx = Height(i.uv + duvdx) - h0, hy = Height(i.uv + duvdy) - h0;
                    float3 r1 = cross(dpdy, N), r2 = cross(N, dpdx);
                    float det = dot(dpdx, r1);
                    float3 grad = sign(det) * (hx * r1 + hy * r2);
                    float fade = saturate(1.0 - (pixelMm - 0.6) / 2.4);                  // none where a pixel covers millimetres
                    N = normalize(abs(det) * N - grad * (_Bump * 0.001 * fade));
                }
                // Bone's fine grain: a procedural pitting too small for the texture.
                [branch] if (_Grain > 0.0)
                {
                    float3 q = i.positionMm * 1.6;
                    const float e = 0.2;
                    float3 g = float3(LabNoise(q + float3(e, 0, 0)) - LabNoise(q - float3(e, 0, 0)),
                                      LabNoise(q + float3(0, e, 0)) - LabNoise(q - float3(0, e, 0)),
                                      LabNoise(q + float3(0, 0, e)) - LabNoise(q - float3(0, 0, e)));
                    g = TransformObjectToWorldDir(g, false);
                    g -= N * dot(g, N);
                    N = normalize(N + g * _Grain * saturate(1.0 - (pixelMm - 0.3) / 1.2));
                }

                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                Light light = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                float open = saturate(i.bake.r);
                float sky = lerp(1.0, open, _Occlusion);
                float ao = lerp(1.0, open * open, _Occlusion);                           // crevices darker than open sky alone
                albedo *= lerp(_CavityTint.rgb, 1.0, smoothstep(0.25, 0.9, open));       // and warmer: light that got there bounced off tissue
                float3 bake = float3(sky, i.bake.g * 60.0, i.bake.b * 0.25);
                float3 lit = LabShadeTissue(albedo, N, V, light.direction, light.color, gloss, _Skin, ao, light.shadowAttenuation,
                                            i.positionMm, pixelMm, bake);
                lit = min(max(lit, 0.0), 8.0);
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
