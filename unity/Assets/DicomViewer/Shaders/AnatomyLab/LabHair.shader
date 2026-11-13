// The body's hair as strands (backend/tools/anatomy_model/hair.py): brows, lashes, the stubble of scalp and beard,
// the hair of chest, arms and legs. Every hair is a ribbon whose two vertices per ring lie ON its centre line; this
// shader pushes them apart to the hair's width, facing the camera. A hair is thinner than a pixel in almost every
// view, so the ribbon is never drawn under a pixel wide and what share of that pixel the hair really covers goes
// into alpha, blended over the skin: without this hair sparkles and vanishes. The strands are not sorted; they are
// thin, mostly a fraction of a pixel, and lie on the skin, so the order hardly shows. Far away, strands are dropped by their random seed and the rest widened, so the hair
// keeps its weight.
// Per vertex: NORMAL = the skin's normal at the root (hair is lit with the skin it grows from), TANGENT = the
// strand's direction, uv0 = (side -1/+1, distance along 0..1), uv1 = (width mm, seed), COLOR = the hair's colour.
// Lighting: Kajiya-Kay diffuse and two highlights along the strand, the key light's shadow, the lab's ambient.
Shader "DicomViewer/LabHair"
{
    Properties
    {
        _WidthScale ("Width scale", Range(0.25, 4)) = 1
        _KeepMm ("Pixel size (mm) from which strands are dropped", Range(0.05, 2)) = 0.3
        _Shine ("Highlight", Range(0, 2)) = 1
        _Darken ("Colour scale", Range(0, 2)) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "RenderPipeline" = "UniversalPipeline" }

        Pass
        {
            Name "LabHair"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            ZWrite Off
            Blend SrcAlpha OneMinusSrcAlpha

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

            CBUFFER_START(UnityPerMaterial)
                float _WidthScale, _KeepMm, _Shine, _Darken;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 tangentOS : TANGENT;
                float2 uv : TEXCOORD0;
                float2 uv2 : TEXCOORD1;
                float2 uv3 : TEXCOORD2;                        // the lashes: their lid's weight and eye (LabLids.hlsl)
                float4 color : COLOR;
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float3 rootNormalWS : TEXCOORD1;
                float3 tangentWS : TEXCOORD2;
                float4 data : TEXCOORD3;                       // side, along, coverage, seed
                float3 colour : TEXCOORD4;
            };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                float3 positionOS = v.positionOS.xyz, tangentOS = v.tangentOS.xyz, normalOS = v.normalOS;
                LabLid(v.uv3, positionOS, tangentOS, normalOS);                 // lashes go with their lid
                float3 centre = TransformObjectToWorld(positionOS);
                float3 T = normalize(TransformObjectToWorldDir(tangentOS));
                float3 V = normalize(_WorldSpaceCameraPos - centre);
                float3 side = cross(T, V);
                side = dot(side, side) > 1e-8 ? normalize(side) : float3(0, 0, 0);
                float pixelMm = max(LabPixelMm(centre), 1e-4);
                // Fewer, wider strands with distance: the seed decides which stay.
                float keep = saturate(_KeepMm / pixelMm);
                float alive = step(v.uv2.y, max(keep, 0.02));
                float widthMm = v.uv2.x * _WidthScale / sqrt(max(keep, 0.02));
                float drawnMm = max(widthMm, pixelMm);                          // never under a pixel wide
                o.positionWS = centre + side * (v.uv.x * 0.5 * drawnMm * 0.001 * alive);
                o.positionCS = TransformWorldToHClip(o.positionWS);
                o.rootNormalWS = TransformObjectToWorldNormal(normalOS);
                o.tangentWS = T;
                o.data = float4(v.uv.x, v.uv.y, saturate(widthMm / pixelMm) * alive, v.uv2.y);
                o.colour = SRGBToLinear(v.color.rgb);
                return o;
            }

            half4 Frag(Varyings i) : SV_Target
            {
                float along = i.data.y;
                float alpha = i.data.z * smoothstep(0.0, 0.08, along + 0.02);    // the root sinks into the skin
                alpha *= 1.0 - smoothstep(0.55, 1.0, abs(i.data.x));              // soft across its width
                clip(alpha - 0.004);

                float3 T = normalize(i.tangentWS);
                float3 N = normalize(i.rootNormalWS);
                float3 V = normalize(_WorldSpaceCameraPos - i.positionWS);
                Light light = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                float3 L = light.direction;
                float shade = light.shadowAttenuation;
                float3 albedo = i.colour * _Darken * lerp(0.6, 1.0, saturate(along * 4.0));   // darker at the root, among its neighbours

                // Kajiya-Kay: a hair is lit most when the light falls across it; the skin's side of the body gates it.
                float tl = dot(T, L);
                float across = sqrt(saturate(1.0 - tl * tl));
                float facing = saturate((dot(N, L) + 0.35) / 1.35);
                float3 diffuse = light.color * across * facing * shade;
                float3 up = float3(0, 1, 0);
                float3 ambient = lerp(float3(0.11, 0.105, 0.10), float3(0.36, 0.365, 0.38), dot(N, up) * 0.5 + 0.5);
                float3 colour = albedo * (diffuse * 0.85 + ambient);

                float3 H = normalize(L + V);
                float th = dot(T, H);
                float sinTH = sqrt(saturate(1.0 - th * th));
                float primary = pow(sinTH, 110.0) * 0.20;                          // the cuticle's white glint
                float secondary = pow(sinTH, 26.0) * 0.14;                         // the broad one, coloured by the hair
                colour += light.color * facing * shade * _Shine * (primary + secondary * albedo * 4.0);
                return half4(min(max(colour, 0.0), 8.0), saturate(alpha * 1.6));
            }
            ENDHLSL
        }
    }
}
