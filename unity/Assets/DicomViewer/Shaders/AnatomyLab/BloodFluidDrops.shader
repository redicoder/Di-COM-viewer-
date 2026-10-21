// Draws every alive BloodDrop as a camera-facing quad and ray-casts a sphere in the fragment.
// Pass 0 "Depth":     stores 1/eyeDepth of the nearest sphere surface (BlendOp Max on a 0-cleared R32F target,
//                     so no custom clear colour is needed; 0 = no blood).
// Pass 1 "Thickness": accumulates the chord length the view ray travels inside each sphere (metres).
// Both passes test against the opaque scene by reading _CameraDepthTexture, so they work at half resolution
// without needing a matching depth attachment.
Shader "DicomViewer/BloodFluidDrops"
{
    SubShader
    {
        Tags { "RenderPipeline" = "UniversalPipeline" "RenderType" = "Transparent" }
        Cull Off
        ZWrite Off
        ZTest Always

        HLSLINCLUDE
        #pragma target 4.5
        #pragma exclude_renderers gles
        #include "BloodFluidCommon.hlsl"

        struct BloodDrop { float3 position; float radius; float3 normal; uint alive; };   // 32 bytes, matches C#

        StructuredBuffer<BloodDrop> _BloodDrops;
        float4x4 _BloodBodyToWorld;
        float4   _BloodDropParams;   // x = body scale (local -> world metres), y = quad scale, z = full/target resolution ratio, w = depth bias (m)

        struct Varyings
        {
            float4 positionCS : SV_POSITION;
            float3 centreVS   : TEXCOORD0;
            float3 posVS      : TEXCOORD1;
            float  radius     : TEXCOORD2;
        };

        static const float2 kCorners[6] = { float2(-1,-1), float2(1,-1), float2(1,1), float2(-1,-1), float2(1,1), float2(-1,1) };

        Varyings Vert(uint vid : SV_VertexID, uint iid : SV_InstanceID)
        {
            Varyings o = (Varyings)0;
            BloodDrop d = _BloodDrops[iid];
            if (d.alive == 0)
            {
                o.positionCS = float4(0, 0, 0, 1);   // all six verts collapse: zero-area, no fragments
                return o;
            }
            float r = d.radius * _BloodDropParams.x;
            float3 cWS = mul(_BloodBodyToWorld, float4(d.position, 1.0)).xyz;
            float3 cVS = mul(UNITY_MATRIX_V, float4(cWS, 1.0)).xyz;
            // Billboard in view space; the quad is slightly larger than the sphere to cover perspective bulge.
            float3 pVS = cVS + float3(kCorners[vid % 6], 0.0) * (r * _BloodDropParams.y);
            o.positionCS = mul(UNITY_MATRIX_P, float4(pVS, 1.0));
            o.centreVS = cVS;
            o.posVS = pVS;
            o.radius = r;
            return o;
        }

        // Ray-sphere in view space. Discards misses and fragments hidden by the opaque scene.
        void Intersect(Varyings i, out float eyeDepth, out float chord)
        {
            float3 ro, rd;
            if (IsPerspectiveProjection()) { ro = 0.0; rd = normalize(i.posVS); }
            else                           { ro = float3(i.posVS.xy, 0.0); rd = float3(0.0, 0.0, -1.0); }

            float3 oc = ro - i.centreVS;
            float b = dot(rd, oc);
            float c = dot(oc, oc) - i.radius * i.radius;
            float h = b * b - c;
            clip(h);
            float s = sqrt(h);
            float3 hit = ro + rd * (-b - s);
            eyeDepth = -hit.z;
            chord = 2.0 * s;
            clip(eyeDepth - 1e-4);                                   // sphere behind the camera

            uint2 px = uint2(floor(i.positionCS.xy) * _BloodDropParams.z);
            float scene = BloodSceneEyeDepth(px);
            clip(scene - eyeDepth + _BloodDropParams.w);             // hidden by the body
        }
        ENDHLSL

        Pass
        {
            Name "Depth"
            Blend One One
            BlendOp Max
            ColorMask R

            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment FragDepth
            float FragDepth(Varyings i) : SV_Target
            {
                float eyeDepth, chord;
                Intersect(i, eyeDepth, chord);
                return 1.0 / eyeDepth;   // max(1/d) == nearest surface; background stays 0
            }
            ENDHLSL
        }

        Pass
        {
            Name "Thickness"
            Blend One One
            BlendOp Add
            ColorMask R

            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment FragThickness
            float FragThickness(Varyings i) : SV_Target
            {
                float eyeDepth, chord;
                Intersect(i, eyeDepth, chord);
                return chord;
            }
            ENDHLSL
        }
    }
    Fallback Off
}
