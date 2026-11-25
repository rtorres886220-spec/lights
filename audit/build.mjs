import fs from 'fs'; import { build } from 'esbuild';
const W='/tmp/claude-0/-home-user/71bea1d5-1852-559c-8221-ddba5218ec9e/scratchpad/work';
const D='/home/user/lynar-landing';
let html=fs.readFileSync(D+'/src.html','utf8');
const m=html.match(/<script type="module">([\s\S]*?)<\/script>/);
fs.writeFileSync(W+'/app.js',m[1]);
const r=await build({entryPoints:[W+'/app.js'],bundle:true,minify:true,format:'esm',target:'es2020',write:false,nodePaths:[W+'/node_modules'],
  alias:{'gsap/ScrollTrigger':W+'/node_modules/gsap/ScrollTrigger.js'},legalComments:'none'});
let js=r.outputFiles[0].text.replace(/<\/script/g,'<\\/script');
const b64=fs.readFileSync(D+'/lynar-l.glb').toString('base64');
html=html.replace(/<script type="importmap">[\s\S]*?<\/script>\n/,'')
 .replace(m[0],()=>'<script type="module">'+js+'</script>')
 .replace('<script>window.LYNAR_GLB=null;</script>',()=>'<script>window.LYNAR_GLB="'+b64+'";</script>');
fs.writeFileSync(D+'/index.html',html);
console.log('js',js.length,'html',html.length);
