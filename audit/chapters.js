// Screenshot all 10 chapters at 1440x900 (SwiftShader). Usage: node audit/chapters.js <page.html> <outdir>
const http=require('http'),fs=require('fs'),path=require('path');const {chromium}=require(process.env.PW||'playwright');
const [,,page,OUT]=process.argv;fs.mkdirSync(OUT,{recursive:true});const DIR=path.dirname(path.resolve(page)),FILE=path.basename(page);
const srv=http.createServer((q,s)=>{const u=q.url.split('?')[0];const p=path.join(DIR,u==='/'?FILE:u);fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);return s.end()}s.writeHead(200,{'Content-Type':p.endsWith('.html')?'text/html':'application/octet-stream'});s.end(d)})}).listen(0);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const pg=await (await b.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1})).newPage();
const errs=[];pg.on('pageerror',e=>errs.push('pageerror '+e.message));pg.on('console',m=>{if(m.type()==='error'||m.type()==='warning')errs.push(m.type()+' '+m.text().slice(0,200))});
await pg.goto(`http://localhost:${srv.address().port}/?${process.argv[4]||""}`);
await pg.waitForFunction(()=>document.documentElement.dataset.ready==='1',null,{timeout:300000});
const wf=async n=>{const s=await pg.evaluate(()=>window.__fc);await pg.waitForFunction(t=>window.__fc>=t,s+n,{timeout:300000});};
const n=await pg.evaluate(()=>document.querySelectorAll('[data-ch]').length);
for(let i=0;i<n;i++){await pg.evaluate(i=>window.__app.lenis.scrollTo(document.querySelectorAll('[data-ch]')[i],{immediate:true,force:true}),i);
 await pg.waitForTimeout(2800);await wf(10);await pg.screenshot({path:`${OUT}/ch${String(i).padStart(2,'0')}.png`});}
console.log(JSON.stringify({info:await pg.evaluate(()=>window.__info),perf:await pg.evaluate(()=>window.__perf),errors:errs.slice(0,20)}));
await b.close();srv.close()})();
