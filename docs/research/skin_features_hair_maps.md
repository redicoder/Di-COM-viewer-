# Skin features and hair maps for the procedural cadaver (research notes)

Status: FINAL of this research pass (web research, 2026-11-12).

Reading rule for every number: "V" = verified on a source read in this session; "S" = taken from a search-result summary of the named source (source not read in full); "K" = standard textbook / anthropometry knowledge of the researcher, NOT re-verified online in this session. K values are good defaults for code, not citations. Section 9 lists what could not be verified.

## 0. The specimen: Visible Human Male

| Item | Value | Mark |
|---|---|---|
| Identity | white male, 39 years, died August 1993 (Texas) | V |
| Preparation | frozen in a gelatin + water block, cut axially every 1 mm, 1,871 cross-sections photographed; dataset finished November 1994 | V |
| Known defects of the body | one testicle, no appendix; formalin injection damage on the dorsum of each forearm; right sartorius cut at the femoral vein drain; brain slightly swollen by freezing | V |
| Height / weight | about 180 cm (5 ft 11 in), about 90 kg (199 lb): the commonly quoted figures (Spitzer et al. 1996); two searches and the PMC abstract page did NOT show them, so unconfirmed | K |
| Build | heavy, muscular; BMI about 27.8 from the two numbers above | K |

Sources: https://en.wikipedia.org/wiki/Visible_Human_Project ; https://www.nlm.nih.gov/research/visible/mri.html ; https://www.nlm.nih.gov/research/visible/frozen_ct.html ; Spitzer et al. 1996 https://pmc.ncbi.nlm.nih.gov/articles/PMC116294 (full text is in the PDF only)

## B1. Hair streams (flumina pilorum): direction rules by region

Primary source read in full text: W. Kidd, "The Direction of Hair in Animals and Man", London 1903, chapter IV "Critical areas - Man" (https://archive.org/details/directionhairin00kiddgoog ; text saved in build/research/skin_src/kidd/kidd.txt). Kidd summarises and corrects the older maps of Eschricht (1837) and Voigt (1857). Terminology: flumen pilorum = hair stream, vortex pilorum = whorl, crux pilorum = cross (https://ifaa.unifr.ch/Public/TNAEntryPage/auto/unit/EN/TAH7406%20Unit%20EN.htm).

"Direction" always means the way the free TIP points (root -> tip), as a tangent vector on the surface.

| Region | Direction rule (root -> tip) | Mark |
|---|---|---|
| Scalp | Radiates from ONE whorl ("crown") near the posterior fontanelle, usually a little right or left of the midline (rarely exactly on it, sometimes double). From the whorl: forward over the vault to the frontal hairline, diverging to each side over the temples, and downward at the back. Streams follow the round outline of the head (spiral, not straight meridians). | V |
| Frontal hairline | The stream reaches the edge pointing forward/down and parts there: left-of-midline parting most common (45 of 70), central 17, right 6. | V |
| Forehead (vellus) | Between hairline and eyebrows the hair runs laterally toward the temple; near the hairline it curves down-and-lateral, near the eyebrow up-and-lateral. | V |
| Eyebrow | Stream runs lateral along the brow; a constant "break" in the stream lies over the lateral attachment of corrugator (about the junction of the medial third and lateral two thirds), more marked on the left in 76.5 %. | V |
| Nape | Type 1 (49 %): midline stream straight down along the spine, lateral parts curve out to the side of the neck. Type 2 (51 %): lateral parts converge down-and-medially to the midline. Pick one (306 vs 321 of 627 people). | V |
| Face/beard and front of neck | The stream from the face runs down over the jaw onto the neck. At about the middle of the anterior triangle of the neck it meets an ASCENDING stream from the chest and lower neck; the two merge and turn backward round the side of the neck to join the nape stream. This is the reversal of grain known from shaving. | V |
| Chest | Parting level = sternal angle (2nd costal cartilage). Below it: hair runs DOWN the sternal groove and over the pectorals. Above it: hair runs UP in the midline to the neck; over the clavicles it slopes up-and-medially, as far as the upper border of the larynx. | V |
| Back | Midline stream runs straight DOWN the spinal furrow from the nape to the coccyx. Lateral trunk hair runs toward the spine; from the angles of the ribs the thoracic streams slope UP-and-medially at about 45 degrees to the spine until they reach the erector spinae bulge, then turn sharply down into the midline stream. Lumbar streams stay nearly transverse (pointing medially). At the back border of the axilla the hair slopes toward the acromion / spine of the scapula. | V |
| Flank | A parting line runs from the axilla to the middle of the inguinal ligament, slightly convex toward the navel; a radiating whorl interrupts it just above navel level. Ventral hair leaves the line forward/medially, dorsal hair backward/medially. | V |
| Abdomen | Both sides converge on the midline (linea alba), where the hairs meet in a slightly raised crest; classical maps draw a converging vortex at the navel. Practical rule: lateral abdomen points medially and slightly down; above the navel down-medially to the navel; on the crest below the navel toward the navel in the first 30-40 mm, lower down toward the pubis. Large individual variation. | K |
| Upper arm | Mostly down the limb (shoulder -> elbow) on front and back; the deltoid region is disturbed: hair slopes up-and-back toward the acromion. | V |
| Forearm, flexor side | Two streams start at a parting on the flexor surface, run toward the wrist first, then curve round the radial and the ulnar borders until they lie at right angles to the limb axis. | V |
| Forearm, extensor side | The two streams from the borders meet along the posterior border of the ulna and form one narrow stream that runs PROXIMALLY, straight to the olecranon, ending in a converging whorl just proximal to the olecranon. The reversal starts 25-50 mm proximal to the distal end of the ulna. So: radial part of the dorsum points transversely to the ulnar side, the ulnar strip points to the elbow, the distal 25-50 mm points to the wrist/ulnar side. | V |
| Hand dorsum | Toward the ULNAR border, nearly transverse. A parting runs along the middle of the 1st metacarpal: radial of it a thin sparse stream points to the radial border. | V |
| Fingers (dorsum) | Toward the ulnar border (oblique, distal-ulnar); a narrow strip on the radial side of each digit stays longitudinal (pointing distally). | V |
| Thigh | Down the limb (hip -> knee). Exception: proximal third of the posterior surface, where two converging streams join and the central tract points UP to the gluteal fold. | V |
| Leg (shin, calf) | Straight down the limb to the ankle, no disturbance. Terminal hair stops abruptly just above the malleoli. | V |
| Foot dorsum and toes | Like the hand: transverse toward the FIBULAR (lateral) border; parting along the 1st metatarsal; sparse hair only on dorsum and proximal phalanges. | V |

Programmer's shortcut: direction field = (1) base field "down the trunk / distally along each limb" + (2) diverging points: scalp whorl (spiral), flank whorl at navel level + (3) converging points/lines: olecranon whorl, navel and linea alba + (4) parting lines: horizontal line at the sternal angle, axilla-to-mid-inguinal line, mid-neck meeting line + (5) rotation to "transverse toward ulnar/fibular border" on forearm dorsum, hand and foot. Project on the tangent plane, normalise, add +/- 15-25 degrees of per-hair jitter.

## B2. Hair table by region (adult white male, 39 y, brown hair, average-to-hairy)

Density = visible hairs per cm2 (for vellus: follicles per cm2). Spacing in mm = 10 / sqrt(density). Diameter in micrometres (um).
Colours (sRGB 0-255, fibre albedo; K, art-directed defaults for medium/dark brown): SCALP (72,52,36); BEARD (84,58,40) plus 3-8 % grey fibres (200,198,190) on chin and temples at 39; BROW (58,42,30); LASH (40,29,22); BODY (96,70,50) drawn at 60-80 % opacity because the fibres are thin; PUBIC and AXILLA (52,38,28); VELLUS colourless (225,210,195) at 15-25 % opacity. Shaved stubble seen through skin reads blue-grey: multiply the skin colour by (0.80,0.82,0.86) at full beard density.

| Region | Density /cm2 | Length mm | Diameter um | Curl | Exit angle | Direction (root -> tip) | Mark |
|---|---|---|---|---|---|---|---|
| Scalp, shaved | 214-230 hairs (frontal 230 +/- 33, vertex 226 +/- 20, occipital 214 +/- 28), in follicular units of 1-4 hairs (mean about 2.3; 70-100 units/cm2) | stubble 0.5-2 (growth 0.35 mm/day) | 60-80 | straight/wavy | 30-45 deg top, 10-20 deg temples and nape | spiral out of the whorl | density S; rest K |
| Eyebrow | 300-500 hairs per brow (100-150 /cm2 on about 3.5 cm2; transplant practice 200-400 grafts per brow) | head 5-7, body 8-12, tail 5-8 | 50-90 | slight arc | 10-15 deg (almost flat) | section A3 | S (clinics) / K |
| Eyelashes | upper 90-160 in 5-6 rows; lower 75-80 in 3-4 rows; band 2 mm wide | upper 8-12, lower 6-8 | 70-80 root, 80-120 middle, 5-10 tip | upper curves up, lower down, radius 8-12 mm | - | perpendicular to the lid margin, fanning | S |
| Moustache | 80-110 | 1-day stubble 0.3-0.5 (growth 0.27-0.47 mm/day) | 100-150, elliptical | straight | 30-50 deg | down and lateral, 20-45 deg off vertical | S |
| Chin | 70-120 | 0.3-0.5 | 100-150 | straight | 40-60 deg | down, converging on the midline; under the chin down-and-back | S |
| Cheek, upper | 30-80 | 0.3-0.5 | 80-120 | straight | 30-45 deg | down and slightly forward (sideburn -> jaw / mouth corner) | S |
| Cheek, lower and jaw | 20-40 | 0.3-0.5 | 80-120 | straight | 30 deg | down over the jaw edge | S |
| Neck (beard part) | 20-40 (no reliable figure found) | 0.3-0.5 | 80-120 | straight | 10-20 deg (very flat) | upper neck down; lower neck UP; meeting line at hyoid/thyroid level; swirls 20-30 mm beside the midline are common; side of neck turns backward | direction V; density K |
| Chest, hairy zones | 10-30 (thorax follicles 22 /cm2 incl. vellus) | 10-30 | 50-90 | wavy/curly, radius 5-15 mm | 20-40 deg | node at the sternal angle: above up, below down; pectoral down-and-medial; ring round the areola pointing away from the nipple | pattern V; numbers K |
| Abdomen, midline strip | 15-30 in a strip 15-30 mm wide, widening to the pubic field; 3-10 lateral | 10-25 | 50-90 | wavy | 20-30 deg | converging on the midline | K |
| Pubic | 30-60 | 20-50 | 100-150, elliptical | tight, radius 2-6 mm | 30-60 deg | down and medially to the root of the penis | K |
| Scrotum, perineum | 5-15 | 10-30 | 60-100 | curly | - | toward the raphe | K |
| Axilla | 40-80 on a patch about 50 x 100 mm | 20-50 | 80-120 | curly, radius 5-10 mm | 30-60 deg | radiating from the apex of the hollow, mostly toward the trunk and down | K |
| Upper arm | 5-15 terminal on back/lateral side; front nearly vellus (follicles 32 /cm2) | 5-15 | 30-60 | straight | 20-30 deg | distally; deltoid up-and-back | K; direction V |
| Forearm, extensor | 15-25 (follicles 18 /cm2) | 10-20 | 40-70 | straight/slightly wavy | 15-30 deg | to the ulnar border; ulnar strip to the olecranon | K; direction V |
| Forearm, flexor | 3-8 | 3-8 | 25-45 | straight | 15-30 deg | distal, then curving to both borders | K; direction V |
| Hand dorsum | 5-15, mostly ulnar two thirds | 5-12 | 40-70 | straight | 15-30 deg | to the ulnar border | K; direction V |
| Fingers | proximal phalanx: tuft of 10-30 hairs on about 10 x 12 mm; middle phalanx 0-10 (mainly ring and middle finger); distal phalanx none; palm none | 4-8 | 40-60 | straight | 20-30 deg | distal-ulnar | K; direction V |
| Thigh, front and lateral | 10-20 (follicles 17 /cm2, mean shaft 29 um); medial thigh 3-8 | 10-25 | 50-80 | wavy | 20-30 deg | distally; back of proximal third up to the gluteal fold | S/K; direction V |
| Shin and calf | 10-18 (follicles 14 /cm2 = lowest of all sites; mean shaft 42 um, largest orifice) ; bald worn patches on the lateral calf and at sock level are common | 10-25 | 60-100 | wavy | 20-30 deg | straight down; ends just above the malleoli | S; direction V |
| Foot dorsum | 3-8 | 5-10 | 40-70 | straight | 20-30 deg | to the lateral border | K; direction V |
| Toes | great toe proximal phalanx tuft 10-30 hairs; toes 2-4: 3-10; sole none | 3-8 | 50-80 | straight | - | distal-lateral | K; direction V |
| Back, shoulders | follicles 29 /cm2, nearly all vellus; terminal 0-3 on shoulder tops and upper back; 3-10 in a lumbosacral patch | 8-15 | 30-60 | straight | 20-30 deg | B1 back rule | S/K; direction V |
| Buttock, natal cleft | 3-10 on the buttock, 20-40 in the cleft | 10-20 | 50-90 | wavy | - | toward the cleft and down | K |
| Ear (tragus, helix rim), nostril | 5-20 hairs per ear at 39; nostril hairs show 1-3 mm inside the rim | 3-8 | 60-100 | straight | - | outward | K |
| VELLUS, face | forehead 292 follicles/cm2 (highest), shaft 16 um | 0.5-2 | under 30 | straight | 30-60 deg | regional stream | S (Otberg) |
| VELLUS, trunk and limbs | 14-32 follicles/cm2 | 0.5-2 | under 30 | straight | 30-60 deg | regional stream | S/K (Otberg) |
| No follicles at all | palms, soles, palmar/plantar side of digits, lip vermilion, nipple, glans, dorsum of distal phalanges, navel pit | - | - | - | - | - | K |

Implementation notes: (1) vellus = shader sheen/fuzz term; fibres only in close-up. (2) Terminal hair: length x lognormal(sigma 0.3); direction jitter +/- 15-25 deg; 10-15 % strays up to 60 deg. (3) Every field needs a soft 15-30 mm falloff at its border. (4) Shaved stubble = dark dot (follicle mouth + cut shaft, 0.1-0.15 mm) + fibre 0.3-2 mm; scalp dots in groups of 1-4 within 0.3 mm. (5) Pooled literature value for all body sites: 1.40 hairs/mm2 = 140 /cm2 (dominated by head/neck), head/neck > trunk > arms > legs (V, PMC5685878).

Chest pattern (Setty, 1,400 white men aged 17-71; V via Wikipedia "Chest hair"): terminal hair in the pectoral area 77 %, sternal 74 %, infraclavicular 63 %, circumareolar ring 16 %. Patterns: pecto-sterno-infraclavicular (PSI) 57 %, pecto-sternal 13 %, hairless 6 %, circumareolar only 6 %, pectoral only 5 %, circumareolo-sternal 5 %, every other under 2 %. Default = PSI: a sternal strip (40-60 mm wide, sternal angle to xiphoid, densest), two pectoral fields (density falling toward the axilla), two infraclavicular patches under the medial ends of the clavicles, joined to the strip.

## B3. Borders by landmarks

| Border | Rule | Mark |
|---|---|---|
| Frontal hairline | Midpoint 60-70 mm above the glabella over the surface (upper third of the face). Line types in men: straight 49 %, straight with central peak 28 %, round 10 %, round with peak 14 %. At 39 add fronto-temporal recessions: line swings back 15-25 mm above the lateral third of each brow, comes forward to a temporal point about 30-40 mm above and slightly behind the lateral canthus. Irregular edge: single hairs for 5-10 mm before full density. | types S; distances K |
| Sideburn | In front of the ear, 15-20 mm wide, ends between tragus and ear-lobe base, merges into the beard. | K |
| Nape hairline | 50-80 mm below the external occipital protuberance (about C3-C4), M- or W-shaped. | K |
| Whorl | 60-70 mm behind the ear-to-ear line over the vertex (6.25 cm and 7.05 +/- 3.3 cm in two series), 10-20 mm off the midline (right 51 %), clockwise from above in 73 % or more. | S |
| Beard, cheek line | From the lower end of the sideburn to the mouth corner, sagging 5-10 mm below the straight line; above it scattered hairs fading over 10 mm. | K |
| Moustache | Nostril sill and alar base down to the vermilion border; laterally 5-10 mm beyond the mouth corner; thinner in the philtrum groove. | K |
| Lower lip / chin | Soul patch 10-15 mm wide under the lower lip midline, a sparse zone each side, then full density on the chin pad. | K |
| Beard, lower limit | Under the jaw down to the laryngeal prominence, thinning over the next 20-30 mm (grooming guides trim 1-2 finger widths above the Adam's apple); laterally a U from below each ear lobe. | S / K |
| Pubic field | Base on the pubic crease, apex up the linea alba toward the navel (diamond), sides along the inguinal folds onto the upper medial thighs. | K |

## B4. Hair on dissection cadavers and in commercial tables

- Teaching cadavers: scalp hair is commonly clipped or shaved at preparation (Boston University lab report: a donor whose long hair "had been shaved away"; S). No universal rule was found; body hair is normally left. A faithful look: shaved scalp with 0.5-2 mm stubble, beard stubble 0.3-0.5 mm, natural body hair. Hair does not grow after death; skin drying only makes stubble stand out more.
- Visible Human Male: whether he was shaved before freezing was not found; check the dataset's own head photographs.
- Anatomage, 3D Organon, Complete Anatomy: NOT verified (the one search returned nothing). General knowledge only: skin layers are shown without fibre hair.

## A. Face

Coordinate rule: all offsets are for an interpupillary distance (IPD) of 64 mm; scale every number by measured IPD / 64. "Up" = superior, "lateral" = away from the midline.

### A1. Lips, philtrum, nostrils, fold (young adult white male norms, Farkas-type direct anthropometry; K unless marked)

| Feature | Number | Landmark rule |
|---|---|---|
| Mouth width (corner to corner) | 54 +/- 3 mm (50-58) | corners lie about under the medial edge of each iris, i.e. 27 mm from the midline |
| Lip line (stomion) below the nose base (subnasale) | 22 +/- 2 mm | the lip line is the horizontal crease detected between nose and chin |
| Upper vermilion height, midline | 8 +/- 1.5 mm | thins linearly to 0 at the corner |
| Lower vermilion height, midline | 9.5 +/- 1.5 mm (upper : lower about 1 : 1.2-1.6) | fullest within 10 mm of the midline; lower border convex downward |
| Cupid's bow | two peaks 5-6 mm either side of the midline (on the philtral columns); central dip 1.5-3 mm below the peaks; from each peak a straight or slightly concave line to the corner | central tubercle of the upper lip hangs 1-2 mm at the midline |
| White roll | 1 mm pale raised rim along the vermilion border | height 0.2-0.4 mm |
| Lip surface | sagittal furrows 0.5-1.5 mm apart, 10-15 visible grooves per half of the lower lip | direction: perpendicular to the lip line |
| Lip colour, living | versus surrounding skin: L* -12 to -18, a* +10 to +14; example skin (224,187,165) -> lip (188,112,108) | - |
| Lip colour, fresh cadaver | pale grey-violet (168,130,135); after hours of drying the exposed part goes dark red-brown (120,80,75) and leathery | upper surface of the body is pale; bluish tinge only |
| Philtrum | length nose base to upper lip border 13-16 mm; width 10-12 mm at the lip, 6-8 mm under the columella; groove depth 1-2.5 mm | columns end at the Cupid's bow peaks |
| Nose | width across the alae 35 +/- 2 mm; height nasion to subnasale 55 +/- 3 mm; tip projection 19-20 mm; columella width 6-7 mm | alae lie about under the medial canthi |
| Nostril | oval 12-15 mm long x 5-8 mm wide, long axis inclined 45-60 deg to the midline (front ends converge); alar wall 4-5 mm thick | inside colour: dark warm brown (60,35,30), not black |
| Nasolabial fold | starts 2-3 mm lateral of the upper alar groove, runs down-lateral 30-40 deg off vertical, ends 10-15 mm lateral of the mouth corner; at 39 depth 1-2 mm, width 3-5 mm | marionette line faint below the corner |

### A2. Closed eyes (K unless marked)

| Feature | Number |
|---|---|
| Palpebral fissure length (medial to lateral canthus) | 30-31 mm in young white men (other adult series 25-29 mm; S: Turkish 24.8-29.1 mm, Korean 27.5 mm) |
| Fissure height, open | 9-11 mm (Korean men 8.3-8.4 mm; S) |
| Medial canthus relative to pupil centre | 15.5 mm medial, 2-3 mm lower (intercanthal distance 33 +/- 3 mm) |
| Lateral canthus relative to pupil centre | 13.5 mm lateral, 0-1 mm lower (outer canthal distance 91 +/- 3 mm); lies 5-7 mm medial to the bony lateral orbital rim and about 10-12 mm behind the corneal apex |
| Canthal tilt | lateral canthus about 2 mm higher than the medial one = 3-5 deg upward (men flatter than women) |
| Closed-lid line | arc through both canthi, lowest point 4-5 mm below the pupil centre (near the lower corneal edge); the upper lid does the travel (about 10 mm) |
| Upper lid crease | 7-8 mm above the lash line at the centre in men (8-10 in women), 4-5 mm medially, 5-6 mm laterally; in the closed eye a faint line parallel to the lid margin |
| Lower lid crease | 3-5 mm below the lash line, fading laterally |
| Corneal bulge under the closed lid | dome 11-12 mm wide, 2.5-3 mm proud of the sclera curve; eyeball diameter 24 mm |
| Lid skin | thinnest skin of the body (under 1 mm); fine horizontal wrinkles 0.5-1 mm apart; colour darker and cooler (section D) |
| Cadaver | lids often 1-3 mm apart, globe slightly sunken; keep closed for the app |

### A3. Eyebrows

| Feature | Number / rule | Mark |
|---|---|---|
| Length (width) | 47.3 +/- 4.6 mm in white male models; 55 mm in Korean men | S |
| Height (thickness) | 8-10 mm at head and body (Korean mean 8.3 mm), tapering to 2-4 mm at the tail | S / K |
| Position | male brow is flat and low, lying ON the supraorbital rim; lower border 11.2 mm above the lateral canthus (mean) | S |
| Start | medial end vertically above the medial canthus / alar base, 13-17 mm from the midline (gap between brows 25-30 mm) | K |
| Peak | at the lateral two thirds of the length (about above the lateral edge of the iris to the lateral canthus), only 2-4 mm above the head-to-tail line in men | S |
| Tail | ends on the line alar base -> lateral canthus, 8-12 mm beyond the lateral canthus, at the height of the lower edge of the head or slightly above | K |
| Hair count | 300-500 per brow | K/S |
| Hair length, diameter | 5-12 mm (longest in the body), 50-90 um, exit angle 10-15 deg (S), growth about 0.15 mm/day | K |
| Direction | head (medial 5-8 mm): 1-2 staggered rows pointing straight UP, fanning 0-30 deg laterally; body: upper rows point down-lateral, lower rows up-lateral, interlocking on a ridge line (herringbone, starting above the medial edge of the iris); tail: horizontal lateral and slightly down. Kidd's "break" at the junction medial third / lateral two thirds. | S (PMC5561712) + V (Kidd) |
| Colour | same as scalp or one step darker: (58,42,30) | K |

### A4. Eyelashes

Upper 90-160 lashes in 5-6 rows, 8-12 mm; lower 75-80 in 3-4 rows, 6-8 mm; shaft 70-80 um at the root, 80-120 um mid, 5-10 um at the tip (S: Wikipedia "Eyelash", StatPearls, lash dossier). K: longest in the middle third, shorter toward both canthi, none in the medial 5-6 mm of each lid; darkest hair of the body; growth 0.12-0.14 mm/day; one study counted far fewer (72 upper, 38 lower; S), so 100 upper / 60 lower is a safe render count. Closed eye: upper lashes lie over the lower lid, pointing forward and 10-30 deg down.

### A5. Ears (K)

Length 62-65 mm, width 35-36 mm, long axis tilted back 15-20 deg, top at brow level, bottom at nose-base level, standing 15-20 mm off the head. Redder parts: helix rim and lobule (thin skin, dense vessels): a* +4 to +6 against the cheek, slightly translucent (strong subsurface scattering when backlit). Concha and antihelix paler/yellower. Supine cadaver: the back of the helix and the lobule are dependent and may be livid purple.

Sources for A: Farkas norms summary https://pmc.ncbi.nlm.nih.gov/articles/PMC6571015 and https://pubmed.ncbi.nlm.nih.gov/35290428/ (numbers themselves K) ; male brow https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_2771635744 , https://read.qxmd.com/read/16052142/the-male-eyebrow-a-topographic-anatomic-analysis ; brow hair direction https://pmc.ncbi.nlm.nih.gov/articles/PMC5561712/ ; eyelids https://pmc.ncbi.nlm.nih.gov/articles/PMC5586704 , https://scielo.br/j/abo/a/hfNtj7vL7WJhmkDYwzfjmjP/abstract/?lang=en ; lashes https://en.wikipedia.org/wiki/Eyelash

## C. Skin features

### C1. Male nipple and areola

| Item | Number | Mark |
|---|---|---|
| Areola diameter | 26.6-28 mm round (one series: oval 27 x 20 mm or round 23 mm) | S (Beckenstein 1996; Shulman 2001; 2018 series) |
| Nipple diameter | 6.9 mm | S |
| Nipple projection | 2-4 mm; areola flush or 0.5-1 mm raised, with 5-12 small bumps of 1-2 mm | K |
| Level | 4th intercostal space in 75 %, 5th in 23 % | S |
| Distances | sternal notch to nipple 20 cm; nipple to nipple 21 cm (10.5 cm from the midline); for a 180 cm / 90 kg chest use 22-24 cm apart | S; scaling K |
| Extra rule | about 2-3 cm medial to the lateral border and 2-3 cm above the lower border of pectoralis major; near the midclavicular line | K |
| Colour | living: brown-pink (176,120,105), L* about -15 against the chest; cadaver: grey-brown (150,115,105); nipple slightly darker than areola; 5-20 terminal hairs on the rim | K |

### C2. Navel

Midline. Xiphoid-to-navel = 56.4 +/- 0.9 % of the xiphoid-to-pubis distance (S, 50 men / 50 women); in male models the ratio (xiphoid to navel) / (navel to lower abdominal crease) is 1.68 +/- 0.38 (S). Level: top of the iliac crests (L3-L4 disc to L4; K), 1-3 cm lower in heavy men. Shape (K): oval pit 15-20 mm high x 10-15 mm wide, 5-15 mm deep, with a skin hood on the upper edge; vertical oval in lean men, rounder or horizontal with more belly fat; inside darker and redder than the abdomen (L* -8, a* +3), hairless pit, hair converging on it.

### C3. Nails

| Item | Number | Mark |
|---|---|---|
| Fingernail width / length ratio, men, thumb to little finger | 1.04, 0.94, 0.95, 0.95, 0.93 | S (300 Korean adults) |
| Transverse curvature radius, men | 11.4, 8.9, 8.8, 7.3, 5.8 mm | S |
| Width (men, approx.) | thumb 15-17, index 11-13, middle 12-13, ring 11-12, little 9-10 mm; length = width / ratio above | K |
| Free edge | 0.5-2 mm, off-white (235,228,215), translucent | K |
| Lunula | thumb: almost always visible, 3-4 mm (20-25 % of the length); smaller on index and middle; usually hidden on the little finger; colour (240,222,212) | K |
| Plate | 0.5 mm thick on fingers, 1.0-1.3 mm on toes; fine longitudinal ridges 0.1-0.2 mm apart; glossy (roughness 0.2-0.3) | K |
| Nail bed colour | living pink (232,170,160); cadaver pale grey-violet to bluish (185,165,172); toenails yellower (225,205,165) | K |
| Toenails | great toe 16-20 mm wide x 12-16 long; toes 2-4: 8-10 x 6-8; little toe 5-7 x 4-5 | K |
| Nail folds | proximal fold with 0.5-1 mm cuticle; lateral folds 1-1.5 mm high; skin of the folds redder (a* +3) | K |

### C4. Creases, ridges, sole (K unless marked)

| Item | Number / rule |
|---|---|
| Dorsal knuckle wrinkles, PIP joint | oval pad 12-15 mm long, 6-10 transverse folds 0.8-1.5 mm apart, deep ones 0.3-0.5 mm; concentric at the pad edges |
| DIP joint | 3-5 transverse folds 0.7-1.0 mm apart |
| MCP knuckles | shallow dimpled wrinkles; redder and slightly darker over the bone (section D) |
| Palmar finger creases | proximal crease at the web (15-20 mm distal to the MCP joint), middle crease double over the PIP joint, distal crease single over the DIP joint; each 0.3-0.6 mm wide |
| Palm creases | distal transverse ("heart"), proximal transverse ("head"), thenar ("life") curving round the thumb base, often a middle longitudinal; 2-3 wrist creases 8-12 mm apart |
| Friction ridges | period 0.45-0.50 mm on finger pads in men, 0.5-0.65 mm on palm and sole; ridge height 40-80 um; sweat pores on the ridge tops every 0.4-0.5 mm; male ridge density 11-13 ridges per 25 mm2 (S) |
| Finger patterns | loops about 60-65 %, whorls 30-35 %, arches 5 % |
| Sole | horny layer 0.6-1.5 mm, yellow callus on heel and ball, pink arch; ridges transverse on the ball, longitudinal in the arch; no hair, no sebaceous pores |

Sources for C: https://pubmed.ncbi.nlm.nih.gov/8722981/ ; https://www.qxmd.com/r/11743381 ; https://pubmed.ncbi.nlm.nih.gov/29329370/ ; navel https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9592660/ and https://thieme-connect.de/products/ejournals/html/10.1055/s-0040-1721869 ; nails https://www.thieme-connect.de/products/ejournals/html/10.5999/aps.2015.42.6.753 ; ridge density https://pmc.ncbi.nlm.nih.gov/articles/PMC8689342

## D. Colour zones

Measured anchors (S): redness depends mostly on the BODY SITE, lightness and yellowness mostly on the person; forehead is the reddest site and the inner arm the least red (Leeds study); face has higher a* and lower L* than the forearm; cheek a* 11.9 against inner arm a* 8.2 in one series (difference +3.7); erythema index highest on the forehead. No measured map for nose, ears, knees etc. was found: the table below is K (order-of-magnitude defaults for a fair-skinned brown-haired man).

Baseline (untanned trunk, living): CIELAB about L* 68, a* 9, b* 16 = sRGB about (224,187,165).

| Zone | dL* | da* | db* | Note |
|---|---|---|---|---|
| Inner upper arm, medial thigh, buttock, flank | +2 to +4 | -2 to -3 | -1 | palest skin of the body |
| Face overall | -2 to -4 | +3 to +5 | +1 | exposed, more blood |
| Forehead | -2 | +4 | +2 to +3 | reddest and yellowish |
| Cheeks (malar), chin | -2 | +4 to +6 | 0 | flush area, patchy |
| Nose tip and alae | -3 | +5 to +7 | 0 | tiny vessels on the alae |
| Ears (helix, lobule) | -2 | +4 to +6 | 0 | |
| Lips | -12 to -18 | +10 to +14 | -2 | |
| Eyelids, under the eyes | -5 to -8 | +1 | -3 to -4 | thin skin, bluish-brown |
| Beard shadow (shaved) | -3 to -6 | -1 to -2 | -3 to -5 | blue-grey |
| Neck V, nape | -4 to -6 | +3 to +4 | +3 | sun; under the chin stays pale |
| Forearm dorsum, hand dorsum | -4 to -6 | +1 to +2 | +3 to +4 | tan |
| Knuckles | -3 to -5 | +3 to +5 | +1 | |
| Elbows, knees | -4 to -8 | +2 to +4 | +2 | thick, dry, darker |
| Palms, finger pads | +3 to +5 | +3 to +6 (mottled) | +2 | no tan; pink over thenar, hypothenar, pads |
| Soles, heel, ball | +2 | +2 | +6 to +10 | yellow horn |
| Axilla, groin fold | -5 to -8 | +2 to +3 | +2 | more pigment |
| Areola, nipple | -12 to -16 | +4 to +6 | +2 | |
| Scrotum, penis, perianal | -8 to -15 | +3 to +5 | +3 | |
| Shins | +1 | -1 | 0 | shinier (lower roughness), dry |
| Feet and hands versus trunk | -2 | +2 to +3 | 0 | in life redder/bluer; in a cadaver see below |

Superficial veins (K): dorsum of hand (network, 2-3 mm wide), radial and ulnar side of the wrist and front of the forearm (1-4 mm), elbow fold (3-5 mm), cephalic vein along the biceps and the delto-pectoral groove in lean men, dorsum of foot (arch 2-4 mm), in front of the medial malleolus (3-4 mm), temple (1.5-2 mm), inner thigh and behind the knee. Colour against skin: dL* -3 to -6, da* -4 to -7, db* -4 to -8 (blue-green grey, e.g. skin (224,187,165) -> vein (198,186,178)); edges blurred over 1-2 mm. On the upper surface of a cadaver the veins are empty and FLAT (no relief); keep only the colour at half strength.

Naevi and spots: a typical white adult carries roughly 20-40 common naevi of 2 mm or more (K; counts rise through youth and fall after the fourth decade, S; a Chinese cohort had median 30, range 1-137, S). Men have most on the TRUNK, and naevi of 5 mm or more sit on intermittently sun-exposed skin (S). Default: N = 25 +/- 10; diameter lognormal, median 3 mm, range 2-6 mm; 60 % trunk (back > chest and abdomen), 20 % arms, 10 % legs, 10 % face and neck; colour from (150,100,70) to (95,60,45); soft 0.3 mm edge; 20 % raised 0.3-1 mm. Freckles (K): 1-3 mm, (200,150,115), nose, cheeks, shoulders, forearms, 0-5 per cm2, few for a brown-haired man. Cherry angiomas (K): 5-10 bright red 1-3 mm dots on the trunk at about 40.

Death, first day (S: forensic reviews; colours K):

| Change | Timing | Look | sRGB example |
|---|---|---|---|
| Pallor | 15-30 min | upper surface loses red: da* -5 to -7, dL* +2 to +4, waxy, slightly yellow-grey | living (224,187,165) -> (214,196,178) |
| Livor mortis (lividity) | starts 20-30 min, clearly visible about 2 h, fixed after 8-12 h (6-12 h in some texts) | red-purple on the lowest parts; supine: nape, back, loins, back of arms and thighs, back of ear; upper edge is a soft band at about the mid-axillary line | full (150,95,110); edge (190,140,145) |
| Contact blanching | with livor | pale patches where the body rests: back of head, shoulder blades, buttocks/sacrum, calves, heels; also strap and crease lines | (222,208,190) |
| Cold storage | - | lividity becomes pinker/brighter in the cold | (185,110,120) |
| Lips | hours | pale grey-violet, then dark and leathery where dry | (168,130,135) -> (120,80,75) |
| Nail beds, fingertips | hours | pale to bluish; fingertips may wrinkle and darken as they dry | (185,165,172) |
| Not in the first day when chilled | later | green abdomen, marbling of veins, skin slip: do not show | - |

The search did not return a source for "lips and nail beds bluish" specifically; it is standard forensic description (K).

Sources for D: https://eprints.whiterose.ac.uk/id/eprint/100718/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC7732761 ; https://library.scconline.org/v032n01/1 ; naevi https://academic.oup.com/bjd/article/184/2/289/6599752 , https://link.springer.com/article/10.1007/s13555-022-00806-x , https://medicaljournals.se/acta/content/html/10.2340/00015555-2172 ; livor https://pmc.ncbi.nlm.nih.gov/articles/PMC12450430/ , https://www.osmosis.org/answers/livor-mortis

## E. Skin micro-relief

| Layer | Region | Size | Spacing / frequency | Depth | Mark |
|---|---|---|---|---|---|
| Visible pores | nose, medial cheek, chin, forehead | 250-500 um across (visible to the eye) | reported 200-300 follicle openings per cm2 on the face (spacing 0.6-0.7 mm); enlarged visible pores on the cheek 10-90 per cm2 (spacing 1-3 mm) | 50-150 um pit | S (Flament 2015 and review); depth K |
| Nose | tip and alae | 300-500 um | 0.5-0.8 mm | 100-150 um | K |
| Medial cheek | within 30 mm of the nose | 250-400 um | 0.8-1.5 mm, fading to none at the lateral cheek | 50-100 um | K |
| Forehead | - | 150-300 um | 0.6-1.0 mm (follicles 292 /cm2 = 0.59 mm) | 30-80 um | S/K |
| Follicle openings, trunk and limbs | back, chest, arms, thigh, calf | orifice 66 um on the forehead up to 165 um on the calf | 14-32 per cm2 = 1.8-2.7 mm | 20-50 um; a small raised cone round each terminal hair on the limbs | S/K (Otberg) |
| Sweat pores | everywhere | 50-80 um | 100-200 per cm2 on the body, 500-700 per cm2 on palm and sole | not visible beyond close-up | K |
| Primary lines | all hairy skin | 30-100 um deep (some sources 20-200 um), 50-100 um wide | polygons (triangles, rhombs) with sides 0.3-1.0 mm = 1-3 cycles/mm | S |
| Secondary lines | inside the polygons | 5-40 um deep | 0.1-0.3 mm = 3-10 cycles/mm | S |
| Anisotropy | - | lines become deeper, fewer and more parallel with age and along the tension direction | elongate the polygon cell 1.5-2.5 x along the Langer direction | S/K |

Polygon size by region (K): face 0.2-0.5 mm, nearly isotropic, pores at the crossings; forearm front 0.3-0.6 mm; forearm back and hand dorsum 0.8-2 mm rhombs stretched across the limb; abdomen and back 0.5-1.0 mm stretched along the tension lines; elbows and knees 1-2 mm coarse plates; scalp 0.3-0.5 mm with follicle groups; lips and palms/soles use their own patterns (C4).

Tension / cleavage lines for the anisotropy direction (S: DermNet, review in Plast Aesthet Res; K for detail):

| Region | Langer (cleavage) direction | Wrinkle direction (relaxed skin tension lines, across the muscle pull) |
|---|---|---|
| Forehead | - | horizontal; 3-5 lines 8-12 mm apart, 0.1-0.4 mm deep at 39, slightly wavy, dipping at the midline |
| Glabella | - | 2 vertical lines 8-12 mm apart, 10-15 mm long |
| Eye corner | - | 3-5 lines radiating from the lateral canthus over a 60-90 deg fan, 10-20 mm long, 2-3 mm apart at 5 mm from the canthus |
| Lower lid | - | 2-3 fine arcs parallel to the lid margin |
| Lips, around the mouth | - | radial to the mouth (vertical on the upper lip); nasolabial oblique |
| Neck | transverse (same as wrinkles) | 2-3 horizontal "necklace" lines 15-25 mm apart |
| Chest | roughly transverse, bending up toward the axilla over the pectorals | - |
| Abdomen | transverse, sloping down-medially below the navel (parallel to the inguinal fold) | - |
| Back | transverse on thoracic and lumbar back, oblique over the shoulders, curving round the shoulder blade | - |
| Limbs | mostly longitudinal on thigh, distal limbs, elbow fold and wrist (S) | transverse across every joint: knuckles (C4); elbow tip: concentric/transverse folds 1.5-3 mm apart on a 40 x 50 mm patch; knee: transverse folds 2-4 mm apart over a 60 x 60 mm patch above and on the patella; wrist front: 2-3 creases 8-12 mm apart |

Layers for a procedural normal function (period in mm, amplitude in mm):

| Layer | Period | Amplitude | Where |
|---|---|---|---|
| Secondary lines | 0.1-0.3 | 0.005-0.04 | everywhere but lips, palms, soles |
| Primary polygon net (Voronoi/cell edges) | 0.3-1.0 (table above) | 0.03-0.1 | everywhere, stretched along the Langer direction |
| Pores (Poisson points, pits) | 0.5-1.5 face; 1.8-2.7 body | 0.05-0.15 face; 0.02-0.05 body | density maps above |
| Friction ridges | 0.45-0.65 | 0.04-0.08 | palms, soles, digit pads |
| Lip furrows | 0.5-1.5 | 0.05-0.15 | vermilion |
| Joint wrinkles | 0.8-1.5 fingers; 1.5-4 elbow/knee | 0.1-0.5 | joint patches |
| Expression lines | 8-12 forehead; 2-3 crow's feet | 0.1-0.4 | face |
| Goose-bump cones round terminal hairs | at each follicle | 0.03-0.08, 0.3-0.5 wide | forearms, legs, chest |

Sources for E: https://pubmed.ncbi.nlm.nih.gov/25733918/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC4337418 (pores) ; https://pmc.ncbi.nlm.nih.gov/articles/PMC9838641 and https://orbi.uliege.be/bitstream/2268/8627/1/FROM%20SKIN.pdf (micro-relief line depths) ; https://pro.dermnetnz.org/topics/skin-tension-lines ; https://www.oaepublish.com/articles/2347-9264.2020.14 ; https://www.exploreplasticsurgery.com/relaxed-skin-tension-lines-of-the-face-and-scar-revision/

## 9. Not verified in this session (treat as defaults, check before quoting)

1. Height 180 cm and weight 90 kg of the Visible Human Male (not on any page that could be read; Spitzer 1996 full text is PDF only).
2. Whether the Visible Human Male was shaved, and what Anatomage / 3D Organon / Complete Anatomy show for hair.
3. Otberg per-site follicle densities other than the forehead (back 29, thorax 22, upper arm 32, forearm 18, thigh 17, calf 14 per cm2): from memory of the paper; forehead 292 and shaft 16/29/42 um were confirmed second-hand.
4. All TERMINAL body hair densities, lengths and diameters marked K (chest, abdomen, pubic, axilla, arms, hands, legs, feet, back): no phototrichogram table for men could be opened (Loussouarn et al. 2016 gives growth 180-485 um/day only in the abstract).
5. Beard borders and the cheek/moustache/chin directions (K; only the neck reversal is from Kidd and shaving guides). Beard densities come from one secondary site (keratin.com).
6. Abdomen and axilla hair directions (K).
7. Farkas face numbers (mouth 54 mm, vermilion 8 / 9.5 mm, fissure 30-31 mm, canthus offsets, crease 7-8 mm, 2 mm canthal tilt): quoted from memory; the searches did not show them.
8. Eyebrow hair count 300-500, brow hair diameter, all hair colours (sRGB are art-directed).
9. Absolute nail sizes, lunula, friction-ridge period 0.45-0.50 mm, palm/sole details (K).
10. The whole colour-zone table and the vein table (K); only the "forehead reddest, inner arm least red, face redder and darker than forearm, cheek a* +3.7 over inner arm" statements are sourced.
11. Naevus default 20-40 (K; sourced only: trunk-dominant in men, size threshold 2 mm, Chinese median 30).
12. Pore spacing by facial region, polygon sizes, wrinkle counts and amplitudes (K); only pore size 250-500 um, face 200-300 /cm2, cheek 10-90 /cm2 and line depths 30-100 / 5-40 um are sourced.
13. Death colours as sRGB (K); timings are sourced.
