"""The anatomy model: the labelled body as named surface meshes, layer by layer (tools/build_model_meshes.py).

Modules
    common   the body export (Body), a mesh with its per-vertex data (Structure), surfaces, decimation, the bake
    glb      the GLB writer and reader (the file Unity imports)
    preview  a small software renderer: a picture of any structures without Unity
    palette  the tissues' colours
    skin     the skin and the briefs
    layers   fat, muscles, skeleton, organs from the labels
    frames   coordinate mappings from the sources' native grids (SIO, CT, region exports) into the body

Frame of every mesh ("glTF metres"): x = patient left, y = up (towards the head), z = front, origin at the centre
of the body export's volume box. It is the body's metre frame (x left, y up, z back) with z negated.
"""
