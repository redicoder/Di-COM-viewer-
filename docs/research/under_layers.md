# The layers under the skin: a survey, the fat, the muscles, the organs, and the skeleton (2026-11-25 and 26)

Research before the layers under the skin were worked on (product owner: "ok do what you recommend", on: bring
the layers under the skin up to the skin's standard). Marks as in the other reports: **O** read on our own data,
pictures or code, **K** from general knowledge.

## 1. What each layer looked like (O)

Looked at: the snapshot pictures of each layer (`build/snapshots/anatomy_<layer>*.png`) as built on 2026-11-25,
after the skin, the names and the check on what shows through the skin.

**Fat** (what a student sees first when the skin comes off):

- holes with the muscle showing red in them, ragged at the edges: down both shins, at the knees, on both
  forearms. Wherever the fat is thinner than a voxel or two the labels have none, and the mesh has a hole;
- the head faceted, in flat triangles of 4 to 5 mm, with a lump for an ear;
- the face one patchwork: the fat was cleared over each muscle of expression so that it showed in a window
  (`face_muscles.expose`), and the windows' edges were the triangles' saw teeth;
- two dark lines across both thighs (873 and 942 mm up), left by the check of the day before, which pressed the
  labels' fat in unevenly near the hips' passed-over photographs;
- good where the fat is thick: the trunk, the thighs.

**Muscles:** the right forearm's surface is perforated like lace (its surface is read from photographs that do
not hold all of the arm); the chest's and the belly's muscle mass is in pieces with cracks between them through
which the ribs show white; the hands have next to no muscle (the data has none). The legs (the University of
Denver's set), the neck and the face are good.

**Skeleton:** good. The right wrist's bones are dark where they crowd together (the shading baked into them).

**Organs:** good in the belly. The windpipe is a white lattice (a thin-walled label with holes), and the lungs'
surface is torn where the heart lies against it.

## 2. The order of work

1. The fat (this report, built the same day): it is the first layer under the skin and had the most wrong.
2. The muscles: the forearm's lace, the cracks in the trunk's mass.
3. The organs: the windpipe, the lungs at the heart.
4. The skeleton: the wrist's shading.

## 3. The fat: what was built, and what was tried (O)

The cure the feet and the hands already had (`feet.sock`, `hands.glove`) for all of him: **the fat's outer
surface is the skin's own outline, moved in** (`fat_shell.py`). 1.5 mm in the head, contoured at the outline's
0.66 mm in triangles of 1.4 mm; 1.8 mm below the head, contoured at the export's grid in triangles of 3 mm.
The labels' fat nearer the skin than 4 mm gives way to it; their triangles that lie wholly deeper stay as the
layer's inner side.

Five things were found on the way:

- **The outline is not the skin as drawn.** Where photographs were passed over, the skin's mesh may move 2.25 mm
  when it is relaxed. First the surface was sunk 1.5 mm more in those stretches: it had three grooves round him,
  at the chest, the hips and the knees. Now each of its vertices is kept 1.2 mm under the skin's MESH
  (`under_the_mesh`: against the nearest skin vertex of the same facing, so that an arm's skin does not push
  the trunk's fat), and there are no grooves.
- **The windows in the face ran together.** With a surface that covers everything, clearing it over every
  superficial muscle left one hole from the brow to the chin, with bone between the muscles' ribbons, scraps of
  the labels' fat at its edge and a gap one saw through. A face with the skin off is covered by its fat as the
  rest of him is (K); its muscles are the muscles layer's to show. The windows are gone; the eyes are open
  (`Body.eye_pits`), their rims drawn smooth (`smooth_rims`), and the red of the lips (below).
- **What lies under the fat must lie under THIS surface**, not only under the skin: the check on whole
  triangles (`head_layers.under_skin_everywhere`) asks 1.5 mm more of the muscles, the bones and the organs in
  the head, the hands and the feet, 1.8 mm more elsewhere. Measured coarsely and asked the trunk's depth of, a
  finger's bones were pressed thin where a hand lies in a band of the trunk: a band now leaves what lies in a
  hand's box to the hand's own, finer measure.
- **The mouth: no fat under the red of the lips.** The surface is made over the closed lips, as the outline has
  them. Every structure is given its share in the jaw's turn afterwards (`mouth.assign`), and what the open mouth
  would draw into sheets is taken out: 677 triangles of the new surface, along their edges. With the skin off
  the teeth showed in a ragged slit and scraps of the lips' muscles at both corners. First try: the fat parted
  along the lip line, as the skin is, and left whole. The mouth closed well, but the fat's edge then lay where
  the lips' inner sides are, and with the mouth open a yellow line ran round the lips, on the skin. What was
  built: the fat is open over the red of the lips (`fat_shell.lips`, `red_of_the_lips`): a lens along the lip
  line as the skin's red is laid out (6 mm over the line in the middle, 7.5 mm under it), and to the corners
  and 4 mm past them at least 1.5 mm over the line and 4 mm under it (the lower lip's inner side sinks 3 mm
  behind its edge). The red of a lip has no fat under it: the lips' muscle lies under their skin (K). With the
  skin off the lips are the orbicularis oris, red in the yellow face, the teeth between them.
- **It goes as the skin over it goes.** The fat's jaw weights were read at its own place, a millimetre or two
  under the skin. Where the weights change quickly that is enough for it to move otherwise than the skin: with
  the mouth open, fat came through the skin of the upper lip and at the jaw. Each vertex of the surface now
  takes the movement of the skin's triangle over it (`mouth.on_the_skin`: of the sixteen nearest triangles the
  nearest that looks the way the fat's surface does, so that in a fold the fold's other side is not taken; its
  corners read, at the lips on the vertex's own lip's side, and weighed by where the vertex lies under it: the
  skin moves straight between its corners). Tried first: reading at the skin's point over the vertex; that left
  a quarter more fat showing than reading the triangle does (1300 pixels against 1044 in the seven views).
  Two smaller faults came with the labels' fat that is kept as the inner side, which is in
  triangles of 10 to 25 mm: a triangle with one deep corner reached up to the skin (now only triangles that are
  wholly deeper than 4 mm are kept), and a rim vertex of one, drawn smooth with the opening's rim, went 20 mm
  and stood out under the nose (only the surface's own rims are drawn smooth).

Measured as the skin is (`ModelSnapshot.RunThrough`): every pixel of sixteen views asked which mesh is in front,
now with the skin off as well ("through the fat"), and once more with the skin on and THE MOUTH OPEN, from seven
sides ("through the skin, the mouth open": the teeth and the tongue are meant to be seen then and are counted
apart). See ARCHITECTURE for the counts of the build.

## 4. What stayed open after the fat

- Steps 2 to 4 of section 2.
- With the skin off the eyes stand uncovered in openings as wide as the orbits' rims: the lids are the skin's,
  and the fat has none of its own under them.
- The right ring finger's last bone shows at its tip through the fat (7 pixels in the hands' view). That finger
  lay bent otherwise in the CT than under the camera; its bones are already moved by the most allowed. To be
  turned at its joint when the skeleton is worked on.
- The fat has no thickness to look at yet where it is thin: its inner side is the labels' where they are
  wholly deeper than 4 mm, and nothing elsewhere. That matters when it is cut (the scalpel, later), not for the
  look.
- What still shows through the skin with the mouth wide open: 1044 pixels of fat and 3180 of other structures
  in seven close views of 1.44 million pixels each. The fat is mostly under the chin and along the jaw, where
  the opened jaw brings the chin's skin down on the neck's (probably the two skins pass through each other
  there, and the fat of one is seen through the other: not looked into yet). The rest is the lower lip's muscle
  along the inside of the lip and at his left corner (2516), the mandible behind the lower front teeth (260), a
  cheek muscle (162) and smaller things. It is asked for the first time in this build, so there is no earlier
  number to compare it with; while the fat's cure was built it was 6400. To be brought to nothing with the
  muscles.

## 5. The muscles: what the faults were, and what was built (O)

Product owner: "ok do what you recommend", on: the muscles next (the right forearm's lace, the cracks in the
chest and the belly, what shows in the opened mouth). Looked at before anything was changed: the build's log;
cross-sections of the trunk and of an arm as the muscles' surface is made from them (the photograph, the labels,
the coverage, and where the surface comes out); the mass's mesh itself; and a count, on the export's grid, of
where the labels have muscle and the photographs show no muscle colour within 2 mm.

- **The arms' "lace" was each arm's muscle in the model twice.** Section 1 took it for a surface in holes. The
  mass's mesh has no hole (not one open edge in 666 000 triangles). `fine_muscle.surfaces` gives the two arms'
  unnamed masses to the whole mass's surface (they are one flesh: `MASSES`), and `layers.build`, which meshes
  from its labels every muscle object that has no fine surface of its own, meshed them once more: a fine
  surface and a coarse one a millimetre apart at the most, each showing through the other in patches. The log
  said so (the rule on what lies under the skin moved vertices of "muscles of the right arm", a structure that
  should not have been there). They are meshed once now: 537 structures, not 539.
- **How near the skin a muscle may begin** is decided where its coverage is read, not afterwards. The coverage
  was cut 1.3 mm under the outline, within each photograph, and what came nearer the skin than the layers' rule
  allows (3.6 mm since the fat is the outline moved in) was pressed in afterwards, vertex by vertex: 12 271
  vertices of the mass in the last build of the fat's stage, each by its own lack, which leaves a relief of
  small pits wherever a muscle lies shallow over a stretch. Now the coverage ends 3.6 mm under the outline,
  measured in space on blocks of 2 x 2 x 2 voxels (`under_limit`, good to a third of a millimetre), between the
  feet and the head (those two keep their own rules), and the surface comes out there as one smooth level, as
  the fat's does. The rule afterwards moved 2601 vertices of the mass, 1845 of them in the feet.
- **Thin sheets.** A sheet of muscle a voxel or two thick (the muscles over the ribs, the flat muscles at the
  belly's side) blurs to less than half and is not contoured; the cross-section at 1380 mm shows the labels'
  band whole over the ribs and the surface broken along it. Where an object's own labels are thin (no cube of
  three voxels fits: `thin_parts`), every voxel of them that holds tissue counts as the object, whatever its
  colour.
- **The rectus sheath is an aponeurosis** and a labelled object of the muscles' layer. Read by colour, three
  quarters of it were left out (19 827 of its 26 532 voxels have no muscle colour within 2 mm: the count's
  largest item by far), and the belly's wall stood open along the midline, across the rectus and down its
  sides. Objects named in `fine_muscle.SHEETS` are taken as their labels have them, whole, a little tidier
  (`tidy_sheet`: gaps of a voxel closed, scraps under 60 voxels left out), in a colour of their own, a shade
  pinker and darker than bone. What shows now is the pattern a student knows: the linea alba, the tendinous
  intersections, the semilunar lines. It is as ragged at its edges as the labels are.
- **What the white in the chest is.** Seen from the front, 95 % of the trunk's wall under the fat is muscle by
  the labels. The white down the chest's middle is the sternum and the costal cartilages, which lie under the
  skin there (K); the slits under the pectoral's lower edge lie between muscle bodies, where the labels have
  fat and fascia and no muscle: left as they are.
- **The lips' muscle was pressed out of the lip.** Under the red of the lips the fat is open (section 3), yet the
  rule asked the lips' muscle to lie 2.5 mm under the skin, as under fat: a lip is a few millimetres through,
  and the muscle came out of its inner side (2516 pixels in the opened mouth's seven views). Under the red of
  the lips no more is asked than of the fat itself (`faces_under_skin(eased=...)`, from
  `fat_shell.red_of_the_lips`).

## 6. What stays open after the muscles

- The hands have next to no muscle (the labels have none there): they would have to be drawn, as the face's
  are. The arms' muscles are one unnamed mass each (no dataset of this body names them).
- In the opened mouth (see ARCHITECTURE for the last count): the lower lip's muscle is still seen along the
  inside of the lip, where the lip is thinner than the muscle as drawn; fat under the chin, where the opened
  jaw brings the chin's skin down on the neck's; the mandible behind the lower front teeth.
- The rectus sheath is ragged at its edges, as its labels are.
- Steps 3 and 4 of section 2 (the organs, the skeleton), and what section 4 lists.

## 7. The organs: what the faults were, and what was built (O)

Product owner: "ok do what you say", on: the organs next (the windpipe's lattice, the lungs torn at the heart).
Looked at before anything was changed: the organs' meshes (none has an open edge); the labels' objects of the
chest and the neck with their sizes; pictures of the chest with and without single structures; the labels in
cross-section at three heights beside the photograph; and counts of how thick each thin object is.

- **The windpipe's label is its wall only.** The labels' "trachea" (2839 voxels) is the C of cartilage round the
  front and the sides of the windpipe, one voxel thick: no cube of three voxels fits into any of it. The air
  inside is another object, "trachea lumen" (8107 voxels), which was not meshed, being no organ. Contoured by
  itself the wall was a white ladder of ring fragments. The windpipe is now the tube: the wall and what it
  encloses as one solid (9828 voxels), with the rings as ridges on it (`thin_organs.airways`).
- **The bronchi share that lumen.** It runs on into the two main bronchi, inside the labels' "bronchi". Each voxel
  of the lumen goes to the wall it lies nearer, so the windpipe ends where the bronchi begin and both are solid
  (the bronchi 4717 voxels, 3599 before).
- **The "lungs torn at the heart" were the heart's sac.** Section 1 was wrong about what it saw: the lungs' meshes
  are whole. The labels' "pericardium" (42 386 voxels) is two things: round the roots of the great vessels a
  thick mass (18 587 voxels lie in parts thicker than two voxels), and over the front of the heart a sheet one
  voxel thick, in holes. Behind and under the heart the labels have no sac at all: of the 32 094 voxels that
  touch the heart from outside, 7642 are pericardium and 13 542 are fat. Contoured as it was, the sheet lay over
  the heart as a pale rag with the heart red in its holes. Three ways were weighed. Closed up, the sac would
  hide the heart, and nothing in the app can yet open or take off a structure. With all its thick parts kept,
  pads of it lay down the heart's front as pale drips (tried, and looked at). What was built: the sac OPENED, as
  a prepared specimen has it (`thin_organs.opened`): its thick parts that do not lie in front of the heart and
  that reach the great vessels (2878 voxels: the mass round the roots of the aorta, the pulmonary trunk and the
  superior vena cava). The heart is seen whole between the lungs. What was done is said in the structure's
  info, and it is not marked as drawn: every voxel of it is the labels' own.
- **The pulmonary arteries were red and their trunk blue.** The colours go by the first key that fits a name, and
  "arter" came before "pulmonary trunk". They are their trunk's colour now, as an atlas has them (K: the
  pulmonary arteries carry the blood the veins of the body bring).

## 8. What stays open after the organs

- The whole sac, when it can be cut; and a way to take a structure off by touch ("hide"), which would let the
  closed sac be shown at once. Not built: it is a new function of the app and the product owner's to ask for.
- The heart's chambers lie inside the myocardium and are not seen.
- The larynx is the labels' few voxels (1669) and comes out as lumps.
- The organs' surfaces are contoured at the export's 1.32 x 2 mm, not at the photographs' 0.66 mm as the skin's,
  the fat's and the muscles' are.
- Step 4 of section 2 (the skeleton), and what sections 4 and 6 list.

## 9. The skeleton: what the faults were, and what was built (O)

Product owner: "ok do what you recommend", on: the skeleton next (the dark wrist bones, the ring finger's bone
at the fingertip), then a way to take a structure off. Looked at before anything was changed: the skeleton's
pictures; every bone of the arms and hands with its extent and the shading baked into it; and the right ring
finger's bones as BoneHub places them, after each step of their fitting, by their depth under the skin.

- **The wrists' shading was baked from another skeleton than the one shown.** The shading (how open the room
  over a surface is) is read from a blurred occupancy of the layer, and for the skeleton that was the LABELS'
  bone, while the bones shown are BoneHub's, which lie up to 8 mm beside the labels' (a wrist most of all). The
  small bones of the wrist were shaded in blotches that did not follow their shapes. The occupancy is now of
  the bones as shown: each of BoneHub's meshes filled on the labels' grid (`common.solid_of`), with the labels'
  cartilages and discs. In the picture the wrist's bones are light, with the dark in the clefts between them.
- **Two nameless bones in the hands were the labels' own fingers.** Bone of the labels that BoneHub has nothing
  near is kept, unnamed (the arms' bones above the elbows, the hyoid). Where a finger lay bent otherwise in the
  CT, the labels' piece of it is further than the 12 mm allowed from BoneHub's finger, and stood beside it as a
  second bone ("bone (not named) 39" and "40", at the two hands' fingers). BoneHub has every bone of a hand, so
  the labels' hand bones are no longer candidates; nor is what lies INSIDE one of BoneHub's bones (the middle
  of a thick bone is further than 12 mm from its own surface). 240 bones and cartilages now, 242 before.
- **The ring finger's bone at the fingertip: the thinning did it, not the bend alone.** Section 4 said the finger
  lay bent otherwise in the CT and its bones were "moved by the most allowed". Measured: after the move of the
  whole finger (3.7 mm) none of its vertices lies nearer the skin than 1 mm, and 558 of 5076 nearer than 2.5.
  Then what is too near is thinned towards the bones' long axis (`feet.to_axis`, made for a toe's short straight
  bones): ONE straight line through all three bones of a finger, which leaves a bent finger at its tip. Points
  moved onto it lay 6 mm OUTSIDE the skin at the right ring finger, and outside it at seven fingers of ten
  (pressed back in afterwards corner by corner, and squeezed). Tried first: turning each bone at its joint. It
  cannot be done: BoneHub has a finger's three bones as one mesh, grown together at the joints. What was built
  (`hands.following`, `hands.to_middle`): the mesh is taken in slices of 3 mm along its length; a slice that
  lies too near the skin is moved across the length, 6 mm at the most, to where the fewest of its vertices lie
  so near, never by a way that passes through the skin (the first version took the right ring finger's tip over
  into the little finger); the slices' moves are evened out along the length; and what is still too near goes
  towards the mesh's own middle line there, not a straight one. In the build the ten fingers' bones were bent by
  0.8 to 5.0 mm, none of their vertices lies nearer the skin than 2.58 mm, and the ring finger's bone no longer
  shows through the fat (11 pixels before, none now).

## 10. What stays open after the skeleton

- The upper arm bones end in a slanting point above the elbows, and the elbows' bones are missing: BoneHub's
  arm bones stop where the CT's picture did, and the photographs do not hold the arms' outer sides there
  either. It would have to be drawn. (Half wrong, and not looked at when it was written: the photographs hold
  43 mm more of each arm than the CT, and the elbow's bone is in them. Section 12.)
- Nameless bone in the head (two pieces of the labels' bone inside the skull), to be looked at with the skull.
- The rest of BoneHub's skeleton is still the CT's size (3 % small in the plane), as the model's notes say.
- A way to take a structure off by touch ("hide"): next.

## 11. The opened mouth: what still shows, where, and what was tried (O)

Product owner: "yes do what you recommend", on: the wide-open mouth, the one check that is not clean (3138 pixels
in seven close views). It is NOT cured. This is what was found, with a tool made for it
(`ModelSnapshot.RunThroughOpen`: of each of the seven views a picture in flat colours, the skin's layer grey and
whatever shows through it loud; the same views with the mouth shut; the same with only the skin's layer drawn;
and for every structure that shows, which of the skin's own surfaces it stands before).

- **It is the pose, not the view.** With the mouth SHUT the seven views are clean: 0 pixels, the nostrils seen
  from below among them. And the skin's layer alone, with the mouth open, has no gap anywhere. So whatever shows
  stands BEFORE one of the skin's surfaces, and only with the mouth open: it and the skin have moved apart.
- **Where it is.** Sections 4 and 6 named the places before they were looked at, and wrongly ("along the inside
  of the lip", "under the chin"). The pictures: the lower lip's muscle (1430 pixels) is in slivers on the cheek
  just beside both corners of the mouth, most at his left one; the fat (1044) is one sliver on the neck under
  his right jaw (seen in three views), two thin lines on the chin, a sliver at the left corner, and in both
  nostrils seen from below; the maxilla and a levator of the lip (190) are in the nostrils too, with the upper
  lip lifted; the mandible (260) stands before the lower gum; the left buccinator (160) before the mouth's wall.
- **Tried, and taken back: what lies near the skin takes the skin's movement.** Three ways, each worse than what
  there was: (1) the weights' field read at the skin's triangle over a vertex: 3863 pixels (near the lower lip
  the field is not what the skin has: the skin knows which lip it is of; the lower lip's depressors came out);
  (2) the built skin's own movement at its nearest triangle: 5088 (the lips' own muscles, 3022 and 378);
  (3) the same from the skin's outer surface only, without the lips' inner sides: 6655 (3852 and 927). The fat's
  1044 pixels were the same in all three, to the pixel: nothing of this touches them.
- **Tried: the lip ring's ends cut 8 mm short of the corners** (in the cache only). The lower lip's muscle fell
  to 794 pixels, and the muscles that lie behind it showed in its place (the depressors of the mouth's angle
  347, the buccinator 127): 2969 in all. So it is not the lip's muscle that is wrong at the corners.
- **What it is, then.** At the mouth's corners the skin itself comes in past the flesh under it when the mouth
  opens: the corner is a web of skin drawn straight between the upper lip, which is lifted, and the lower, which
  goes down with the jaw (`mouth.skin_weights`, the sheet's rim, where both sides move alike). Whatever lies
  under that web shows through it; take one muscle away and the next one shows.

What it would take (a piece of work on the mouth, not a clean-up): the corner of the mouth in the skin's own
movement, so that the cheek's skin beside the corner is drawn out over the flesh and not through it; the nostrils'
floor under a lifted lip; the lower gum against the mandible (a misfit at rest, which only the opened mouth lets
one see); the single slivers of fat on the neck and the chin, which were not run down.

## 12. The elbows: read from the photographs, not drawn (O)

Product owner: "ok do what you recommend", on: leaving the mouth as it is and drawing the missing elbows next.
Looked at before anything was drawn: each arm's three bones as BoneHub places them, level by level; the arm's
outline in the fine skin there; and the photographs' own cross-sections through both elbows.

- **What is missing, measured.** The CT's picture is 478 mm wide and he is wider than that at the elbows.
  BoneHub's bones are from the CT, so its edge cuts them: the humerus LENGTHWISE over 84 mm at his right
  (1316 to 1400 mm up from his soles, at x = 49.9 mm) and 76 mm at his left (1335 to 1411, x = 525.2), which is
  the "slanting point" of section 10: a blade, not an end; the radius over 24 and 28 mm and the ulna over 44
  and 40 mm at their upper ends. The elbow itself lies wholly beyond that edge.
- **The photographs hold it.** Section 10 said they do not. Their frame cuts each arm 43 mm further out than the
  CT (at x = 7 and 570 mm, where the arm's skin ends in a flat face), and in every photograph through the
  elbow the bone is there: pale, deep in the dark muscle. The labels have no bone beyond the CT's edge (the
  pale tissue of the arms is "fat" to them), which is why the model had none.
- **So it is read, not drawn** (`anatomy_model/elbows.py`). Beyond the CT's edge, bone is the tissue that is not
  muscle-red (`fine_muscle`'s coverage under 0.35), deeper than 6 mm under the skin (the fat under the skin is
  pale too), within 36 mm of the bones' own lines (the humerus's from above and the ulna's and the radius's
  from below, fitted to the stretches BoneHub has whole and drawn on to where they meet: the pale fat of the
  flank lies beyond the CT's edge as well, where the arm lies against the trunk); without what is thinner than
  a film (2.6 mm: the fascia between the muscles); in pieces of 1.5 cm3 and more, and of a tenth of the largest
  and more (a scrap of 2.6 cm3 lay beside the left elbow's 125); and with what a photograph's bone encloses
  (the marrow is red). It laps 1 mm over the CT's edge, onto BoneHub's bones.
- **The two halves did not meet, and why.** The first build had the read bone beside BoneHub's blade of the
  humerus with a slit between them along 80 mm, most at his left. Cross-sections (the photograph, BoneHub's
  section, the read bone) showed it: BoneHub's arm bones do not lie where the photographs have the same bones.
  Measured on the whole stretches next to the elbows, photograph by photograph (the pale, deep piece lying on
  BoneHub's section; its middle against the section's): the right humerus 2.4 to 4.3 mm beside, the right ulna
  3.2 to 5.9, the right radius 4.9 to 6.6, the left humerus 4.0 to 4.8, the left ulna 3.4 to 6.9, the left
  radius 2.8 to 4.6; steadily along each bone, each arm in its own direction (the arm lay a little otherwise in
  the scanner, and the skeleton is still the CT's size). Nearer the shoulder the measure fails: the bone runs
  together with the joint's pale tissue there.
- **BoneHub's arm bones are moved onto the photographs' bone at the elbow** (`onto_photographs`, `bone_at`,
  `turned`). Of the three photographs nearest a bone's cut in which the bone is found, the middle one of the
  distances is taken; the bone is moved by it across its length, wholly there and on towards the elbow, by
  less and less towards its far end (the shoulder; the wrist), which stays where it is: as if turned about its
  far joint by a degree or two. Moved: the right humerus 3.8 mm, ulna 5.4, radius 6.1; the left humerus 4.2,
  ulna 3.5, radius 2.8. What is left in the measured photographs afterwards: 2 to 5 mm at the most, towards
  the far ends, which are not moved at all. In cross-section the moved bone lies on the photograph's bone and
  the read half completes it; in the pictures the slit is gone. (The left radius has no vertex left that
  has to be pressed in under the skin afterwards: 14 before.)
- **Spurs.** A peg and a ragged tail of pale tissue, 3 mm thick, stood on the left elbow's point. Of the bone
  found, what is thinner than 4 mm is taken off (an opening of the filled mass, not of the pale tissue: a
  shaft's wall is thinner than that round its marrow).
- **What came out.** His right elbow: 105 cm3 in one piece, from 1193 to 1394 mm up; his left: 123 cm3 in one
  piece, 1183 to 1407. Each a closed mesh of 16 000 triangles. In the pictures the humerus goes on down and
  widens into its two knobs, the point of the elbow (the olecranon) stands behind them, and the forearm's two
  bones leave it downwards to meet BoneHub's. The skeleton has 242 structures now (240 before).
- **What it is called.** ONE mass for each elbow: the lower end of the humerus and the upper ends of the ulna and
  the radius, with their cartilage and with what tendon lies on them. Where one bone ends and the next begins
  the photographs' colour does not say, and it is not guessed: a wrong name on the olecranon would be worse
  than none. "Bones of the right elbow", Ossa cubiti dextri, Ossa del gomito destro; the card says it is read
  from the photographs (not drawn), and a note says why it is one mass.
- **What it is not.** (1) Not the whole elbow: it ends where the photographs do, flat, 6 mm inside the arm's flat
  face; the outermost of the outer knob may be missing, and the arm's SKIN there is still cut flat by the
  photographs' frame, as before. (2) Not three bones: see above. (3) Not bone alone: pale is not only bone, and
  cartilage and tendon on the bone are in it. (4) Not seamless: BoneHub's humerus is a little thicker than
  the bone read (26 against 23 mm across), and where its blade lies on the read bone a low ridge runs along
  it; from behind, a notch shows at his right where the blade's point ends. (5) The arm's bones are moved at
  the elbow only: at the shoulder and the wrist they are where the CT has them, so between the two a bone is
  up to its whole move away from one or the other truth; the whole skeleton set by the photographs would be
  the cure, and this section's measure (`bone_at`) is a way to it for the limbs' shafts. (6) `frame` takes a
  humerus for cut when it lies along its outermost plane for 40 mm or more (his: 84 and 76; the bones the
  edge does not cut: 28 at the most): a rule made on this one body.
- **Measured** (`RunThrough`): through the skin 0 pixels in sixteen views; through the fat 208 017 pixels, the
  same as before to the pixel (its openings); with the mouth open 3138 in seven views, as before. Tests:
  `tests/test_elbows.py` (a made-up arm: pale bone with red marrow in red muscle under pale fat, a film of
  fascia, a scrap, a spur; made-up arm bones cut by a plane; bones lying 5 mm beside the photographs' bone).
