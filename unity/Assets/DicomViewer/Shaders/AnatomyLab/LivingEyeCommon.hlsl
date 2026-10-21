#ifndef DICOMVIEWER_LIVING_EYE_COMMON_INCLUDED
#define DICOMVIEWER_LIVING_EYE_COMMON_INCLUDED

// Each shader includes this file first (it brings in URP's Core.hlsl, which defines CBUFFER_START), then
// declares its own UnityPerMaterial cbuffer. Nothing here reads material properties, so the shared passes stay
// SRP-Batcher compatible for every eye shader.

#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
#include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

struct EyeAttributes
{
    float4 positionOS : POSITION;
    float3 normalOS   : NORMAL;
    float2 uv         : TEXCOORD0;
};

// GGX lobe, height-correlated Smith visibility, Schlick Fresnel. Returns the BRDF * NdotL for one light.
float3 EyeSpecular(float3 n, float3 v, float3 l, float roughness, float f0)
{
    float3 h = normalize(l + v);
    float NoL = saturate(dot(n, l));
    float NoV = saturate(dot(n, v));
    float NoH = saturate(dot(n, h));
    float VoH = saturate(dot(v, h));
    float a2 = roughness * roughness;
    a2 *= a2;
    float d = NoH * NoH * (a2 - 1.0) + 1.0;
    float D = a2 / (PI * d * d);
    float Vis = 0.5 / (NoL * sqrt(NoV * NoV * (1.0 - a2) + a2) + NoV * sqrt(NoL * NoL * (1.0 - a2) + a2) + 1e-4);
    float F = f0 + (1.0 - f0) * pow(1.0 - VoH, 5.0);
    return (D * Vis * F * NoL).xxx;
}

float EyeFresnel(float NoV, float f0)
{
    return f0 + (1.0 - f0) * pow(1.0 - saturate(NoV), 5.0);
}

// Wrapped Lambert: soft terminator so the sclera and iris read as tissue, not plastic.
float EyeWrapDiffuse(float NoL, float wrap)
{
    return saturate((NoL + wrap) / ((1.0 + wrap) * (1.0 + wrap)));
}

// ------------------------------------------------------------------ depth-only / depth-normals / shadows

struct EyeDepthVaryings
{
    float4 positionCS : SV_POSITION;
    float3 normalWS   : TEXCOORD0;
};

EyeDepthVaryings EyeDepthVert(EyeAttributes i)
{
    EyeDepthVaryings o;
    o.positionCS = TransformObjectToHClip(i.positionOS.xyz);
    o.normalWS = TransformObjectToWorldNormal(i.normalOS);
    return o;
}

half4 EyeDepthOnlyFrag(EyeDepthVaryings i) : SV_Target
{
    return 0;
}

void EyeDepthNormalsFrag(EyeDepthVaryings i, out half4 outNormalWS : SV_Target0)
{
#if defined(_GBUFFER_NORMALS_OCT)
    float2 oct = PackNormalOctQuadEncode(normalize(i.normalWS));
    outNormalWS = half4(PackFloat2To888(saturate(oct * 0.5 + 0.5)), 0.0);
#else
    outNormalWS = half4(NormalizeNormalPerPixel(i.normalWS), 0.0);
#endif
}

// Set by URP's shadow caster pass.
float3 _LightDirection;
float3 _LightPosition;

float4 EyeShadowVert(EyeAttributes i) : SV_POSITION
{
    float3 positionWS = TransformObjectToWorld(i.positionOS.xyz);
    float3 normalWS = TransformObjectToWorldNormal(i.normalOS);
#if _CASTING_PUNCTUAL_LIGHT_SHADOW
    float3 lightDirectionWS = normalize(_LightPosition - positionWS);
#else
    float3 lightDirectionWS = _LightDirection;
#endif
    float4 positionCS = TransformWorldToHClip(ApplyShadowBias(positionWS, normalWS, lightDirectionWS));
#if UNITY_REVERSED_Z
    positionCS.z = min(positionCS.z, UNITY_NEAR_CLIP_VALUE);
#else
    positionCS.z = max(positionCS.z, UNITY_NEAR_CLIP_VALUE);
#endif
    return positionCS;
}

half4 EyeShadowFrag(float4 positionCS : SV_POSITION) : SV_Target
{
    return 0;
}

#endif
