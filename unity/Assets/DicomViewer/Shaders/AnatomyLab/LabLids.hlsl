// The eyelids of the modelled body opening (backend/tools/anatomy_model/lids.py cuts the slits and writes, per
// vertex of the skin and of the lashes, the lid's weight: positive on the upper lid, negative on the lower, 1 on
// the lid's edge at the middle of the eye, 0 at the corners and at the brow; and which eye).
// A lid vertex turns about its eye's centre, round the axis across the face, by its weight times how far that
// eye is open: the edge travels up over the globe, the skin behind it gathers into the fold.
// ModelBody sets the values on the skin's and the lashes' materials, in the meshes' own object space.
//
// The values are material properties: a shader that uses this file lists LAB_LID_PROPERTIES' names in its
// Properties block and puts LAB_LID_UNIFORMS inside its UnityPerMaterial buffer. (Left outside the buffer they
// are taken for global values by the SRP batcher wherever the rest of the shader is batchable, and what the
// material says is ignored: the lashes stayed down while their lid went up.)
#ifndef LAB_LIDS_INCLUDED
#define LAB_LIDS_INCLUDED

// _EyeR, _EyeL: the eyes' centres. _EyeFwd, _EyeUp: the face's forward and up.
// _LidOpen: x the right eye open 0..1, y the left; z the upper lid's full turn, w the lower's (radians).
#define LAB_LID_UNIFORMS float4 _EyeR; float4 _EyeL; float4 _EyeFwd; float4 _EyeUp; float4 _LidOpen;

float3 LabLidTurn(float3 x, float3 k, float s, float c)
{
    return x * c + cross(k, x) * s + k * (dot(k, x) * (1.0 - c));
}

// lid: (weight, which eye: 0.05 the right, 0.55 the left, plus 0.2 times how much the skin there stands out as a
// fold when the lid is open). Turns a position and two directions (normal, tangent), and lifts the fold.
static const float LabLidFoldM = 0.0022;                       // the fold's height, in the meshes' metres
void LabLid(float2 lid, float3 eyeR, float3 eyeL, float3 fwd, float3 up, float4 lidOpen, inout float3 position, inout float3 a, inout float3 b)
{
    float weight = lid.x;
    if (abs(weight) < 1e-4) return;
    bool right = lid.y < 0.5;
    float open = right ? lidOpen.x : lidOpen.y;
    float angle = open * weight * (weight > 0.0 ? lidOpen.z : lidOpen.w);
    if (abs(angle) < 1e-5) return;
    float3 centre = right ? eyeR : eyeL;
    float3 k = normalize(cross(fwd, up));                       // turning by a positive angle carries forward towards up
    float s, c;
    sincos(angle, s, c);
    position = centre + LabLidTurn(position - centre, k, s, c);
    float fold = saturate((lid.y - (right ? 0.05 : 0.55)) / 0.2);
    position += normalize(position - centre) * (open * fold * LabLidFoldM);   // the skin gathered above the lid stands out
    a = LabLidTurn(a, k, s, c);
    b = LabLidTurn(b, k, s, c);
}

#endif
