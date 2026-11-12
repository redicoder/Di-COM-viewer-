# What our own data holds for the head and face (Visible Human Male)

Inspection only; nothing in the repository was changed. Scripts, intermediate arrays and pictures are in `build/research/head_data/`. Education-only material.

Conventions used here
- Photographs: 1216 x 2048 px, nominal 0.33 mm, 1 mm apart, head folder holds slices 1001..1260. After `read_photo` rows run front to back and columns grow towards patient left (so the left of every picture is the patient's right).
- `backend/out/photo_head/body.raw`: y index 0 = slice 1225, y index 224 = slice 1001 (slice = 1225 - y); crop of the photographs rows 240..972, cols 732..1296.
- Scale: all in-plane millimetres below are NOMINAL (0.33 mm per pixel). `ct_registration.json` says CT mm = 0.968 x photo mm; my direct outline comparison at slice 1097 gives 0.988 (CT outline 157.1 x 210.4 mm against 159.1 x 212.9 mm), but the CT outline includes a thin wrap line outside the skin. True size is 1..3 % below nominal. Slice direction (1 mm) is not affected.
- The head CT is 0.527 mm per pixel (not 0.9375), 1 mm slices, slices 1006..1300 present.

## 1. What the 0.33 mm photographs really resolve

| Region | Picture | What is resolved | What is not |
|---|---|---|---|
| Eyes | a_eyes_slice1109_x5.png, sel_eyes.png, sag_eyes_cols918_1132_x4.png | Eyeballs largest at slices 1108..1110, about 23 mm across. Lens sharp (yellow-white, about 9 x 4 mm). Dark vitreous, sclera as a thin pale ring, cornea plus anterior chamber as a thin dark crescent in front of the lens. Lids closed: a skin and muscle band 2.5..3 mm thick lies directly on the cornea. In the sagittal reconstruction the lid fissure is a notch in the outline at slice 1112..1113 (right eye) and 1114..1115 (left eye). | Iris and pupil are not separable from the dark chamber. Upper and lower lid are not separate layers; the fissure is 0..1 slice high, no gelatin between the lids or under them. No individual lashes or brow hairs. |
| Nose | b_nose_slices1148_1152_x3.png, sel_nose.png | Alar cartilages (white, about 0.5 mm) and septal cartilage; columella; both nostrils and the vestibule are filled with blue gelatin, so the nostril openings are true holes in the tissue (slices about 1148..1156). Nasal cavity and all sinuses are gelatin-filled (blue) and therefore easy to segment. | Skin pores. |
| Lips, teeth, tongue | c_lips_teeth_slices1178_1184_x3.png, c_teeth_upper1172_lower1194_x3.png, sel_lips.png, sag_lips_cols1016_1028_x3.png | Every tooth crown and root with its pulp; gaps between neighbouring crowns 1..2 px. Vermilion seen as a pinker band (slice 1184 cuts the lip tangentially). Tongue with its muscle fibres fills the oral cavity. Blue gelatin in the vestibule in front of the incisors and in the cheek pouches. Restorations visible (white in an upper molar at 1178, dark in a lower left molar at 1184). | A clean open gap between the lips (they touch). |
| Ear | sel_ear_left.png, d_ear_left_slices1125_1135_x4.png | Auricular cartilage as a crisp white 1 mm band; helix, antihelix, concha and the gap behind the ear (gelatin) are resolved in every slice; about 60 slices through each ear. | Folds thinner than 1 mm between slices. |
| Scalp and beard | e_scalp_side1040_occiput1110_x5.png, e_stubble_upper_lip_slice1160_x8.png, front_colour_033.png | The man is shaved. No hair projects into the gelatin anywhere. Hair follicles show as regular dark oblique streaks in the scalp dermis and as 1..2 px dark shafts inside the upper lip skin. In the surface colour the moustache and beard area shows as grey stubble dots; the brow area is only a faint darker band. | Hair shafts above the skin, hair length, hairline shape as strands. |
| Neck | sel_neck.png, f_neck_slice1236.png | Skin, platysma, fat, larynx; shoulders and trapezius already flare at slice 1221. (f_neck_front_skin_slice1236_x6.png is mis-framed: it shows the muscles under the chin, with beard follicles in the dermis at its corners.) | A free neck (see section 6). |
| Skin colour | front_colour_033.png | Pale yellow-tan; brown discolouration around both eyes; lips dull brown-red; no frost crust. A teal halo 3..5 px wide surrounds the skin wherever the surface slopes away under the translucent gelatin (deeper skin shining through). | Living skin tone. |

## 2. The outer surface at full resolution

- In-slice boundary noise of the front outline (deviation from a 2 mm smooth curve, robust sigma, slices 1050..1225): 0.54 px = 0.18 mm at 0.33 mm; 0.40 px = 0.26 mm at 0.66 mm. Picture: boundary_033_vs_066_slice1184.png (top row with the mask edge in red, 0.33 mm left, 0.66 mm right). The 0.33 mm edge is one-pixel jagged but follows the skin; it sits inside the teal halo.
- Slice-to-slice registration jitter, face slices 1090..1200 (outline against its smoothed neighbours, and second differences): front-back sigma 0.21..0.25 px (0.07..0.08 mm), 95 % below 0.45 px, worst 1.1 px at slice 1112 (also 1111: 0.6); sideways sigma 0.08..0.10 px, worst 0.45 px. The round fiducial disc in the block moves 0.13 px (columns) and 0.22 px (rows) around its trend. The photographs are registered to better than one pixel; no de-jitter step is needed beyond a light correction.
- relief_raw033_vs_export066.png: shaded front surface from the raw 0.33 x 1 mm masks (left) against the present 0.66 mm export (right). relief_033_dejittered_and_smoothed.png: the same at 0.33 mm after the per-slice offset is removed (left) and after a light smooth of 0.7 slice x 0.5 mm (right).
- Result: a 0.33 x 0.33 x 1 mm surface shows the closed lid line, the upper lid crease, the folds under the eyes, both nostrils, the philtrum, the lip line and the mouth corners, the nasolabial folds. The 0.66 mm export shows the same features blurred and terraced; the present mesh (2.3..2.5 mm edges) loses them. Ear folds are resolved in the slices (the relief here is a front height field and does not show the ears).
- Defect to remove: an oval seam line runs round the face at constant depth (forehead, temples, cheeks, jaw). It is visible in the relief and in the colour and looks like the waterline between two gelatin pours.
- Limit: the slice step is 1 mm, so horizontal features (lid line, lip line) are only 0..2 slices high.

## 3. State of the mouth, eyes, nose

- Eyes: closed. Lid fissure 0..1 slice, no gelatin between the lids or on the cornea. Fissure at about slice 1110..1113 (right) and 1114..1115 (left).
- Lips: closed and touching over slices about 1183..1186 at the midline; 0 slices of clear gelatin between them (a tinted band 3..4 slices thick marks the contact). In 3D there is a groove, not a gap.
- Teeth: not clenched. Upper incisor edges at about slice 1178..1180, lower incisor edges at about 1188..1190: an opening of 8..10 mm, filled by the tongue tip and by gelatin.
- Tongue: fills the oral cavity, lies against the palate, tip between the incisors up to the back of the lips.
- Foreign content: blue gelatin in the oral vestibule (slices about 1179..1187), in the cheek pouches, in both nostrils, the nasal cavity, all sinuses and the pharynx. No tube seen in mouth or nose.

## 4. The head CT

Pictures: ct_overview_6slices.png, ct_orbit1109_sinus1128_vault1040_x4.png, ct_teeth_mip_upper_lower_x5.png, ct_teeth_slices_x5.png.
- Resolves what the photographs do not: bone against everything else without colour ambiguity; the thin orbital walls and ethmoid cells; the sinuses as AIR (the CT was made before embedding, the photographs show them full of gelatin); the diploe of the vault; enamel against dentine; metal.
- Does not resolve: skull sutures (only a faint notch at slice 1040), skin detail (a wrap line lies on the skin), the lens only faintly.
- Dental state: about 14 teeth in the upper arch and 13..14 in the lower (no clear third molars); exact count not certain. Large metal restorations with streak artefacts (3071 HU, saturated) in slices 1173..1188: upper right molar region (two teeth), upper left (two blobs), lower left molar (large), one small metal point in a lower right molar. The streaks spoil CT slices 1174..1187 around the crowns; the photographs are the better source for the crowns there.
- The mandible is last seen at CT slice 1233; in the photographs the bone arch is already gone at 1232. CT and photograph numbering may differ by a few slices at the chin.

## 5. The present skin mesh of the head

Pictures: mesh_sheet_views.png (face, head_top, face_right, face_left), mesh_sheet_closeups.png (eyes, mouth, left profile, left ear); single files mesh_face.png, mesh_face_left.png, mesh_face_right.png, mesh_head_top.png, mesh_eyes_closeup.png, mesh_mouth_closeup.png, mesh_profile_left.png, mesh_ear_left_closeup.png.
Head part of `skin`: 40 269 vertices, 80 061 faces, median edge 2.3 mm.
Defects against the photographs:
1. No lid line, no lid crease, no eyeball bulge under the lids: the eyes are two shallow brown smears.
2. Nostrils are shallow dimples, not holes; the alar groove is gone.
3. No lip line and no mouth corners: the lips are a pink tint on a smooth bulge.
4. Ears are smooth lumps with one hole; helix, antihelix, concha and the gap behind the ear are fused to the head.
5. Colour is flat tints with straight polygon borders (scalp cap, beard zone, lip band); the photographed colour (brown eye surround, stubble dots, lip colour) is not used at this detail.
6. Concentric terrace rings on the vertex; a rough band round the neck.
7. The philtrum, nasolabial folds and under-eye folds present in the 0.33 mm surface are smoothed away.
8. The heavy jowls and the pad under the chin are reproduced faithfully, so the face reads wider and heavier than a living face.
9. Hair, beard, brow and lash strand structures exist in the cache (252 384, 38 372, 13 776 and 5 040 vertices) but are not visible in the software render.

## 6. Measurements

Nominal 0.33 mm pixels; the second column is x 0.968 (CT registration). Vertical values are slice counts (1 mm) and are not scaled.

| Measure | Nominal mm | x 0.968 | How |
|---|---|---|---|
| Head length (glabella to back of head, midline) | 213.5 | 206.7 | front 102.6 mm at slices 1089..1097, back 316.1 mm at 1105 |
| Head breadth (above the ears, slice about 1100) | 159.4 | 154.3 | outline width |
| Head height, vertex to bony menton | about 235 | - | vertex extrapolated to slice 998..999 (photographs start at 1001, section already 27 x 42 mm); mandible ends at CT slice 1233 |
| Vertex to the lowest point of the pad under the chin | about 252 | - | profile drops back at slice 1250..1252 |
| Face height, nasion to menton | about 132 | - | nasion slice 1101, menton 1233 (plus or minus 4) |
| Nasion to lip line | 84 | - | lip contact at slice 1185 |
| Bizygomatic breadth (soft tissue, in front of the ears, slices 1109..1133) | 157 | 152 | outline width, rows 300..600 |
| Lower face breadth (cheeks and jowls, slices 1169..1177) | 166 | 160 | wider than the bizygomatic breadth |
| Interpupillary distance, body.json eye centres | 72.5 | 70.2 | 3D distance 72.6; right eye 3.3 mm higher than the left |
| Same from slice 1109 (lens centres / globe centres) | 71.6 / 70.3 | 69.3 / 68.0 | columns 916 and 1133 / 919 and 1132 |
| Nose length, nasion to subnasale | 55 | - | slices 1101 to 1156 |
| Nasion to nose tip | 49 | 48 | 44 mm down, 21 mm forward (tip at slice 1145) |
| Nose protrusion in front of the upper lip base | 14..17 | 13.5..16.5 | profile 83.2 mm at the tip, 97..100 mm at subnasale |
| Nose width at the alae | 37..39 | 36..38 | slice 1152 and front_colour_033.png |
| Mouth width (lip line ends) | about 55 | 53 | front_colour_033.png, plus or minus 3 |
| Ear length | about 60 each | - | right ear slices about 1104..1164, left about 1116..1176, plus or minus 3 |
| Ear protrusion from the head | 5..9 | - | outline step at the ears |
| Neck | no free neck | - | smallest closed outline between jaw and shoulders 560 mm (542) at slices 1213..1217, which still cuts the chin; front neck width 139..140 mm at slices 1233..1265; the shoulders flare from slice 1221 |

Distortion compared with a living, upright face
- Head rolled about 3..4 degrees: the right eye is 3.3 mm and the right ear about 12 mm higher than the left; the midline shifts from column 1028 at the nose to 1017 at the mouth (3.6 mm).
- Supine and embedded: cheeks and jowls have slid sideways and back (lower face 166 mm, wider than the 157 mm cheekbone breadth); a fat pad hangs 15..20 mm below the mandible towards the chest; shoulders are pushed up to the jaw.
- Back of the head rests flat: the back profile is constant within 1 mm over slices 1093..1113.
- Ears lie close to the head (5..9 mm).
- Lids and the tissue under the eyes look puffy; jaw dropped 8..10 mm behind closed lips, which lengthens the face.
- The oval gelatin seam line crosses forehead, temples and cheeks.

## 7. Conclusion: what our data can give for the face

| Feature | In our data at 0.33 mm? | Best source | Must come from a template or be generated |
|---|---|---|---|
| Overall head and face shape, proportions | Yes, sub-millimetre (jitter 0.07 mm, edge noise 0.18 mm) | photographs, 0.33 x 0.33 x 1 mm surface | correction of the supine sag, roll and jaw drop if a living look is wanted |
| Closed eyelids, lid line, lid crease, under-eye folds | Yes as surface relief (fissure 0..1 slice) | 0.33 mm surface | open eyes, lid margin thickness, lashes |
| Eyeball position and size, lens | Yes (23 mm globes, lens sharp) | photographs | iris, pupil, cornea shape |
| Eyebrows | Only a faint darker band in the colour | surface colour | brow hairs |
| Nose shape, alae, columella, nostril openings | Yes (nostrils are gelatin-filled holes; cartilages visible) | photographs | pores |
| Lips: outline, vermilion colour, lip line, mouth corners | Yes as a groove and as colour; lips touch | 0.33 mm surface plus surface colour | a parted mouth, fine lip wrinkles |
| Teeth | Yes, every crown and root; about 27..28 teeth; metal restorations | photographs for crowns, CT for enamel and bone (CT streaked in slices 1174..1187) | occlusion in a closed bite (jaw is open 8..10 mm) |
| Tongue, palate, oral cavity | Yes | photographs | - |
| Ears: helix, antihelix, concha, cartilage | Yes in every slice (about 60 slices each) | photographs, 0.33 mm masks with the gelatin behind the ear | folds finer than 1 mm; ears pressed to the head |
| Scalp hair, beard, lashes as strands | No (shaved; follicles and stubble dots only) | zone maps from the surface colour | all strands |
| Skin colour map (discolouration, stubble shadow, lips) | Yes at 0.33 x 1 mm | surface colour sampled 1..2 mm under the edge | living skin tone, pores, fine wrinkles |
| Skull, orbit walls, sinuses as air, mandible | Yes | CT at 0.527 mm | sutures |
| Neck as a free cylinder | No (shoulders raised to the jaw) | - | neck shape if the pose is changed |

## What could not be determined
- The exact tooth count and which teeth are missing (about 14 upper, 13..14 lower).
- Iris and pupil; whether any lash or brow hair is preserved.
- The true in-plane scale to better than 1..3 % (0.968 from the registration file against 0.988 from my outline check).
- The bony menton to better than plus or minus 4 slices, and whether CT and photograph slice numbers agree exactly at the chin.
- A neck circumference in the usual sense.
- What the oval seam line physically is (gelatin pour line is my reading).
- Whether `lid_line_y_m` in body.json is right: by my index conversion it lies at slices about 1105.7 and 1109, 4..6 mm above the fissures I see (1110..1113 and 1114..1115); my conversion of the export origin may be off, so this needs a check in the app.
- Not looked at one by one: d_ear_left_slices1125_1135_x4.png, f_neck_slice1236.png, ov_sagittal_x100.png, ov_sagittal_x180.png and the single mesh_*.png files (same content seen in sel_ear_left.png, sel_neck.png and the two mesh sheets).

## Files
Scripts: hd.py, s1_overview.py, s2_sheets.py, s3_sheets.py, s4_crops.py, s5_pass.py, s6_analyse.py, s7_ct.py, s8_mesh.py. Arrays: pass.npz (per-slice outlines, sagittal planes), front_depth_mm.npy, front_colour_033.npy, ct_index.json.
