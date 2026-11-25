"""LYNAR asset rebuild — one repeatable command.

    python3 asset/build_asset.py <src_plain.glb> <work_dir>

Input is the decoded (no meshopt/quantization) GLB from asset/decode.mjs.
Output in <work_dir>: geometry.glb (geometry, UV0 tiling, UV1 bake atlas, tangents,
material slots by real part) plus the bake textures ao.png, edge.png, matid.png.
asset/finish.mjs then builds the final textured, compressed GLB.

Node names and world positions are preserved: src.html looks parts up by name.
Everything named VIS_* is visualisation geometry added here, not manufacturer CAD.
"""
import bpy, bmesh, sys, math, os, json, time
from mathutils import Vector, Matrix
from math import radians

SRC, WORK = sys.argv[-2], sys.argv[-1]
os.makedirs(WORK, exist_ok=True)
BAKE = int(os.environ.get('BAKE_RES', 4096))
SAMPLES = int(os.environ.get('BAKE_SAMPLES', 48))
T0 = time.time()
def log(*a): print(f"[{time.time()-T0:7.1f}s]", *a, flush=True)
REPORT = {}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'): bpy.data.objects.remove(o)
OBJ = bpy.data.objects
def meshes(): return [o for o in OBJ if o.type == 'MESH']

# ------------------------------------------------------------------ 0. unit scale
# The decoded GLB stores each mesh normalised with a per-node scale. Bake the scale
# into the mesh data so all distances below are real metres; instancing is kept.
done = set()
for o in meshes():
    m = o.data
    s = o.matrix_world.to_scale()
    users = [u for u in meshes() if u.data == m]
    if m.name in done: continue
    loc_s = o.scale.copy()
    m.transform(Matrix.Diagonal((*loc_s, 1)))
    for u in users: u.scale = (1, 1, 1)
    done.add(m.name)
bpy.context.view_layer.update()
log('unit scale baked into', len(done), 'meshes')

def world_verts(o): return [o.matrix_world @ v.co for v in o.data.vertices]
def bbox(o):
    vs = world_verts(o); return Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)])
def center(o):
    if o.type == 'MESH': a, b = bbox(o); return (a + b) / 2
    vs = [v for c in o.children_recursive if c.type == 'MESH' for v in world_verts(c)]
    return Vector([(min(v[i] for v in vs) + max(v[i] for v in vs)) / 2 for i in range(3)])

# ------------------------------------------------------------------ 1. clean CAD meshes
# weld 0.05 mm, drop degenerate faces and exact duplicate faces (same verts, same facing)
def clean(m):
    bm = bmesh.new(); bm.from_mesh(m)
    v0, f0 = len(bm.verts), len(bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.00005)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
    seen, kill = {}, []
    for f in bm.faces:
        k = tuple(sorted(v.index for v in f.verts))
        if k in seen and seen[k].normal.dot(f.normal) > 0.9: kill.append(f)
        else: seen[k] = f
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(m); bm.free()
    return v0 - len(m.vertices), f0 - len(m.polygons), len(kill)
cl = {}
for m in {o.data for o in meshes()}:
    cl[m.name] = clean(m)
REPORT['clean'] = {k: dict(zip(['verts_welded', 'faces_removed', 'dup_faces'], v)) for k, v in cl.items()}
log('cleaned', sum(v[0] for v in cl.values()), 'verts welded,', sum(v[1] for v in cl.values()), 'faces removed')

# ------------------------------------------------------------------ 2. triangle budget
# black / hidden parts were over-dense; collapse-decimate to targets (triangles per unique mesh)
TARGET = {
    'Mesh_34': 1600,   # RYLO reflector (x16 instances, 148k tris before)
    'Mesh_33': 4500,   # RYLO reflector carrier
    'Mesh_50': 9000, 'Mesh_51': 9000,   # EYE main bodies (visible silhouettes: keep dense)
    'Mesh_47': 5000, 'Mesh_49': 5000,   # EYE body 2
    'Mesh_39': 4500, 'Mesh_40': 4500,   # EYE funnels (inner baffle)
    'Mesh_3': 6500,    # BIBA cover
    'Mesh_22': 9000,   # ATOS reflector
    'Mesh_5': 2600,    # BIBA cable blocker
}
def tris(m): return sum(len(p.vertices) - 2 for p in m.polygons)
dec = {}
for o in meshes():
    m = o.data
    key = next((k for k in TARGET if m.name == k or o.name == k), None)
    if not key or m.name in dec: continue
    t0 = tris(m)
    if t0 <= TARGET[key]: continue
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    mod = o.modifiers.new('dec', 'DECIMATE'); mod.ratio = TARGET[key] / t0; mod.use_collapse_triangulate = True
    mesh_new = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    o.modifiers.remove(mod)
    m.clear_geometry();
    bm = bmesh.new(); bm.from_mesh(mesh_new); bm.to_mesh(m); bm.free(); bpy.data.meshes.remove(mesh_new)
    dec[m.name] = (t0, tris(m))
REPORT['decimate'] = dec
log('decimated', dec)

# ------------------------------------------------------------------ 3. profile rebuild
# Exact CAD cross-section (measured by bisecting mesh_36/mesh_36_1 at x=-1.2 m),
# symmetric about the centre line. (u lateral from centre, v height) in mm.
# Outer faces (white in CAD) run from the top outer corner down the wall round the bottom lip.
HALF = [  # right half, from top-channel floor centre around to track top centre
    (0, 5.41, 'K'), (11.66, 5.41, 'K'), (11.74, 4.80, 'K'), (11.84, 4.10, 'K'), (15.07, 3.98, 'K'), (18.49, 3.95, 'K'),
    (18.49, 7.92, 'K'), (15.07, 7.92, 'K'), (15.01, 8.53, 'K'), (15.25, 8.83, 'K'), (16.84, 9.69, 'K'),
    (16.84, 10.24, 'K'), (16.35, 10.91, 'K'), (16.35, 11.70, 'K'), (16.66, 12.68, 'K'), (17.63, 13.72, 'K'),
    (18.78, 13.51, 'K'), ('R', 20.02, 13.29, 1.2, 'W'),           # top outer corner, 1.2 mm roll
    ('R', 20.02, -52.14, 0.85, 'W'),                                # bottom outer corner of the lip, 0.85 mm roll
    ('R', 18.61, -52.14, 0.45, 'W'),                                # inner nose of the lip, 0.45 mm (lip is 1.41 mm wide)
    (18.58, -34.37, 'K'), ('R', 18.39, -15.58, 0.6, 'K'), (13.45, -15.43, 'K'), ('R', 8.30, -15.37, 0.5, 'K'),
    (8.26, -7.84, 'K'), ('R', 8.24, -0.81, 0.4, 'K'), (0, -0.81, 'K'),
]
def fillet(pts):
    """pts: list of (u,v,tag) or ('R',u,v,r,tag). Returns (u,v,tag,smooth_into) polyline with arcs."""
    base = [(p[1], p[2], p[4], p[3]) if p[0] == 'R' else (p[0], p[1], p[2], 0) for p in pts]
    out = []
    n = len(base)
    for i, (u, v, tag, r) in enumerate(base):
        if r <= 0 or i == 0 or i == n - 1: out.append((u, v, tag, False)); continue
        P = Vector((u, v)); A = Vector(base[i - 1][:2]); B = Vector(base[i + 1][:2])
        d1 = (A - P).normalized(); d2 = (B - P).normalized()
        ang = d1.angle(d2); t = r / math.tan(ang / 2)
        t = min(t, (A - P).length * 0.45, (B - P).length * 0.45); rr = t * math.tan(ang / 2)
        T1, T2 = P + d1 * t, P + d2 * t
        bis = (d1 + d2).normalized(); C = P + bis * (rr / math.sin(ang / 2))
        a1 = math.atan2(*(T1 - C).yx); a2 = math.atan2(*(T2 - C).yx)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        segs = 6
        for k in range(segs + 1):
            a = a1 + da * k / segs; out.append((C.x + rr * math.cos(a), C.y + rr * math.sin(a), tag, 0 < k <= segs))
    return out
right = fillet(HALF)
left = [(-u, v, tag, s) for (u, v, tag, s) in reversed(right)]
# closed loop: right half top->bottom centre, then left half bottom->top centre (drop duplicate centre points)
SECTION = right + left[1:-1]
REPORT['profile_section_points'] = len(SECTION)

PX = -682.91e-3; PY = 463.915e-3   # run centre lines (measured from CAD bounds)
def sweep(name, parent, path, mats):
    """Sweep SECTION along a polyline path (list of 3D points, z ignored -> section v is world z, mm).
    Mitred at interior vertices. Faces get material 0 (white/outer) or 1 (black/inner)."""
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    rings = []
    for i, p in enumerate(path):
        dirs = []
        if i > 0: dirs.append((path[i] - path[i - 1]).normalized())
        if i < len(path) - 1: dirs.append((path[i + 1] - path[i]).normalized())
        lat = Vector((0, 0, 0))
        for d in dirs: lat += Vector((-d.y, d.x, 0))          # left normal of travel
        lat.normalize()
        if len(dirs) == 2: lat /= math.cos(dirs[0].angle(dirs[1]) / 2)   # mitre stretch
        rings.append([bm.verts.new(Vector((p.x, p.y, 0)) + lat * (u * 1e-3) + Vector((0, 0, v * 1e-3))) for (u, v, _, _) in SECTION])
    bm.verts.ensure_lookup_table()
    n = len(SECTION)
    for r in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((rings[r][k], rings[r][k2], rings[r + 1][k2], rings[r + 1][k]))
            f.material_index = 0 if (SECTION[k][2] == 'W' and SECTION[k2][2] == 'W') or (SECTION[k][2] == 'W' and k2 < n and SECTION[k2][2] == 'K' and False) else 1
            f.smooth = True
    # sharp edges: along-run edges where the section turns > 35 deg and is not inside a fillet
    bm.normal_update()
    bm.to_mesh(me); bm.free()
    for mt in mats: me.materials.append(mt)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    # sweep was built in world space: parent while keeping world transform
    ob.parent = parent; ob.matrix_parent_inverse = parent.matrix_world.inverted()
    # outward check: a face on the outer wall (+u side of the first run) must point away from the centre line
    return ob

MAT = {}
def mat(name):
    if name not in MAT:
        m = bpy.data.materials.new(name); m.use_nodes = True; MAT[name] = m
    return MAT[name]

white, black = mat('powder_white'), mat('powder_black')
runs = {  # node name -> (old mesh objects, path)
    'Intra-lighting_LYNAR-SDI003': (['mesh_36', 'mesh_36_1'], [Vector((-1.71833, PY, 0)), Vector((-0.71833, PY, 0))]),
    'Intra-lighting_LYNAR-CS-SDI_Corner-element-092': (['mesh_34', 'mesh_34_1'], [Vector((-0.71833, PY, 0)), Vector((PX, PY, 0)), Vector((PX, 0.42817, 0))]),
    'Intra-lighting_LYNAR-SDI002': (['mesh_33', 'mesh_33_1'], [Vector((PX, 0.42817, 0)), Vector((PX, -0.57183, 0))]),
    'Intra-lighting_LYNAR-SDI004': (['mesh_39', 'mesh_39_1'], [Vector((PX, -0.57183, 0)), Vector((PX, -1.57183, 0))]),
}
for node, (olds, path) in runs.items():
    parent = OBJ[node]
    keep = olds[0]
    for n in olds: OBJ.remove(OBJ[n])
    sweep(keep, parent, path, [white, black])
# verify facing: outward normal on the outer white wall of SDI003 must point +y (away from centre line)
o = OBJ['mesh_36']; flips = 0
for p in o.data.polygons:
    c = o.matrix_world @ p.center
    if p.material_index == 0 and abs(p.normal.z) < 0.1 and c.y > PY + 0.019:
        if (o.matrix_world.to_3x3() @ p.normal).y < 0: flips += 1
if flips:
    for n in ['mesh_36', 'mesh_34', 'mesh_33', 'mesh_39']:
        m = OBJ[n].data; bm = bmesh.new(); bm.from_mesh(m); bmesh.ops.reverse_faces(bm, faces=bm.faces[:]); bm.to_mesh(m); bm.free()
REPORT['profile_flipped'] = bool(flips)
log('profile rebuilt, faces flipped:', bool(flips))

# ------------------------------------------------------------------ 4. opal diffusers (VIS: thickness + walls)
def opal_bar(name, parent, cx, y0, y1, z_face, facing, width=0.0335, thick=0.003, bulge=0.0006, r=0.0008):
    """Rounded opal bar along Y. facing = -1 (emits down) or +1 (emits up). UV0: u across width 0..1, v = length/10mm."""
    half = width / 2; prof = []
    # cross-section (x across, zz towards the emitting side): convex emitting face, rolled front edges, flat back
    N = 16
    for k in range(N + 1):                      # emitting face, slight convex bulge
        x = -half + r + (width - 2 * r) * k / N; prof.append((x, bulge * (1 - (x / half) ** 2), 'F'))
    for k in range(1, 6):                       # right rolled edge: centre (half-r, -r), 90 -> 0 deg
        a = math.pi / 2 * (1 - k / 5); prof.append((half - r + r * math.cos(a), -r + r * math.sin(a), 'S'))
    prof.append((half, -thick, 'S')); prof.append((-half, -thick, 'B'))
    for k in range(0, 5):                       # left rolled edge: centre (-half+r, -r), 180 -> 90 deg
        a = math.pi * (1 - k / 10); prof.append((-half + r + r * math.cos(a), -r + r * math.sin(a), 'S'))
    me = bpy.data.meshes.new(name); bm = bmesh.new(); uv = bm.loops.layers.uv.new('tile')
    rings = []
    for y in (y0, y1):
        rings.append([bm.verts.new(Vector((cx + x, y, z_face + facing * (zz)))) for (x, zz, _) in prof])
    n = len(prof)
    for k in range(n):
        k2 = (k + 1) % n
        f = bm.faces.new((rings[0][k], rings[0][k2], rings[1][k2], rings[1][k]))
        f.smooth = prof[k][2] != 'B'
        for l in f.loops:
            x = l.vert.co.x - cx; l[uv].uv = ((x + half) / width, (l.vert.co.y - y0) / 0.010)
    for ring, rev in ((rings[0], True), (rings[1], False)):
        f = bm.faces.new(list(reversed(ring)) if rev else ring); f.smooth = False
        for l in f.loops: l[uv].uv = ((l.vert.co.x - cx + half) / width, 0.0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free(); me.materials.append(mat('emit_opal'))
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent; ob.matrix_parent_inverse = parent.matrix_world.inverted()
    return ob

# KALIS: replace CAD diffuser (mesh_54 + 2-tri face mesh_54_1) — emitting face down at the old face plane
k_par = OBJ['Mirror002']; a, b = bbox(OBJ['mesh_54_1'])
OBJ.remove(OBJ['mesh_54']); OBJ.remove(OBJ['mesh_54_1'])
opal_bar('VIS_opal_kalis', k_par, (a.x + b.x) / 2, a.y, b.y, a.z + 0.0002, -1, width=0.0330)
# Indirect: replace 12-tri plane with a 3 mm opal bar, emitting face up
i_par = OBJ['IntraLighting_Indirect_ilumination001']; a, b = bbox(OBJ['Mesh_30'])
OBJ.remove(OBJ['Mesh_30'])
opal_bar('Mesh_30', i_par, (a.x + b.x) / 2, a.y, b.y, b.z, +1, width=0.0324, thick=0.0025)
log('opal bars built')

# ------------------------------------------------------------------ 5. lens / glow discs (VIS)
def aperture(shell_objs, origin, axis, depth=0.0006):
    """Find the mouth plane and inner radius of a ring-shaped shell along axis from origin."""
    vs = [v for o in shell_objs for v in world_verts(o)]
    s = [(v - origin).dot(axis) for v in vs]; front = max(s)
    rad = [((v - origin) - axis * si).length for v, si in zip(vs, s) if si > front - depth]
    return front, min(rad)
def disc(name, parent, ctr, axis, radius, matname, segs=48):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); uv = bm.loops.layers.uv.new('tile')
    t1 = axis.orthogonal().normalized(); t2 = axis.cross(t1)
    ring = [bm.verts.new(ctr + (t1 * math.cos(2 * math.pi * k / segs) + t2 * math.sin(2 * math.pi * k / segs)) * radius) for k in range(segs)]
    f = bm.faces.new(ring)
    if f.normal.dot(axis) < 0: bmesh.ops.reverse_faces(bm, faces=[f])
    for l in f.loops:
        d = l.vert.co - ctr; l[uv].uv = (0.5 + d.dot(t1) / (2 * radius), 0.5 + d.dot(t2) / (2 * radius))
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    for f in bm.faces: f.smooth = False
    bm.to_mesh(me); bm.free(); me.materials.append(mat(matname))
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent; ob.matrix_parent_inverse = parent.matrix_world.inverted(); return ob
lenses = {}; LENS_R = {}
def nearest(p, objs): return min(objs, key=lambda o: (center(o) - p).length)
# ATOS: axis LED -> front cover (same rule src.html uses for the beam)
covers = [o for o in OBJ if o.name.startswith('Cover_Atos_CT')]
atos_refl = [o for o in OBJ if o.type == 'MESH' and o.data.name == 'Mesh_22']
for led_name, tag in (('LED016', 'atos_1'), ('LED020', 'atos_2')):
    led = center(OBJ[led_name]); cov = nearest(led, covers); axis = (center(cov) - led).normalized()
    refl = nearest(led, atos_refl)
    front, rin = aperture([refl], led, axis); LENS_R[tag] = round(rin * 1000, 2)
    lenses[tag] = disc(f'VIS_lens_{tag}', OBJ[cov.parent.name], led + axis * (front - 0.0006), axis, rin - 0.0002, 'lens_glow')
# EYE: axis COB -> funnel
funnels = [o for o in OBJ if o.name.startswith('Brooke_Funnel')]
eye_refl = [o for o in OBJ if o.type == 'MESH' and o.data.name in ('Mesh_41', 'Mesh_42')]
for cob_name, tag in (('Imported010', 'eye_1'), ('Imported011', 'eye_2')):
    cob = center(OBJ[cob_name]); fn = nearest(cob, funnels); axis = (center(fn) - cob).normalized()
    refl = nearest(cob, eye_refl)
    front, rin = aperture([refl], cob, axis); LENS_R[tag] = round(rin * 1000, 2)
    lenses[tag] = disc(f'VIS_lens_{tag}', OBJ['EYE_60_C_double_angle001'], cob + axis * (front - 0.0006), axis, rin - 0.0002, 'lens_glow')
# BIBA: straight down from the LED through the cover
led = center(OBJ['LED011']); axis = Vector((0, 0, -1))
front, rin = aperture([OBJ['Mesh_4']], led, axis); LENS_R['biba'] = round(rin * 1000, 2)
lenses['biba'] = disc('VIS_lens_biba', OBJ['Sestav_ROUND_round_2_002'], led + axis * (front - 0.0006), axis, rin - 0.0002, 'lens_glow')
# RYLO: a glow cap in each of the 16 reflector mouths
rylo_par = OBJ['Intra-lighting_LYNAR_RYLO-LightLineKalis001']; refl = [o for o in OBJ if o.type == 'MESH' and o.data.name == 'Mesh_34']
for i, r in enumerate(sorted(refl, key=lambda o: center(o).y)):
    ledc = center(nearest(center(r), [o for o in OBJ if o.type == 'MESH' and o.data.name == 'Mesh_35']))
    front, rin = aperture([r], ledc, Vector((0, 0, -1))); LENS_R[f'rylo_{i:02d}'] = round(rin * 1000, 2)
    disc(f'VIS_glow_rylo_{i:02d}', rylo_par, ledc + Vector((0, 0, -1)) * (front - 0.0008), Vector((0, 0, -1)), rin - 0.0002, 'lens_glow', segs=32)
REPORT['aperture_inner_radius_mm'] = LENS_R
log('lens / glow discs', len(lenses), '+ 16 RYLO caps')

# ------------------------------------------------------------------ 6. materials by real part
ASSIGN = {  # mesh object name (or mesh data name) -> material, per slot index when list
    'Mesh_13': 'steel_dark',
    'mesh_37': ['powder_white'], 'mesh_37_1': ['powder_black'], 'mesh_38': ['powder_white'], 'mesh_38_1': ['powder_black'],
    'Mesh_10': 'powder_black', 'Mesh_38': 'powder_black',
    'Mesh_0': 'powder_black', 'Mesh_1': 'powder_black', 'Mesh_3': 'baffle_black', 'Mesh_4': 'alu_reflector',
    'Mesh_5': 'chrome', 'Mesh_6': 'steel_dark', 'Mesh_2': 'rubber_cable',
    'Mesh_7': 'holder_white', 'mesh_42': 'holder_white', 'mesh_42_1': 'emit_cob',
    'Mesh_14': 'anodized_black', 'Mesh_15': 'powder_black',
    'Mesh_35': 'emit_led', 'Mesh_31': 'anodized_black', 'Mesh_32': 'powder_black', 'Mesh_33': 'baffle_black', 'Mesh_34': 'alu_reflector',
    'Mesh_22': 'alu_reflector', 'Mesh_23': 'baffle_black', 'Mesh_24': 'powder_black', 'mesh_58': 'holder_white', 'mesh_58_1': 'emit_cob',
    'Mesh_27': 'powder_white', 'mesh_60': 'holder_white', 'mesh_60_1': 'emit_cob', 'mesh_70': 'holder_white', 'mesh_70_1': 'emit_cob',
    'mesh_67': 'holder_white', 'mesh_67_1': 'emit_cob', 'Mesh_28': 'powder_white', 'Mesh_29': 'powder_white',
    'Mesh_36': 'emit_cob', 'Mesh_37': 'emit_cob', 'Mesh_47': 'powder_black', 'Mesh_49': 'powder_black', 'Mesh_48': 'steel_dark',
    'Mesh_50': 'powder_black', 'Mesh_51': 'powder_black', 'Mesh_39': 'baffle_black', 'Mesh_40': 'baffle_black',
    'Mesh_41': 'alu_reflector', 'Mesh_42': 'alu_reflector', 'Mesh_43': 'powder_black', 'Mesh_44': 'holder_white', 'Mesh_45': 'holder_white',
    'Mesh_46': 'steel_dark',
}
unassigned = []
for o in meshes():
    if o.name.startswith('VIS_') or o.name in ('mesh_36', 'mesh_34', 'mesh_33', 'mesh_39', 'Mesh_30'): continue
    key = o.name if o.name in ASSIGN else o.name.split('.')[0] if o.name.split('.')[0] in ASSIGN else o.data.name if o.data.name in ASSIGN else None
    if key is None: unassigned.append(o.name); continue
    v = ASSIGN[key]; names = v if isinstance(v, list) else [v] * max(1, len(o.data.materials))
    if len(o.data.materials) == 0: o.data.materials.append(mat(names[0]))
    for i in range(len(o.data.materials)): o.data.materials[i] = mat(names[min(i, len(names) - 1)])
REPORT['unassigned'] = unassigned
for m in list(bpy.data.materials):
    if m.users == 0: bpy.data.materials.remove(m)
log('materials:', sorted(MAT), 'unassigned:', unassigned)

# ------------------------------------------------------------------ 7. bevels on prismatic parts + normals
BEVEL = {'Mesh_10': 0.0006, 'Mesh_38': 0.0006, 'Mesh_13': 0.0004, 'Mesh_24': 0.0004, 'Mesh_43': 0.0004,
         'Mesh_14': 0.0005, 'Mesh_31': 0.0005, 'Mesh_2': 0.0}
NEW = {'mesh_36', 'mesh_34', 'mesh_33', 'mesh_39', 'Mesh_30'}
def apply_mods(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    for mname in [md.name for md in o.modifiers]: o.modifiers.remove(o.modifiers[mname])
    old = o.data; users = [u for u in meshes() if u.data == old]
    for u in users: u.data = me
    me.name = old.name;
    if old.users == 0: bpy.data.meshes.remove(old)
done = set(); bev = {}
def sharp_by_angle(m, deg):
    bm = bmesh.new(); bm.from_mesh(m)
    for f in bm.faces: f.smooth = True
    for e in bm.edges:
        lf = e.link_faces
        e.smooth = len(lf) == 2 and lf[0].normal.length > 0 and lf[1].normal.length > 0 and lf[0].normal.angle(lf[1].normal) < radians(deg)
    bm.to_mesh(m); bm.free()
UNIQ_OBJ = list({o.data.name: o for o in meshes()}.values())     # one object per shared mesh: modifiers applied once
for o in UNIQ_OBJ:
    m = o.data
    if o.name.startswith('VIS_') or o.name == 'Mesh_30': continue      # built with final shading
    if o.name in NEW: sharp_by_angle(m, 35); continue                  # swept profile: fillets smooth, corners sharp
    sharp_by_angle(m, 30)
    w = BEVEL.get(m.name) or BEVEL.get(o.name.split('.')[0])
    if w:
        bv = o.modifiers.new('bev', 'BEVEL'); bv.width = w; bv.segments = 3; bv.limit_method = 'ANGLE'; bv.angle_limit = radians(30)
        bv.harden_normals = True; bv.use_clamp_overlap = True; bev[m.name] = w
    wn = o.modifiers.new('wn', 'WEIGHTED_NORMAL'); wn.keep_sharp = True; wn.weight = 50; wn.mode = 'FACE_AREA_WITH_ANGLE'
    apply_mods(o)
REPORT['bevel_m'] = bev
# triangulate everything (tangents need triangles) keeping the custom normals; validate mesh data
for o in list({o.data.name: o for o in meshes()}.values()):
    t = o.modifiers.new('tri', 'TRIANGULATE'); t.keep_custom_normals = True; t.quad_method = 'BEAUTY'; t.ngon_method = 'BEAUTY'
    apply_mods(o)
    o.data.validate(clean_customdata=False)
log('bevels + weighted normals applied on', len(UNIQ_OBJ), 'meshes; bevelled:', list(bev))

# ------------------------------------------------------------------ 8. UV0 (tiling, 40 mm per UV unit) + UV1 (bake atlas)
TILE = 0.040
def ensure_uv(m, name):
    if name not in m.uv_layers: m.uv_layers.new(name=name)
    return m.uv_layers[name]
def box_uv(o):
    """World-scale box projection into UV 'tile'. Reflectors get cylindrical UV (u around the axis) for anisotropy."""
    m = o.data; uv = ensure_uv(m, 'tile').data; M = o.matrix_world
    for p in m.polygons:
        n = (M.to_3x3() @ p.normal).normalized(); ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = M @ m.vertices[m.loops[li].vertex_index].co
            a, b = [(1, 2), (0, 2), (0, 1)][ax]
            uv[li].uv = (co[a] / TILE, co[b] / TILE)
def cyl_uv(o, axis, origin):
    m = o.data; uv = ensure_uv(m, 'tile').data; M = o.matrix_world
    t1 = axis.orthogonal().normalized(); t2 = axis.cross(t1)
    for p in m.polygons:
        angs = []
        for li in p.loop_indices:
            d = M @ m.vertices[m.loops[li].vertex_index].co - origin
            angs.append((li, math.atan2(d.dot(t2), d.dot(t1)), d.dot(axis)))
        ref = angs[0][1]
        for li, a, h in angs:
            if a - ref > math.pi: a -= 2 * math.pi
            if ref - a > math.pi: a += 2 * math.pi
            uv[li].uv = (a / (2 * math.pi) * 24, h / TILE)   # 24 facets around
refl_axes = {}
for o in meshes():
    if o.data.materials and o.data.materials[0].name == 'alu_reflector':
        # axis: from the emitter at the back to the mouth = direction of largest open end; use nearest lens/glow disc normal
        discs = [d for d in meshes() if d.name.startswith('VIS_')]
        d = min(discs, key=lambda d: (center(d) - center(o)).length)
        ax = (d.matrix_world.to_3x3() @ d.data.polygons[0].normal).normalized()
        refl_axes[o.name] = (ax, center(o))
for o in meshes():
    m = o.data
    if o.name.startswith('VIS_') or o.name == 'Mesh_30':   # built with their own UV0 (radial / across-width)
        continue
    if o.name in refl_axes: cyl_uv(o, *refl_axes[o.name])
    else: box_uv(o)
# order: 'tile' must be UV index 0 (TEXCOORD_0), 'bake' index 1
for m in {o.data for o in meshes()}:
    for l in [l for l in m.uv_layers if l.name not in ('tile',)]: m.uv_layers.remove(l)
    ensure_uv(m, 'tile'); ensure_uv(m, 'bake'); m.uv_layers['tile'].active_render = True
# atlas: smart project every unique mesh, small parts get 2.5x texel density, pack all together
uniq = {}
for o in meshes(): uniq.setdefault(o.data.name, o)
bpy.ops.object.select_all(action='DESELECT')
for o in uniq.values(): o.select_set(True)
bpy.context.view_layer.objects.active = next(iter(uniq.values()))
for o in uniq.values(): o.data.uv_layers.active = o.data.uv_layers['bake']
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=radians(60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.average_islands_scale()
bpy.ops.object.mode_set(mode='OBJECT')
PROFILE = {'mesh_36', 'mesh_34', 'mesh_33', 'mesh_39'}
for o in uniq.values():
    if o.name in PROFILE: continue
    uv = o.data.uv_layers['bake'].data
    for d in uv: d.uv = d.uv * 2.5
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, margin_method='FRACTION', margin=0.0025, shape_method='CONCAVE', scale=True)
bpy.ops.object.mode_set(mode='OBJECT')
log('UVs done')

# ------------------------------------------------------------------ 9. bakes (Cycles): AO, edge mask, material id
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.use_denoising = False
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
world.light_settings.distance = 0.05      # AO search distance 50 mm
def image(name):
    img = bpy.data.images.new(name, BAKE, BAKE, alpha=False, float_buffer=False); img.colorspace_settings.name = 'Non-Color'; return img
def set_target(img):
    for m in bpy.data.materials:
        nt = m.node_tree; n = nt.nodes.get('BAKE') or nt.nodes.new('ShaderNodeTexImage'); n.name = 'BAKE'; n.image = img
        uvn = nt.nodes.get('BAKEUV') or nt.nodes.new('ShaderNodeUVMap'); uvn.name = 'BAKEUV'; uvn.uv_map = 'bake'
        nt.links.new(uvn.outputs[0], n.inputs[0]); nt.nodes.active = n
for o in meshes(): o.data.uv_layers.active = o.data.uv_layers['bake']
VISD = [o for o in meshes() if o.name.startswith(('VIS_lens', 'VIS_glow'))]
for o in VISD: o.hide_render = True          # glow discs must not occlude reflector AO
bpy.ops.object.select_all(action='DESELECT')
for o in uniq.values():
    if o not in VISD: o.select_set(True)
bpy.context.view_layer.objects.active = next(o for o in uniq.values() if o not in VISD)
def bake(kind, img, samples):
    set_target(img); sc.cycles.samples = samples
    sc.render.bake.margin = 12; sc.render.bake.margin_type = 'EXTEND'; sc.render.bake.use_clear = True
    bpy.ops.object.bake(type=kind, use_clear=True, margin=12)
    img.filepath_raw = os.path.join(WORK, img.name + '.png'); img.file_format = 'PNG'; img.save()
# AO
ao = image('ao'); bake('AO', ao, SAMPLES); log('AO baked')
# edge mask: emission = 1 - dot(bevel normal, geometric normal), scaled
PALETTE = sorted(MAT)
orig_out = {}
for m in bpy.data.materials:
    nt = m.node_tree; out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    orig_out[m.name] = [l.from_socket for l in out.inputs['Surface'].links]
    em = nt.nodes.new('ShaderNodeEmission'); em.name = 'EDGE'
    bv = nt.nodes.new('ShaderNodeBevel'); bv.inputs['Radius'].default_value = 0.0008; bv.samples = 8
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    nt.links.new(bv.outputs[0], dot.inputs[0]); nt.links.new(geo.outputs['Normal'], dot.inputs[1])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(dot.outputs['Value'], inv.inputs[1])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 6.0; mul.use_clamp = True
    nt.links.new(inv.outputs[0], mul.inputs[0]); nt.links.new(mul.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
edge = image('edge'); bake('EMIT', edge, 16); log('edge baked')
# material id: flat emission colour per material (index encoded in red, 1 sample = no blending)
for i, name in enumerate(PALETTE):
    m = bpy.data.materials[name]; nt = m.node_tree; out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = ((i + 1) / 32, 0, 0, 1); em.inputs['Strength'].default_value = 1
    nt.links.new(em.outputs[0], out.inputs['Surface'])
mid = image('matid'); bake('EMIT', mid, 1); log('matid baked')
json.dump(PALETTE, open(os.path.join(WORK, 'palette.json'), 'w'))

# ------------------------------------------------------------------ 10. reset shaders, export
for m in bpy.data.materials:
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
for o in meshes(): o.data.uv_layers.active = o.data.uv_layers['tile']; o.data.uv_layers['tile'].active_render = True
stats = {'unique_tris': sum(tris(m) for m in {o.data for o in meshes()}), 'drawn_tris': sum(tris(o.data) for o in meshes()), 'objects': len(meshes())}
REPORT['stats'] = stats; log('stats', stats)
for o in VISD: o.hide_render = False
want = dict(filepath=os.path.join(WORK, 'geometry.glb'), export_format='GLB', export_yup=True,
    export_texcoords=True, export_normals=True, export_tangents=True, export_materials='EXPORT', export_image_format='NONE',
    export_lights=False, export_cameras=False, export_extras=False, export_apply=True, export_attributes=False,
    export_vertex_color='NONE', use_visible=False, use_renderable=False)
props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
log('export opts dropped:', [k for k in want if k not in props])
bpy.ops.export_scene.gltf(**{k: v for k, v in want.items() if k in props})
json.dump(REPORT, open(os.path.join(WORK, 'build_report.json'), 'w'), indent=1)
log('exported', os.path.join(WORK, 'geometry.glb'))
