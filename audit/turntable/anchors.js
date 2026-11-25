// Compare world-space centres of the named nodes src.html relies on, old vs new GLB (mm).
const http=require('http'),fs=require('fs'),path=require('path');const {chromium}=require(process.env.PW||'playwright');
const REPO=path.resolve(__dirname,'../..'),NM='/home/user/tools/node_modules';const [,,A,B]=process.argv;
const srv=http.createServer((q,s)=>{let u=decodeURIComponent(q.url.split('?')[0]);let p=u.startsWith('/nm/')?path.join(NM,u.slice(4)):path.join(REPO,u);fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);return s.end()}s.writeHead(200,{'Content-Type':p.endsWith('.html')?'text/html':p.endsWith('.js')?'text/javascript':'application/octet-stream'});s.end(d)})}).listen(0);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});const pg=await b.newPage();
await pg.goto(`http://localhost:${srv.address().port}/audit/turntable/viewer.html?glb=/${A}`);await pg.waitForFunction(()=>window.__ready,null,{timeout:300000});
const N=['Intra-lighting_LYNAR-CS-SDI_Corner-element90_1','Intra-lighting_LYNAR-CS-SDI_End_cover001','Intra-lighting_LYNAR-CS-SDI_End_cover002','Intra-lighting_LYNAR-SDI004','LED011','Mirror002','Sestav_Atos_LYN001','EYE_60_C_double_angle001','Intra-lighting_LYNAR_RYLO-LightLineKalis001','IntraLighting_Indirect_ilumination001','Intra-lighting_LYNAR_BIBA-LYN001','LED016','LED020','Imported010','Imported011'];
const centres=async()=>pg.evaluate(N=>N.map(n=>{const o=window.__root.getObjectByName(n);if(!o)return [n,null];const c=window.__box(o);return [n,c]}),N);
await pg.addScriptTag({type:'module',content:"import * as THREE from 'three';window.__box=o=>{const b=new THREE.Box3().setFromObject(o);if(b.isEmpty())return null;const c=b.getCenter(new THREE.Vector3()).sub(window.__root.position);return c.toArray().map(v=>+(v*1000).toFixed(2))};window.__boxReady=1;"});
await pg.waitForFunction(()=>window.__boxReady);const ca=await centres();
await pg.goto(`http://localhost:${srv.address().port}/audit/turntable/viewer.html?glb=/${B}`);await pg.waitForFunction(()=>window.__ready,null,{timeout:300000});
await pg.addScriptTag({type:'module',content:"import * as THREE from 'three';window.__box=o=>{const b=new THREE.Box3().setFromObject(o);if(b.isEmpty())return null;const c=b.getCenter(new THREE.Vector3()).sub(window.__root.position);return c.toArray().map(v=>+(v*1000).toFixed(2))};window.__boxReady=1;"});
await pg.waitForFunction(()=>window.__boxReady);const cb=await centres();
let worst=0;for(let i=0;i<N.length;i++){const a=ca[i][1],c=cb[i][1];const d=a&&c?Math.hypot(a[0]-c[0],a[1]-c[1],a[2]-c[2]):NaN;worst=Math.max(worst,d||0);console.log(N[i].padEnd(48),a?'ok':'MISSING-A',c?'ok':'MISSING-B','delta_mm',d.toFixed(2));}
console.log('WORST_DELTA_MM',worst.toFixed(2));await b.close();srv.close();})();
