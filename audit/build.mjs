// Bundle src.html + GLB into the self-contained index.html.
//   TOOLS=<dir with node_modules: three@0.170.0 gsap@3.12.5 lenis@1.1.13 esbuild@0.24.0> node audit/build.mjs [glb]
import fs from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
const D = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const W = process.env.TOOLS || '/home/user/tools';
const { build } = await import(path.join(W, 'node_modules/esbuild/lib/main.js'));
const GLB = process.argv[2] || path.join(D, 'lynar-l.glb');
let html = fs.readFileSync(D + '/src.html', 'utf8');
const m = html.match(/<script type="module">([\s\S]*?)<\/script>/);
fs.writeFileSync(W + '/app.js', m[1]);
const r = await build({ entryPoints: [W + '/app.js'], bundle: true, minify: true, format: 'esm', target: 'es2020', write: false, nodePaths: [W + '/node_modules'],
  alias: { 'gsap/ScrollTrigger': W + '/node_modules/gsap/ScrollTrigger.js' }, legalComments: 'none' });
const js = r.outputFiles[0].text.replace(/<\/script/g, '<\\/script');
const b64 = fs.readFileSync(GLB).toString('base64');
html = html.replace(/<script type="importmap">[\s\S]*?<\/script>\n/, '')
  .replace(m[0], () => '<script type="module">' + js + '</script>')
  .replace('<script>window.LYNAR_GLB=null;</script>', () => '<script>window.LYNAR_GLB="' + b64 + '";</script>');
const out = process.env.OUT || path.join(D, 'index.html');
fs.writeFileSync(out, html);
console.log('js', js.length, 'html', html.length, '->', out);
