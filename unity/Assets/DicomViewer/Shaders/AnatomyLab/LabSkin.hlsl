// Skin shading shared by the photographed body (PhotoBody.shader) and skin taken in hand (TissueSheet.shader).
// A dissection room's light rather than one lamp in the void: the scene's main light is the key, the shader adds a
// softer fill from the viewer's other side, a cool rim from behind, and a hemisphere of ambient (grey ceiling,
// dark floor). Skin: light scattering under the surface warms and softens the terminator, the specular is a
// rough dielectric (GGX, F0 0.028) broken up by a micro-relief, cut tissue and blood are wet and glossier.
#ifndef LAB_SKIN_INCLUDED
#define LAB_SKIN_INCLUDED

// The skin's scattering, pre-integrated (SkinBake.PreintegratedLut): diffuse light by the cosine of the light's
// angle (u) and the surface's curvature (v). Only the skin mesh sets _SkinLutOn; the others keep the wrap below.
TEXTURE2D(_SkinLut);  SAMPLER(sampler_SkinLut);
float _SkinLutOn;

// Value noise on a 3D lattice, for the skin's micro-relief (no textures: the body is a volume).
float LabHash(float3 p)
{
    p = frac(p * 0.3183099 + float3(0.1, 0.17, 0.23));
    p *= 17.0;
    return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float LabNoise(float3 x)
{
    float3 i = floor(x), f = frac(x);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(lerp(LabHash(i), LabHash(i + float3(1, 0, 0)), f.x), lerp(LabHash(i + float3(0, 1, 0)), LabHash(i + float3(1, 1, 0)), f.x), f.y),
                lerp(lerp(LabHash(i + float3(0, 0, 1)), LabHash(i + float3(1, 0, 1)), f.x), lerp(LabHash(i + float3(0, 1, 1)), LabHash(i + float3(1, 1, 1)), f.x), f.y), f.z);
}

// Cellular noise: the distance to the nearest of jittered points on a lattice, 0 at a point, ~0.7 between.
float LabCells(float3 x)
{
    float3 i = floor(x), f = frac(x);
    float best = 2.0;
    [unroll] for (int k = 0; k < 27; k++)
    {
        float3 c = float3(k % 3, (k / 3) % 3, k / 9) - 1.0;
        float3 q = i + c;
        float3 p = c + float3(LabHash(q), LabHash(q + 11.3), LabHash(q + 29.7)) - f;
        best = min(best, dot(p, p));
    }
    return sqrt(best);
}

// The skin's relief as a height, millimetres in: pores (a cell lattice, ~0.5 mm apart, each a small dip), fine
// lines between them, and the slow unevenness of skin over a few millimetres.
float LabSkinHeight(float3 posM)
{
    float pores = 1.0 - smoothstep(0.0, 0.32, LabCells(posM * 2.1));      // 1 at a pore's centre
    float lines = 1.0 - abs(LabNoise(posM * 1.4) * 2.0 - 1.0);           // ridges where the noise crosses its middle
    float slow = LabNoise(posM * 0.35);
    return -0.030 * pores - 0.010 * lines * lines + 0.025 * slow;
}

// How many millimetres one pixel covers at a world point: its distance to the camera over the projection's
// scale and the screen's height (no screen-space derivatives, which the ray-marcher's branches would forbid).
float LabPixelMm(float3 wpos)
{
    float dist = length(_WorldSpaceCameraPos - wpos);
    return 2000.0 * dist / max(_ScreenParams.y * unity_CameraProjection._m11, 1.0);
}

// The normal with the skin's relief added (pores and creases a fraction of a millimetre across); posM is a
// position in millimetres that moves with the tissue. Fades out where a pixel covers more than a pore
// (pixelMm, from LabPixelMm), so the relief never sparkles at a distance.
float3 LabSkinDetailNormal(float3 N, float3 posM, float amount, float pixelMm)
{
    float fade = saturate(1.0 - (pixelMm - 0.15) / 0.6) * saturate(amount * 1e3);
    float3 T = normalize(cross(N, abs(N.y) < 0.9 ? float3(0, 1, 0) : float3(1, 0, 0)));
    float3 B = cross(N, T);
    const float e = 0.12;
    float3 bent = N;
    [branch] if (fade > 0.0)
    {
        float h0 = LabSkinHeight(posM);
        float dT = (LabSkinHeight(posM + T * e) - h0) / e;
        float dB = (LabSkinHeight(posM + B * e) - h0) / e;
        bent = normalize(N - (T * dT + B * dB) * amount * fade);
    }
    return bent;
}

// The normal with the skin's fine relief added (pores and creases a fraction of a millimetre across), for the
// specular only; posM is a position in millimetres that moves with the tissue.
float3 LabSkinMicroNormal(float3 N, float3 posM, float amount)
{
    const float e = 0.15;
    float3 q = posM * 3.0;
    float3 g = float3(LabNoise(q + float3(e, 0, 0)) - LabNoise(q - float3(e, 0, 0)),
                      LabNoise(q + float3(0, e, 0)) - LabNoise(q - float3(0, e, 0)),
                      LabNoise(q + float3(0, 0, e)) - LabNoise(q - float3(0, 0, e)));
    float3 q2 = posM * 0.6;
    g += 0.6 * float3(LabNoise(q2 + float3(e, 0, 0)) - LabNoise(q2 - float3(e, 0, 0)),
                      LabNoise(q2 + float3(0, e, 0)) - LabNoise(q2 - float3(0, e, 0)),
                      LabNoise(q2 + float3(0, 0, e)) - LabNoise(q2 - float3(0, 0, e)));
    g -= N * dot(g, N);
    return normalize(N + g * amount);
}

// The photographs are of frozen tissue in a blue bath under flash, which leaves the skin yellow-olive. Graded
// towards the tone skin has in a room's light: the blue cast lifted, the yellow eased, a touch less saturated.
// Set by eye against the head, and kept mild: the colour is still his.
float3 LabSkinGrade(float3 albedo, float skin)
{
    float3 g = albedo * float3(1.08, 1.0, 1.16);
    float l = dot(g, float3(0.3, 0.59, 0.11));
    g = lerp(l.xxx, g, 0.92);
    return lerp(albedo, g, skin);
}

float LabGGX(float ndh, float rough)
{
    float a2 = rough * rough;
    a2 *= a2;
    float d = ndh * ndh * (a2 - 1.0) + 1.0;
    return a2 / (3.14159 * d * d + 1e-6);
}

// albedo: the tissue's colour. wet: 0..1 (blood, fresh cut). skin: 1 on intact skin, 0 on cut tissue.
// ao: occlusion 0..1 (contact, instruments). shade: the key light's shadow 0..1. posM: a millimetre position
// carried with the tissue. bake: what SkinBake.cs baked into the skin mesh (x: how open the room above the
// surface is, 0..1; y: tissue behind the surface, mm; z: curvature, 1/mm); the volume passes an open, thick, flat
// skin and keeps its own occlusion.
float3 LabShadeSkinBaked(float3 albedo, float3 N, float3 V, float3 L, float3 keyColor, float wet, float skin, float ao,
                         float shade, float3 posM, float pixelMm, float3 bake)
{
    float3 up = float3(0, 1, 0);
    float3 Nsmooth = N;
    // The skin's relief shades everything, close up (pores in the diffuse too); cut tissue has none.
    N = LabSkinDetailNormal(N, posM, 1.6 * skin, pixelMm);
    float ndv = saturate(dot(N, V));
    float sky = bake.x;

    // Diffuse: the key with light wrapped round by scattering under the skin, the band at the terminator warmed by
    // the blood-coloured light that comes back out; on the skin mesh, the scattering pre-integrated over the
    // surface's curvature instead (the LUT: a cheek's terminator is wide and warm, a flat belly's is crisp).
    float ndl = dot(N, L);
    float wrapAmt = lerp(0.2, 0.55, skin);
    float wrapped = saturate((ndl + wrapAmt) / (1.0 + wrapAmt));
    float band = saturate(1.0 - abs(ndl) * 2.2);
    float3 scatter = lerp(float3(1, 1, 1), float3(1.0, 0.42, 0.30), band * 0.6 * skin);
    float3 key = wrapped * scatter;
    [branch] if (_SkinLutOn > 0.5 && skin > 0.001)
    {
        float ndlLut = lerp(ndl, dot(Nsmooth, L), 0.6);
        float3 pre = SAMPLE_TEXTURE2D_LOD(_SkinLut, sampler_SkinLut, float2(ndlLut * 0.5 + 0.5, bake.z / 0.25), 0).rgb;
        key = lerp(key, pre, skin);
    }
    float3 diffuse = keyColor * key * shade * lerp(0.75, 1.0, sky);

    float3 camR = normalize(cross(up, V) + float3(1e-4, 0, 0));
    float3 fillDir = normalize(-camR * 0.75 + up * 0.35 + V * 0.55);
    float fill = saturate((dot(N, fillDir) + 0.4) / 1.4);
    diffuse += keyColor * float3(0.85, 0.9, 1.0) * fill * 0.32 * sky;
    float3 rimDir = normalize(-V * 0.7 + up * 0.5 + camR * 0.45);
    float rim = pow(1.0 - ndv, 2.5) * saturate(dot(N, rimDir)) * 0.45;
    diffuse += float3(0.75, 0.85, 1.0) * rim * sky;

    float3 ambient = lerp(float3(0.085, 0.075, 0.07), float3(0.30, 0.31, 0.34), dot(N, up) * 0.5 + 0.5);
    float3 color = albedo * (diffuse + ambient * lerp(0.2, 1.0, sky)) * ao;

    // Light through thin skin (the ears, the nose's wings, the webs of the fingers): what reaches the far side
    // comes out blood-red, strongest looking towards the light.
    float through = exp(-bake.y / 5.0) * skin;
    [branch] if (through > 0.003)
    {
        float3 Lt = normalize(L + Nsmooth * 0.35);
        float toward = pow(saturate(dot(V, -Lt)), 3.0) * 1.2 + 0.25;
        color += albedo * float3(1.0, 0.32, 0.18) * keyColor * toward * through * 0.9;
    }

    // Specular: a rough dielectric, finer where wet; the skin's relief breaks the highlight up.
    float gloss = max(wet, 1.0 - skin);
    float rough = lerp(0.52, 0.22, gloss);
    float3 Ns = LabSkinMicroNormal(N, posM, lerp(0.5, 0.08, gloss) * skin);
    float f0 = lerp(0.028, 0.045, gloss);
    float3 H = normalize(L + V);
    float ndh = saturate(dot(Ns, H)), vdh = saturate(dot(V, H));
    float F = f0 + (1.0 - f0) * pow(1.0 - vdh, 5.0);
    float keySpec = LabGGX(ndh, rough) * F * saturate(ndl) * 0.25 * shade;
    float3 Hf = normalize(fillDir + V);
    float fillSpec = LabGGX(saturate(dot(Ns, Hf)), rough + 0.15) * f0 * saturate(dot(N, fillDir)) * 0.12;
    float sheen = pow(1.0 - ndv, 4.0) * 0.08 * skin;                       // the skin's grazing sheen
    color += keyColor * (keySpec + fillSpec + sheen) * ao;

    // A soft shoulder so a highlight rolls off instead of clipping.
    float peak = max(color.r, max(color.g, color.b));
    return color / (1.0 + 0.12 * peak);
}

// The same without a bake: the volume and skin in hand (open, thick, gently curved).
float3 LabShadeSkin(float3 albedo, float3 N, float3 V, float3 L, float3 keyColor, float wet, float skin, float ao,
                    float shade, float3 posM, float pixelMm)
{
    return LabShadeSkinBaked(albedo, N, V, L, keyColor, wet, skin, ao, shade, posM, pixelMm, float3(1.0, 60.0, 0.08));
}

#endif
