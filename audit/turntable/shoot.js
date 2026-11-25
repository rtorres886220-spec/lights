// Usage: node shoot.js <glb path relative to repo> <outdir> <shots.json> [query]
// shots.json: [{name,target,dir:"x,y,z",dist,fov}]
const http=require('http'),fs=require('fs'),path=require('path');const {chromium}=require(process.env.PW||'playwright');
const REPO=path.resolve(__dirname,'../..'), NM=process.env.NM||'/home/user/tools/node_modules';
const [,,glb,out,shotsFile,extra='']=process.argv; fs.mkdirSync(out,{recursive:true});
const srv=http.createServer((q,s)=>{let u=decodeURIComponent(q.url.split('?')[0]);let p=u.startsWith('/nm/')?path.join(NM,u.slice(4)):path.join(REPO,u);
 fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);return s.end()}s.writeHead(200,{'Content-Type':p.endsWith('.html')?'text/html':p.endsWith('.js')?'text/javascript':'application/octet-stream'});s.end(d)})}).listen(0);
(async()=>{const port=srv.address().port;const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const pg=await b.newPage({viewport:{width:1200,height:900}});const errs=[];pg.on('pageerror',e=>errs.push(e.message));pg.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await pg.goto(`http://localhost:${port}/audit/turntable/viewer.html?glb=/${glb}&${extra}`);
await pg.waitForFunction(()=>window.__ready,null,{timeout:300000});
for(const s of JSON.parse(fs.readFileSync(shotsFile))){const info=await pg.evaluate(s=>window.shoot(s.target,s.dir,s.dist,s.fov),s);
 await pg.locator('canvas').screenshot({path:`${out}/${s.name}.png`});console.log(s.name,JSON.stringify(info));}
if(errs.length)console.log('ERRORS',errs.join('|'));await b.close();srv.close();})();
