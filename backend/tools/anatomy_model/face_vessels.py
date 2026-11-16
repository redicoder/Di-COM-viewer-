"""The face's vessels and nerves, drawn on his own head.

No open data set has the facial artery and vein, the superficial temporal artery or the branches of the facial
and trigeminal nerves as shapes, and a frozen CT without contrast does not show them
(docs/research/head_anatomy_data.md, 4.1 and 5.8). So they are GENERATED, as the muscles of expression are
(face_muscles.py): each is a tube along the course the textbooks give, from landmark to landmark, and the
landmarks are HIS: the heads of his mandible's condyles, the front edge of his masseter where it meets the
mandible's lower border, the border itself, his eyes, nose and lip line. Between the landmarks a tube keeps a
depth under his skin and stays out of his bone and off his chewing muscles. They show where these vessels and
nerves run in a head of his shape; they are not a reading of his own. Every one carries info["generated"].

Drawn, each side: the facial artery (winding, as it does) and vein, the superficial temporal artery with its
frontal and parietal branches, the facial nerve's trunk and its five branches (temporal, zygomatic, buccal,
marginal mandibular, cervical), and the three nerves of the face's skin where they leave the bone (supraorbital,
infraorbital, mental).
"""
from __future__ import annotations

import numpy as np

from . import bonehub, face_muscles, head_layers
from .common import Body, Structure
from .zones import MM

ARTERY, VEIN, NERVE = (0.66, 0.20, 0.18), (0.36, 0.40, 0.58), (0.90, 0.84, 0.62)
STEP_MM = 1.2                         # a tube's rings
COVER_MM = 1.8                        # skin over a tube, at the least
BED_MM = 26.0                         # bone or muscle further under the skin than this is not what a tube lies on


def tube(points: np.ndarray, radius_mm: np.ndarray, sides: int = 8):
    """A closed tube along `points` (n, 3 in metres) with a radius (mm) at each: vertices, faces wound outward."""
    p = np.asarray(points, np.float64)
    n = len(p)
    t = np.gradient(p, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    first = np.cross(t[0], [0.0, 1.0, 0.0])
    if np.linalg.norm(first) < 0.2:
        first = np.cross(t[0], [1.0, 0.0, 0.0])
    normal = [first / np.linalg.norm(first)]
    for i in range(1, n):                                                     # the frame carried along without twisting
        v = normal[-1] - t[i] * (normal[-1] @ t[i])
        normal.append(v / max(np.linalg.norm(v), 1e-12))
    normal = np.array(normal)
    other = np.cross(t, normal)
    angle = np.linspace(0.0, 2 * np.pi, sides, endpoint=False)
    r = np.broadcast_to(np.asarray(radius_mm, np.float64), (n,)) * MM
    ring = p[:, None, :] + (np.cos(angle)[None, :, None] * normal[:, None, :] + np.sin(angle)[None, :, None] * other[:, None, :]) * r[:, None, None]
    v = np.concatenate([ring.reshape(-1, 3), p[:1], p[-1:]])
    faces = []
    for i in range(n - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            c, d = a + sides, b + sides
            faces += [(a, b, d), (a, d, c)]
    start, end = n * sides, n * sides + 1
    for j in range(sides):
        faces.append((start, (j + 1) % sides, j))
        faces.append((end, (n - 1) * sides + j, (n - 1) * sides + (j + 1) % sides))
    f = np.array(faces, np.int64)
    a, b, c = (v[f[:, k]] - p.mean(axis=0) for k in range(3))
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
        f = f[:, ::-1]
    return v.astype(np.float32), f


def bed_map(maps: face_muscles.Maps, meshes: list) -> np.ndarray:
    """What a tube must stay outside of, by direction (mm from the head's middle): his skull and mandible, and the
    given meshes (the chewing muscles) where they stand out over the bone."""
    bed = maps.bone.copy()
    for v, f in meshes:
        points = face_muscles._dense(np.asarray(v, np.float64), np.asarray(f), 0.0008)
        offset = points - maps.centre
        r = np.linalg.norm(offset, axis=1)
        bed = np.maximum(bed, face_muscles._splat(bed.shape, maps.cell(offset / r[:, None]), r * 1000.0, least=False))
    return bed


def course(maps: face_muscles.Maps, bed: np.ndarray, stops: list, width_mm: float, wind_mm: float = 0.0) -> np.ndarray:
    """The centre line of a vessel or nerve through `stops`: (a point in glTF metres, its depth under the skin in
    mm or None for "where the point itself is", free). Between the stops the direction from the head's middle is
    turned evenly and the depth under the skin changes evenly; the line keeps COVER_MM of skin over the tube and
    stays out of the bed (bone, chewing muscles) except towards a stop marked free (a deep stretch: behind the
    jaw's ramus, under the mandible). `wind_mm`: it winds from side to side by this much. Returns points (n, 3) metres."""
    dirs = np.array([maps.direction(p) for p, _, _ in stops])
    skin_at = maps.radius(maps.skin, dirs)
    depth = np.array([skin_at[k] - np.linalg.norm(np.asarray(p) - maps.centre) * 1000.0 if d is None else d for k, (p, d, _) in enumerate(stops)])
    free = np.array([1.0 if s[2] else 0.0 for s in stops])
    at = maps.centre + dirs * ((skin_at - depth)[:, None] * MM)
    legs = np.linalg.norm(np.diff(at, axis=0), axis=1) * 1000.0
    total = float(legs.sum())
    n = max(4, int(np.ceil(total / STEP_MM)) + 1)
    t = np.linspace(0.0, 1.0, n)
    edges = np.concatenate([[0.0], np.cumsum(legs)]) / max(total, 1e-9)
    line = np.zeros((n, 3))
    for k in range(len(legs)):
        mine = (t >= edges[k] - 1e-12) & (t <= edges[k + 1] + 1e-12)
        line[mine] = face_muscles._slerp(dirs[k], dirs[k + 1], (t[mine] - edges[k]) / max(edges[k + 1] - edges[k], 1e-9))
    for _ in range(4):                                                        # the corners at the stops rounded
        line[1:-1] = (line[:-2] + 2 * line[1:-1] + line[2:]) / 4
        line /= np.linalg.norm(line, axis=1, keepdims=True)
    if wind_mm > 0:
        tangent = np.gradient(line, axis=0)
        side = np.cross(line, tangent)
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-12)
        sway = np.sin(2 * np.pi * t * total / 17.0) * np.sin(np.pi * t) ** 0.5
        line = line + side * (sway * wind_mm / 95.0)[:, None]
        line /= np.linalg.norm(line, axis=1, keepdims=True)
    under = np.interp(t, edges, depth)
    loose = np.interp(t, edges, free)
    skin = maps.radius(maps.skin, line)
    known = skin > 20.0
    if known.any() and not known.all():                                       # a direction that met no skin: its neighbours' skin
        skin = np.interp(np.arange(n), np.nonzero(known)[0], skin[known])
    radius = skin - under
    floor = maps.radius(bed, line)
    on_bed = (floor > 20.0) & (skin - floor < BED_MM) & (loose < 0.5)
    radius = np.where(on_bed, np.maximum(radius, floor + width_mm / 2 + 0.4), radius)
    radius = np.minimum(radius, skin - (width_mm / 2 + COVER_MM))
    points = maps.centre + line * (radius[:, None] * MM)
    for _ in range(3):
        points[1:-1] = (points[:-2] + 2 * points[1:-1] + points[2:]) / 4
    return points


def _structure(name: str, kind: tuple, tubes: list, note: str) -> Structure:
    v = np.concatenate([t[0] for t in tubes])
    f = np.concatenate([t[1] + k for t, k in zip(tubes, np.cumsum([0] + [len(t[0]) for t in tubes[:-1]]))])
    bake = np.tile(np.array([240, 6, 82, 150], np.uint8), (len(v), 1))
    albedo = np.tile(np.round(np.array(kind) * 255).astype(np.uint8), (len(v), 1))
    what = "artery" if kind is ARTERY else "vein" if kind is VEIN else "nerve"
    return Structure(name, "organs", v, f.astype(np.uint32), kind, bake=bake, albedo=albedo,
                     info={"class": "organ", "kind": what, "generated": True, "note": note,
                           "source": "drawn along its textbook course between landmarks of his own skull, jaw and face (docs/research/head_anatomy_data.md 5.8)"})


def build(body: Body, log=print) -> list[Structure]:
    """The face's vessels and nerves of both sides; [] where the face, the jaw's joint or the masseter are not at hand."""
    got = face_muscles.prepare(body, log)
    m = getattr(body, "mouth", None)
    if got is None or m is None or m.condyles is None:
        return []
    face, maps = got
    lay = face_muscles.Layout(face, maps, m.lip_w)
    chewing = {s.name: s for s in head_layers.structures(body, "muscles", log) if s.name.split(" ", 1)[-1] in ("masseter", "temporalis")}
    placed, _, _ = bonehub.load_or_build(body, None, log)
    jaw = next((body.to_gltf(v, f)[0] for _, name, v, f in placed if name == "mandible"), None)
    if jaw is None:
        return []
    bed = bed_map(maps, [(s.v, s.f) for s in chewing.values()])
    ju, jw, jd = face.local(jaw)
    lip, sub, half = float(m.lip_w(0.0)), face.subnasale_w, face.half_ipd
    ex, ey, ez = face.ex * MM, face.ey * MM, face.ez * MM
    out = []

    def line(stops, width, taper=1.0, wind=0.0):
        points = course(maps, bed, stops, width, wind)
        return tube(points, np.linspace(width / 2, width / 2 * taper, len(points)))

    def skin(u, w, depth):
        return (lay.on_skin(u, w), depth, False)

    for side, sg, condyle in (("right", -1.0, m.condyles[0]), ("left", 1.0, m.condyles[1])):
        ew = face.eye_w[side]
        masseter = chewing.get(f"{side} masseter")
        if masseter is None:
            continue
        # Where the masseter's front edge meets the mandible's lower border: there the facial artery and vein cross the jaw.
        mu, mw, md = face.local(masseter.v)
        cross_d = float(md[mw < mw.min() + 12.0].max()) + 2.0
        here = (np.sign(ju) == sg) & (np.abs(jd - cross_d) < 2.5)
        if not here.any():
            continue
        border_w = float(jw[here].min())
        low = here & (jw < border_w + 4.0)
        border = face.origin + ex * float(sg * np.abs(ju[low]).max()) + ey * border_w + ez * cross_d

        def by(point, across=0.0, up=0.0, forward=0.0):
            return point + ex * (sg * across) + ey * up + ez * forward

        # The facial artery: up out of the neck round the jaw's border, winding to beside the mouth's corner, beside the nose, to the eye's inner corner.
        out.append(_structure(f"{side} facial artery", ARTERY, [line(
            [(by(border, -10, -9, -14), None, True), (by(border, 1.5, -1.5, 0), None, True), (by(border, 2.5, 9, 5), None, False), skin(sg * 40.0, lip + 2.0, 9.0),
             skin(sg * 25.0, sub + 2.0, 7.0), skin(sg * 17.5, sub + 22.0, 4.5), skin(sg * (half - 19.0), ew - 3.0, 3.6)], 2.8, taper=0.5, wind=1.8)],
            "it crosses the jaw's border at the masseter's front edge; its upper end is the angular artery"))
        out.append(_structure(f"{side} facial vein", VEIN, [line(
            [skin(sg * (half - 15.0), ew - 7.0, 3.6), skin(sg * 27.0, sub + 6.0, 6.5), skin(sg * 43.0, lip + 5.0, 8.5), (by(border, 3.0, 4.0, -7.0), None, False),
             (by(border, 0.0, -15.0, -17.0), None, True)], 3.2, taper=1.25)], "behind the artery and straighter"))
        # The superficial temporal artery: up before the ear over the root of the cheek bone's arch, then its two branches.
        split = (by(condyle, 0, 40, 6), 3.6, False)
        out.append(_structure(f"{side} superficial temporal artery", ARTERY, [
            line([(by(condyle, 0, -22, -9), 16.0, True), (by(condyle, 0, -4, 2), 6.0, False), (by(condyle, 0, 14, 4), 4.2, False), split], 2.4, taper=0.85, wind=0.6),
            line([split, (by(condyle, 0, 60, 34), 3.4, False), skin(sg * 44.0, ew + 44.0, 3.4)], 2.0, taper=0.55, wind=1.2),
            line([split, (by(condyle, 0, 74, -4), 3.4, False), (by(condyle, 0, 104, -24), 3.4, False)], 2.0, taper=0.55, wind=1.0)],
            "with its frontal and parietal branches; it crosses the arch about a centimetre in front of the ear"))
        # The facial nerve: out of the skull behind the jaw's joint, dividing in the parotid, its branches forward over the masseter.
        division = (by(condyle, 0, -19, -3), 11.0, True)
        out.append(_structure(f"{side} facial nerve", NERVE, [line([(by(condyle, -4, -12, -15), None, True), division], 2.6)], "its trunk, from the stylomastoid foramen to where it divides"))
        for branch, stops in (("temporal", [(by(condyle, 0, 6, 22), 6.5, False), skin(sg * 46.0, ew + 21.0, 4.6)]),
                              ("zygomatic", [(by(condyle, 0, -6, 35), 8.0, False), skin(sg * 50.0, ew - 12.0, 5.0)]),
                              ("buccal", [(by(condyle, 0, -22, 35), 9.0, False), skin(sg * 41.0, lip + 10.0, 7.0)]),
                              ("marginal mandibular", [(by(condyle, 0, -45, 10), 9.0, False), (by(border, 3.0, 2.0, -2.0), 6.5, False), skin(sg * 30.0, lip - 20.0, 5.0)]),
                              ("cervical", [(by(condyle, 0, -50, 0), 8.0, False), (by(condyle, 0, -86, 12), 5.0, False)])):
            out.append(_structure(f"{side} facial nerve, {branch} branch", NERVE, [line([division] + stops, 1.5, taper=0.55)], ""))
        # The skin's nerves where they leave the bone: on one upright line 26 mm from the midline.
        u0 = sg * 26.0
        notch = (lay.on_bone(u0, ew + 13.0), None, False)
        out.append(_structure(f"{side} supraorbital nerve", NERVE, [line([notch, skin(u0 - sg * 2.0, ew + 40.0, 4.2), skin(u0 - sg * 4.0, ew + 72.0, 4.0)], 1.5, taper=0.5),
                                                                    line([notch, skin(u0 + sg * 8.0, ew + 36.0, 4.2), skin(u0 + sg * 12.0, ew + 64.0, 4.0)], 1.3, taper=0.5)],
                              "from the notch in the eye socket's upper rim"))
        hole = (lay.on_bone(u0, ew - 25.0), None, False)
        out.append(_structure(f"{side} infraorbital nerve", NERVE, [line([hole, skin(u0 + sg * 1.0, ew - 17.0, 4.0)], 1.3, taper=0.5),
                                                                    line([hole, skin(sg * 18.0, sub + 9.0, 4.5)], 1.3, taper=0.5),
                                                                    line([hole, skin(sg * 19.0, lip + 7.0, 5.0)], 1.5, taper=0.5)],
                              "from its foramen under the eye socket's lower rim, to the lower lid, the nose's side and the upper lip"))
        chin = (np.sign(ju) == sg) & (np.abs(ju - u0) < 2.5)
        if chin.any():
            foramen = (lay.on_bone(u0, float(jw[chin].min()) + 14.0), None, False)
            out.append(_structure(f"{side} mental nerve", NERVE, [line([foramen, skin(sg * 16.0, lip - 6.0, 4.5)], 1.3, taper=0.5),
                                                                  line([foramen, skin(sg * 25.0, lip - 5.0, 4.5)], 1.2, taper=0.5),
                                                                  line([foramen, skin(sg * 13.0, lip - 23.0, 4.0)], 1.2, taper=0.5)],
                                  "from its foramen in the jaw, to the lower lip and the chin"))
    log(f"face vessels and nerves: {len(out)} drawn on his head (generated), {sum(s.triangles for s in out)} triangles")
    return out
