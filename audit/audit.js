const http=require('http'),fs=require('fs'),path=require('path');const {chromium}=require(process.env.PW||'playwright');
const D=process.env.PAGE_DIR||require('path').resolve(__dirname,'..'), GF=__dirname+'/gf', OUT=__dirname+'/aud';fs.mkdirSync(OUT,{recursive:true});
const srv=http.createServer((q,s)=>{const p=path.join(D,decodeURIComponent(q.url.split('?')[0]==='/'?'/index.html':q.url.split('?')[0]));fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);return s.end()}s.writeHead(200,{'Content-Type':p.endsWith('.html')?'text/html':'application/octet-stream'});s.end(d)})}).listen(8766);
const [,,mode='desktop',which='all']=process.argv;
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const vp=mode==='mobile'?{viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true}:{viewport:{width:1440,height:900},deviceScaleFactor:1};
const ctx=await b.newContext(vp);const pg=await ctx.newPage();
if(fs.existsSync(GF)) await pg.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:fs.readFileSync(GF+'/fonts.css')}));
if(fs.existsSync(GF)) await pg.route('https://fonts.gstatic.com/**',r=>{const f=GF+'/'+r.request().url().replace('https://fonts.gstatic.com/','').replace(/\//g,'_');r.fulfill({status:200,contentType:'font/woff2',body:fs.readFileSync(f)})});
const errs=[];pg.on('console',m=>{if(m.type()==='error'||m.type()==='warning')errs.push(m.type()+': '+m.text())});pg.on('pageerror',e=>errs.push('pageerror: '+e.message));
pg.on('requestfailed',r=>errs.push('reqfail: '+r.url().slice(0,80)));
await pg.goto('http://localhost:8766/');
await pg.waitForFunction(()=>document.documentElement.dataset.ready==='1',null,{timeout:240000});
const waitFrames=async n=>{const s=await pg.evaluate(()=>window.__fc);await pg.waitForFunction(t=>window.__fc>=t,s+n,{timeout:240000});};
const chs=which==='all'?[0,1,2,3,4,5,6,7,8,9]:which.split(',').map(Number);
for(const i of chs){
  await pg.evaluate(i=>{const s=document.querySelectorAll('[data-ch]')[i];window.__app.lenis.scrollTo(s,{immediate:true,force:true});},i);
  await pg.waitForTimeout(2600); await waitFrames(12);
  await pg.screenshot({path:`${OUT}/${mode}_${i}.png`});
  console.log('shot',mode,i,'ch',await pg.evaluate(()=>window.__app.current));
}
console.log('fonts',await pg.evaluate(()=>[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family+' '+f.weight+' '+f.stretch).join(' | ')));
console.log(errs.slice(0,20).join('\n'));
await b.close();srv.close()})();
