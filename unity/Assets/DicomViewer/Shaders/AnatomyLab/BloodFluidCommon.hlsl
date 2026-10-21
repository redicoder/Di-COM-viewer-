#ifndef DICOMVIEWER_BLOOD_FLUID_COMMON_INCLUDED
#define DICOMVIEWER_BLOOD_FLUID_COMMON_INCLUDED

#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"

// Set per pass by BloodFluidFeature: xy = target size in pixels, zw = 1 / size.
float4 _BloodTargetSize;

// Opaque-scene eye depth (metres, positive) at a full-resolution pixel. Works for both projections;
// LinearEyeDepth(_ZBufferParams) is only valid for perspective.
float BloodSceneEyeDepth(uint2 fullResPixel)
{
    fullResPixel = min(fullResPixel, uint2(_ScreenSize.xy) - 1);
    float raw = LoadSceneDepth(fullResPixel);
    return IsPerspectiveProjection() ? LinearEyeDepth(raw, _ZBufferParams) : LinearDepthToEyeDepth(raw);
}

// Device depth (what the depth buffer stores, reversed-Z included) for an eye depth, any projection.
// Only the z row of the projection matters, so this stays correct for off-axis (Sony SR) frusta.
float BloodEyeToDeviceDepth(float eyeDepth)
{
    float4 c = mul(UNITY_MATRIX_P, float4(0.0, 0.0, -eyeDepth, 1.0));
    return c.z / c.w;
}

#endif
