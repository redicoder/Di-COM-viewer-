// Blood drops from BloodSim drawn as small, flattened, glossy spheres (camera-facing quads with sphere depth), one
// instance per slot; free slots collapse to nothing. A stand-in until a liquid-blood renderer merges them into films.
Shader "DicomViewer/BloodDrop"
{
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry+10" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            ZWrite On
            ZTest LEqual

            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Drop { float3 position; float radius; float3 normal; uint alive; };
            StructuredBuffer<Drop> _Drops;
            float4x4 _BodyToWorld;
            float _BodyScale;

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 centreVS : TEXCOORD1;
                float radius : TEXCOORD2;
            };
            struct FragOut { half4 color : SV_Target; float depth : SV_Depth; };

            static const float2 Corners[6] = { float2(-1, -1), float2(1, -1), float2(1, 1), float2(-1, -1), float2(1, 1), float2(-1, 1) };

            Varyings Vert(uint vid : SV_VertexID, uint iid : SV_InstanceID)
            {
                Varyings o = (Varyings)0;
                Drop d = _Drops[iid];
                if (d.alive == 0) return o;                       // all six corners at the origin: nothing drawn
                float3 centreWS = mul(_BodyToWorld, float4(d.position, 1.0)).xyz;
                float3 c = TransformWorldToView(centreWS);
                float r = d.radius * _BodyScale;
                float2 uv = Corners[vid];
                o.uv = uv;
                o.centreVS = c;
                o.radius = r;
                o.positionCS = TransformWViewToHClip(c + float3(uv * r, 0.0));
                return o;
            }

            FragOut Frag(Varyings i)
            {
                float r2 = dot(i.uv, i.uv);
                if (r2 > 1.0) discard;
                float h = sqrt(1.0 - r2);
                float3 surfaceVS = i.centreVS + float3(i.uv * i.radius, h * i.radius * 0.6);    // view space: +z faces the camera
                float3 n = normalize(float3(i.uv, 1.6 * h));                                  // a flattened, spreading drop
                Light light = GetMainLight();
                float3 l = normalize(TransformWorldToViewDir(light.direction));
                float diff = 0.5 + 0.5 * saturate(dot(n, l));
                float spec = pow(saturate(dot(reflect(-l, n), float3(0, 0, 1))), 60.0) * 0.6;
                FragOut f;
                f.color = half4(float3(0.11, 0.0012, 0.002) * diff * light.color + spec * light.color, 1.0);
                float4 cs = TransformWViewToHClip(surfaceVS);
                f.depth = cs.z / cs.w;
                return f;
            }
            ENDHLSL
        }
    }
}
