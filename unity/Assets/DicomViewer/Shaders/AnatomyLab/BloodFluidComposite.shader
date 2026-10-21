// Final full-screen pass. Reconstructs a world-space surface from the smoothed blood depth, shades it as a
// wet dark-red liquid over the (copied) camera colour, and writes the blood's depth so later transparents sort.
Shader "DicomViewer/BloodFluidComposite"
{
    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" }
        Cull Off
        ZWrite On
        ZTest Always
        Blend Off

        Pass
        {
            Name "Composite"
            HLSLPROGRAM
            #pragma target 4.5
            #pragma exclude_renderers gles
            #pragma vertex Vert
            #pragma fragment Frag
            #include "BloodFluidCommon.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.core/Runtime/Utilities/Blit.hlsl"

            TEXTURE2D_X(_BloodDepth);       // linear eye depth (m), 0 = no blood; point sampled
            TEXTURE2D_X(_BloodThickness);   // metres of blood along the view ray; bilinear
            float4 _BloodDepthTexelSize;    // xy = 1 / depth texture size
            float4 _BloodColor;             // rgb = transmission tint
            float4 _BloodParams;            // x = absorption (1/m), y = specular strength, z = refraction strength, w = edge thickness (m)
            float4 _BloodParams2;           // x = roughness, y = reflection strength, z = scatter strength, w = debug view

            struct Output
            {
                float4 color : SV_Target;
                float  depth : SV_Depth;
            };

            float BloodDepthAt(float2 uv)
            {
                return SAMPLE_TEXTURE2D_X(_BloodDepth, sampler_PointClamp, uv).r;
            }

            float3 WorldAt(float2 uv, float eyeDepth)
            {
                return ComputeWorldSpacePosition(uv, BloodEyeToDeviceDepth(eyeDepth), UNITY_MATRIX_I_VP);
            }

            // Edge-aware tangent: take the neighbour whose depth is closest to the centre, never a neighbour
            // without blood, so silhouettes do not smear the normal.
            float3 Tangent(float2 uv, float2 delta, float dc, float3 P)
            {
                float dp = BloodDepthAt(uv + delta);
                float dm = BloodDepthAt(uv - delta);
                bool okP = dp > 0.0, okM = dm > 0.0;
                if (!okP && !okM) return float3(0.0, 0.0, 0.0);
                bool useP = okP && (!okM || abs(dp - dc) <= abs(dm - dc));
                return useP ? (WorldAt(uv + delta, dp) - P) : (P - WorldAt(uv - delta, dm));
            }

            Output Frag(Varyings i)
            {
                float2 uv = i.texcoord;
                float dc = BloodDepthAt(uv);
                clip(dc - 1e-6);   // no blood here: colour and depth stay as they were
                float t = max(SAMPLE_TEXTURE2D_X(_BloodThickness, sampler_LinearClamp, uv).r, 0.0);

                float3 P = WorldAt(uv, dc);
                float3 V = IsPerspectiveProjection() ? normalize(GetCameraPositionWS() - P) : -GetViewForwardDir();
                float3 tx = Tangent(uv, float2(_BloodDepthTexelSize.x, 0.0), dc, P);
                float3 ty = Tangent(uv, float2(0.0, _BloodDepthTexelSize.y), dc, P);
                float3 n = cross(tx, ty);
                n = (dot(n, n) > 1e-18) ? normalize(n) : V;
                if (dot(n, V) < 0.0) n = -n;   // cross() sign depends on uv handedness; the surface always faces the camera

                Light light = GetMainLight();
                float3 L = normalize(light.direction);
                float3 H = normalize(L + V);
                float NoL = saturate(dot(n, L));
                float NoV = saturate(dot(n, V));
                float NoH = saturate(dot(n, H));
                float VoH = saturate(dot(V, H));

                // Wet surface: water-like F0, GGX with height-correlated Smith visibility.
                const float F0 = 0.02;
                float rough = max(_BloodParams2.x, 0.02);
                float a2 = rough * rough;
                a2 *= a2;
                float dd = NoH * NoH * (a2 - 1.0) + 1.0;
                float D = a2 / (PI * dd * dd);
                float Vis = 0.5 / (NoL * sqrt(NoV * NoV * (1.0 - a2) + a2) + NoV * sqrt(NoL * NoL * (1.0 - a2) + a2) + 1e-4);
                float Fh = F0 + (1.0 - F0) * pow(1.0 - VoH, 5.0);
                float Fv = F0 + (1.0 - F0) * pow(1.0 - NoV, 5.0);
                float3 spec = D * Vis * Fh * NoL * light.color * _BloodParams.y;

                // Procedural draws carry no per-object reflection probe, so use URP's global skybox cubemap.
                float3 R = reflect(-V, n);
                float mip = PerceptualRoughnessToMipmapLevel(rough);
                float4 enc = SAMPLE_TEXTURECUBE_LOD(_GlossyEnvironmentCubeMap, sampler_GlossyEnvironmentCubeMap, R, mip);
                float3 env = DecodeHDREnvironment(enc, _GlossyEnvironmentCubeMap_HDR) * Fv * _BloodParams2.y;

                // Beer-Lambert: channels the blood colour lacks are absorbed fastest, so a thin film tints the
                // background red and a thick pool goes to a near-black red.
                float3 sigma = _BloodParams.x * (1.0 - saturate(_BloodColor.rgb));
                float3 T = exp(-sigma * t);

                float3 nVS = mul((float3x3)UNITY_MATRIX_V, n);
                float2 ruv = uv + nVS.xy * (_BloodParams.z * saturate(t / 0.004));
                float3 bg  = SAMPLE_TEXTURE2D_X(_BlitTexture, sampler_LinearClamp, ruv).rgb;
                float3 bg0 = SAMPLE_TEXTURE2D_X(_BlitTexture, sampler_LinearClamp, uv).rgb;

                // Some in-scattering so deep blood reads as dark red rather than a hole.
                float3 ambient = SampleSHPixel(half3(0.0, 0.0, 0.0), n);
                float3 scatter = _BloodColor.rgb * (ambient + light.color * NoL) * _BloodParams2.z;

                float3 col = bg * T + scatter * (1.0 - T) + spec + env;
                float edge = saturate(t / max(_BloodParams.w, 1e-5));
                col = lerp(bg0, col, edge);

                int debug = (int)_BloodParams2.w;
                if (debug == 1)      col = frac(dc * 2.0).xxx;
                else if (debug == 2) col = saturate(t * 100.0).xxx;
                else if (debug == 3) col = n * 0.5 + 0.5;

                Output o;
                o.color = float4(col, 1.0);
                o.depth = BloodEyeToDeviceDepth(dc);
                return o;
            }
            ENDHLSL
        }
    }
    Fallback Off
}
