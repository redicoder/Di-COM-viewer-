// The photographed body (DicomViewer.AnatomyLab.PhotoBody): ray-marches the colour photo volume in the unit cube and
// shades the first tissue it meets. Cut walls (from the dissection mask) show the photo's own colour; intact skin
// takes its colour from 1.5 mm under the surface (the photos' outermost pixels mix with the blue gelatin). Blood
// stains, eyelids that slide open, and modelled eyes in place of the real ones; tissue pulled or folded back (TissueWarp.hlsl, sampled where it came from). Writes SV_Depth, so meshes and blood
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

            // Skin flaps (TissueFlaps.cs), evaluated exactly: a filtered displacement field would blend a flap's
            // centimetre moves with the still tissue beside it and spray fragments around the flap.
            #define MAX_FLAPS 4
            TEXTURE3D(_SkinDepthTex);  SAMPLER(sampler_SkinDepthTex);   // mm below the outer skin
            float _FlapCount;
            float4 _FlapA[MAX_FLAPS], _FlapB[MAX_FLAPS];   // the cut's two ends, mm (texture axes)
            float4 _FlapInfo[MAX_FLAPS];                // -, width mm, depth mm, fold angle (rad)
            float4 _FlapDir[MAX_FLAPS];                 // from the cut into the flap (unit, mm space)
            float4 _FlapOut[MAX_FLAPS];                 // out of the body at the cut
            // The cut's curve: its offset from the straight line A..B (x along _FlapOut, y along the fold direction,
            // mm) at s = k/8, k = 1..7, in _FlapCurve[f * 8 + k]; the ends lie on the line. A forehead cut bows ~1 cm
            // out of that line, and a hinge on the line would fold the middle of the flap into the head.
            #define CURVE_KNOTS 8
            float4 _FlapCurve[MAX_FLAPS * CURVE_KNOTS];

            float2 FlapCurveAt(int f, float s)
            {
                float u = saturate(s) * CURVE_KNOTS;
                int k = min((int)u, CURVE_KNOTS - 1);
                float2 c0 = k == 0 ? float2(0, 0) : _FlapCurve[f * CURVE_KNOTS + k].xy;
                float2 c1 = k + 1 >= CURVE_KNOTS ? float2(0, 0) : _FlapCurve[f * CURVE_KNOTS + k + 1].xy;
                return lerp(c0, c1, u - k);
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

            float SkinDepthAt(float3 uvw) { return SAMPLE_TEXTURE3D_LOD(_SkinDepthTex, sampler_SkinDepthTex, uvw, 0).r; }

            // Where the tissue shown at uvw comes from, if a flap moved it; WARP_EMPTY_UVW where a flap left space.
            // Each flap hinges along its cut (the free edge), W further in the fold direction, rotating about the cut's direction.
            float3 FlapSource(float3 uvw)
            {
                float3 sizeMm = _SizeM.xyz * 1000.0;
                float3 x = uvw * sizeMm;
                [loop] for (int f = 0; f < (int)_FlapCount; f++)
                {
                    float3 A = _FlapA[f].xyz, AB = _FlapB[f].xyz - A;
                    float len2 = max(dot(AB, AB), 1e-6);
                    float s = dot(x - A, AB) / len2;
                    if (s < 0.0 || s > 1.0) continue;                    // beyond the cut's ends: untouched
                    float3 T = AB * rsqrt(len2);
                    float3 Nf = _FlapDir[f].xyz - dot(_FlapDir[f].xyz, T) * T;
                    float nl = length(Nf);
                    if (nl < 1e-4) continue;
                    Nf /= nl;
                    float3 U = cross(T, Nf);
                    if (dot(U, _FlapOut[f].xyz) < 0.0) U = -U;
                    float2 bow = FlapCurveAt(f, s);
                    float3 C = A + AB * s + U * bow.x + Nf * bow.y;     // the cut itself, here
                    float W = _FlapInfo[f].y, D = _FlapInfo[f].z;
                    float3 rel = x - (C + Nf * W);                      // from the hinge
                    float a = dot(rel, Nf), b = dot(rel, U);
                    if (a < -2.0 * W - D || a > W + D || abs(b) > W + D) continue;   // far from this flap
                    float sn, cs;
                    sincos(_FlapInfo[f].w, sn, cs);
                    float a2 = a * cs - b * sn, b2 = a * sn + b * cs;   // undo the outward fold
                    float3 pu = (x + (a2 - a) * Nf + (b2 - b) * U) / sizeMm;
                    if (a2 >= -W && a2 <= 0.0)
                    {
                        float dp = SkinDepthAt(pu);
                        if (dp > 0.0 && dp <= D) return pu;              // flap tissue, folded back
                    }
                    if (a >= -W && a <= 0.0)
                    {
                        float dx = SkinDepthAt(uvw);
                        if (dx > 0.0 && dx <= D) return WARP_EMPTY_UVW;  // where the flap was: open
                    }
                }
                return uvw;
            }

            // Where the tissue shown at uvw really is: live grabs first, then flaps, then the baked grab field.
            float3 SourceUVW(float3 uvw)
            {
                float3 y = uvw + GrabDisplacement(uvw);
                if (_FlapCount > 0.5)
                {
                    y = FlapSource(y);
                    if (WarpIsEmpty(y)) return y;
                }
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
                float m = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvw, 0).r : 1.0;
                float3 w = (uvw - 0.5) * _SizeM.xyz;
                bool lidsMove = _HasLids > 0.5 && _Open > 0.001;
                float keep = 1.0;
                if (lidsMove && SAMPLE_TEXTURE3D_LOD(_LidTex, sampler_LidTex, uvw, 0).r > 0.12) keep = 0.0;
                if (_ModelEyes > 0.5 && (distance(w, _EyeBall0.xyz) < _EyeBall0.w || distance(w, _EyeBall1.xyz) < _EyeBall1.w))
                    keep = 0.0;
                float d = c.a * m * keep;
                rgb = c.rgb;
                if (lidsMove)
                {
                    // Each lid folds towards its attachment: the upper lid is squeezed upwards, the lower downwards,
                    // so the gap between them opens over the eyeball.
                    [unroll] for (int e = 0; e < 2; e++)
                    {
                        float4 E = e == 0 ? _Eye0 : _Eye1;
                        float R = E.w, dx = w.x - E.x;
                        if (abs(dx) >= R || w.z > E.z) continue;       // only in front of the eyeball (the face looks to -z)
                        float s = 1.0 - (dx / R) * (dx / R);
                        float dy = w.y - E.y, ys;
                        bool upper = dy >= 0.0;
                        if (upper) { float hu = _Open * 0.85 * R * s; if (dy > R || dy < hu) continue; ys = (dy - hu) * R / (R - hu); }
                        else       { float hl = _Open * 0.45 * R * s; if (dy < -R || dy > -hl) continue; ys = (dy + hl) * R / (R - hl); }
                        float3 uvs = float3(w.x, E.y + ys, w.z) / _SizeM.xyz + 0.5;
                        float lid = SAMPLE_TEXTURE3D_LOD(_LidTex, sampler_LidTex, uvs, 0).r;
                        if (upper ? lid < 0.37 : (lid < 0.12 || lid > 0.37)) continue;
                        float4 c2 = SAMPLE_TEXTURE3D_LOD(_ColorTex, sampler_ColorTex, uvs, 0);
                        float m2 = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, uvs, 0).r : 1.0;
                        float d2 = c2.a * m2;
                        if (d2 > d) { d = d2; rgb = c2.rgb; }
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

                // Gradient in object space; the tissue grows inwards, so the outward normal is -g.
                float3 e = 1.0 / _Dims.xyz;
                float3 g = float3(Density(p + float3(e.x, 0, 0)) - Density(p - float3(e.x, 0, 0)),
                                  Density(p + float3(0, e.y, 0)) - Density(p - float3(0, e.y, 0)),
                                  Density(p + float3(0, 0, e.z)) - Density(p - float3(0, 0, e.z))) / (2.0 * e);
                float3 gm = g / _SizeM.xyz;                             // per metre of body
                bool flat = first || dot(gm, gm) < 1e-6;                // the specimen's own cut edge
                float3 inwardM = flat ? float3(0, 0, 1) : normalize(gm);
                float3 N = flat ? -normalize(TransformObjectToWorldDir(d)) : normalize(TransformObjectToWorldNormal(-g));

                float3 srcHit = SourceUVW(p + 0.5);
                float m0 = _MaskEnabled > 0.5 ? SAMPLE_TEXTURE3D_LOD(_MaskTex, sampler_MaskTex, srcHit, 0).r : 1.0;
                float skin = smoothstep(0.8, 1.0, m0);                  // 1 on intact skin, 0 on a cut wall
                float depthM = flat ? 0.0 : lerp(0.0003, 0.0015, skin);
                float3 pc = p + inwardM * depthM / _SizeM.xyz;
                float3 up = float3(0, 1.0 / _Dims.y, 0);                // one photo slice
                float3 c0, c1, c2;
                Tissue(pc - up, c0);
                Tissue(pc, c1);
                Tissue(pc + up, c2);
                float3 albedo = 0.25 * c0 + 0.5 * c1 + 0.25 * c2;      // softens the 1 mm steps between photos

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
                float wrap = saturate((dot(N, L) + 0.35) / 1.35) * shade;
                float3 H = normalize(L + V);
                float glisten = max(wet, 1.0 - skin);                    // blood and fresh cut tissue are wet
                float spec = pow(saturate(dot(N, H)), lerp(36.0, 90.0, glisten)) * lerp(0.06, 0.45, glisten);
                float occ = 0.0;
                if (!flat)
                {
                    float3 outM = -inwardM;
                    occ = Density(p + outM * 0.0012 / _SizeM.xyz) + Density(p + outM * 0.0025 / _SizeM.xyz)
                        + Density(p + outM * 0.0045 / _SizeM.xyz);
                }
                float ao = (1.0 - 0.45 * saturate(occ / 3.0) * lerp(0.3, 1.0, skin)) * aoInstr;
                float3 ambient = max(SampleSH(N), 0.22);
                float3 lit = albedo * (ambient + light.color * wrap * 0.95) * ao + light.color * spec * ao * shade;

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
