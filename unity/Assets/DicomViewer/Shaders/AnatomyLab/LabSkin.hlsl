// Skin shading shared by the photographed body (PhotoBody.shader) and skin taken in hand (TissueSheet.shader).
// A dissection room's light rather than one lamp in the void: the scene's main light is the key, the shader adds a
// softer fill from the viewer's other side, a cool rim from behind, and a hemisphere of ambient (grey ceiling,
// dark floor). Skin: light scattering under the surface warms and softens the terminator, the specular is a
// rough dielectric (GGX, F0 0.028) broken up by a micro-relief, cut tissue and blood are wet and glossier.
#ifndef LAB_SKIN_INCLUDED
#define LAB_SKIN_INCLUDED

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
// ao: occlusion 0..1. shade: the key light's shadow 0..1. posM: a millimetre position carried with the tissue.
float3 LabShadeSkin(float3 albedo, float3 N, float3 V, float3 L, float3 keyColor, float wet, float skin, float ao,
                    float shade, float3 posM)
{
    float3 up = float3(0, 1, 0);
    float ndv = saturate(dot(N, V));

    // Diffuse: the key with light wrapped round by scattering under the skin, the band at the terminator warmed by
    // the blood-coloured light that comes back out; a fill and a rim set against the camera.
    float ndl = dot(N, L);
    float wrapAmt = lerp(0.2, 0.55, skin);
    float wrapped = saturate((ndl + wrapAmt) / (1.0 + wrapAmt));
    float band = saturate(1.0 - abs(ndl) * 2.2);
    float3 scatter = lerp(float3(1, 1, 1), float3(1.0, 0.42, 0.30), band * 0.6 * skin);
    float3 diffuse = keyColor * wrapped * scatter * shade;

    float3 camR = normalize(cross(up, V) + float3(1e-4, 0, 0));
    float3 fillDir = normalize(-camR * 0.75 + up * 0.35 + V * 0.55);
    float fill = saturate((dot(N, fillDir) + 0.4) / 1.4);
    diffuse += keyColor * float3(0.85, 0.9, 1.0) * fill * 0.32;
    float3 rimDir = normalize(-V * 0.7 + up * 0.5 + camR * 0.45);
    float rim = pow(1.0 - ndv, 2.5) * saturate(dot(N, rimDir)) * 0.45;
    diffuse += float3(0.75, 0.85, 1.0) * rim;

    float3 ambient = lerp(float3(0.085, 0.075, 0.07), float3(0.30, 0.31, 0.34), dot(N, up) * 0.5 + 0.5);
    float3 color = albedo * (diffuse + ambient) * ao;

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

#endif
