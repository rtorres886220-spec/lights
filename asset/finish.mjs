// Final GLB: materials + textures + compression.
//   node asset/finish.mjs <work_dir> <out.glb>
// Needs @gltf-transform/{core,extensions,functions}@4.5.1 and meshoptimizer resolvable (NODE_PATH).
import fs from 'fs';
import path from 'path';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTTextureWebP, KHRMaterialsClearcoat, KHRMaterialsAnisotropy, KHRMaterialsEmissiveStrength } from '@gltf-transform/extensions';
import { prune, dedup, reorder, quantize, weld } from '@gltf-transform/functions';
import { EXTMeshoptCompression } from '@gltf-transform/extensions';
import { MeshoptEncoder } from 'meshoptimizer';

const [, , W, OUT] = process.argv;
const T = path.join(W, 'tex');
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
const doc = await io.read(path.join(W, 'geometry.glb'));
const root = doc.getRoot();

const webp = doc.createExtension(EXTTextureWebP).setRequired(true);
const cc = doc.createExtension(KHRMaterialsClearcoat);
const an = doc.createExtension(KHRMaterialsAnisotropy);
const es = doc.createExtension(KHRMaterialsEmissiveStrength);
const tex = (name, srgb) => doc.createTexture(name).setImage(fs.readFileSync(path.join(T, name))).setMimeType('image/webp').setURI(name);
const ORM = tex('orm.webp'), PEEL = tex('orange_peel_n.webp'), FACET = tex('facet_n.webp'), LENS = tex('lens_e.webp'), OPAL = tex('opal_e.webp');

const lin = hex => { const c = parseInt(hex.slice(1), 16); return [16, 8, 0].map(s => { const v = ((c >> s) & 255) / 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); };
// [base sRGB hex, options]; roughness/metalness come from the ORM atlas (factors 1)
const SPEC = {
  powder_white:   ['#F1F0EA', { peel: 0.10, clearcoat: [0.30, 0.25] }],
  powder_black:   ['#1C1C1C', { peel: 0.06, clearcoat: [0.35, 0.3] }],
  baffle_black:   ['#121212', {}],
  alu_reflector:  ['#E8EAEC', { facet: 1.0, aniso: 0.6 }],
  chrome:         ['#F2F2F2', {}],
  steel_dark:     ['#5A5B5E', {}],
  holder_white:   ['#E9E7E1', {}],
  rubber_cable:   ['#161616', {}],
  anodized_black: ['#151515', { clearcoat: [0.2, 0.3] }],
  emit_cob:       ['#E2B43A', { emissive: [1, 0.86, 0.66], strength: 4 }],          // yellow phosphor
  emit_led:       ['#E2B43A', { emissive: [1, 0.86, 0.66], strength: 4 }],
  emit_opal:      ['#F4F2EE', { emissive: [1, 0.9, 0.78], strength: 3, emap: OPAL }],
  lens_glow:      ['#000000', { emissive: [1, 0.9, 0.78], strength: 4, emap: LENS, alpha: 0.35 }],
};
const seen = [];
for (const m of root.listMaterials()) {
  const s = SPEC[m.getName()];
  if (!s) throw new Error('no spec for material ' + m.getName());
  seen.push(m.getName());
  const [hex, o] = s;
  m.setBaseColorFactor([...lin(hex), o.alpha ?? 1]).setBaseColorTexture(null);
  m.setRoughnessFactor(1).setMetallicFactor(1);
  m.setMetallicRoughnessTexture(ORM); m.getMetallicRoughnessTextureInfo().setTexCoord(1);
  m.setOcclusionTexture(ORM); m.getOcclusionTextureInfo().setTexCoord(1); m.setOcclusionStrength(1);
  m.setDoubleSided(false);
  if (o.peel) { m.setNormalTexture(PEEL).setNormalScale(o.peel); m.getNormalTextureInfo().setTexCoord(0); }
  if (o.facet) { m.setNormalTexture(FACET).setNormalScale(o.facet); m.getNormalTextureInfo().setTexCoord(0); }
  if (o.clearcoat) m.setExtension('KHR_materials_clearcoat', cc.createClearcoat().setClearcoatFactor(o.clearcoat[0]).setClearcoatRoughnessFactor(o.clearcoat[1]));
  if (o.aniso) m.setExtension('KHR_materials_anisotropy', an.createAnisotropy().setAnisotropyStrength(o.aniso).setAnisotropyRotation(0));
  if (o.emissive) {
    m.setEmissiveFactor(o.emissive);
    if (o.emap) { m.setEmissiveTexture(o.emap); m.getEmissiveTextureInfo().setTexCoord(0); }
    m.setExtension('KHR_materials_emissive_strength', es.createEmissiveStrength().setEmissiveStrength(o.strength));
  }
  if (o.alpha != null) m.setAlphaMode('BLEND');
}
await doc.transform(
  prune(), dedup(), weld(),
  reorder({ encoder: MeshoptEncoder, target: 'size' }),
  quantize({ quantizePosition: 16, quantizeNormal: 12, quantizeTexcoord: 14, quantizeColor: 8, pattern: /^(POSITION|NORMAL|TANGENT|TEXCOORD_\d)$/ }),
);
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.FILTER });
await io.write(OUT, doc);
const sz = fs.statSync(OUT).size;
console.log(JSON.stringify({ out: OUT, bytes: sz, materials: seen, textures: root.listTextures().map(t => t.getURI()) }));
