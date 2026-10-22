// The photographed body (DicomViewer.AnatomyLab.PhotoBody): ray-marches the colour photo volume in the unit cube and
// shades the first tissue it meets. Cut walls (from the dissection mask) show the photo's own colour; intact skin
// takes its colour from 1.5 mm under the surface (the photos' outermost pixels mix with the blue gelatin). Blood
// stains, eyelids that slide open, and modelled eyes in place of the real ones; tissue pulled (TissueWarp.hlsl, sampled where it came from), skin lifted away by the sheets (TissueSheets.cs) hidden. Writes SV_Depth, so meshes and blood
// drops drawn after it are hidden behind tissue.
Shader "DicomViewer/PhotoBody"
{
    Properties
    {
        _ColorTex ("Photo colour (RGB) + tissue (A)", 3D) = "" {}
        _MaskTex ("Dissection mask", 3D) = "white" {}
        _StainTex ("Blood stain", 3D) = "black" {}
        _LidTex ("Eyelids (0.25 lower, 0.5 upper)", 3D) = "black" {}
        _OccTex ("Occupancy (tissue somewhere in this brick)", 3D) = "white" {}
        _ShowStain ("Show blood stains", Float) = 1
        _SkinDepthTex ("Skin depth (mm)", 3D) = "black" {}
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Name "PhotoBody"
            Tags { "LightMode" = "UniversalForward" }
            Cull Front
            ZWrite On
            ZTest LEqual

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            #define BRICK 8.0

            TEXTURE3D(_ColorTex);  SAMPLER(sampler_ColorTex);
            TEXTURE3D(_MaskTex);   SAMPLER(sampler_MaskTex);
            TEXTURE3D(_StainTex);  SAMPLER(sampler_StainTex);
            TEXTURE3D(_LidTex);    SAMPLER(sampler_LidTex);
            TEXTURE3D(_OccTex);    SAMPLER(sampler_point_clamp);

            CBUFFER_START(UnityPerMaterial)
                float4 _Dims;              // voxels per axis
                float4 _SizeM;             // body size in metres (x left, y up, z back)
                float _MaskEnabled;
                float _HasLids;
                float _Open;               // eyelids: 0 shut .. 1 open
                float _ModelEyes;          // 1: the real eyeballs are hidden, modelled eyes sit in their place
                float _StepScale;          // ray step in voxels: 0.5 at rest, 1 while the body moves
                float _ShowStain;          // 0: blood hidden (dry dissection)
                float4 _Eye0, _Eye1;       // per eye: x, lid line y, eyeball centre z, radius (metres)
                float4 _EyeBall0, _EyeBall1;   // the real eyeballs (centre xyz, radius), hidden when _ModelEyes
            CBUFFER_END

            #include "TissueWarp.hlsl"         // live grabs (GrabDisplacement) and the baked grab field
            #include "LabSkin.hlsl"            // the skin's lighting

            TEXTURE3D(_SkinDepthTex);  SAMPLER(sampler_SkinDepthTex);   // mm below the outer skin
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

            float SkinDepthAt(float3 uvw) { return SAMPLE_TEXTURE3D_LOD(_SkinDepthTex, sampler_SkinDepthTex, uvw, 0).r; }

            // Skin taken over by a sheet (TissueSheets.cs: physics), which draws it instead: per sheet a grid over the
            // body (origin, axes, node spacing in .w of the origin, thickness in .w of E1) and a map with, per node,
            // 1 where the sheet has taken the tissue and the skin's height above the grid.
            #define MAX_SHEETS 4
            #define SHEET_N 64.0
            float _SheetCount;
            float4 _SheetOrigin[MAX_SHEETS], _SheetE1[MAX_SHEETS], _SheetE2[MAX_SHEETS], _SheetE3[MAX_SHEETS];
            TEXTURE2D_ARRAY(_SheetMaps); SAMPLER(sampler_SheetMaps);

            bool SheetHidden(float3 uvw)
            {
                float3 x = uvw * _SizeM.xyz * 1000.0;
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

            // Where the tissue shown at uvw really is: live grabs first, then the baked field (incision gapes).
            float3 SourceUVW(float3 uvw)
            {
                float3 y = uvw + GrabDisplacement(uvw);
                if (_WarpFieldOn > 0.5)
                {
                    float4 fw = _WarpField.SampleLevel(sampler_WarpField, y, 0);
                    if (fw.w > 0.5) return WARP_EMPTY_UVW;
                    y += fw.xyz;
                }
                return y;
            }

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 objPos : TEXCOORD0; };
            struct FragOut { half4 color : SV_Target; float depth : SV_Depth; };

            Varyings Vert(Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.objPos = v.positionOS.xyz;
                return o;
            }

            // Tissue density (0..1) at a SOURCE texture coordinate (where the tissue really is, before any pulling),
            // after cuts, eyelid movement and the eyeball swap; colour via rgb.
            float TissueAt(float3 uvw, out float3 rgb)
            {
                float4 c = SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, uvw, 0);
                if (_SheetCount > 0.5 && c.a > 0.0 && SheetHidden(uvw)) { rgb = c.rgb; return 0.0; }
                float m = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvw, 0).r : 1.0;
                float3 w = (uvw - 0.5) * _SizeM.xyz;
                bool lidsMove = _HasLids > 0.5 && _Open > 0.001;
                float keep = 1.0;
                if (_ModelEyes > 0.5 && (distance(w, _EyeBall0.xyz) < _EyeBall0.w || distance(w, _EyeBall1.xyz) < _EyeBall1.w))
                    keep = 0.0;
                float d = c.a * m * keep;
                rgb = c.rgb;
                if (lidsMove)
                {
                    // The eyes open as eyes do: an almond-shaped fissure, widest at the middle and closed at the corners,
                    // whose lids slide away from it into the orbit, the upper further than the lower. The tissue above
                    // the opening is the lid and brow skin drawn up, continuous with the untouched skin at the
                    // fissure's ends and at the brow (the mapping is the identity there), so there is no edge to see.
                    [unroll] for (int e = 0; e < 2; e++)
                    {
                        float4 E = e == 0 ? _Eye0 : _Eye1;
                        float4 ball = e == 0 ? _EyeBall0 : _EyeBall1;
                        float R = E.w, dx = w.x - E.x, dy = w.y - E.y, dz = w.z - E.z;   // the face looks to -z
                        float Lu = 1.5 * R, Ll = 1.2 * R;
                        if (abs(dx) > 1.3 * R || dz > 0.35 * R || dy > Lu || dy < -Ll) continue;
                        float t = dx / (1.15 * R);
                        float s = saturate(1.0 - t * t);
                        float hu = _Open * 0.72 * R * s, hl = _Open * 0.33 * R * s;
                        if (dy < hu && dy > -hl)
                        {
                            // In the opening: the lid is gone from in front of the eyeball; the eyeball stays.
                            if (dz < -0.15 * R && distance(w, ball.xyz) > ball.w) d = 0.0;
                            continue;
                        }
                        float ys = dy >= 0.0 ? (dy - hu) * Lu / (Lu - hu) : (dy + hl) * Ll / (Ll - hl);
                        float3 uvs = float3(w.x, E.y + ys, w.z) / _SizeM.xyz + 0.5;
                        float4 c2 = SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, uvs, 0);
                        float m2 = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvs, 0).r : 1.0;
                        float keep2 = _ModelEyes > 0.5 && distance(float3(w.x, E.y + ys, w.z), ball.xyz) < ball.w ? 0.0 : 1.0;
                        d = c2.a * m2 * keep2;
                        rgb = c2.rgb;
                    }
                }
                return d;
            }

            // Tissue shown at object-space p (-0.5..0.5): follows the pulls and flaps back to where it came from.
            float Tissue(float3 p, out float3 rgb)
            {
                float3 src = SourceUVW(p + 0.5);
                rgb = float3(0, 0, 0);
                return WarpIsEmpty(src) ? 0.0 : TissueAt(src, rgb);
            }

            float Density(float3 p)
            {
                float3 c;
                return Tissue(p, c);
            }

            FragOut Frag(Varyings i)
            {
                float3 o = TransformWorldToObject(_WorldSpaceCameraPos);
                float3 d = normalize(i.objPos - o);
                float3 inv = 1.0 / d;
                float3 t0 = (-0.5 - o) * inv, t1 = (0.5 - o) * inv;
                float3 tmin = min(t0, t1), tmax = max(t0, t1);
                float tNear = max(max(max(tmin.x, tmin.y), tmin.z), 0.0);
                float tFar = min(min(tmax.x, tmax.y), tmax.z);
                if (tNear >= tFar) discard;

                float maxDim = max(_Dims.x, max(_Dims.y, _Dims.z));
                float fine = max(_StepScale, 0.25) / maxDim;
                float coarse = 0.5 * BRICK / maxDim;                 // half a brick: empty bricks are grown by one
                float t = tNear + fine * 0.5, prev = t;
                bool hit = false, first = true;
                [loop] for (int k = 0; k < 4096; k++)
                {
                    if (t > tFar) break;
                    float3 src = SourceUVW(o + d * t + 0.5);
                    // Empty space is judged where the tissue comes from, so pulled skin is never skipped.
                    if (WarpIsEmpty(src) || SAMPLE_TEXTURE3D_LOD(_OccTex, sampler_point_clamp, src, 0).r < 0.5)
                    {
                        prev = t;
                        t += coarse;
                        first = false;
                        continue;
                    }
                    float3 c;
                    if (TissueAt(src, c) > 0.5) { hit = true; break; }
                    prev = t;
                    first = false;
                    t += fine;
                }
                if (!hit) discard;

                float a = prev, b = t;
                if (!first)
                {
                    [unroll] for (int r = 0; r < 6; r++) { float mid = 0.5 * (a + b); if (Density(o + d * mid) > 0.5) b = mid; else a = mid; }
                }
                float3 p = o + d * b;

                // Gradient in object space; the tissue grows inwards, so the outward normal is -g. Over one voxel it
                // follows every step between photos; intact skin takes its normal over 1.2 mm instead, so the face
                // is as smooth as a face. Cut walls keep the fine one: the mask's edge is sharp.
                float3 srcHit = SourceUVW(p + 0.5);
                float m0 = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, srcHit, 0).r : 1.0;
                float skin = smoothstep(0.8, 1.0, m0);                  // 1 on intact skin, 0 on a cut wall
                float3 e = 1.0 / _Dims.xyz;
                float3 g = float3(Density(p + float3(e.x, 0, 0)) - Density(p - float3(e.x, 0, 0)),
                                  Density(p + float3(0, e.y, 0)) - Density(p - float3(0, e.y, 0)),
                                  Density(p + float3(0, 0, e.z)) - Density(p - float3(0, 0, e.z))) / (2.0 * e);
                if (skin > 0.01)
                {
                    float3 ew = 0.0012 / _SizeM.xyz;
                    float3 gw = float3(Density(p + float3(ew.x, 0, 0)) - Density(p - float3(ew.x, 0, 0)),
                                       Density(p + float3(0, ew.y, 0)) - Density(p - float3(0, ew.y, 0)),
                                       Density(p + float3(0, 0, ew.z)) - Density(p - float3(0, 0, ew.z))) / (2.0 * ew);
                    if (dot(gw, gw) > 1e-8) g = lerp(g, gw, skin);
                }
                float3 gm = g / _SizeM.xyz;                             // per metre of body
                bool flat = first || dot(gm, gm) < 1e-6;                // the specimen's own cut edge
                float3 inwardM = flat ? float3(0, 0, 1) : normalize(gm);
                float3 N = flat ? -normalize(TransformObjectToWorldDir(d)) : normalize(TransformObjectToWorldNormal(-g));
                // The bed a sheet was lifted from is cut tissue too: wet, its own colour.
                if (_SheetCount > 0.5 && !flat && SheetHidden(SourceUVW(p + 0.5 - inwardM * 0.0012 / _SizeM.xyz))) skin = 0.0;
                // Skin takes its colour from just under the surface: the epidermis itself, not the fat below it.
                float depthM = flat ? 0.0 : lerp(0.0003, 0.0007, skin);
                float3 pc = p + inwardM * depthM / _SizeM.xyz;
                float3 up = float3(0, 1.0 / _Dims.y, 0);                // one photo slice
                float3 c0, c1, c2;
                Tissue(pc - up, c0);
                Tissue(pc, c1);
                Tissue(pc + up, c2);
                float3 albedo = 0.18 * c0 + 0.64 * c1 + 0.18 * c2;    // softens the 1 mm steps between photos
                albedo = LabSkinGrade(albedo, skin);

                float stain = max(SAMPLE_TEXTURE3D_LOD(_StainTex, sampler_StainTex, srcHit, 0).r,
                                  SAMPLE_TEXTURE3D_LOD(_StainTex, sampler_StainTex, SourceUVW(p + 0.5 + inwardM * 0.0006 / _SizeM.xyz), 0).r);
                float wet = smoothstep(0.04, 0.35, stain) * _ShowStain;
                albedo = lerp(albedo, float3(0.13, 0.0018, 0.0025), wet * 0.92);

                float3 wpos = TransformObjectToWorld(p);
                float3 V = normalize(_WorldSpaceCameraPos - wpos);
                Light light = GetMainLight();
                float3 L = light.direction;
                float aoInstr = 1.0, shade = 1.0;
                if (_InstrCount > 0.5) shade = InstrumentShade(wpos, L, aoInstr);
                float occ = 0.0;
                if (!flat)
                {
                    float3 outM = -inwardM;
                    occ = Density(p + outM * 0.0012 / _SizeM.xyz) + Density(p + outM * 0.0025 / _SizeM.xyz)
                        + Density(p + outM * 0.0045 / _SizeM.xyz);
                }
                float ao = (1.0 - 0.45 * saturate(occ / 3.0) * lerp(0.3, 1.0, skin)) * aoInstr;
                float3 lit = LabShadeSkin(albedo, N, V, L, light.color, wet, skin, ao, shade, srcHit * _SizeM.xyz * 1000.0);

                FragOut f;
                f.color = half4(lit, 1.0);
                float4 cs = TransformObjectToHClip(p);
                f.depth = cs.z / cs.w;
                return f;
            }
            ENDHLSL
        }
    }
}
