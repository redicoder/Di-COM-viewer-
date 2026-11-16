# The throat behind the mouth: what our own data holds (2026-11-16)

Written before the throat was built (`backend/tools/anatomy_model/throat.py`). Everything here was read from
our own data: the head's photographs (0.66 x 1 x 0.66 mm), the frozen CT (0.527 mm round the mouth) and
TotalSegmentator's labels on it. Positions are in millimetres from the point where the lips meet in the midline:
z back, y up, x to his left. The working pictures are in `build/research/throat/` (not committed).

## What the photographs show

In the midline section, front to back:

| Structure | Where | How it was read |
|---|---|---|
| Hard palate | pale band, ends at z 67 to 70, y +21 to +28 | photographs; the CT's bone ends at z 69.8 |
| Mouth's space under it | dark band 3 mm thick, y +19 to +22 | photographs |
| Tongue | fills the mouth to the palate; its pale rim runs from (z 50, y +19) through (z 70, y +15), (z 78, y +8), (z 86, y 0) to (z 94, y -11) | photographs |
| Soft palate | pale band 8 to 10 mm thick, lying ON the tongue's back, from the hard palate's hind edge down and back | photographs |
| Uvula | pale oval at x -6, z 93 to 95, from y +10 down to y -5 | photographs (coronal section at z 94, axial at y 0) |
| Throat's lumen | a film of dark fluid 3 to 6 mm deep round the uvula, z 95 to 101; a few air bubbles in the CT along it | photographs and CT |
| Back wall | z 100 to 103, before the vertebrae (their fronts at z 104 to 108) | photographs and CT |
| Left tonsil | pale lobed mass at x +8 to +22, z 82 to 98, round y 0 | photographs (axial at y 0) |
| Right tonsil | less distinct, about x -30 to -18 | photographs |

The tongue's own middle lies 5.3 mm to his right of the lips' middle at its back: the head is a little turned.

So he was frozen with the tongue filling the mouth, the soft palate draped over its back, and the throat fallen
shut behind it. There is no open throat in the scan to copy: the uvula lies between the tongue's root and the
back wall.

## What cannot be read

- **Colour does not separate the lumen from muscle.** Measured: the dark film (105, 56, 45), the tongue's muscle
  (120, 65, 49), the muscle before the spine (80, 40, 32); pale mucosa is (150 to 175, 111 to 125, 80 to 92). A
  threshold on darkness took 74 cm3 of muscle with the lumen. The lumen was therefore not segmented.
- **The CT does not separate the soft palate from the tongue** (the same density). TotalSegmentator's
  `soft_palate` label is a 1.2 cm3 blob at the hard palate's hind edge only.
- **Where the tongue touches the soft palate** there is no dark line between them in most sections: pale on pale.

## What can be relied on

- **TotalSegmentator's `tongue` label follows the tongue's pale rim** behind the hard palate to about a
  millimetre (checked along rays from the tongue's centre through the photographs). It is the tongue's true back.
- The model's tongue had been grown up to palate height everywhere. Behind the hard palate that put the soft
  palate INTO the tongue (68.7 cm3 against 59.7 cm3 after the correction), and in the opened mouth it stood as a
  wall before the throat. That was the "dark wall".

## The jaw's turn

With the jaw turned about the condyles' heads, a point at the lower back teeth (z 62, y 0) goes 17.6 mm BACK and
9 mm down at 18 degrees: everything under the joints swings into the throat. A living jaw's condyles slide about
a centimetre forward as it opens wide; rotation plus that slide is one rotation about an axis under the joints,
near the middle of the ramus. With the axis 30 mm under the condyles' heads the same point goes 8.3 mm back and
10.4 mm down, the condyles' heads go 9.3 mm forward, and the lower incisors' edges still go 23 mm down.
(The 30 mm and the centimetre of slide are from memory of textbook anatomy, not read at a source: check before
showing them to a student as numbers.)

## What was decided

1. The tongue behind the hard palate is the label itself.
2. The soft palate's under side is the tongue's own frozen surface there, held with the skull.
3. The throat is DRAWN at the measured places, and marked as generated: the space below the soft palate's free
   edge (15 mm under the hard palate's hind edge), the uvula (14 mm, tip at about z 95, y -5, as measured), the
   back wall at z 101.5, the side walls 16 mm from the middle, a tonsil in each with a fold behind it.
4. The jaw's axis lies 30 mm under the condyles' heads.
5. The tongue lies down as the mouth opens (towards the level of the lower teeth's edges, lower at its root):
   frozen up against the palate, it would hide the throat whatever is built behind it.
6. One closed wall lies 2.5 mm outside all the mouth's and the throat's lining (a "mouth bag", as game
   characters have): a gap between the lining's parts shows a shaded wall, not the layers behind.
7. BoneHub's vertebrae C1 and C2 stand at z 99.5 and 100.6, 4 to 7 mm before where the CT has their fronts
   (z 104 to 108), and so before the back wall at z 102.4; the CT's labels of the throat's constrictors too
   (z 100.6). Whatever of the layers under the skin reaches into the throat as drawn is moved out of it
   (`throat.tuck`).

## Not done, and why

- The lumen as it really lay (the film round the uvula) is not modelled: it cannot be segmented, and a throat
  fallen shut shows nothing.
- The tonsils are simple lobes at measured places, not his own: the left one is clear in the photographs and
  could be segmented by hand later.
- The nose's part of the throat, the epiglottis and the larynx's entrance are not built.
