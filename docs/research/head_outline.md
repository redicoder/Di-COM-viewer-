# The head's outline (2026-11-24)

Research before the head's skin was read from its tissue (`fine_skin.head_outline`), and what was found on the
way. Marks as in the other reports: **O** read on our own data (the photographs, the built model), **K** from
general knowledge. Working pictures are in `build/research/head/` and `build/research/body/` (not committed: the
photographs are data).

## 1. How far the old outline stood off his skin (O)

The head was still read by the first rule: whatever lies 2.6 mm inside the export's mask is body, whatever its
colour, and the photograph refines the edge only within 2.6 mm of the mask. Measured on fifteen photographs from
the chin to the crown: the kept outline's edge against the edge of the tissue as the body's rule reads it
(`fine_skin.body_outline`), in millimetres (median; tenth to ninetieth part of the edge).

| mm above the lowest photograph | what is cut there | kept outline outside the tissue |
|---|---|---|
| 1650 | under the chin | 2.4 (1.5 to 6.1) |
| 1670 to 1710 | chin, mouth, upper teeth | 1.65 to 1.9 (1.0 to 2.8) |
| 1725 to 1755 | nose's wings, cheek bones, ears | 1.65 to 1.8 (1.0 to 3.3) |
| 1770 to 1800 | eyes, brows | 1.65 (1.0 to 2.3) |
| 1815 to 1830 | forehead | 2.3 (1.7 to 3.1) |
| 1845 to 1868 | the crown | 4.1 to 4.9 (3.1 to 7.2) |
| 1871 to 1876 | the top six photographs | 9 to 16 |

So the face stood 1.65 mm too far out all round, as the trunk did, and the crown far more. The top six
photographs counted as blank (less than 0.6 of the mask is tissue on them) and took the mask itself: the head
ended in a flat cap some 50 by 60 mm across.

## 2. Why the crown is worst: the camera sees the skin below (O)

On the top photographs the cut face (brown, sharp-edged, about 16 by 24 mm on the last one) lies in a pale ring 10 to
15 mm wide that carries the dots of his shaved hair. That ring is not in the cut: it is his scalp further down,
seen through the gelatin. So the photographs look at each cut face from the head's end, and what lies below a
cut and wider than it shows round it. Round most of him that is a thin frost-coloured halo, which the body's rule
already leaves out (greener than red, hardly redder than blue). Over the crown, where his surface lies nearly flat
under the cut, it is wide and in places as red as tissue: on the last two photographs the tissue test alone takes
a spur and a patch of it.

What tells it apart there: above 1850 mm the head only grows smaller from one photograph to the next (O: his
area falls steadily, by about 800 voxels of 0.44 mm2 a photograph near the top), so what a photograph shows of
him beyond the photograph below is that halo. On the last photograph his area is 440 mm2 and still falling by
about 450 mm2 a photograph: **the top of his head lies about a millimetre above the last photograph.** The mesh
closes it flat there, some 20 mm across.

## 3. What the tissue rule gives on the head (O)

Tried on a copy of the outline, meshed and rendered before anything was built on it:

- **Nostrils.** At 1725 mm the nose's wings and its middle wall are three lobes with two notches between them:
  the nostrils. The old outline ran round all three as one lump. Above the notches each nostril is a hole his
  outline encloses.
- **Cavities.** The maxillary sinuses (about 30 by 35 mm on a photograph), the ethmoid and mastoid cells and the
  nose's passages are filled with the same blue gelatin as the outside. They open to the outside through the
  nostrils, so the trunk's way of telling a cavity from a gap (`fill_closed`: a gap opens to the outside on a
  photograph near) would call all of them open space. In the head whatever the outline encloses on a photograph
  is taken as him; a nostril then ends in a ceiling where it stops being a notch, a few millimetres in.
- **Lids.** On the six photographs through the lid lines (1763 to 1770 mm) the outline runs over the closed lids,
  1.5 to 3 mm of lid over each globe (by eye on the pictures): nowhere does it break through into the eye.
- **Ears.** The auricles are followed fold by fold, and the gap behind an ear stays open where it is wider than
  2 mm. The ear canals are open from the side.
- **Steps between photographs.** The cheeks' front surface moves by 0.13 mm from one photograph to the next
  (median), and nowhere by more than 0.9 mm: no seam, and smoother than the old outline was there. So the head
  is not evened out along the body (`steady`, used below the head, would take a lid line with it: it is a
  millimetre high).
- **Photographs that are not whole:** none in the head by the measure used below it (his area against the
  photographs before and after).

## 4. What was fitted to the old skin, and what happened to it (O)

| part | how it is tied to the skin | after the rebuild |
|---|---|---|
| lid lines | read from the skin's own relief (`zones.Face.lid_line`) | found again by themselves, 6.5 and 6.0 mm below the globes' middles; the furrows are 1.6 and 1.2 mm deep where they were 0.5 and 0.6 |
| eyeballs | measured in the photographs; drawn back if they reach the lids (`eyes.py`) | none drawn back; the corneas' tops lie 3.6 and 3.1 mm under the skin (5.6 and 4.9 before) |
| mouth | lip line and jaw measured on the surface (`mouth.prepare`) | measured again by itself; opens as before |
| face muscles, vessels, nerves | drawn between skin and bone on maps of both (`face_muscles.make_maps`) | drawn again on the new skin |
| eye sockets' lining | its walls ended 1.5 mm under the EXPORT's outline, which stands 1.65 mm outside his skin | **showed:** 83 and 162 triangles at the skin or outside it, by up to 2.4 and 3.2 mm: a dark line down from the right eye's inner corner. Now ended by the skin as drawn |
| fat | from the labels, in triangles of 4 to 5 mm | **showed:** 66 triangles at the skin or outside (up to 1.4 mm), yellow in both nostrils and in an ear; five more at the neck |
| left temporalis | from the CT, vertices drawn under the skin | **showed:** 166 triangles within 0.3 mm of the skin at the left temple |
| temporal bones | BodyParts3D's, fitted | 23 triangles at the skin of the ear canals |

The last three have one cause: the rules that keep a layer under the skin look at vertices, and the head's skin
now has openings and creases narrower than those layers' triangles. Cured by measuring points spread over every
triangle (`head_layers.faces_under_skin`), in the head and the neck.

## 5. What stays open

- The photographs end about a millimetre under the top of his head (section 2).
- The nostrils end in a ceiling a few millimetres in, and the ear canals where the gelatin did: the passages
  behind them are not modelled as open space.
- With the lids fully open a red sliver shows above each upper lid (the fold of the lid turning back). It was
  there before the head was read again; not looked into here.
- The head's colour from the photographs is sampled 1.2 to 3.6 mm under the skin. With the skin at his true
  surface those samples lie a millimetre and a half deeper in him than before. No change was seen in the
  pictures; not measured.
