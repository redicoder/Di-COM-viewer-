// What the photographed body's shaders share (PhotoBody.shader for the volume, LabSkinMesh.shader for the skin
// drawn as a mesh over it): the textures of the body, where skin has been taken in hand by a sheet
// (TissueSheets.cs), the eyes' opening (AnatomyLab.cs), and the instruments' shadows (LabInstruments.cs).
#ifndef LAB_BODY_INCLUDED
#define LAB_BODY_INCLUDED

TEXTURE3D(_ColorTex);  SAMPLER(sampler_ColorTex);
TEXTURE3D(_MaskTex);   SAMPLER(sampler_MaskTex);
TEXTURE3D(_StainTex);  SAMPLER(sampler_StainTex);
TEXTURE3D(_SkinDepthTex);  SAMPLER(sampler_SkinDepthTex);   // mm below the outer skin

float SkinDepthAt(float3 uvw) { return SAMPLE_TEXTURE3D_LOD(_SkinDepthTex, sampler_SkinDepthTex, uvw, 0).r; }

// Skin taken over by a sheet (TissueSheets.cs: physics), which draws it instead: per sheet a grid over the body
// (origin, axes, node spacing in .w of the origin, thickness in .w of E1) and a map with, per node, 1 where the
// sheet has taken the tissue and the skin's height above the grid.
#define MAX_SHEETS 4
#define SHEET_N 64.0
float _SheetCount;
float4 _SheetOrigin[MAX_SHEETS], _SheetE1[MAX_SHEETS], _SheetE2[MAX_SHEETS], _SheetE3[MAX_SHEETS];
TEXTURE2D_ARRAY(_SheetMaps); SAMPLER(sampler_SheetMaps);

bool SheetHidden(float3 uvw, float3 sizeMm)
{
    float3 x = uvw * sizeMm;
    [loop] for (int s = 0; s < (int)_SheetCount; s++)
    {
        float3 d = x - _SheetOrigin[s].xyz;
        float2 g = float2(dot(d, _SheetE1[s].xyz), dot(d, _SheetE2[s].xyz)) / _SheetOrigin[s].w;
        if (any(g < 0.0) || any(g > SHEET_N - 1.0)) continue;
        float2 m = SAMPLE_TEXTURE2D_ARRAY_LOD(_SheetMaps, sampler_SheetMaps, (g + 0.5) / SHEET_N, s, 0).rg;
        if (m.r < 0.5) continue;
        float hz = dot(d, _SheetE3[s].xyz), thick = _SheetE1[s].w;
        if (hz > m.g + 1.0 || hz < m.g - thick - 3.0) continue;
        float sd = SkinDepthAt(uvw);
        if (sd > 0.0 && sd <= thick) return true;
    }
    return false;
}

// The eyes (per eye: x, lid line y, eyeball centre z, radius, metres; the face looks to -z). Where a point in
// body metres lies in the lids' zone, and whether it is inside the opening at this _Open.
bool InLidZone(float3 w, float4 E)
{
    float R = E.w, dx = w.x - E.x, dy = w.y - E.y, dz = w.z - E.z;
    return abs(dx) <= 1.3 * R && dz <= 0.35 * R && dy <= 1.5 * R && dy >= -1.2 * R;
}

bool InLidOpening(float3 w, float4 E, float open)
{
    float R = E.w, dx = w.x - E.x, dy = w.y - E.y;
    float t = dx / (1.15 * R);
    float s = saturate(1.0 - t * t);
    float hu = open * 0.72 * R * s, hl = open * 0.33 * R * s;
    return dy < hu && dy > -hl;
}

// Instruments over the body (LabInstruments.cs) as capsules, world space: a, radius in w; b.
#define MAX_INSTR 8
float _InstrCount;
float4 _InstrA[MAX_INSTR], _InstrB[MAX_INSTR];

// Soft shadow of the instruments towards the light at world point p (1 = lit), and their contact darkening.
float InstrumentShade(float3 p, float3 L, out float ao)
{
    float lit = 1.0;
    ao = 1.0;
    [loop] for (int i = 0; i < (int)_InstrCount; i++)
    {
        float3 a = _InstrA[i].xyz, d2 = _InstrB[i].xyz - a, r0 = p - a;
        float r = _InstrA[i].w;
        float a12 = dot(L, d2), a22 = max(dot(d2, d2), 1e-10), b1 = dot(L, r0), b2 = dot(d2, r0);
        float u = saturate((b2 - a12 * b1) / max(a22 - a12 * a12, 1e-10));
        float t = max(a12 * u - b1, 0.0);
        u = saturate(dot(d2, r0 + L * t) / a22);
        float dist = length(r0 + L * t - d2 * u);
        lit *= smoothstep(r * 0.4, r + t * 0.12 + r * 0.3, dist);
        float dc = length(r0 - d2 * saturate(b2 / a22)) - r;   // gap between the skin and the capsule
        ao *= 1.0 - 0.55 * saturate(1.0 - dc / (r * 1.2 + 1e-5));
    }
    return lit;
}

#endif
