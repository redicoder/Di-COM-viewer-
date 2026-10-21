// One direction of a separable "narrow-range" depth filter (Truong & Yuksel 2018, simplified):
// samples closer than (centre - threshold) belong to another surface and are skipped; samples farther than
// (centre + threshold) are clamped to that bound instead of discarded, so the surface stays continuous
// without bleeding across silhouettes. Radius in pixels follows distance so the smoothing is a fixed size
// in metres. Input/output are linear eye depth in metres, 0 = no blood. The first iteration converts the
// drop pass's 1/depth encoding (w flag).
Shader "DicomViewer/BloodFluidBlur"
{
    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" }
        Cull Off ZWrite Off ZTest Always Blend Off

        Pass
        {
            Name "NarrowRangeBlur"
            HLSLPROGRAM
            #pragma target 4.5
            #pragma exclude_renderers gles
            #pragma vertex Vert
            #pragma fragment Frag
            #include "BloodFluidCommon.hlsl"
            #define USE_FULL_PRECISION_BLIT_TEXTURE
            #include "Packages/com.unity.render-pipelines.core/Runtime/Utilities/Blit.hlsl"

            float4 _BloodBlurDir;      // xy = step in pixels, (1,0) or (0,1)
            float4 _BloodBlurParams;   // x = radius (m), y = max radius (px), z = depth threshold (m), w = input is 1/depth

            float LoadDepth(int2 p)
            {
                p = clamp(p, int2(0, 0), int2(_BloodTargetSize.xy) - 1);
                float v = LOAD_TEXTURE2D_X(_BlitTexture, p).r;
                return (_BloodBlurParams.w > 0.5 && v > 0.0) ? 1.0 / v : v;
            }

            float Frag(Varyings i) : SV_Target
            {
                int2 p = int2(i.positionCS.xy);
                float c = LoadDepth(p);
                if (c <= 0.0) return 0.0;

                // pixels per metre at this depth (abs(): the projection's y row is negated on flipped targets)
                float pxPerM = 0.5 * _BloodTargetSize.y * abs(UNITY_MATRIX_P._m11);
                if (IsPerspectiveProjection()) pxPerM /= c;
                float radius = clamp(_BloodBlurParams.x * pxPerM, 1.0, _BloodBlurParams.y);
                float sigma = max(radius * 0.5, 0.5);
                float invTwoSigma2 = 0.5 / (sigma * sigma);
                float thr = _BloodBlurParams.z;
                int R = (int)ceil(radius);
                int2 step = int2(_BloodBlurDir.xy);

                float sum = c, wsum = 1.0;
                [loop]
                for (int k = 1; k <= R; k++)
                {
                    float w = exp(-(float)(k * k) * invTwoSigma2);
                    float d0 = LoadDepth(p + step * k);
                    float d1 = LoadDepth(p - step * k);
                    if (d0 > 0.0 && d0 >= c - thr) { sum += min(d0, c + thr) * w; wsum += w; }
                    if (d1 > 0.0 && d1 >= c - thr) { sum += min(d1, c + thr) * w; wsum += w; }
                }
                return sum / wsum;
            }
            ENDHLSL
        }
    }
    Fallback Off
}
