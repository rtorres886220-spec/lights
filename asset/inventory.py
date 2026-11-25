"""Inventory every mesh part of the source GLB: tris, open/non-manifold edges,
inconsistent normals, duplicate faces, coplanar overlaps between parts.
Usage: python3 asset/inventory.py <plain.glb> <out.txt>"""
import bpy, bmesh, sys, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
inp, out = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=inp)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
lines = []; tot = 0
def path(o):
    p=[]; x=o.parent
    while x and x.name not in ('FBX_Root','empty_1'): p.append(x.name); x=x.parent
    return '/'.join(reversed(p[-3:]))
bvh = {}
for o in meshes:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    tris = len(bm.faces); tot += tris
    open_e = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    # duplicate faces: same rounded vertex set
    seen = {}; dup = 0
    for f in bm.faces:
        k = tuple(sorted(tuple(round(c*1e4) for c in v.co) for v in f.verts))
        if k in seen: dup += 1
        else: seen[k] = 1
    # normal consistency: faces whose winding disagrees with a neighbour across a manifold edge
    bad = 0
    for e in bm.edges:
        if len(e.link_faces) == 2:
            a, b = e.link_faces; v1, v2 = e.verts
            def order(f):
                vs = list(f.verts); i = vs.index(v1); return vs[(i+1) % len(vs)] is v2
            if order(a) == order(b): bad += 1
    # merge-by-distance candidates (0.05 mm)
    bm2 = bm.copy(); before = len(bm2.verts)
    bmesh.ops.remove_doubles(bm2, verts=bm2.verts[:], dist=0.00005); merged = before - len(bm2.verts); bm2.free()
    mats = ','.join(s.material.name for s in o.material_slots if s.material)
    lines.append(f"{o.name:16s} {mats:16s} tris={tris:6d} open_edges={open_e:5d} nonmanifold={nonman:4d} winding_flips={bad:4d} dup_faces={dup:4d} weld_0.05mm={merged:5d}  [{path(o)}]")
    bvh[o.name] = (BVHTree.FromBMesh(bm), bm)
# coplanar overlap between DIFFERENT parts (z-fighting): sample face centres of A, find B face within 0.02 mm with parallel normal
lines.append("\n# Coplanar overlaps between different parts (z-fight candidates): A -> B : faces")
names = list(bvh)
for a in names:
    ta, bma = bvh[a]
    for b in names:
        if a >= b: continue
        tb, bmb = bvh[b]
        if not ta.overlap(tb): continue
        n = 0
        for f in bma.faces:
            c = f.calc_center_median(); hit = tb.find_nearest(c, 0.00002)
            if hit[0] is not None and abs(hit[1].dot(f.normal)) > 0.999: n += 1
        if n: lines.append(f"{a} -> {b} : {n} coplanar faces")
lines.insert(0, f"# Source GLB inventory  total_tris={tot}  parts={len(meshes)}\n")
open(out, 'w').write('\n'.join(lines) + '\n'); print('\n'.join(lines[-40:]))
