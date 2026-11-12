# Reference palette measured from photographs

Reference colours for the anatomy model palette, measured from real photographs (Wikimedia Commons). Method: each photograph was looked at, a rectangle containing only the tissue (no specular highlight, no deep shadow) was chosen on a gridded view, and the median sRGB (0-255) of that rectangle recorded. The table gives, per tissue, the median over photographs and the spread. Education-only colour reference. All measurements with rectangles are in palette/palette.csv; the cropped rectangles are in palette/crops_final.jpg.

## Final table

| Tissue | Median sRGB | Hex | Spread (min-max per channel over photos; n) | Surface look | Sources |
|---|---|---|---|---|---|
| 01 skin abdomen | 195,168,154 | #c3a89a | r 138-244, g 118-226, b 108-199 (n=4) | Matte to faint satin sheen; strong subsurface scattering (red bleed at shadow edges); pinker over sternum, nipples and flanks, yellower over abdomen; fine pores, sparse to dense hair, small naevi and red spots. | [1](https://commons.wikimedia.org/wiki/File:Bodymorphproj_DanielMMS_modB001_20211025_posA01.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Bodymorphproj_mkg_modA002_20070407_posA01.jpg) ; [3](https://commons.wikimedia.org/wiki/File:A_nude_Torso_of_a_Man.JPG) ; [4](https://commons.wikimedia.org/wiki/File:Central_Obesity_008.jpg) |
| 01 skin chest | 204,168,143 | #cca88f | r 166-229, g 131-204, b 109-192 (n=3) | Matte to faint satin sheen; strong subsurface scattering (red bleed at shadow edges); pinker over sternum, nipples and flanks, yellower over abdomen; fine pores, sparse to dense hair, small naevi and red spots. | [1](https://commons.wikimedia.org/wiki/File:Bodymorphproj_DanielMMS_modB001_20211025_posA01.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Bodymorphproj_mkg_modA002_20070407_posA01.jpg) ; [3](https://commons.wikimedia.org/wiki/File:Median_Sternotomy_Example.jpg) |
| 02 lips lower | 166,76,93 | #a64c5d | r 153-168, g 68-92, b 68-106 (n=3) | Vermilion is semi-matte and dry with fine vertical creases; darker and more saturated at the wet line, paler toward the skin border; lower lip lighter and pinker than the upper. | [1](https://commons.wikimedia.org/wiki/File:Close_up_man_lips.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Lips_man_110.jpg) ; [3](https://commons.wikimedia.org/wiki/File:Luca_Nowak_portrait.jpg) |
| 02 lips upper | 138,64,75 | #8a404b | one photo; IQR r 123-151, g 52-75, b 62-87 | Vermilion is semi-matte and dry with fine vertical creases; darker and more saturated at the wet line, paler toward the skin border; lower lip lighter and pinker than the upper. | [1](https://commons.wikimedia.org/wiki/File:Close_up_man_lips.jpg) |
| 02r skin of chin | 174,142,132 | #ae8e84 | r 165-184, g 134-150, b 131-133 (n=2) | Vermilion is semi-matte and dry with fine vertical creases; darker and more saturated at the wet line, paler toward the skin border; lower lip lighter and pinker than the upper. | [1](https://commons.wikimedia.org/wiki/File:Lips_man_110.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Close_up_man_lips.jpg) |
| 03 areola male | 124,87,71 | #7c5747 | r 104-131, g 59-123, b 50-125 (n=3) | Matte, slightly wrinkled disc with small pale bumps (Montgomery tubercles); brown-pink, darkest at the nipple base, soft blurred edge into chest skin; hair around the rim. | [1](https://commons.wikimedia.org/wiki/File:Male_Areola.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Bodymorphproj_mkg_modA002_20070407_posA01.jpg) ; [3](https://commons.wikimedia.org/wiki/File:Median_Sternotomy_Example.jpg) |
| 03 nipple male | 122,117,121 | #7a7579 | one photo; IQR r 117-128, g 109-125, b 112-130 | Matte, slightly wrinkled disc with small pale bumps (Montgomery tubercles); brown-pink, darkest at the nipple base, soft blurred edge into chest skin; hair around the rim. | [1](https://commons.wikimedia.org/wiki/File:Male_Areola.jpg) |
| 03r skin beside areola | 166,152,143 | #a6988f | r 149-204, g 131-168, b 109-149 (n=3) | Matte, slightly wrinkled disc with small pale bumps (Montgomery tubercles); brown-pink, darkest at the nipple base, soft blurred edge into chest skin; hair around the rim. | [1](https://commons.wikimedia.org/wiki/File:Male_Areola.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Bodymorphproj_mkg_modA002_20070407_posA01.jpg) ; [3](https://commons.wikimedia.org/wiki/File:Median_Sternotomy_Example.jpg) |
| 04 lunula | 214,200,204 | #d6c8cc | r 174-253, g 158-241, b 170-239 (n=2) | Hard clear plate with a strong narrow gloss stripe along the finger axis and faint longitudinal ridges; colour comes from the nail bed (pink), lunula is an opaque pale half-moon at the base, free edge off-white. | [1](https://commons.wikimedia.org/wiki/File:Fingernail_label_%28enwiki%29.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Thumb-nail_and_hand.jpeg) |
| 04 nail plate over nail bed | 180,122,130 | #b47a82 | r 180-181, g 102-141, b 113-147 (n=2) | Hard clear plate with a strong narrow gloss stripe along the finger axis and faint longitudinal ridges; colour comes from the nail bed (pink), lunula is an opaque pale half-moon at the base, free edge off-white. | [1](https://commons.wikimedia.org/wiki/File:Lunula_07.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Thumb-nail_and_hand.jpeg) |
| 05 palm | 220,165,124 | #dca57c | r 211-228, g 157-173, b 119-129 (n=2) | Matte, hairless, thick skin with crease lines and fine ridges; pinker/redder on the thenar and hypothenar pads and fingertips, yellower in the hollow; creases darker and redder. | [1](https://commons.wikimedia.org/wiki/File:Open_Palm_of_the_Left_Hand%2C_Fingers.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Right_Hand_Palm.png) |
| 06 subcutaneous fat | 214,120,39 | #d67827 | r 212-216, g 112-127, b 36-42 (n=2) | Wet, glistening lobules 3-10 mm across separated by thin white fibrous septa, small red vessels and blood staining between lobules; butter-yellow to orange, translucent at edges. | [1](https://commons.wikimedia.org/wiki/File:Electrocautery_during_abdominoplasty.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Rectus_diastasis_repair_during_abdominoplasty.jpg) |
| 06b omental fat | 203,148,74 | #cb944a | r 167-239, g 106-190, b 73-75 (n=2) | Wet, glistening lobules 3-10 mm across separated by thin white fibrous septa, small red vessels and blood staining between lobules; butter-yellow to orange, translucent at edges. | [1](https://commons.wikimedia.org/wiki/File:Gallenblase.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Splenose.jpg) |
| 07 muscle fresh | 180,72,72 | #b44848 | r 142-218, g 31-113, b 32-111 (n=2) | Wet satin gloss, parallel fibre bundles running along the line of pull, covered by thin translucent fascia that greys the colour; deep red to red-brown, darker when blood-filled, paler pink when drained. | [1](https://commons.wikimedia.org/wiki/File:Intraoperative_fibularis_longus_tendon.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Ruptured_achilles_tendon.jpg) |
| 08 aponeurosis | 199,153,77 | #c7994d | one photo; IQR r 177-230, g 124-196, b 38-124 | Pearly white to cream, strongly anisotropic silky sheen along tightly parallel fibres; aponeurosis is a flat sheet of the same with crossing fibre layers, a little muscle red or fat yellow showing through. | [1](https://commons.wikimedia.org/wiki/File:Electrocautery_during_abdominoplasty.jpg) |
| 08 tendon | 220,199,196 | #dcc7c4 | r 206-235, g 199-199, b 192-199 (n=2) | Pearly white to cream, strongly anisotropic silky sheen along tightly parallel fibres; aponeurosis is a flat sheet of the same with crossing fibre layers, a little muscle red or fat yellow showing through. | [1](https://commons.wikimedia.org/wiki/File:Achilles_tendon_02.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Intraoperative_fibularis_longus_tendon.jpg) |
| 09b dry bone | 183,169,120 | #b7a978 | r 159-207, g 157-181, b 108-131 (n=2) | Fresh bone: ivory to pinkish-cream with thin glistening periosteum and fine red vessels, cut surface red and porous (marrow). Dry bone: matte chalky cream-tan, darker in pores and sutures. | [1](https://commons.wikimedia.org/wiki/File:Skull_-_midsaggital_section_P.2005.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Anthroplogy_-_human_skull_of_a_boy.JPG) |
| 10 articular cartilage fresh | 194,166,152 | #c2a698 | r 185-204, g 145-186, b 125-178 (n=2) | Smooth, wet, glassy and slightly translucent; costal cartilage pearly white to pale yellow-grey bars; articular cartilage bluish-white to ivory with a high gloss, yellowing with age. | [1](https://commons.wikimedia.org/wiki/File:Head_of_femur_avascular_necrosis.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Head_of_femur.jpg) |
| 11 liver | 152,82,73 | #985249 | r 92-206, g 46-134, b 48-102 (n=3) | Smooth wet capsule with strong broad highlights, sharp inferior edge; uniform red-brown with faint fine lobular mottling, paler/yellower when fatty. | [1](https://commons.wikimedia.org/wiki/File:Gallbladder_in_laparoscopy.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Gallenblase.jpg) ; [3](https://commons.wikimedia.org/wiki/File:Splenose.jpg) |
| 12x lung cut surface | 114,102,111 | #72666f | one photo; IQR r 95-134, g 82-126, b 89-137 | Wet glossy pleura over a spongy surface; pink to pink-grey with a fine polygonal lobular network and black carbon speckling along it, darker and redder in dependent parts. (These rows are not that fresh surface - see caveats.) | [1](https://commons.wikimedia.org/wiki/File:Normal_lung_%283661494812%29.jpg) |
| 12y lung outer surface | 42,36,29 | #2a241d | one photo; IQR r 32-64, g 26-54, b 21-41 | Wet glossy pleura over a spongy surface; pink to pink-grey with a fine polygonal lobular network and black carbon speckling along it, darker and redder in dependent parts. (These rows are not that fresh surface - see caveats.) | [1](https://commons.wikimedia.org/wiki/File:Human_lung.jpg) |
| 12z lung resected lobe | 61,21,27 | #3d151b | one photo; IQR r 49-72, g 17-26, b 22-33 | Wet glossy pleura over a spongy surface; pink to pink-grey with a fine polygonal lobular network and black carbon speckling along it, darker and redder in dependent parts. (These rows are not that fresh surface - see caveats.) | [1](https://commons.wikimedia.org/wiki/File:VATS_08.jpg) |
| 13a epicardial fat | 231,176,126 | #e7b07e | r 214-248, g 159-194, b 73-178 (n=2) | Wet gloss; red-brown myocardium largely hidden by yellow epicardial fat along the coronary grooves, coronary vessels as red/blue cords in the fat, thin shiny epicardium. | [1](https://commons.wikimedia.org/wiki/File:Humhrt2.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Human_heart_male_adult_autopsy.jpg) |
| 13b myocardium through epicardium | 174,102,102 | #ae6666 | r 165-183, g 75-128, b 93-110 (n=2) | Wet gloss; red-brown myocardium largely hidden by yellow epicardial fat along the coronary grooves, coronary vessels as red/blue cords in the fat, thin shiny epicardium. | [1](https://commons.wikimedia.org/wiki/File:Humhrt2.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Human_heart_male_adult_autopsy.jpg) |
| 14 small intestine | 183,139,107 | #b78b6b | one photo; IQR r 174-195, g 127-153, b 97-120 | Wet, glossy, thin-walled loops, pink to pink-grey, slightly translucent, fine branching red vessels entering from the mesenteric border; mesentery yellow fat with vessel arcades. | [1](https://commons.wikimedia.org/wiki/File:Splenose.jpg) |
| 15 large intestine | 214,179,106 | #d6b36a | one photo; IQR r 202-224, g 163-192, b 92-125 | Paler and greyer than small bowel; wet gloss, sacculated (haustra) with three pale longitudinal bands (taeniae) and yellow fat tags (appendices epiploicae). | [1](https://commons.wikimedia.org/wiki/File:Splenose.jpg) |
| 16 stomach serosa | 140,124,117 | #8c7c75 | one photo; IQR r 129-150, g 115-132, b 109-124 | Wet, smooth, thick-walled; pale pink to grey-pink serosa with prominent vessels along both curvatures and yellow omental fat attached. | [1](https://commons.wikimedia.org/wiki/File:Sleeve-ex_situ.jpg) |
| 17 spleen | 157,105,100 | #9d6964 | one photo; IQR r 146-163, g 91-112, b 85-108 | Dark purple-red to slate maroon, smooth taut capsule with dull satin gloss, notched border; the darkest solid organ. | [1](https://commons.wikimedia.org/wiki/File:Splenectomy_specimen.jpg) |
| 18 kidney surface | 241,186,87 | #f1ba57 | one photo; IQR r 238-245, g 182-190, b 82-92 | Smooth, glossy thin capsule, red-brown (bean), often with faint stellate surface veins; yellow perirenal fat around the hilum. | [1](https://commons.wikimedia.org/wiki/File:Kidney_for_transplant_from_live_donor.jpg) |
| 18b perirenal hilum fat | 249,181,22 | #f9b516 | one photo; IQR r 237-255, g 157-199, b 7-45 | Smooth, glossy thin capsule, red-brown (bean), often with faint stellate surface veins; yellow perirenal fat around the hilum. | [1](https://commons.wikimedia.org/wiki/File:Kidney_for_transplant_from_live_donor.jpg) |
| 20 gallbladder | 181,164,179 | #b5a4b3 | one photo; IQR r 169-190, g 151-176, b 166-191 | Thin smooth wet wall; blue-green to grey-green where bile shows through, whiter where the wall is thick, fine surface vessels. | [1](https://commons.wikimedia.org/wiki/File:Gallenblase.jpg) |
| 22 brain cortex fresh | 172,126,96 | #ac7e60 | r 149-199, g 112-169, b 80-157 (n=4) | Fresh cortex: glistening, pink-grey to cream under the transparent arachnoid with red surface vessels in every sulcus; cut white matter is matte ivory white, grey matter pink-grey. | [1](https://commons.wikimedia.org/wiki/File:Brain_autopsy_lateral_view.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Brain_autopsy_top_view.jpg) ; [3](https://commons.wikimedia.org/wiki/File:Gross_pathology_of_normal_brain_and_brain_of_patient_treated_with_methylene_blue_before_death.jpg) ; [4](https://commons.wikimedia.org/wiki/File:Craniotomy_Arachnoid.jpg) |
| 26 thyroid | 168,89,112 | #a85970 | one photo; IQR r 134-206, g 55-139, b 81-157 | Red-brown, beefy, smooth wet lobes with a thin capsule and many surface vessels. | [1](https://commons.wikimedia.org/wiki/File:Thyroid_Surgery.jpg) |
| 29 eyelid skin | 204,161,156 | #cca19c | r 170-239, g 135-187, b 128-184 (n=2) | Very thin matte skin, slightly darker and redder/browner than cheek, fine horizontal creases, faint vessels showing through. | [1](https://commons.wikimedia.org/wiki/File:Closed_human_eye%2C_superior_view.jpg) ; [2](https://commons.wikimedia.org/wiki/File:Black_eyebrow.jpg) |
| 29r skin below the eye | 238,200,203 | #eec8cb | one photo; IQR r 230-251, g 188-221, b 190-224 | Very thin matte skin, slightly darker and redder/browner than cheek, fine horizontal creases, faint vessels showing through. | [1](https://commons.wikimedia.org/wiki/File:Closed_human_eye%2C_superior_view.jpg) |
| 30 scalp stubble brown | 119,82,62 | #77523e | one photo; IQR r 107-134, g 72-94, b 53-73 | Short brown stubble reads as a grey-brown shadow over scalp skin; individual hairs dark brown with a narrow anisotropic highlight. | [1](https://commons.wikimedia.org/wiki/File:Luca_Nowak_portrait.jpg) |
| 30b beard hair brown | 45,28,17 | #2d1c11 | one photo; IQR r 25-79, g 16-48, b 10-33 | Short brown stubble reads as a grey-brown shadow over scalp skin; individual hairs dark brown with a narrow anisotropic highlight. | [1](https://commons.wikimedia.org/wiki/File:Luca_Nowak_portrait.jpg) |
| 30r forehead skin | 226,163,131 | #e2a383 | one photo; IQR r 220-230, g 157-170, b 126-138 | Short brown stubble reads as a grey-brown shadow over scalp skin; individual hairs dark brown with a narrow anisotropic highlight. | [1](https://commons.wikimedia.org/wiki/File:Luca_Nowak_portrait.jpg) |
| 31 eyebrow brown | 88,52,37 | #583425 | one photo; IQR r 69-117, g 40-74, b 26-56 | Brown eyebrow hairs lying obliquely upward and outward over skin; denser medially, dark neutral brown with skin showing through. | [1](https://commons.wikimedia.org/wiki/File:Luca_Nowak_portrait.jpg) |
| 31 eyebrow dark brown | 77,61,60 | #4d3d3c | one photo; IQR r 64-107, g 52-86, b 51-81 | Brown eyebrow hairs lying obliquely upward and outward over skin; denser medially, dark neutral brown with skin showing through. | [1](https://commons.wikimedia.org/wiki/File:Black_eyebrow.jpg) |
| 31r skin above eyebrow | 189,153,145 | #bd9991 | one photo; IQR r 185-193, g 150-156, b 141-151 | Brown eyebrow hairs lying obliquely upward and outward over skin; denser medially, dark neutral brown with skin showing through. | [1](https://commons.wikimedia.org/wiki/File:Black_eyebrow.jpg) |

## Every measurement

| Tissue | Photo | Rectangle px | r,g,b | Hex | IQR |
|---|---|---|---|---|---|
| 01 skin chest (light, living) | Bodymorphproj_DanielMMS_modB001_20211025_posA01.jpg | 409,357,742,492 of 1280x795 | 229,204,192 | #e5ccc0 | r 227-231 g 201-207 b 189-194 |
| 01 skin abdomen (light, living) | Bodymorphproj_DanielMMS_modB001_20211025_posA01.jpg | 448,596,768,755 of 1280x795 | 222,198,186 | #dec6ba | r 219-225 g 191-201 b 181-190 |
| 01 skin chest (light, living) | Bodymorphproj_mkg_modA002_20070407_posA01.jpg | 409,343,601,457 of 1280x763 | 166,131,109 | #a6836d | r 163-169 g 126-134 b 104-113 |
| 01 skin abdomen (light, living) | Bodymorphproj_mkg_modA002_20070407_posA01.jpg | 448,610,832,724 of 1280x763 | 168,138,122 | #a88a7a | r 165-170 g 134-141 b 118-126 |
| 01 skin abdomen (light, living) | A_nude_Torso_of_a_Man.JPG | 291,337,460,450 of 768x1024 | 138,118,108 | #8a766c | r 133-147 g 113-126 b 102-115 |
| 01 skin abdomen (light, living) | Central_Obesity_008.jpg | 384,431,704,616 of 1280x1232 | 244,226,199 | #f4e2c7 | r 241-247 g 222-232 b 192-205 |
| 01 skin chest (light, living) | Median_Sternotomy_Example.jpg | 685,604,914,720 of 1143x1162 | 204,168,143 | #cca88f | r 194-212 g 158-182 b 135-152 |
| 02 lips upper | Close_up_man_lips.jpg | 512,346,665,399 of 1280x1050 | 138,64,75 | #8a404b | r 123-151 g 52-75 b 62-87 |
| 02 lips lower | Close_up_man_lips.jpg | 422,493,640,567 of 1280x1050 | 166,92,106 | #a65c6a | r 140-177 g 69-103 b 80-118 |
| 03 areola male | Male_Areola.jpg | 358,785,460,921 of 1280x1707 | 131,123,125 | #837b7d | r 117-141 g 109-134 b 111-137 |
| 03 nipple male | Male_Areola.jpg | 480,836,524,887 of 1280x1707 | 122,117,121 | #7a7579 | r 117-128 g 109-125 b 112-130 |
| 03 areola male | Bodymorphproj_mkg_modA002_20070407_posA01.jpg | 357,515,369,545 of 1280x763 | 104,59,50 | #683b32 | r 99-111 g 53-64 b 45-56 |
| 03 areola male | Median_Sternotomy_Example.jpg | 211,546,251,586 of 1143x1162 | 124,87,71 | #7c5747 | r 104-140 g 75-100 b 60-81 |
| 04 lunula | Fingernail_label_%28enwiki%29.jpg | 824,351,871,380 of 1044x634 | 253,241,239 | #fdf1ef | r 252-255 g 217-246 b 219-245 |
| 05 palm | Open_Palm_of_the_Left_Hand%2C_Fingers.jpg | 256,528,640,768 of 1280x960 | 211,157,119 | #d39d77 | r 198-224 g 145-169 b 110-129 |
| 05 palm | Right_Hand_Palm.png | 384,1206,896,1608 of 1280x2011 | 228,173,129 | #e4ad81 | r 221-234 g 162-184 b 119-139 |
| 06 subcutaneous fat (surgery) | Electrocautery_during_abdominoplasty.jpg | 128,844,384,1152 of 1280x1920 | 212,127,36 | #d47f24 | r 191-231 g 102-152 b 19-55 |
| 06 subcutaneous fat (surgery) | Rectus_diastasis_repair_during_abdominoplasty.jpg | 256,422,384,672 of 1280x1920 | 216,112,42 | #d8702a | r 181-242 g 80-137 b 11-65 |
| 06b omental fat (laparoscopy) | Gallenblase.jpg | 768,528,1152,682 of 1280x853 | 167,106,75 | #a76a4b | r 158-180 g 96-116 b 66-85 |
| 06b omental fat (open) | Splenose.jpg | 320,644,537,718 of 1280x1239 | 239,190,73 | #efbe49 | r 229-247 g 167-204 b 62-83 |
| 07 muscle fresh (bloody field) | Intraoperative_fibularis_longus_tendon.jpg | 422,768,576,853 of 1280x1707 | 218,113,111 | #da716f | r 195-238 g 84-138 b 83-136 |
| 07 muscle fresh | Ruptured_achilles_tendon.jpg | 436,558,519,608 of 1180x822 | 142,31,32 | #8e1f20 | r 83-177 g 13-52 b 18-52 |
| 08 tendon (Achilles, cut) | Achilles_tendon_02.jpg | 711,392,732,512 of 1280x1707 | 206,199,199 | #cec7c7 | r 192-211 g 181-207 b 176-206 |
| 08 aponeurosis (abdominal fascia) | Electrocautery_during_abdominoplasty.jpg | 384,1344,512,1459 of 1280x1920 | 199,153,77 | #c7994d | r 177-230 g 124-196 b 38-124 |
| 11 liver (laparoscopy) | Gallbladder_in_laparoscopy.jpg | 422,259,652,432 of 768x576 | 152,82,73 | #985249 | r 141-168 g 75-89 b 67-84 |
| 11 liver (laparoscopy) | Gallenblase.jpg | 704,255,1088,341 of 1280x853 | 92,46,48 | #5c2e30 | r 82-107 g 39-56 b 40-60 |
| 11 liver (open, pale/fatty) | Splenose.jpg | 320,123,640,433 of 1280x1239 | 206,134,102 | #ce8666 | r 195-216 g 121-151 b 92-113 |
| 20 gallbladder (laparoscopy) | Gallenblase.jpg | 396,281,486,383 of 1280x853 | 181,164,179 | #b5a4b3 | r 169-190 g 151-176 b 166-191 |
| 03r skin beside areola (same photos, for ratio) | Male_Areola.jpg | 102,1365,384,1621 of 1280x1707 | 149,152,149 | #959895 | r 143-155 g 146-158 b 141-156 |
| 03r skin beside areola (same photos, for ratio) | Bodymorphproj_mkg_modA002_20070407_posA01.jpg | 409,343,601,457 of 1280x763 | 166,131,109 | #a6836d | r 163-169 g 126-134 b 104-113 |
| 03r skin beside areola (same photos, for ratio) | Median_Sternotomy_Example.jpg | 685,604,914,720 of 1143x1162 | 204,168,143 | #cca88f | r 194-212 g 158-182 b 135-152 |
| 13a epicardial fat (fresh heart, small photo) | Humhrt2.jpg | 62,29,103,49 of 173x224 | 248,194,178 | #f8c2b2 | r 239-253 g 177-211 b 162-189 |
| 13b myocardium through epicardium (fresh heart, small photo) | Humhrt2.jpg | 95,112,138,156 of 173x224 | 165,75,110 | #a54b6e | r 128-205 g 42-120 b 66-155 |
| 18 kidney surface (flushed donor kidney, blood washed out) | Kidney_for_transplant_from_live_donor.jpg | 614,302,806,379 of 1280x960 | 241,186,87 | #f1ba57 | r 238-245 g 182-190 b 82-92 |
| 18b perirenal hilum fat (donor kidney) | Kidney_for_transplant_from_live_donor.jpg | 396,432,563,494 of 1280x960 | 249,181,22 | #f9b516 | r 237-255 g 157-199 b 7-45 |
| 22 brain cortex fresh (autopsy) | Brain_autopsy_lateral_view.jpg | 384,240,768,480 of 1280x960 | 188,169,157 | #bca99d | r 163-198 g 140-182 b 131-171 |
| 22 brain cortex fresh (autopsy) | Brain_autopsy_top_view.jpg | 230,860,537,1173 of 1280x1565 | 156,129,97 | #9c8161 | r 135-173 g 106-149 b 81-116 |
| 22 brain cortex fresh (autopsy) | Gross_pathology_of_normal_brain_and_brain_of_patient_treated_with_methylene_blue | 192,104,537,390 of 1280x1302 | 149,112,96 | #957060 | r 78-212 g 59-156 b 45-134 |
| 14 small intestine (open abdomen) | Splenose.jpg | 576,1053,896,1177 of 1280x1239 | 183,139,107 | #b78b6b | r 174-195 g 127-153 b 97-120 |
| 15 large intestine (probable transverse colon, open abdomen) | Splenose.jpg | 256,780,704,916 of 1280x1239 | 214,179,106 | #d6b36a | r 202-224 g 163-192 b 92-125 |
| 29 eyelid skin (closed upper lid) | Closed_human_eye%2C_superior_view.jpg | 256,115,768,288 of 1280x960 | 239,187,184 | #efbbb8 | r 231-248 g 173-206 b 169-205 |
| 29r skin below the eye (same photo, for ratio) | Closed_human_eye%2C_superior_view.jpg | 384,787,896,912 of 1280x960 | 238,200,203 | #eec8cb | r 230-251 g 188-221 b 190-224 |
| 10 articular cartilage fresh (femoral head, blood-stained) | Head_of_femur_avascular_necrosis.jpg | 512,404,665,501 of 1280x964 | 204,145,125 | #cc917d | r 199-209 g 137-157 b 118-137 |
| 10 articular cartilage fresh (femoral head, clean) | Head_of_femur.jpg | 512,283,716,526 of 1280x1013 | 185,186,178 | #b9bab2 | r 173-198 g 178-200 b 171-194 |
| 04 nail plate over nail bed | Lunula_07.jpg | 704,832,1024,1046 of 1280x1189 | 181,102,113 | #b56671 | r 175-187 g 96-108 b 106-120 |
| 04 nail plate over nail bed | Thumb-nail_and_hand.jpeg | 537,802,793,921 of 1280x1707 | 180,141,147 | #b48d93 | r 168-191 g 131-153 b 137-156 |
| 04 lunula | Thumb-nail_and_hand.jpeg | 563,964,768,1024 of 1280x1707 | 174,158,170 | #ae9eaa | r 168-179 g 146-173 b 159-186 |
| 26 thyroid (thyroidectomy, flash photo) | Thyroid_Surgery.jpg | 492,451,544,499 of 1280x960 | 168,89,112 | #a85970 | r 134-206 g 55-139 b 81-157 |
| 13a epicardial fat (autopsy heart) | Human_heart_male_adult_autopsy.jpg | 307,593,409,741 of 1280x1483 | 214,159,73 | #d69f49 | r 212-215 g 152-165 b 66-80 |
| 13b myocardium through epicardium (autopsy heart) | Human_heart_male_adult_autopsy.jpg | 435,697,537,815 of 1280x1483 | 183,128,93 | #b7805d | r 172-203 g 118-142 b 85-98 |
| 17 spleen (splenectomy specimen) | Splenectomy_specimen.jpg | 435,570,537,677 of 1280x1189 | 157,105,100 | #9d6964 | r 146-163 g 91-112 b 85-108 |
| 08 tendon | Intraoperative_fibularis_longus_tendon.jpg | 576,662,742,691 of 1280x1707 | 235,199,192 | #ebc7c0 | r 231-239 g 193-204 b 184-198 |
| 12x lung cut surface (autopsy, not pleural surface) | Normal_lung_%283661494812%29.jpg | 94,740,315,888 of 630x987 | 114,102,111 | #72666f | r 95-134 g 82-126 b 89-137 |
| 12y lung outer surface (dark preserved or smoker's lung, not fresh) | Human_lung.jpg | 324,633,756,864 of 1080x1920 | 42,36,29 | #2a241d | r 32-64 g 26-54 b 21-41 |
| 09b dry bone (skull, inner table) | Skull_-_midsaggital_section_P.2005.jpg | 192,219,528,395 of 960x878 | 159,157,108 | #9f9d6c | r 152-168 g 149-166 b 99-118 |
| 09b dry bone (skull, frontal) | Anthroplogy_-_human_skull_of_a_boy.JPG | 537,153,793,307 of 1280x853 | 207,181,131 | #cfb583 | r 195-214 g 169-191 b 112-146 |
| 31 eyebrow dark brown (hairs with skin between) | Black_eyebrow.jpg | 141,117,329,154 of 471x309 | 77,61,60 | #4d3d3c | r 64-107 g 52-86 b 51-81 |
| 31r skin above eyebrow (same photo, for ratio) | Black_eyebrow.jpg | 141,30,376,77 of 471x309 | 189,153,145 | #bd9991 | r 185-193 g 150-156 b 141-151 |
| 29 eyelid skin (upper lid below brow) | Black_eyebrow.jpg | 141,222,282,253 of 471x309 | 170,135,128 | #aa8780 | r 166-173 g 132-139 b 125-131 |
| 02 lips lower | Lips_man_110.jpg | 422,879,556,915 of 960x1441 | 153,76,93 | #994c5d | r 144-161 g 72-82 b 87-100 |
| 02r skin of chin (same photos as lips, for ratio) | Lips_man_110.jpg | 384,979,576,1037 of 960x1441 | 165,134,131 | #a58683 | r 157-171 g 128-141 b 119-138 |
| 02r skin of chin (same photos as lips, for ratio) | Close_up_man_lips.jpg | 921,630,1216,840 of 1280x1050 | 184,150,133 | #b89685 | r 173-190 g 139-156 b 123-140 |
| 30 scalp stubble brown (buzz cut over scalp) | Luca_Nowak_portrait.jpg | 190,30,260,55 of 500x500 | 119,82,62 | #77523e | r 107-134 g 72-94 b 53-73 |
| 30r forehead skin (same photo, for ratio) | Luca_Nowak_portrait.jpg | 165,85,275,135 of 500x500 | 226,163,131 | #e2a383 | r 220-230 g 157-170 b 126-138 |
| 30b beard hair brown (dense) | Luca_Nowak_portrait.jpg | 115,290,150,330 of 500x500 | 45,28,17 | #2d1c11 | r 25-79 g 16-48 b 10-33 |
| 31 eyebrow brown (hairs with skin between) | Luca_Nowak_portrait.jpg | 135,162,175,172 of 500x500 | 88,52,37 | #583425 | r 69-117 g 40-74 b 26-56 |
| 02 lips lower | Luca_Nowak_portrait.jpg | 195,296,235,304 of 500x500 | 168,68,68 | #a84444 | r 141-184 g 48-84 b 44-83 |
| 16 stomach serosa (fresh sleeve-gastrectomy specimen) | Sleeve-ex_situ.jpg | 640,537,921,672 of 1280x960 | 140,124,117 | #8c7c75 | r 129-150 g 115-132 b 109-124 |
| 22 brain cortex fresh (living, craniotomy, orange-cast photo) | Craniotomy_Arachnoid.jpg | 166,238,242,329 of 758x568 | 199,124,80 | #c77c50 | r 177-212 g 104-137 b 65-87 |
| 12z lung resected lobe (collapsed, blood-stained) | VATS_08.jpg | 288,194,364,251 of 960x719 | 61,21,27 | #3d151b | r 49-72 g 17-26 b 22-33 |

## Not measured / caveats

### How to read the numbers

- Every value is the median sRGB of a hand-chosen rectangle in a 1280 px (or smaller) Wikimedia Commons thumbnail, after looking at the photograph and at the cropped rectangle. Nothing was white-balanced or exposure-corrected. Photographs differ a lot in exposure and colour cast, so trust hue and saturation more than brightness, and trust rows with n >= 3 more than single-photo rows.
- Rows ending in "r" (02r, 03r, 29r, 30r, 31r) are skin measured in the same photograph as the feature, so the feature can be expressed relative to skin, which cancels most of the lighting difference.
- Contact sheets, gridded zooms and the cropped rectangles (crops*.jpg) are in build/research/palette/ for checking; sources.json maps each short key to its Commons page; palette.csv has every rectangle.

### Relative factors (feature colour divided by skin colour in the same photo)

| Feature | r, g, b factor per photo | Suggested factor | Applied to measured trunk skin 204,168,143 |
|---|---|---|---|
| Male areola | 0.63,0.45,0.46 ; 0.61,0.52,0.50 ; (0.88,0.81,0.84 in a washed-out photo) | 0.62, 0.48, 0.48 | 126,81,69 (#7e5145) |
| Lips (lower) | 0.90,0.61,0.80 ; 0.93,0.57,0.71 ; 0.74,0.42,0.51 | 0.90, 0.57, 0.71 | 184,96,102 (#b86066) |
| Eyelid | 1.00,0.94,0.91 ; 0.90,0.88,0.88 | 0.95, 0.91, 0.90 | 194,153,129 (#c29981) |
| Scalp stubble (brown buzz cut) | 0.53,0.50,0.47 | 0.53, 0.50, 0.47 | 108,84,67 (#6c5443) |
| Brown eyebrow (hair plus skin between) | 0.39,0.32,0.28 ; 0.41,0.40,0.41 | 0.40, 0.36, 0.34 | 82,60,49 (#523c31) |

### Weak rows (measured, but do not rely on them alone)

- 04 lunula: one photo is overexposed (red channel clipped), the other is blurred with a cool cast. The lunula is simply a paler, whiter version of the nail-bed pink.
- 06 subcutaneous fat: both photos are from one abdominoplasty series under a hard surgical light; fat really is this saturated orange-yellow when fresh and blood-stained, but clean fat is closer to the omental value 239,190,73.
- 07 muscle: only two usable human photos, both bloody operative fields (one bright, one in shadow); they disagree widely (218,113,111 against 142,31,32). Fresh muscle sits between: a deep red around 150-170, 50-60, 50-60.
- 08 aponeurosis: the abdominal fascia rectangle is stained yellow by fat; the tendon values (pearly white to pale pink) are better for a clean aponeurosis.
- 10 articular cartilage: the clean femoral head has a slight green tint reflected from the surgical drape; the other is blood-stained. No costal cartilage photograph was found.
- 11 liver: the two laparoscopic photos differ only in exposure (same hue); the third is a pale fatty liver.
- 12 lung: NOT the fresh pink-grey surface. The three rows are an autopsy cut surface, a dark preserved or heavy-smoker lung, and a collapsed blood-stained resected lobe. See fallback below.
- 13 heart: epicardial fat is reliable in hue (yellow); myocardium comes from a very small photo and from a fatty autopsy heart.
- 14 and 15 intestine: one photograph, open abdomen under warm light; the large-bowel structure is identified by its attached omentum and is only probably transverse colon.
- 16 stomach: one fresh sleeve-gastrectomy specimen, slightly underexposed.
- 17 spleen: one splenectomy specimen. 20 gallbladder: one laparoscopic photo. 26 thyroid: one flash photo full of highlights.
- 18 kidney: a donor kidney flushed with preservation fluid (blood washed out) under strongly yellow light; a kidney in the body is red-brown, close to the liver but a little lighter. Treat this row as unusable for the in-situ colour.
- 22 brain: cortex only (surface with vessels). The living craniotomy photo has an orange cast. No fresh cut section, so white matter was not measured.
- 09 bone: dry bone only (two skulls).

### Could not be measured (no usable photograph found within the budget)

Fresh bone with periosteum; costal cartilage; living pink lung surface; pancreas; urinary bladder; aorta or other artery wall; vena cava; superficial veins through skin; nerve; trachea; fresh cadaver skin (pallor) and livor mortis; brain white matter; kidney in situ. Commons keyword search is thin for intraoperative photographs and rate-limits downloads; these need a targeted source (open-access surgical atlases or PMC case reports).

Fallback starting values for these, from textbook description only, NOT measured, to be replaced when photographs are found:

| Tissue | Fallback sRGB | Hex |
|---|---|---|
| Fresh bone with periosteum | 226,205,180 | #e2cdb4 |
| Costal cartilage | 222,214,196 | #ded6c4 |
| Living lung surface (pink, with grey mottling 170,150,155) | 214,150,150 | #d69696 |
| Pancreas | 222,180,140 | #deb48c |
| Urinary bladder (outer wall) | 205,160,150 | #cda096 |
| Aorta / artery wall (empty) | 225,200,175 | #e1c8af |
| Vena cava (blood-filled) | 90,70,110 | #5a466e |
| Superficial vein through light skin | skin x 0.85, 0.95, 1.00 | - |
| Nerve | 235,222,190 | #ebdebe |
| Trachea (rings / membrane between) | 228,215,200 / 215,160,150 | #e4d7c8 / #d7a096 |
| Cadaver skin, pallor | 200,180,160 | #c8b4a0 |
| Livor mortis | 130,80,100 | #825064 |
| Brain white matter (cut) | 235,225,205 | #ebe1cd |
| Kidney in situ | 150,80,70 | #96504a |

