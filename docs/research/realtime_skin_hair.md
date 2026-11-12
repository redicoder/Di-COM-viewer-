# Real-time skin and hair for the cadaver: research report

Date: 2026-11-12. Scope: web research plus a reading of `unity/Assets/DicomViewer/Shaders/AnatomyLab/LabSkin.hlsl`
and `LabModel.shader`. No repository source file was changed; this report is the only file written.

Marking used throughout: **[V]** = verified in this session (page, API or file actually read),
**[S]** = seen only as a search-result summary (page itself not opened or blocked),
**[M]** = from the author's memory of the literature, not re-checked today. Treat [S] and [M] as leads, not facts.

---

## 0. What our shader does today (read from the two files) [V]

| Aspect | Today | Gap against AAA practice |
|---|---|---|
| Diffuse | Wrapped Lambert; on the skin mesh a pre-integrated LUT by N.L and baked curvature (`bake.z / 0.25`) | One normal for all colour channels; shadow edge is grey, not red |
| Baked per vertex | openness (colour.r), thickness mm (colour.g * 60), curvature (colour.b * 0.25), gloss (colour.a); albedo in uv0.xy + uv1.x; **uv1.y is carried to the fragment (`data.a`) but never used** | One free channel now; TEXCOORD2/3 are unused |
| Micro relief | `LabSkinHeight`: Worley pores (27-cell loop) + lines + slow noise, 3 evaluations for a finite-difference normal, then `LabSkinMicroNormal` (12 more noise taps) | Expensive, no mip chain, pores are round blobs of one size |
| Specular | One GGX lobe, roughness 0.52 (dry) to 0.22 (wet), F0 0.028, fixed 0.25 factor instead of a visibility term | No second lobe, no cavity occlusion, no roughness variation |
| Sheen | `pow(1-ndv,4) * 0.08`, not tied to light or occlusion | Glows in shadow; should be a lit fuzz term |
| Translucency | `exp(-thickness/5 mm)`, red, view dependent | Good; could also tint the albedo in thin areas |
| Environment | Hard-coded hemisphere ambient, synthetic fill and rim | No reflection of the room in the skin; no HDRI |
| Colour | Vertex albedo with a global grade (`LabSkinGrade`) | No variation finer than the vertex spacing (about 2.7 mm on average for 600k triangles over about 1.9 m2) |
| Hair | None | The largest single gap |

---

## 1. How AAA games render skin

### 1.1 Texture set
The set is the same everywhere (Unreal Digital Humans / MetaHuman, Activision's "Next-Generation Character Rendering",
Unity's Heretic/Enemies digital human):

| Map | Typical size (head) | Purpose | Our equivalent without UVs |
|---|---|---|---|
| Albedo, de-lit | 4K to 8K | Colour without baked light | Per-vertex albedo (too coarse for pores, fine for regions) |
| Tangent normal (scan, mesoscale) | 4K to 8K | Wrinkles, folds | Real geometry: 600k triangles already carry it |
| Tiling micro-normal, masked by region | 512 to 1K, tiled 20-60x | Pores, fine lines | Procedural now; triplanar tile recommended (section 3) |
| Cavity | 4K | Multiplies specular (and a little diffuse) in pores | Missing; derive from the pore height |
| Roughness / gloss | 2K to 4K | Oily T-zone, lips, dry cheeks | Missing; region mask in a vertex channel + noise |
| Specular level (F0) | constant or 1K | Skin F0 0.028 (IOR about 1.4) | Already 0.028 |
| Scatter / thickness / translucency | 1K to 2K | SSS radius, light through ears | Baked per vertex already |
| Fuzz mask | packed channel | Peach-fuzz sheen | Missing |

Evidence: MetaHuman baked textures pack "Specular, Roughness, Metallic and Fuzz" in one texture [S]
(https://dev.epicgames.com/documentation/metahuman/metahuman-materials-and-textures). Epic's Digital Humans page says
roughness was not painted but converted from the normal map (a Toksvig-style normal-to-roughness step) [S]
(https://docs.unrealengine.com/4.26/Resources/Showcases/DigitalHumans, fetch returned 403). The Activision deck lists
the specular term as `cavity * Specular(gloss, reflectance)` [S] (slides: https://www.iryoku.com/stare-into-the-future,
323 MB pptx link confirmed on the page [V]).

### 1.2 Dual-lobe specular
- Unreal Subsurface Profile "Dual Specular": **Roughness0 = 0.75, Roughness1 = 1.3, LobeMix = 0.85** (shown as the
  constructor example in the UE Python API docs for `SubsurfaceProfileStruct`) [S]
  (https://docs.unrealengine.com/5.0/en-US/PythonAPI/class/SubsurfaceProfileStruct.html). The two roughness values
  are multipliers on the material roughness. As I recall the engine source, the blend is
  `lerp(D(lobe0), D(lobe1), LobeMix)`, i.e. 85 % broad lobe and 15 % sharp lobe [M]; the direction of the mix was
  not confirmed today, so tune by eye.
- Unity HDRP has the same idea: a diffusion profile with a dual lobe and a "Lobe Mix" whose default is 0.5 [S]
  (https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@15.0/manual/Diffusion-Profile.html).
  URP has none of this built in.
- Translating to our numbers: base roughness 0.45 gives a sharp lobe at 0.34 (the oily glint) and a broad lobe at
  0.58 (the soft sheen). A single lobe at 0.52 can only do one of the two, which is the classic "plastic or chalk"
  choice.

### 1.3 Subsurface scattering
| Method | Used by | What it needs | URP 17 forward |
|---|---|---|---|
| Pre-integrated LUT by curvature (Penner 2011) [M] | Many forward and mobile titles; ours | A LUT and a curvature value | Custom shader only. Already in place |
| Separable screen-space SSS (Jimenez et al.) | Activision; about 1 ms for two 1D passes [S] (https://graphics.unizar.es/papers/Separable-Subsurface-Scattering.pdf) | Diffuse lighting in its own target, depth, a skin mask | **Renderer feature** (two full-screen passes) plus a second colour output from the skin shader |
| Burley normalised diffusion, screen space [M] | Unreal 4.25+, Unity HDRP | Same as above plus per-pixel profile | **Renderer feature**; not in URP |
| Thickness-based transmission | Everyone | Thickness map or shadow-map depth | Custom shader only. Already in place |

For a static, single-key-light cadaver the pre-integrated route is adequate. Its two known weaknesses have forward
fixes (section 6, step 5): scattering does not soften the normal detail (fix: a smoother normal for red than for
blue), and it does not bleed into shadow edges (fix: tint the penumbra).

### 1.4 Cavity, specular occlusion, peach fuzz
- Cavity multiplies specular; one published look-dev breakdown removes the micro cavity at glancing angles so the
  skin does not look too rough there [S] (https://virtualvagabond.artstation.com/projects/OoLokg).
- Peach fuzz: Unity's Enemies moved its Skin Attachment system to the GPU "for high-density meshes" for effects
  like peach fuzz, i.e. real strands [S] (https://unity.com/resources/creating-realistic-digital-humans-in-unity).
  MetaHuman carries a Fuzz channel in the skin textures [S]. Cheaper titles use a grazing-angle fuzz lobe only.

### 1.5 Studio by studio
- **Rockstar (RDR2, GTA V, GTA 6)**: Rockstar has published nothing technical on skin. Secondary reports of Digital
  Foundry's GTA 6 trailer 2 analysis say hair looks strand-based rather than card-based, mention subsurface
  scattering on faces and visible arm hair on Jason; the outlets themselves stress this is interpretation [S]
  (https://rockstarintel.com/digital-foundry-reacts-to-gta-6-trailer-astonishing-detail-but-60fps-mode-unlikely,
  https://gtaintel.com/news/gta-6-strand-hair-and-detail-tech). No RDR2 skin study was found.
- **Naughty Dog**: the talks exist ("The Technical Art of Uncharted 4", "Character Shading of Uncharted 4",
  SIGGRAPH 2020 TLOU2 talks) but were not opened; details unverified [S]
  (https://advances.realtimerendering.com/other/2016/naughty_dog/index.html,
  https://www.naughtydog.com/blog/naughty_dog_at_siggraph_2020).
- **Unreal MetaHuman / Digital Humans**: as in 1.1 to 1.3.
- **Unity Heretic / Enemies**: HDRP only (skin shader graphs, tearline normal blur, GPU skin attachment, tension
  solver for wrinkle and blood-flow maps) [S]. Not usable in URP as is; useful as a reference.
- **Call of Duty (Jimenez, von der Pahlen)**: separable SSS, cavity-multiplied specular, pores, eyes [S].

### 1.6 What URP 17 forward can do
Custom shader only (no renderer feature): dual-lobe GGX, cavity and specular occlusion, micro-normal, roughness
variation, pre-integrated SSS, per-channel normals, penumbra tint, thickness transmission, fuzz lobe, reflection
probe and SH ambient, extra lights, alpha-to-coverage hair with MSAA.
Needs a renderer feature: screen-space SSS blur (separable or Burley), screen-space contact shadows (hair on skin,
creases), order-independent transparency for hair, any depth pre-pass special to hair. URP's built-in SSAO feature
only affects shaders that read its texture and write a DepthNormals pass, which `LabModel.shader` does not have.

---

## 2. Hair

### 2.1 Techniques
| Technique | How | Close-range look | Cost | Generated by code? |
|---|---|---|---|---|
| Hair cards | Strips with a multi-strand alpha texture | Good for long hair, poor for sparse short hair (cards read as flat flakes) | 5k-100k triangles, heavy overdraw, sorting trouble | Possible but needs a strand texture; not the right tool for short hair |
| Shells (and fins) | Skin drawn N times, pushed out along the normal, fragments discarded outside strand cross-sections (Lengyel et al. 2001) | Good from above for dense short fur; layers visible at grazing angles, "overly transparent" at silhouettes without fins [S] (https://hhoppe.com/proj/fur/) | N x the skin's fragment cost (8-16 shells); restrict to hairy sub-meshes | Trivial: needs only normals and a density mask |
| Strands | One polyline per hair, expanded to a camera-facing ribbon or tube | Best; the only method that holds up for eyebrows, lashes, sparse body hair | 2 triangles per segment per hair; thin, so little overdraw | Yes: this is what a Python script emits |
| Procedural stubble in the skin shader | Dark follicle dots + tiny bumps + lost specular | Good beyond about 30 cm, flat when very close | Nearly free | Yes |

Engines: Unity Hair System `com.unity.demoteam.hair` supports "Built-in RP, HDRP, and URP", Unity 2020.2+, renders
strands as lines, view-facing strips or tubes, and can "Scatter strands on built-in primitives, or on user specified
meshes" [V] (https://github.com/Unity-Technologies/com.unity.demoteam.hair). Its licence file was not found at the
expected path, so its terms are unverified; it is a simulation-first system and we need no simulation. Unreal Groom
is the strand equivalent in UE.

A cadaver does not move, so our hair can be **static geometry**: no simulation, no skinning. The only run-time
rule is that hair follows or hides with the skin patch it grows from when skin is cut or lifted (store the root's
skin triangle index, or simply hide strands whose root patch is removed).

### 2.2 Why width clamping matters (the numbers)
At 1080p and a 40 degree vertical field of view, one pixel covers 0.34 mm at 0.5 m and 0.07 mm at 0.1 m. A scalp
hair is about 0.07 mm wide (measured 68.7 to 74.5 um [S], https://pmc.ncbi.nlm.nih.gov/articles/PMC7035527/).
So hair is below one pixel wide in almost every view. Every strand renderer therefore clamps the ribbon to one
pixel wide and scales alpha by the true coverage (width / pixel size). Without this, hair sparkles and vanishes.
`LabPixelMm` in LabSkin.hlsl already gives the pixel size.

### 2.3 Best method per hair type
| Hair | Best at close range | Cost (our body) | Fallback at distance |
|---|---|---|---|
| Eyebrows | Strands, 5 segments, tapered | about 700 strands, 7k triangles | Same geometry, LOD by strand skipping |
| Eyelashes | Strands, 6 segments, strong taper, curved | about 380 strands, 4.4k triangles | Same |
| Shaved scalp / stubble | Short single-segment strands + follicle dots in the skin shader | about 78k strands, 156k triangles | Shader dots only beyond about 0.4 mm per pixel |
| Beard shadow | Blue-grey skin tint + follicle dots + short strands very close | about 12k strands, 25k triangles | Tint and dots |
| Chest, arms, legs | Strands, 6-8 segments, curl | about 100k strands, 1.3M triangles at full density | Strand skipping by distance; skin darkening under hair |
| Pubic, axillary | Strands, 12 segments, tight helix | about 5k strands, 120k triangles | Strand skipping |
| Vellus (peach fuzz) | Fuzz lobe in the skin shader + optional pale strands on the face | 12k strands, 48k triangles | Fuzz lobe only |

Shells are a reasonable alternative for scalp stubble only (6-8 shells over 1.5 mm on the scalp sub-mesh), but
strands look better at the hairline and cost less fill.

### 2.4 Generating strands from a mesh with normals and no UVs
1. **Region masks (per skin vertex, 0..1 per hair type).** No artist is needed: (a) from our own labelled anatomy
   (skin vertices within N mm of calvaria = scalp, of the mandible and maxilla below the zygomatic arch = beard,
   of the superior orbital rim = brows, of sternum and anterior ribs = chest, of radius/ulna, femur, tibia/fibula
   = limbs, of the pubic symphysis = pubic); (b) from the photographs themselves: where the Visible Human albedo is
   dark and unsaturated inside those regions, the real man had hair. Smooth each mask over 5-10 mm.
2. **Roots.** Area-weighted random points on triangles (random triangle by area x mask, random barycentric), then
   Poisson-disk thinning with radius r = 0.7 / sqrt(density) so roots are evenly spaced (dart throwing with a
   spatial hash, or sample elimination). On the scalp, group roots into follicular units of 1-4 hairs 0.2-0.3 mm
   apart.
3. **Growth direction field without UVs** (a unit tangent vector D per vertex), three workable ways:
   - Project a global flow vector g on the tangent plane: `D = normalize(g - N * dot(g, N))`. With g = inferior
     this alone is right for legs, belly and cheeks.
   - Gradient of a geodesic distance: distance from a source point or line by the heat method, then
     `D = normalize(tangential gradient)`, optionally rotated about N by a swirl angle. Crown whorl for the scalp
     (rotate 30-40 degrees), eyelid margin for lashes, a medial brow point for brows. Python: `potpourri3d`
     `MeshHeatMethodDistanceSolver.compute_distance(v)` [V] (https://github.com/nmwsharp/potpourri3d).
   - Interpolate a handful of code-set guide vectors over the surface with the vector heat method:
     `MeshVectorHeatSolver.transport_tangent_vectors(v_inds, vectors)` [V] (same package;
     https://nmwsharp.com/research/vector-heat-method/). A dependency-free substitute: fix the guide vectors,
     average 3D vectors over mesh neighbours 100-200 times, re-project to the tangent plane and normalise.
4. **Strand curve.** Root p0, skin normal N, flow D, side S = cross(N, D). Start direction
   `t0 = normalize(N*cos(tilt) + (D*cos(az) + S*sin(az))*sin(tilt))` with random tilt and azimuth jitter. For each
   of n segments of length L/n: `p += t*L/n; t = normalize(t + bend*D - lift*N + curlTerm)`. Curl is a helix:
   offset `r*(cos(phi0 + 2*pi*turns*s)*U + sin(...)*W)` about the strand axis, radius growing with s. Keep every
   point at least 0.15 mm above the root's tangent plane (for hairs longer than 10 mm, push out against the nearest
   skin point with a KD-tree).
5. **Taper.** Width `w(s) = w0 * (1 - 0.9 * s^2)` for uncut hair (fine tip), constant for cut stubble (blunt tip).
6. **Output.** Either polylines (GLB primitive mode LINES, expanded to ribbons in Unity at import) or ribbons with
   both vertices of each ring at the centre line and expanded in the vertex shader. Use standard slots so an
   importer keeps them: POSITION (centre line), NORMAL (root skin normal), TANGENT.xyz (strand tangent),
   TEXCOORD_0 = (side -1/+1, s 0..1), TEXCOORD_1 = (width mm, random seed), COLOR_0 = hair colour and root
   occlusion. About 210k strands and 1.6M triangles in total; polylines are about 18 MB, baked ribbons roughly
   three times that. Whether the project's glTF importer accepts line primitives was not checked.

### 2.5 Shading and sorting in URP
- **Shading.** Kajiya-Kay diffuse `sqrt(1 - dot(T,L)^2)` with two shifted highlights (Scheuermann 2004 [M]):
  a narrow white one shifted toward the tip (exponent 80-200) and a broad hair-coloured one shifted toward the root
  (exponent 20-60). Marschner / Karis (R, TT, TRT lobes) [M] pays off for long lit hair and is not needed for
  short dark hair; a single back-scatter term `pow(saturate(dot(V,-L)), 8) * hairColour` covers pale and grey hair
  against the light. Multiply by a wrapped `dot(Nroot, L)` so hair on the unlit side is dark, and sample the key
  shadow **at the root** so a hair is shadowed with its skin.
- **Root blend.** Darken and fade the first 10 % of each strand so it sinks into the skin; darken the skin under
  hair from the density mask (hair is not put in the shadow map: thin strands alias badly there).
- **Sorting.** Avoid blending. Draw strands in the opaque queue after the skin with `ZWrite On` and
  `AlphaToMask On` (ShaderLab command; needs MSAA 4x or 8x in the URP asset), output alpha = coverage, and add a
  per-strand hashed offset so coverage steps do not band. Without MSAA use hashed alpha clip with URP's TAA.
  Both are order independent. Plain alpha blending without sorting is tolerable only for sparse body hair.
- **LOD.** Each strand carries a random seed; the vertex shader collapses strands whose seed exceeds
  `keep = saturate(0.25 mm / pixelMm)` and widens the survivors by `1/sqrt(keep)`.
- **Cost.** Vertex bound (about 2.2M vertices at full density, close up); little fill. Hide body-hair groups
  when their region is off screen (split the hair into one mesh per region for frustum culling).

---

## 3. Should we build a UV atlas after all?

**xatlas on 600k triangles.** It works but is slow on large meshes, and the time is dominated by chart merging:
- Issue 36: "I have a mesh of 1000K faces, it spend about 12 hours to generate the atlas"; another user with
  about 1M faces: with `XA_MERGE_CHARTS` set to 0 "it takes ~10 minutes" [V] (https://github.com/jpcy/xatlas/issues/36).
- Issue 103: about 5M faces, "about 41 hours ... if enabling the merging charts option and only 1.5 hours if not",
  33,182 charts reduced to 27,362 [V] (https://github.com/jpcy/xatlas/issues/103).
- Tools that wrap xatlas warn above 50,000 faces [S].
- So for 600k triangles expect anything from about 10 minutes to several hours with the pip package
  (`pip install xatlas`, MIT bindings [V], https://github.com/mworchel/xatlas-python); **not measured here**.
  `XA_MERGE_CHARTS` is a compile-time switch as far as I know [M]. The Python binding offers no progress or cancel [S].
- Expect thousands of small charts on a scan-like surface.

**What seams cost.** Vertices duplicated along every chart edge; 4-8 texels of padding per chart (lost area, mip
bleeding); visible lines wherever a tiling pattern or a tangent-space normal map crosses a chart edge; hair and
pore direction cannot follow UV axes because the charts are oriented arbitrarily.

**What an atlas buys.** Texel size over a whole body (about 1.9 m2, 60 % atlas use): 4K = 0.44 mm, 8K = 0.22 mm.
Pores are 0.1-0.3 mm, so **a whole-body atlas cannot hold pore detail even at 8K**. What it can hold is colour at
6-12 times the linear resolution of our vertices (about 2.7 mm), which matters if the photographs resolve more
than the vertices do (the Visible Human cryosection pixels are about 0.33 mm in plane, 1 mm between slices [M];
check against our SIO data).

**Bake versus evaluate.**
| | Bake to 4K/8K atlas | Evaluate in the shader (today) | Tileable tile, triplanar (middle way) |
|---|---|---|---|
| Pore-scale detail | No (texels too large) | Yes | Yes, with real mip-mapping |
| Colour from photographs | Yes, 0.2-0.4 mm | No (vertex spacing) | No |
| Fragment cost | 1 sample | High: 3 x 27-cell Worley + 12 noise taps | 3 samples |
| Memory | 8K BC7 about 85 MB per map | None | 1K tile: about 1.4 MB |
| Seams | Yes | None | None; soft blend bands at 45 degrees |
| Needs UVs | Yes | No | No |

**Recommendation.** Do not atlas the whole body. (1) Move the pore detail to a tileable tile sampled triplanar in
object space (we own the generator, so no licence question: bake `LabSkinHeight`, improved, into a 1024 x 1024
normal + cavity + height tile once). (2) Only if the photographs really hold more colour detail than the vertices,
unwrap **just the head and the hands** (about 100-150k triangles each, far faster in xatlas) and bake 4K albedo for
those. Triplanar caveats: use a sharp blend (`pow(abs(N), 6)`), blend normals as offsets in object space, and use
the rest-pose position (`posM`) so the pattern stays with the tissue.

---

## 4. Why generated skin looks plastic, and the fixes

| Cause | Fix | Numbers to start from |
|---|---|---|
| One specular lobe of one roughness | Two lobes | sharp = 0.75 x base, broad = 1.3 x base, 15 % / 85 % |
| Highlight continuous across pores | Cavity multiplies specular, released at grazing angles | cavity 0.3 at pore centre; `lerp(cavity, 1, pow(1-ndv, 4))` |
| Same roughness everywhere | Region mask + noise | nose, forehead, lips 0.32-0.38; cheeks, limbs 0.50-0.60; noise +/-0.06 at 4-10 mm |
| Colour uniform between vertices | Three scales, on blood and pigment axes rather than RGB | 20-60 mm blotches +/-12 %, 1-3 mm mottle +/-5 %, pore darkening 10-15 % |
| Grey shadows and grey occlusion | Red penumbra; coloured occlusion; red survives longest | `pow(shade, float3(0.55, 1.0, 1.25))`; AO as `pow(ao, float3(0.7, 0.95, 1.0))` |
| Normal detail equally crisp in all channels | Smoother normal for red than for blue in the diffuse | smooth-normal weight R 0.85, G 0.55, B 0.25 |
| No redness where tissue is thin | Shift albedo toward blood by thickness | weight `exp(-thickness / 6 mm)`, tint (1.12, 0.90, 0.86) |
| No room reflected in the skin | HDRI reflection probe + SH ambient + specular occlusion | broad lobe at mip from roughness 0.55 |
| Too clean | Sparse moles, follicle dots, veins, hair | moles: about 1 per 30 cm2, 1-3 mm |
| No hair at all | Section 2 | |
| Sheen that ignores light | Fuzz lobe scaled by wrapped light and occlusion | 0.10-0.15, exponent 3 |

These starting numbers are my own proposals from general practice [M], not values taken from a cited source.
A cadaver is paler and drier than a living body; keep the grade the owner set by eye and add variation around it
rather than a living flush. Any colouring that depends on body position after death should stay descriptive and
educational, never diagnostic.

---

## 5. Free assets (CC0 or CC BY only)

| Asset | URL | Licence (quoted) | Resolution | Status |
|---|---|---|---|---|
| HDRI "Surgery" (operating room, lamp, table) | https://polyhaven.com/a/surgery | Poly Haven: "Our assets are all licensed as CC0" ... "You can redistribute them" (https://polyhaven.com/license) | up to 17000 x 8500 | [V] API + licence page |
| HDRI "Hospital Room 2" (clinical ward, 4365 K) | https://polyhaven.com/a/hospital_room_2 | same | up to 20480 x 10240 | [V] |
| HDRI "Hospital Room", "Children's Hospital" | https://polyhaven.com/a/hospital_room , https://polyhaven.com/a/childrens_hospital | same | up to 17000 x 8500 | [V] |
| Cloth "Cotton Jersey" | https://polyhaven.com/a/cotton_jersey | same | 8K, tile 26 cm | [V] |
| Cloth "Rough Linen" | https://polyhaven.com/a/rough_linen | same | 8K, tile 27 cm | [V] |
| Cloth "Waffle Pique Cotton", "Terry Cloth" | https://polyhaven.com/a/waffle_pique_cotton , https://polyhaven.com/a/terry_cloth | same | 8K (waffle); terry not checked | [V] waffle, name only for terry |
| Brushed metal Metal009, Metal011, Metal012, Metal010 | https://ambientcg.com/view?id=Metal009 (and the others) | "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License." (https://docs.ambientcg.com/license/) | 1K to 8K, JPG and PNG (seen for Metal009 and Metal011) | [V] licence and sizes; returned by the site's search for "brushed", pictures not inspected |
| Cotton fabric Fabric080 | https://ambientcg.com/view?id=Fabric080 | same | not checked | [V] id only (the one hit for "cotton") |
| Hair alpha "Hair Alphas For Days - hair38.png" | https://opengameart.org/content/hair-alphas-for-days-hair38png | Page shows "License(s): CC0" | 2048 x 2048 [S] | [V] licence line from the page HTML; image not inspected; part of a larger CC0 series |
| Head scan with colour and normal map (Lee Perry-Smith, Infinite Realities) | https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf/LeePerrySmith | "Infinite, 3D Head Scan by Lee Perry-Smith is licensed under a Creative Commons Attribution 3.0 Unported License." | not checked | [V] licence file. CC BY: must be credited in LICENSES.md. Face-specific, not tileable |
| MakeHuman bundled base mesh, skins, textures | https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md | "These assets have been released under CC0 1.0 Universal." Source code is AGPL. "If you use a third part asset, such as one downloaded from the asset repositories, it is your own responsibility to make sure you abide by its specific license." | not checked | [V] licence text. The skin, eyebrow and eyelash files are not in the main repository (only placeholders there); their download location was not found today |

Not found: a CC0 or CC BY **tileable human pore normal map**. The sites that came up (aitextured.com "Free for
personal & commercial use", Gumroad packs) use custom licences and must not be shipped. Recommendation: generate
our own tile from an improved `LabSkinHeight` (no third-party licence at all). No CC0 eyelash or eyebrow texture
was found either; with strand geometry none is needed. ambientCG has no skin and no hair material (search returned
only Leather008 for "skin" and nothing for "hair") [V].

---

## 6. Ranked implementation plan

Ranked by visible gain per unit of work. Sketches use the names in LabSkin.hlsl. None was compiled. Before using
any URP function named here, read it in the URP package source.

### 1. Eyebrows, eyelashes, scalp stubble and beard as generated strands + a `LabHair` shader
New Python tool emits strands (recipe in 6.11), new shader draws them.
```hlsl
// vertex: p = centre line (object), T = strand tangent, uv0 = (side -1/+1, s), uv1 = (width mm, seed)
float3 pw = TransformObjectToWorld(p);
float3 Tw = normalize(TransformObjectToWorldDir(T));
float3 V  = normalize(_WorldSpaceCameraPos - pw);
float px  = LabPixelMm(pw);                              // mm per pixel
float keep = saturate(0.25 / px);                        // strand LOD
float wMm = uv1.x * (1.0 - 0.9 * uv0.y * uv0.y) / sqrt(max(keep, 0.05));
float cover = saturate(wMm / px);                        // true coverage when thinner than a pixel
wMm = (uv1.y > keep) ? 0.0 : max(wMm, px);               // skipped strands collapse; others at least 1 px
pw += normalize(cross(Tw, V)) * uv0.x * 0.5 * wMm * 0.001;   // if world units are metres
// fragment (Kajiya-Kay, two shifted lobes); Nr = root skin normal, shadow sampled at the root
float StrandSpec(float3 T, float3 H, float e) { float th = dot(T, H); return smoothstep(-1.0, 0.0, th) * pow(sqrt(1.0 - th * th), e); }
float3 T1 = normalize(T + Nr * 0.08), T2 = normalize(T - Nr * 0.10);
float tl = dot(T, L);
float wrap = saturate(dot(Nr, L) * 0.5 + 0.5);
float3 c = hairCol * (sqrt(1.0 - tl * tl) * wrap * shade * keyColor + ambient)
         + keyColor * shade * wrap * (0.04 * StrandSpec(T1, H, 120.0) + 0.25 * hairCol * StrandSpec(T2, H, 30.0));
c *= lerp(0.45, 1.0, smoothstep(0.0, 0.15, s));          // root sinks into the skin
return half4(c, cover);                                   // pass: ZWrite On, AlphaToMask On, MSAA 4x+
```

### 2. Dual-lobe specular with pore cavity and roughness variation
```hlsl
float LabVis(float ndl, float ndv, float a) { return 0.5 / max(lerp(2.0 * ndl * ndv, ndl + ndv, a), 1e-4); }
// in LabShadeTissue, replacing the single lobe (cavity comes from step 3; regionOil from a vertex channel)
float rBase = lerp(0.52, 0.22, gloss) - 0.14 * regionOil * skin + (LabNoise(posM * 0.2) - 0.5) * 0.12 * skin;
float r0 = clamp(rBase * 0.75, 0.08, 1.0), r1 = clamp(rBase * 1.30, 0.08, 1.0);
float D  = lerp(LabGGX(ndh, r0), LabGGX(ndh, r1), 0.85);
float cavSpec = lerp(1.0, lerp(cavity, 1.0, pow(1.0 - ndv, 4.0)), skin);
float keySpec = D * F * LabVis(saturate(ndl), ndv, rBase * rBase) * saturate(ndl) * shade * cavSpec;
```
Drop the fixed 0.25 once the visibility term is in, then re-match the overall level by eye.

### 3. Pore detail from a tileable tile, triplanar, with mips
Generate once in Python: 1024 x 1024, RG = normal xy, B = cavity, A = height, tile 8 mm; pores of two sizes
elongated along one axis, fine cross-hatch lines. Sample with an explicit LOD so the ray-marcher can share it.
```hlsl
TEXTURE2D(_SkinDetail); SAMPLER(sampler_SkinDetail);      // tile = _SkinDetailMm (8), 1024 texels
float3 LabSkinDetail(float3 N, float3 Nobj, float3 posM, float amount, float pixelMm, out float cavity)
{
    float lod = log2(max(pixelMm * 1024.0 / _SkinDetailMm, 1.0));
    float3 w = pow(abs(Nobj), 6.0); w /= (w.x + w.y + w.z);
    float4 tx = SAMPLE_TEXTURE2D_LOD(_SkinDetail, sampler_SkinDetail, posM.zy / _SkinDetailMm, lod);
    float4 ty = SAMPLE_TEXTURE2D_LOD(_SkinDetail, sampler_SkinDetail, posM.xz / _SkinDetailMm, lod);
    float4 tz = SAMPLE_TEXTURE2D_LOD(_SkinDetail, sampler_SkinDetail, posM.xy / _SkinDetailMm, lod);
    float3 off = w.x * float3(0.0, tx.g * 2.0 - 1.0, tx.r * 2.0 - 1.0)
               + w.y * float3(ty.r * 2.0 - 1.0, 0.0, ty.g * 2.0 - 1.0)
               + w.z * float3(tz.r * 2.0 - 1.0, tz.g * 2.0 - 1.0, 0.0);
    cavity = dot(w, float3(tx.b, ty.b, tz.b));
    return normalize(N + TransformObjectToWorldDir(off, false) * amount);   // object-space offset, UDN style
}
```
A second sample set at tile 2.3 mm (same texture) gives the micro scale and replaces `LabSkinMicroNormal`.

### 4. Colour variation at three scales, thin-area redness, follicle dots
```hlsl
float3 LabSkinVary(float3 albedo, float3 posM, float thickMm, float cavity, float hairMask, float skin)
{
    float blotch = LabNoise(posM * 0.03) * 0.6 + LabNoise(posM * 0.11) * 0.4;         // 33 mm and 9 mm
    float mottle = LabNoise(posM * 0.55);                                             // 1.8 mm
    float hemo = (blotch - 0.5) * 0.9 + (mottle - 0.5) * 0.3 + 0.8 * exp(-thickMm / 6.0);
    float mela = (LabNoise(posM * 0.07 + 31.0) - 0.5) * 0.5;
    float3 v = albedo * pow(float3(1.02, 0.86, 0.82), hemo) * pow(float3(0.86, 0.78, 0.70), mela);
    v *= 1.0 - 0.14 * (1.0 - cavity);                                                 // pores a little darker
    float dots = 1.0 - smoothstep(0.10, 0.22, LabCells(posM * 1.1));                  // follicles about 0.9 mm apart
    v *= 1.0 - 0.35 * dots * hairMask;                                                // stubble seen through skin
    v *= lerp(float3(1, 1, 1), float3(0.82, 0.84, 0.88), 0.5 * hairMask);             // beard shadow
    return lerp(albedo, v, skin);
}
```
`hairMask` goes in the free vertex channel (uv1.y today) or TEXCOORD2.

### 5. Scattering fixes that stay in forward
```hlsl
float3 ndl3 = float3(dot(normalize(lerp(N, Nsmooth, 0.85)), L), dot(normalize(lerp(N, Nsmooth, 0.55)), L), dot(normalize(lerp(N, Nsmooth, 0.25)), L));
float v = bake.z / 0.25;
float3 pre = float3(SAMPLE_TEXTURE2D_LOD(_SkinLut, sampler_SkinLut, float2(ndl3.r * 0.5 + 0.5, v), 0).r,
                    SAMPLE_TEXTURE2D_LOD(_SkinLut, sampler_SkinLut, float2(ndl3.g * 0.5 + 0.5, v), 0).g,
                    SAMPLE_TEXTURE2D_LOD(_SkinLut, sampler_SkinLut, float2(ndl3.b * 0.5 + 0.5, v), 0).b);
float3 shade3 = lerp(shade.xxx, pow(max(shade, 1e-4), float3(0.55, 1.0, 1.25)), skin);   // red bleeds into the shadow edge
float3 ao3    = lerp(ao.xxx, pow(max(ao, 1e-4), float3(0.7, 0.95, 1.0)), skin);
```

### 6. The room in the skin: HDRI, reflection probe, specular occlusion
Poly Haven "Surgery" or "Hospital Room 2" as skybox and reflection probe. Keep LabSkin.hlsl pipeline-free: let
`LabModel.shader` fetch the two environment terms and pass them in.
```hlsl
// LabModel.shader (URP functions: check signatures in GlobalIllumination.hlsl / Lighting.hlsl)
float3 envDiffuse = SampleSH(N);
float3 envSpec    = GlossyEnvironmentReflection(reflect(-V, N), i.positionWS, 0.6, 1.0, screenUV);
// LabSkin.hlsl
float specOcc = saturate(pow(ndv + sky, exp2(-16.0 * rBase - 1.0)) - 1.0 + sky);
float4 t = rBase * float4(-1.0, -0.0275, -0.572, 0.022) + float4(1.0, 0.0425, 1.04, -0.04);
float a004 = min(t.x * t.x, exp2(-9.28 * ndv)) * t.x + t.y;
float envF = f0 * (-1.04 * a004 + t.z) + (1.04 * a004 + t.w);
color += envSpec * envF * specOcc * cavSpec;       // and envDiffuse replaces the hard-coded ambient
```

### 7. Body hair (chest, arms, legs, pubic) with strand LOD and skin darkening under hair
Same tool and shader as step 1; one mesh per region so off-screen regions are culled. Skin under hair:
`albedo *= 1 - 0.2 * hairDensity`.

### 8. Peach fuzz
Replace the constant sheen with a lit fuzz lobe, then optional pale vellus strands on the face.
```hlsl
float fuzz = pow(1.0 - ndv, 3.0) * 0.12 * skin * fuzzMask;
color += keyColor * fuzz * (saturate(ndl * 0.5 + 0.5) * shade + 0.3 * sky) * ao;
```

### 9. UV atlas for the head and hands only
xatlas on those sub-meshes; bake 4K albedo from the photographs. Only if a test shows the photographs hold detail
the vertices lose. Time it on the real mesh first.

### 10. Screen-space pass (last)
A URP renderer feature: separable or Burley SSS blur on a diffuse-only target, contact shadows for hair and
creases, TAA. Highest cost, least gain for a still body under one light.

### 6.11 Hair generation recipe (numbers for the Python script)
Densities are what we render; real figures in brackets. Angles are from the skin normal (90 = flat on the skin).
The render densities, lengths, widths, tilts and curl values are my proposed starting points [M], to be tuned
against screenshots; only the bracketed scalp figures come from a source seen today.

| Hair | Region and area | Render density per cm2 | Strands | Length mm | Root width um, tip | Segments | Tilt, jitter | Direction field | Curl |
|---|---|---|---|---|---|---|---|---|---|
| Eyebrow (each) | Band on the brow ridge, about 50 x 12 mm | 80 medial to 40 lateral | 350 | 6-8 medial, 9-11 middle, 6-8 lateral | 70, taper to 15 | 5 | 75 (medial tuft 50), +/-8 tilt, +/-12 azimuth | Medial third up and outward; middle outward, upper row angled down, lower row angled up; tail outward and down | Arc back to the skin, 15 degrees |
| Upper lashes (each eye) | 3 staggered rows in a 1.5 mm band along about 30 mm of lid edge | - | 120 (real 90-160 [M]) | 8-12 centre, 5-7 corners | 100, taper to 10 over the last 40 % | 6 | Leaves the lid forward and 15 degrees down, fans +/-25 degrees toward the corners | Away from the lid edge (gradient of distance from the lid margin) | Upward arc 50-70 degrees, radius about 7 mm; 30 % in clumps of 2-3 with converging tips |
| Lower lashes (each eye) | 1-2 rows | - | 70 (real 75-80 [M]) | 5-8 | 80, taper to 10 | 5 | Forward and down | Away from the lid edge | Downward arc 30-40 degrees |
| Scalp stubble | Scalp, about 650 cm2, density ramps over 10 mm at the hairline | 120 as strands, rest as shader dots (real 175-300 terminal hairs per cm2, mean 223 [S]) | 78,000 | 1.5 +/- 0.5 (short crop: 6, 3 segments) | 70-80, blunt tip | 1 | 40, +/-15 | Whorl: gradient of geodesic distance from the crown, rotated 35 degrees | None |
| Beard shadow | Cheeks, jaw, chin, upper lip, upper neck, about 250 cm2 | 50 (real figure not verified) | 12,500 | 0.5-1.0 | 100-140, blunt | 1 | 50, +/-15 | Downward; outward from the philtrum on the lip | None |
| Chest and belly line | About 900 cm2, densest over the sternum, strip to the navel | 20-30 (thorax 22 follicles per cm2 [M]) | 22,000 | 15-35 | 60-80, taper to 20 | 8 | 70-80, +/-10 | Downward and toward the midline | Helix radius 1.5-3 mm, 1-2 turns, random phase |
| Forearm and back of hand (each) | Dorsal two thirds, about 330 cm2; upper arm at 10 per cm2, 8-12 mm | 18 (forearm 18 [M]) | 6,000 + 2,500 | 10-20 | 50-70, taper to 15 | 6 | 75, +/-10 | Distal, rotated 30 degrees toward the ulnar side | Wave amplitude 0.5 mm |
| Thigh and calf (both legs) | About 2,400 + 1,400 cm2 hairy | 17 thigh, 14 calf [M] | 40,000 + 20,000 | 12-25 | 60-80, taper to 20 | 6 | 75, +/-10 | Distal | Helix radius 3-5 mm, half a turn |
| Pubic (and axillary at 20 per cm2) | Triangle of about 140 cm2 | 35 (not verified) | 5,000 | 25-40 | 100-120, taper to 30 | 12 | 50, +/-20 | Downward and medial | Helix radius 2-4 mm, 2-4 turns, axis jitter |
| Vellus on the face | About 400 cm2 | 30 (forehead about 292 follicles per cm2 [M]) | 12,000 | 0.8-2 | 20 (drawn 1 px wide at coverage alpha x 0.5), pale | 2 | 60, +/-15 | Downward | None; drawn only when a pixel is under 0.12 mm |

Totals: about 210,000 strands, about 1.6M triangles at full density; face hair alone (brows, lashes, stubble,
beard, vellus) is about 104,000 strands and 240,000 triangles. Root spacing r = 0.7 / sqrt(density). Hair colour:
take the darkest tenth of the photograph's albedo inside each hair region, so it stays this man's colour. Seed
every random choice from the root index so the build is reproducible (and testable in pytest: counts, lengths,
no point below the skin plane).

---

## 7. Not verified

- The direction of Unreal's LobeMix (which lobe gets 85 %); the Digital Humans page returned 403.
- Rockstar: no primary technical source exists; GTA 6 points are second-hand reports of a video analysis. Nothing
  specific found for RDR2 or GTA V skin.
- Naughty Dog, Activision and Unity Enemies details beyond what the search summaries state (slides not opened).
- xatlas time on our mesh (not run); whether chart merging can be turned off from Python.
- Body-hair follicle densities (Otberg et al. 2004), lash and brow counts, beard and pubic densities: from memory
  or weak sources. Scalp density and diameter came from search summaries of dermatology sources.
- All shader starting values in sections 4 and 6 and the hair recipe's lengths, widths, tilts and curls are
  proposals to tune, not sourced measurements.
- Visible Human photograph resolution quoted from memory; check against our data.
- ambientCG Metal009-012 and Fabric080 pictures and tags, the OpenGameArt hair image itself, the Lee Perry-Smith
  map resolutions: licences confirmed, content not inspected.
- MakeHuman skins, eyebrows and eyelashes: licence text confirmed for bundled assets, but the files' download
  location was not found (the main repository holds placeholders only).
- Licence of `com.unity.demoteam.hair`.
- Whether the project's glTF importer keeps line primitives and TEXCOORD_2/3.
- None of the HLSL sketches was compiled.

---

## 8. Sources

| # | Source | URL | Used for | Status |
|---|---|---|---|---|
| 1 | LabSkin.hlsl, LabModel.shader | repository | Section 0 | [V] |
| 2 | UE Python API, SubsurfaceProfileStruct | https://docs.unrealengine.com/5.0/en-US/PythonAPI/class/SubsurfaceProfileStruct.html | Dual-lobe values | [S] |
| 3 | UE Digital Humans showcase | https://docs.unrealengine.com/4.26/Resources/Showcases/DigitalHumans | Dual specular, roughness from normals | [S] (403) |
| 4 | MetaHuman materials and textures | https://dev.epicgames.com/documentation/metahuman/metahuman-materials-and-textures | Packed Fuzz channel | [S] |
| 5 | Unity HDRP Diffusion Profile | https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@15.0/manual/Diffusion-Profile.html | Lobe mix | [S] |
| 6 | Unity, digital humans featuring Enemies | https://unity.com/resources/creating-realistic-digital-humans-in-unity | Peach fuzz, skin attachment | [S] |
| 7 | Unity Hair System | https://github.com/Unity-Technologies/com.unity.demoteam.hair | Pipelines, strand modes, scatter | [V] |
| 8 | Jimenez, Next-Generation Character Rendering | https://www.iryoku.com/stare-into-the-future | Slides link; cavity x specular | [V] page, [S] content |
| 9 | Jimenez et al., Separable Subsurface Scattering | https://graphics.unizar.es/papers/Separable-Subsurface-Scattering.pdf | Screen-space SSS cost | [S] |
| 10 | Character look development breakdown | https://virtualvagabond.artstation.com/projects/OoLokg | Cavity at glancing angles | [S] |
| 11 | Reports of Digital Foundry on GTA 6 | https://rockstarintel.com/digital-foundry-reacts-to-gta-6-trailer-astonishing-detail-but-60fps-mode-unlikely ; https://gtaintel.com/news/gta-6-strand-hair-and-detail-tech | Rockstar | [S] |
| 12 | Technical Art of Uncharted 4; Naughty Dog at SIGGRAPH 2020 | https://advances.realtimerendering.com/other/2016/naughty_dog/index.html ; https://www.naughtydog.com/blog/naughty_dog_at_siggraph_2020 | Naughty Dog | [S] |
| 13 | Lengyel et al., Real-time fur over arbitrary surfaces | https://hhoppe.com/proj/fur/ | Shells and fins | [S] |
| 14 | NVIDIA, Fur shells and fins | https://developer.download.nvidia.com/SDK/10.5/direct3d/Source/Fur/doc/FurShellsAndFins.pdf | Shell draw order | [S] |
| 15 | xatlas issues 36 and 103 | https://github.com/jpcy/xatlas/issues/36 ; https://github.com/jpcy/xatlas/issues/103 | Unwrap times | [V] |
| 16 | xatlas-python | https://github.com/mworchel/xatlas-python | API, MIT licence | [V] |
| 17 | potpourri3d | https://github.com/nmwsharp/potpourri3d | Heat method, vector heat API | [V] |
| 18 | Scalp hair density | https://bionumbers.hms.harvard.edu/bionumber.aspx?id=116431 | 175-300 hairs per cm2 | [S] |
| 19 | Hair diameter study | https://pmc.ncbi.nlm.nih.gov/articles/PMC7035527/ | 68.7-74.5 um | [S] |
| 20 | Poly Haven licence and API | https://polyhaven.com/license ; https://api.polyhaven.com | Section 5 | [V] |
| 21 | ambientCG licence and API | https://docs.ambientcg.com/license/ | Section 5 | [V] |
| 22 | MakeHuman LICENSE.md | https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md | Section 5 | [V] |
| 23 | Lee Perry-Smith licence file | https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf/LeePerrySmith | Section 5 | [V] |
| 24 | OpenGameArt, Hair Alphas For Days | https://opengameart.org/content/hair-alphas-for-days-hair38png | Section 5 | [V] licence line |
| 25 | Penner, Pre-Integrated Skin Shading (2011); Christensen and Burley (2015); Golubev (2018); Scheuermann (2004); Kajiya and Kay (1989); Marschner et al. (2003); Karis (2016); Otberg et al. (2004) | not opened | Background | [M] |
