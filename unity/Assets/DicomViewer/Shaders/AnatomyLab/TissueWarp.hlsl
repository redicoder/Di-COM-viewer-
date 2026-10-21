#ifndef DICOMVIEWER_TISSUE_WARP_INCLUDED
#define DICOMVIEWER_TISSUE_WARP_INCLUDED

// Backward warp for the ray-marcher: SampleTissue(WarpUVW(uvw)).
//
//   src = y + F(y),   y = uvw + h(uvw)
//
// h = sum of the live grab handles (compact Wendland falloff, evaluated in millimetres so the influence
// region is a true sphere on anisotropic voxels), F = the baked field (_WarpField.xyz). Handles are applied
// first and the field is looked up at the handle-displaced position, so baking a handle into the field
// (see TissueWarp.compute, Compose) reproduces exactly what was on screen while it was live.
// _WarpField.w > 0.5 marks space a lifted flap vacated: WarpUVW returns a point far outside the volume and
// the ray-marcher must treat it as empty (use WarpIsEmpty, or its own bounds check).
//
// Cost per ray step: the handle maths (0-4 handles) + one trilinear fetch, skipped while the field is clean.

Texture3D<float4> _WarpField;
SamplerState sampler_WarpField;          // trilinear, clamp (set on the RenderTexture)

float4 _GrabFrom[4];                     // xyz = uvw where the tissue was grabbed
float4 _GrabTo[4];                       // xyz = uvw where it is held now
float  _GrabRadius[4];                   // effective radius in millimetres (already grown to keep the warp fold-free)
int    _GrabCount;
float3 _WarpSizeMm;                      // physical size of the volume per uvw axis
float  _WarpFieldOn;                     // 0 while nothing has been baked: saves the fetch

#define WARP_EMPTY_UVW float3(-10.0, -10.0, -10.0)

// Wendland C2 kernel: C2-smooth, compact, so the warp is smooth and stops cleanly at the radius.
float WarpKernel(float t)
{
    float q = saturate(1.0 - t);
    return q * q * q * q * (4.0 * t + 1.0);
}

float3 GrabDisplacement(float3 uvw)
{
    float3 d = float3(0, 0, 0);
    [unroll]
    for (int i = 0; i < 4; i++)
    {
        if (i >= _GrabCount) break;
        float3 to = _GrabTo[i].xyz;
        float t = length((uvw - to) * _WarpSizeMm) / max(_GrabRadius[i], 1e-4);
        if (t < 1.0) d -= (to - _GrabFrom[i].xyz) * WarpKernel(t);   // tissue shown at `to` came from `from`
    }
    return d;
}

float3 WarpUVW(float3 uvw)
{
    float3 y = uvw + GrabDisplacement(uvw);
    if (_WarpFieldOn > 0.5)
    {
        float4 f = _WarpField.SampleLevel(sampler_WarpField, y, 0);
        if (f.w > 0.5) return WARP_EMPTY_UVW;
        y += f.xyz;
    }
    return y;
}

bool WarpIsEmpty(float3 src)
{
    return any(src < 0.0) || any(src > 1.0);
}

#endif
