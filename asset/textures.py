"""Build every texture the final GLB uses (WebP). Deterministic (fixed seeds).

    python3 asset/textures.py <work_dir>

Reads the Cycles bakes from build_asset.py (ao.png, edge.png, matid.png, palette.json)
and writes into <work_dir>/tex/:
  orm.webp          R = ambient occlusion, G = roughness (per material, polished at edges), B = metalness  [UV1 atlas]
  orange_peel_n.webp  tileable powder-coat orange-peel normal map, 40 mm per tile                          [UV0]
  facet_n.webp      reflector facets: 24 flat facets around the axis, +/-4 deg                              [UV0 cylindrical]
  lens_e.webp       radial hot-centre emission for lens / glow discs                                         [UV0 radial]
  opal_e.webp       opal diffuser emission: bright centre, softer edges, faint 10 mm LED pitch                [UV0 across/along]
"""
import sys, os, json, numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

W = sys.argv[1]; T = os.path.join(W, 'tex'); os.makedirs(T, exist_ok=True)

# per material: (roughness, metalness, edge polish factor) — must match finish.mjs
PBR = {
    'powder_white': (0.45, 0, 0.30), 'powder_black': (0.55, 0, 0.30), 'baffle_black': (0.85, 0, 0.10),
    'alu_reflector': (0.18, 1, 0.0), 'chrome': (0.06, 1, 0.0), 'steel_dark': (0.35, 1, 0.15),
    'holder_white': (0.50, 0, 0.15), 'rubber_cable': (0.70, 0, 0.0), 'anodized_black': (0.35, 0, 0.25),
    'emit_cob': (0.40, 0, 0.0), 'emit_led': (0.40, 0, 0.0), 'emit_opal': (0.35, 0, 0.0), 'lens_glow': (0.10, 0, 0.0),
}

def save(name, arr, lossless=False, q=92):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    im.save(os.path.join(T, name), 'WEBP', lossless=lossless, quality=q, method=6)
    return os.path.getsize(os.path.join(T, name))

sizes = {}
# ---------------- ORM atlas
pal = json.load(open(os.path.join(W, 'palette.json')))
ao = np.asarray(Image.open(os.path.join(W, 'ao.png')).convert('L')).astype(np.float32) / 255
edge = np.asarray(Image.open(os.path.join(W, 'edge.png')).convert('L')).astype(np.float32) / 255
mid = np.asarray(Image.open(os.path.join(W, 'matid.png')).convert('RGB'))[..., 0].astype(np.float32)
idx = np.rint(mid / 255 * 32).astype(int) - 1          # -1 = outside any island
# AO: Cycles bake noise -> light blur (islands have 12 px margins, so no bleed across parts)
ao = gaussian_filter(ao, 1.1)
edge = gaussian_filter(edge, 0.6)
rough = np.full(ao.shape, 0.5, np.float32); metal = np.zeros(ao.shape, np.float32); pol = np.zeros(ao.shape, np.float32)
unknown = set()
for i, name in enumerate(pal):
    m = idx == i
    if name not in PBR: unknown.add(name); continue
    r, mt, p = PBR[name]; rough[m] = r; metal[m] = mt; pol[m] = p
rough = rough * (1 - pol * edge)                          # edges a little more polished -> they catch a highlight line
orm = np.stack([ao * 255, rough * 255, metal * 255], -1)
sizes['orm.webp'] = save('orm.webp', orm, q=90)
cover = float((idx >= 0).mean())

# ---------------- orange peel (tileable, periodic filtering in Fourier space)
N = 512; rng = np.random.default_rng(7)
def periodic_noise(sigma_px):
    n = rng.standard_normal((N, N)); f = np.fft.fft2(n)
    ky = np.fft.fftfreq(N)[:, None]; kx = np.fft.fftfreq(N)[None, :]
    g = np.exp(-2 * (np.pi * sigma_px) ** 2 * (kx ** 2 + ky ** 2))
    return np.real(np.fft.ifft2(f * g))
# 512 px over 40 mm -> 0.078 mm/px. Orange peel cells ~1.2 mm (sigma ~5 px) plus fine grain.
h = periodic_noise(5.0); h = h / h.std() + 0.25 * (lambda x: x / x.std())(periodic_noise(1.6))
gy, gx = np.gradient(h); s = 0.35                       # strength in the map; finish.mjs scales further
n = np.stack([-gx * s, -gy * s, np.ones_like(h)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
sizes['orange_peel_n.webp'] = save('orange_peel_n.webp', (n * 0.5 + 0.5) * 255, q=95)

# ---------------- reflector facets: one tile in u = one flat facet; normal tilts linearly across the facet
u = (np.arange(256) + 0.5) / 256; ang = np.radians(4.0) * (2 * u - 1)
fn = np.zeros((32, 256, 3)); fn[..., 0] = np.sin(ang)[None, :]; fn[..., 2] = np.cos(ang)[None, :]
sizes['facet_n.webp'] = save('facet_n.webp', (fn * 0.5 + 0.5) * 255, lossless=True)

# ---------------- lens radial emission (hot core, reflector ring, soft rim)
R = 256; yy, xx = np.mgrid[0:R, 0:R]; r = np.hypot(xx - R / 2 + 0.5, yy - R / 2 + 0.5) / (R / 2)
core = np.exp(-(r / 0.22) ** 2)
ring = 0.32 * np.exp(-((r - 0.62) / 0.22) ** 2)
rim = np.clip((1.0 - r) / 0.06, 0, 1)
e = np.clip(core + ring + 0.12, 0, 1) * rim
sizes['lens_e.webp'] = save('lens_e.webp', np.repeat(e[..., None] * 255, 3, -1), q=95)

# ---------------- opal: u across width (0..1), v along length (1 tile = 10 mm LED pitch)
U, V = np.meshgrid((np.arange(128) + 0.5) / 128, (np.arange(64) + 0.5) / 64)
across = 0.62 + 0.38 * np.exp(-((U - 0.5) / 0.30) ** 2)
pitch = 1 + 0.05 * np.cos(2 * np.pi * V)
e = np.clip(across * pitch / 1.05, 0, 1)
sizes['opal_e.webp'] = save('opal_e.webp', np.repeat(e[..., None] * 255, 3, -1), q=95)

json.dump({'sizes': sizes, 'atlas_coverage': round(cover, 3), 'unknown_materials': sorted(unknown),
           'ao_mean_in_islands': round(float(ao[idx >= 0].mean()), 3)}, open(os.path.join(T, 'report.json'), 'w'), indent=1)
print(json.dumps(sizes), 'coverage', round(cover, 3), 'unknown', unknown)
