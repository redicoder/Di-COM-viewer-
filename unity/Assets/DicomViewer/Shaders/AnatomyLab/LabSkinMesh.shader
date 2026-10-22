// The body's skin drawn as a mesh (SkinMesh.cs) over the photo volume: its colour read from the photographs just
// under the surface, graded to a living tone, lit as skin (LabSkin.hlsl) with what SkinBake.cs baked into the
// vertices (occlusion, thickness, curvature) and the main light's shadow map (the arm's shadow on the belly).
// Where the scalpel has cut (the dissection mask), where a sheet has lifted the skin away, and where the eyes
// open, the mesh is cut away and the volume beneath shows instead. Vertices are in body millimetres under the
// body's volume (SkinMesh's root). The second pass casts the mesh's shadow, with the same holes.
Shader "DicomViewer/LabSkinMesh"
{
    Properties
    {
        _ColorTex ("Photo colour (RGB) + tissue (A)", 3D) = "" {}
        _MaskTex ("Dissection mask", 3D) = "white" {}
        _StainTex ("Blood stain", 3D) = "black" {}
        _SkinDepthTex ("Skin depth (mm)", 3D) = "black" {}
        _SheetMaps ("Sheet maps (TissueSheets)", 2DArray) = "" {}
        _SkinLut ("Skin scattering LUT (SkinBake)", 2D) = "white" {}
        _ShowStain ("Show blood stains", Float) = 1
        _Living ("Living tone (0 as photographed, 1 alive)", Range(0, 1)) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry-10" "RenderPipeline" = "UniversalPipeline" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _SizeMm;
            float4 _SizeM;
            float _MaskEnabled, _ShowStain, _Living;
            float _HasLids, _Open;
            float4 _Eye0, _Eye1;
            float _RegionOn;                 // 1: a finer export's mesh covers the box below; this one stays out
            float4 _RegionMin, _RegionMax;   // body mm
            float _ClipBelowMm;              // a region's mesh: nothing below this height (the export's cut end)
        CBUFFER_END

        #include "LabBody.hlsl"
        #include "LabSkin.hlsl"

        // Where the mesh is cut away: the scalpel's track, skin lifted by a sheet, the lids' zone while the eyes
        // open, a region drawn at finer detail, and a region's own cut end. Returns the mask (1 intact).
        float CutAway(float3 positionMm, out bool away)
        {
            float3 uvw = positionMm / _SizeMm.xyz;
            away = true;
            if (_RegionOn > 0.5 && all(positionMm >= _RegionMin.xyz) && all(positionMm <= _RegionMax.xyz)) return 0.0;
            if (positionMm.y < _ClipBelowMm) return 0.0;
            float m = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvw, 0).r : 1.0;
            if (m < 0.5) return m;
            if (_SheetCount > 0.5 && SheetHidden(uvw, _SizeMm.xyz)) return m;
            if (_HasLids > 0.5 && _Open > 0.001)
            {
                float3 w = (uvw - 0.5) * _SizeM.xyz;
                if (InLidZone(w, _Eye0) || InLidZone(w, _Eye1)) return m;
            }
            away = false;
            return m;
        }
        ENDHLSL

        Pass
        {
            Name "LabSkinMesh"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float4 color : COLOR; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 normalWS : TEXCOORD1;
                float3 positionMm : TEXCOORD2;
                float3 normalMm : TEXCOORD3;
                float3 bake : TEXCOORD4;         // occlusion, thickness mm, curvature 1/mm (SkinBake.cs)
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.positionMm = v.positionOS.xyz;
                o.normalMm = v.normalOS;
                o.bake = float3(v.color.r, v.color.g * 60.0, v.color.b * 0.25);
                return o;
            }

            // From the frozen cadaver's photographed tone to a living one: blood in the skin, the blue bath's cast
            // gone, a little more saturation. Set by eye; _Living blends from the photographs (0) to this (1).
            float3 Living(float3 albedo)
            {
                float3 g = albedo * float3(1.08, 1.00, 1.16);
                float l = dot(g, float3(0.3, 0.59, 0.11));
                g = lerp(l.xxx, g, 0.98);
                g += float3(0.02, 0.0, 0.015) * saturate(1.0 - l);          // a little warmth in the shadows
                return lerp(LabSkinGrade(albedo, 1.0), saturate(g), _Living);
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float3 uvw = i.positionMm / _SizeMm.xyz;
                float3 N = normalize(i.normalWS);
                float3 nMm = normalize(i.normalMm);

                bool away;
                float m = CutAway(i.positionMm, away);
                if (away) discard;

                // Colour from just under the skin, averaged over 2 mm of surface (the frozen photographs are
                // blotchy with pooled blood; living skin has an even base, its detail is in the relief).
                float3 inside = (i.positionMm - nMm * 0.7) / _SizeMm.xyz;
                float3 T = normalize(cross(nMm, abs(nMm.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0)));
                float3 B = cross(nMm, T);
                float3 sum = 0.0;
                [unroll] for (int k = 0; k < 7; k++)
                {
                    float ang = k * 0.8976;                                    // 2 pi / 7
                    float3 off = k == 0 ? 0.0 : (T * cos(ang) + B * sin(ang)) * 1.8;   // mm
                    sum += SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, inside + off / _SizeMm.xyz, 0).rgb;
                }
                float3 albedo = Living(sum / 7.0);
                float skin = smoothstep(0.5, 1.0, m);
                float stain = SAMPLE_TEXTURE3D_LOD(_StainTex, sampler_StainTex, uvw, 0).r;
                float wet = smoothstep(0.04, 0.35, stain) * _ShowStain;
                albedo = lerp(albedo, float3(0.13, 0.0018, 0.0025), wet * 0.92);

                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                Light light = GetMainLight(shadowCoord);
                float aoInstr = 1.0, shade = light.shadowAttenuation;
                if (_InstrCount > 0.5) shade *= InstrumentShade(i.positionWS, light.direction, aoInstr);
                float3 lit = LabShadeSkinBaked(albedo, N, V, light.direction, light.color, wet, skin, aoInstr, shade,
                                               i.positionMm, LabPixelMm(i.positionWS), i.bake);
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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionMm : TEXCOORD0; };

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
                o.positionMm = v.positionOS.xyz;
                return o;
            }

            half4 ShadowFrag(Varyings i) : SV_Target
            {
                bool away;
                CutAway(i.positionMm, away);
                if (away) discard;
                return 0;
            }
            ENDHLSL
        }
    }
}
