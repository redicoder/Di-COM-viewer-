# The muscles' surface from the photographs, and the photographs' registration (2026-11-17)

Written while the trunk's and the arms' muscles were rebuilt (`backend/tools/anatomy_model/fine_muscle.py`).
Everything here was measured on our own data: the Visible Human Male photographs (0.33 mm a pixel, 1 mm a slice,
`backend/data/vhp_male_photos`) and the export's labels. Positions along the body are fine slices: millimetres
above the lowest photograph (slice k is photograph 2878 - k). The working pictures are in
`build/research/muscle/` (not committed).

## Why

With the skin and the fat off, the legs looked like a body (70 named muscles from the University of Denver set)
and the trunk and the arms like wax: lumps with steps, patched with holes. Their muscles were meshed from the
labels, which say where muscle is on voxels of 1.32 x 2 x 1.32 mm. The photographs themselves show every muscle:
dark red against the cream of the fat, with the pale lines of the fascia between them.

## Colours (measured, the photographs' own values, mean of r, g, b)

| Tissue (by the labels, two voxels inside) | Median r, g, b | Lightness 5 % .. 95 % |
|---|---|---|
| Muscle | 77, 39, 31 | 36 .. 78 (median 49) |
| Fat | 205, 183, 128 | 114 .. 202 (median 172) |
| Organs | 60, 34, 25 | 20 .. 88: as dark as muscle |
| Bone (marrow and cortex) | 154, 112, 88 | 75 .. 208: overlaps both |

So lightness separates muscle from fat cleanly, and cannot tell muscle from an organ or from red marrow: which
dark red thing a voxel is stays the labels' part.

## The photographs are not all alike

1. **Runs with darker fat.** From one run of photographs to the next the fat is 5 to 10 % darker or lighter while
   the muscle stays (fat's median 161 -> 153 at slice 1462, 147 -> 136 at 1518, 142 -> 132 at 1526; muscle 50 to
   57 throughout). The fat of the shoulders is darker than the arms' anyway (135 against 165). Read with one pair
   of lightnesses, the darker runs' fat counted as a fifth muscle. Each photograph is therefore read against its
   own muscle and fat (the labels' sure voxels in that photograph).
2. **Photographs that are not whole.** Slices 1371 to 1373: a part of the picture is missing (the right arm's
   tissue falls from 135 to 17 cm2). Found by the tissue's area against the neighbours'; 49 photographs in all,
   most of them at the knees' and the hips' joints between the specimen's blocks.
3. **THE PHOTOGRAPHS WERE NOT REGISTERED TO EACH OTHER.** Measured by phase correlation between every photograph
   and the one before it, at the photographs' own pixels: six times the whole picture jumps sideways.

   | At slice (photograph) | Jump (columns, pixels) | The picture then lies at |
   |---|---|---|
   | 1149 (1729, hips) | -5 | -5 px (1.7 mm) |
   | 1462 (1416, chest) | -13 | -18 px (5.9 mm) |
   | 1488 (1390) | +12 | -6 px |
   | 1518 (1360, shoulders) | -13 | -19 px (6.3 mm) |
   | 1626 (1252, neck) | +11 | -8 px |
   | 1648 (1230, head) | -9 | -17 px (5.6 mm) |

   No jump in the rows (front to back), none below the hips. Each of the six shows the same on the picture's left
   half and on its right half measured apart (to a pixel; to 2.5 pixels at the shoulders).

   Five more lone "jumps" of 3 to 4 pixels showed in the whole picture's correlation (slices 66, 114, 332, 1830,
   1838: ankles, a shin, the top of the head). Measured on the two halves apart, each half told another story (the
   two legs slanting differently; the skull's two sides closing in): they are not the picture moving, and were
   left alone. So a jump of about a millimetre cannot be told safely by this method.

   **An independent source says the same.** The SIO is a crop of these same photographs, which its makers aligned
   to the CT. Its crop corner on OUR stack, measured slice by slice when its labels were imported, stepped at
   exactly these photographs: column 156 below photograph 1730, 150 to 1417, 138 to 1391, 150 to 1361, 138 above:
   -6, -18, -6, -18 pixels (to its 3 pixel voxel), against our -5, -18, -6, -19. (This was noted when the labels
   were imported, as "block-wise sideways steps", and taken for the SIO's doing. It was ours.) The frozen CT's
   place on the photographs along the trunk stepped at three of the same places too.

   `prepare_photo_volume.py` stacked the photographs as they came, so the export, the labels, the skin and
   everything fitted to them carried these steps, softened by the coarse voxels and the smoothing. Nobody saw
   them until a surface was contoured at 0.66 mm, where each was a ledge right round the arm and the chest.

## What was decided

1. Every photograph is read again and the lightness of its tissue kept on the fine skin's own grid (0.66 x 1 x
   0.66 mm): `muscle_fine.npy`.
2. Muscle coverage is read from that per photograph, against its own muscle and fat.
3. Each labelled muscle keeps its place and its name and takes the muscle-coloured voxels at and within 4 mm of
   its own coarse voxels; never bone, an organ, a place a named structure was taken out of, or the skin.
4. The unnamed mass and the SIO's two arm masses are meshed as one surface (apart, each was closed where the
   labels' blocks end).
5. The runs' steps are cured at their source (2026-11-17, the product owner's decision): `tools/register_photos.py`
   writes how far each photograph is to be moved, `prepare_photo_volume.read_photo` moves it, and the whole body
   was built again on the stack as lined up. (For a few hours before that the muscles' steps were only spread into
   slopes; that code is gone.)
6. The coverage is blurred 2.5 mm from photograph to photograph (0.8 mm within one).
7. A muscle's colour is its structure's, lighter and darker as the export's colours are 2.5 mm under its
   surface, and towards a tendon's where they are pale.

## After the photographs were lined up

- The SIO's crop corner on the photographs is one constant, (96, 156), over all its 774 slices (before: four steps).
- The frozen CT's place on the photographs along the trunk no longer steps at photographs 1416, 1390 and 1360.
  (It still moves 4 to 5 mm sideways and back between photographs 1440 and 1494. No jump of the picture was
  measured there: the photographs 1504 to 1509 just below are the ones with a part missing, and the outlines
  there mislead. Not looked into further.)
- The skin's outline, 8 photographs under each place against 3 over it, moved sideways by 2.0, 3.9, 3.8 and 3.6 mm
  at the trunk's four places; it moves 0.5, 0.2, 0.4 and 0.0 mm now.
- **The bones, one by one, against his own bone** (BoneHub's bone against the bone of the labels: the CT's, matched
  slice by slice to the photographs; the sideways move that would put BoneHub's bone best on his own):

  | Bone (height, mm) | Before | After |
  |---|---|---|
  | sacrum (1073), L5 (1128) | +1.0, +1.5 | -0.5, -0.5 |
  | L3, L1, T12, T10, T8 (1201 to 1424) | +0.5, +0.5, +1.0, 0.0, -0.5 | the same |
  | T6, T4, T2, T1 (1478 to 1591) | -4.0, -4.0, -3.0, -5.0 | 0.0, 0.0, +0.5, -1.0 |
  | skull (1778) | +1.5 | +5.0 |

  So the trunk's column is straight to a millimetre now, where the chest's vertebrae lay 4 mm aside. And the
  HEAD lay worse: BoneHub's bones are laid on him by one shift for the whole skeleton, and BoneHub's head does
  not lie to its trunk as his does (by 5 mm sideways). Before, that one shift had the head right and the chest
  wrong; lined up, the chest right and the head wrong. The head's bones are therefore settled on his own skull
  (`bonehub.settle`): moved 4.0 mm back, 2.0 mm up and 5.0 mm sideways; 59 % of the skull's surface lay within
  1.5 mm of his own bone, 82 % does now (66 % before any of this: the skull never lay so well).
- Left as it was, and now known: BoneHub's neck vertebrae lie 4 to 8 mm before his own (front to back) and its
  upper thoracic ones 3 mm; and all of BoneHub's skeleton is about 3 % small in the plane against the
  photographs' nominal pixels (the CT's scale on them is 0.968, `ct_frame.SCALE`; BoneHub is laid on without a
  scale). A fit with that scale and the vertebrae settled as the skull is: the next thing to do to the skeleton.
- Not cured: a block of the specimen that was laid a little aside from the one under it. The photographs at the
  joints (knees: 2424 to 2435; hips: 2017 to 2019) are blank or not whole and cannot be measured across.

## Still to do

- The individual muscles of the trunk and the arms are one surface with real grooves, not separate named
  structures. The pale lines of fascia between them are in the photographs and could part them.
- Tendons are pale and are left out with the fat: the forearm's and the hand's muscles end where their tendons
  begin.
