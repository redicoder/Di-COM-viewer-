# The nails (2026-11-23)

Research before the nails were built (`backend/tools/anatomy_model/nails.py`). Marks as in the other reports:
**O** read on our own data (the photographs, the built skin), **S** read at a published source, **K** from
general knowledge (check before showing it to a student as fact). The general numbers are in
`skin_features_hair_maps.md`, section C3, with their sources; they are repeated here only as far as they were used.

## 1. What the photographs hold

Looked at: the photographs through the left foot's toes (14 to 36 mm above the lowest photograph) and through the
left hand's fingertips (972 to 1004 mm), enlarged three times (working pictures in `build/research/nails/`, not
committed: the photographs are data).

- The feet are stretched and the toes bent, so a photograph cuts a toe across at a slant: each toe is an oval with
  its bone in it. The fingers lie on the belly and are cut at a slant as well. (O)
- Every digit has a pale rim, half a millimetre to a millimetre thick: its horny skin. On the back of a digit's
  end the nail's plate is a pale arc of one to three pixels (0.3 to 1 mm) lying on that rim, with a thin darker
  line under it on some photographs (the nail bed). It shows on the second toe 18 and 22 mm up and on a finger
  984 mm up; on the great toe, the largest nail he has, it does not show on any of the six photographs looked
  at. (O)
- A rule that tells the plate from the rim was not found, and at this size is not to be expected: a toenail is
  1.0 to 1.3 mm thick (K), three to four pixels, a fingernail 0.5 mm (K), one and a half.

**So his own nails' outlines are not read.** What can be measured on him is where each digit ends, which way it
points, which side its back is, and how wide and thick it is there. The nails are DRAWN from those: the usual
proportions, at his places, in his sizes as far as the digit's width limits them.

## 2. The numbers used

| | width x length, mm | from |
|---|---|---|
| great toe | 18 x 14 | the textbooks' range 16-20 x 12-16 (K) |
| second, third toe | 9 x 7 | 8-10 x 6-8 (K) |
| fourth toe | 8.5 x 6.5 | the same range, its lower half (K) |
| little toe | 6 x 4.5 | 5-7 x 4-5 (K) |
| thumb, index, middle, ring, little finger | 16 x 15.4, 12 x 12.8, 12.5 x 13.2, 11.5 x 12.1, 9.5 x 10.2 | widths from the textbooks' ranges (K); lengths = width / the measured width-to-length ratios of men's nails, 1.04, 0.94, 0.95, 0.95, 0.93 (S, as read for C3: 300 Korean adults, doi 10.5999/aps.2015.42.6.753) |

A nail is at most 0.72 of its digit's width there (K: a nail takes up about two thirds to three quarters of the
fingertip's width; chosen by eye on the first pictures, where 0.8 looked like nails painted to the edge), and no
wider than 0.8 of its share of the distance to the next digit's nail. It ends 0.22 of the digit's thickness short
of the digit's end (a short-cut nail ends where the end of the digit begins to turn down; K, by eye).

Colours, against the skin's (210, 170, 150): a toenail on its bed (212, 186, 156), yellower; a dead man's
fingernail (201, 170, 162), paler and greyer; the free edge (226, 214, 196); the lunula (216, 196, 186), drawn on
the great toe (and, when the fingers have nails, on the thumb, fainter on the index and middle finger). All K,
toned down from C3's values: at C3's full values the first pictures showed yellow and lilac tiles.

## 3. What was measured on him (O)

On the skin as built on 2026-11-23, by `nails.find`:

| toe | digit there: width, thickness (mm) | nail drawn: width x length (mm) |
|---|---|---|
| left great | 20.7, 17.6 | 14.9 x 11.6 |
| left second | 16.2, 14.4 | 9.0 x 7.0 |
| left third | 12.5, 15.3 | 9.0 x 7.0 |
| left fourth | 14.4, 14.1 | 8.5 x 6.5 |
| left little | 8.3, 13.5 | 6.0 x 4.5 |
| right great | 19.6, 17.7 | 14.1 x 11.0 |
| right second | 15.8, 12.9 | 9.0 x 7.0 |
| right third | 12.5, 17.2 | 9.0 x 7.0 |
| right fourth | 11.8, 14.6 | 8.5 x 6.5 |
| right little | 9.7, 10.6 | 6.0 x 4.5 |

His great toes are 20 mm wide where the nail lies, so their nails come out at 14 to 15 mm, under the textbooks'
16 to 20: either his are narrow or the 0.72 is low for a great toe (it carries the widest nail in proportion).
Left as measured.

## 4. How a nail's place is found, and what failed

1. The digit's bones (BoneHub's `phalanges of the ...`, one mesh for a digit's two or three bones) are moved as
   a whole, up to 6 mm, to where the fewest of their vertices lie at the skin or outside it: the CT has a toe 1
   to 3 mm and a finger up to 5 mm beside where the photographs have it.
2. The digit's end is where the bones' middle line, carried on FROM WITHIN the digit, leaves the skin soonest.
   (Carried on from the bone's own end, it failed on the right foot: its toes were pressed flat when he was
   frozen, and the bones' ends stand out of them.)
3. The back of a toe looks the way the back of its foot looks: across the plane the five metatarsals lie in, to
   the side on which the skin is nearer them (a few millimetres over the bones on the back of a foot, fifteen
   under them), made square to the toe. The same for the fingers from the four metacarpals of the fingers. The
   thumb is turned against the fingers: its back is the side on which the skin lies nearest its bone, not
   towards a finger. **What failed:** that last rule for every digit. Under a nail there is a millimetre or two
   over the bone and under the pad eight, so the back should be the side where the skin is nearest; but on toes
   that lie pressed together the skin at the sides is as near, and the bones are not placed to the millimetre:
   of the ten toes' backs four looked sideways or down.
4. The digit's thickness and width: from its middle line (through its end, the way it points) to the skin either
   way. Where a toe lies pressed to its neighbour there is no skin between them to meet; then the table's width
   stands, narrowed by the neighbours' distance. (Tried before: the digit's end as what lies within reach of the
   tip along the skin; where toes are joined that reach runs over into the neighbour, and the widths came out
   at 26 to 48 mm.)
5. The plate is a grid of 15 x 13 points in that frame, each lifted from the digit's middle to the skin's own
   surface and 0.15 mm over it; towards the digit's end, where the skin turns down round the tip, it goes
   straight on, as a nail does. Its rim is turned down 0.6 mm into the skin.

## 5. The fingers

Tried first with the hands' skin as it was (2026-11-23, morning): 18 of the 20 nails were found; on the left hand
five plausible ones, on the right hand the ring and little fingers' ends were not found and the index and middle
fingers' nails lay across each other. The cause was not the rules but the skin: it was read by the outline rule
that joins what lies together (the same that made the toes one lump), and his right hand lies half closed, its
fingers against each other.

Built the same day, after the hands' skin was read with the fingers apart (ARCHITECTURE, the body below the
head). Measured on that skin (O), digit's width there and nail drawn, mm:

| finger | left: digit, nail | right: digit, nail |
|---|---|---|
| thumb | 17.5, 12.6 x 12.1 | 19.5, 14.0 x 13.5 |
| index | 14.5, 10.4 x 11.1 | 12.8, 9.2 x 9.9 |
| middle | 13.5, 9.7 x 10.3 | 14.6, 10.5 x 11.1 |
| ring | 12.9, 9.3 x 9.8 | 12.3, 8.8 x 9.3 |
| little | 10.4, 7.5 x 8.1 | 11.2, 8.1 x 8.6 |

His fingers are 10 to 15 mm wide at the nail, so every fingernail is limited by the 0.72 of its finger's width
and comes out 1.5 to 3 mm narrower than the textbooks' widths. A hand's or a foot's nails are drawn only if at
least four of them are placed soundly (the digit not thicker than 24 mm there, no nail lying on another):
`nails.sound`.

## 6. What stays unknown

- His real nails' outlines, lengths and state (an old man's toenails are often thick, ridged and yellow; these
  are drawn clean and short). (K)
- Whether the nails' widths are his: see section 3.
- The nail folds are drawn in colour only (the skin round a nail a little redder); the mesh there, at 0.9 mm, is
  too coarse for a fold a millimetre high.

## 7. For the parts to come

Each nail is a structure of its own in the skin layer (`nail of the left great toe`, ...), with `info` saying it
is drawn and from what: it can be named, shown and taken off by itself. For cutting: a toenail's plate is 1.0 to
1.3 mm thick and a fingernail's 0.5 mm (K); under it lie the nail bed and, at its root, the matrix, 3 to 6 mm
under the proximal fold (K); the plates drawn are surfaces 0.15 mm over the skin with a rim, not solids.
