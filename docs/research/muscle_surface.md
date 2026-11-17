# The muscles' surface from the photographs: what the data holds (2026-11-17)

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
3. **THE PHOTOGRAPHS ARE NOT REGISTERED TO EACH OTHER.** Measured by phase correlation between every photograph
   and the one before it: six times the whole picture jumps sideways.

   | At slice | Jump (columns, pixels) | The picture then lies at |
   |---|---|---|
   | 1149 (hips) | -6 | -6 px (2.0 mm) |
   | 1462 (chest) | -12 | -18 px (5.9 mm) |
   | 1488 | +12 | -6 px |
   | 1518 (shoulders) | -14 | -20 px (6.6 mm) |
   | 1626 (neck) | +12 | -8 px |
   | 1648 (head) | -10 | -18 px |

   (Measured at half the photographs' size: to 2 pixels.) Below the hips there is no jump. The feet and the top
   of the head show a steady drift of a pixel or two from every photograph to the next: that is anatomy slanting
   through the stack, not the picture moving.

   **Nothing in this project registers the photographs.** `prepare_photo_volume.py` stacks them as they are, so
   the export, the labels (the SIO's were fitted to it block by block: the "block-wise sideways steps" noted
   when they were imported), the skin and everything fitted to them carry these steps: 2 to 4.6 mm, softened by
   the coarse voxels and the smoothing. Nobody saw them until a surface was contoured at 0.66 mm, where each was
   a ledge right round the arm and the chest.

## What was decided

1. Every photograph is read again and the lightness of its tissue kept on the fine skin's own grid (0.66 x 1 x
   0.66 mm): `muscle_fine.npy`, with every photograph's shift against the one before it.
2. Muscle coverage is read from that per photograph, against its own muscle and fat.
3. Each labelled muscle keeps its place and its name and takes the muscle-coloured voxels at and within 4 mm of
   its own coarse voxels; never bone, an organ, a place a named structure was taken out of, or the skin.
4. The unnamed mass and the SIO's two arm masses are meshed as one surface (apart, each was closed where the
   labels' blocks end).
5. The runs' steps are SPREAD, not removed: each photograph's muscle is slid sideways towards the mean of the
   runs round it (a Gaussian over 10 photographs), so a step is a slope over about 5 cm and away from a step
   nothing moves. Removing them would put the muscles up to 6.6 mm off the skin and the labels they lie in.
6. The coverage is blurred 2.5 mm from photograph to photograph (0.8 mm within one).
7. A muscle's colour is its structure's, lighter and darker as the export's colours are 2.5 mm under its
   surface, and towards a tendon's where they are pale.

## Still to do, properly

- **Register the photographs once, in `prepare_photo_volume.py`, and build everything on that.** It moves the
  export, the labels, the skin, the bones' and the head CT's fit, the legs' muscles and the mouth: a rebuild of
  the whole model, to be done as a task of its own. Until then the trunk above the hips lies 2 to 6.6 mm to one
  side of where the legs say it should, in steps.
- The individual muscles of the trunk and the arms are one surface with real grooves, not separate named
  structures. The pale lines of fascia between them are in the photographs and could part them.
- Tendons are pale and are left out with the fat: the forearm's and the hand's muscles end where their tendons
  begin.
