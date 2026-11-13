// The eyelids of the modelled body opening (backend/tools/anatomy_model/lids.py cuts the slits and writes, per
// vertex of the skin and of the lashes, the lid's weight: positive on the upper lid, negative on the lower, 1 on
// the lid's edge at the middle of the eye, 0 at the corners and at the lid's fold; and which eye).
// A lid vertex turns about its eye's centre, round the axis across the face, by its weight times how far that
// eye is open: the edge travels up over the globe, the skin behind it gathers into the fold.
// ModelBody sets these on the skin's and the lashes' materials, in the meshes' own object space.
#ifndef LAB_LIDS_INCLUDED
#define LAB_LIDS_INCLUDED

float4 _EyeR, _EyeL;            // the eyes' centres
float4 _EyeFwd, _EyeUp;         // the face's forward and up
float4 _LidOpen;                // x: the right eye open 0..1, y: the left; z: the upper lid's full turn, w: the lower's (radians)

float3 LabLidTurn(float3 x, float3 k, float s, float c)
{
    return x * c + cross(k, x) * s + k * (dot(k, x) * (1.0 - c));
}

// lid: (weight, 0.25 for the right eye or 0.75 for the left). Turns a position and two directions (normal, tangent).
void LabLid(float2 lid, inout float3 position, inout float3 a, inout float3 b)
{
    float weight = lid.x;
    if (abs(weight) < 1e-4) return;
    bool right = lid.y < 0.5;
    float open = right ? _LidOpen.x : _LidOpen.y;
    float angle = open * weight * (weight > 0.0 ? _LidOpen.z : _LidOpen.w);
    if (abs(angle) < 1e-5) return;
    float3 centre = right ? _EyeR.xyz : _EyeL.xyz;
    float3 k = normalize(cross(_EyeFwd.xyz, _EyeUp.xyz));       // turning by a positive angle carries forward towards up
    float s, c;
    sincos(angle, s, c);
    position = centre + LabLidTurn(position - centre, k, s, c);
    a = LabLidTurn(a, k, s, c);
    b = LabLidTurn(b, k, s, c);
}

#endif
