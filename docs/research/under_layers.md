# The layers under the skin: a survey, the fat, and the muscles (2026-11-25)

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

