const http=require('http'),fs=require('fs'),path=require('path'),zlib=require('zlib');const {chromium}=require(process.env.PW||'playwright');
const D=process.env.PAGE_DIR||require('path').resolve(__dirname,'..'), GF=__dirname+'/gf';
const srv=http.createServer((q,s)=>{const u=q.url.split('?')[0];const p=path.join(D,u==='/'?'/index.html':u);fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);return s.end()}s.writeHead(200,{'Content-Type':'text/html'});s.end(d)})}).listen(8768);
const st=a=>{a=[...a].sort((x,y)=>x-y);const q=p=>a[Math.min(a.length-1,Math.floor(p*a.length))];return {n:a.length,p50:+q(.5).toFixed(2),p95:+q(.95).toFixed(2),max:+a[a.length-1].toFixed(2)}};
(async()=>{
const html=fs.readFileSync(D+'/index.html');
console.log('WEIGHT raw',html.length,'gzip',zlib.gzipSync(html,{level:9}).length,'brotli',zlib.brotliCompressSync(html).length);
const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--enable-precise-memory-info']});
for(const throttle of [1,4]){
const ctx=await b.newContext({viewport:{width:1440,height:900}});const pg=await ctx.newPage();
if(fs.existsSync(GF)) await pg.route('https://fonts.googleapis.com/**',r=>r.fulfill({status:200,contentType:'text/css',body:fs.readFileSync(GF+'/fonts.css')}));
if(fs.existsSync(GF)) await pg.route('https://fonts.gstatic.com/**',r=>r.fulfill({status:200,contentType:'font/woff2',body:fs.readFileSync(GF+'/'+r.request().url().replace('https://fonts.gstatic.com/','').replace(/\//g,'_'))}));
await pg.addInitScript(()=>{window.__lt=[];new PerformanceObserver(l=>l.getEntries().forEach(e=>window.__lt.push([e.startTime,e.duration]))).observe({type:'longtask',buffered:true});
 window.__cls=0;new PerformanceObserver(l=>l.getEntries().forEach(e=>{if(!e.hadRecentInput)window.__cls+=e.value})).observe({type:'layout-shift',buffered:true});
 window.__ri=[];let last=0;const f=t=>{if(last)window.__ri.push(t-last);last=t;if(window.__ri.length>4000)window.__ri.shift();requestAnimationFrame(f)};requestAnimationFrame(f);});
const cdp=await ctx.newCDPSession(pg);if(throttle>1)await cdp.send('Emulation.setCPUThrottlingRate',{rate:throttle});
const errs=[];pg.on('pageerror',e=>errs.push(e.message));pg.on('console',m=>m.type()==='error'&&errs.push(m.text()));
await pg.goto('http://localhost:8768/');
await pg.waitForFunction(()=>document.documentElement.dataset.ready==='1',null,{timeout:300000});
await pg.waitForTimeout(4000);
const load=await pg.evaluate(()=>{const n=performance.getEntriesByType('navigation')[0];const m=k=>performance.getEntriesByName(k)[0]?.startTime;
 const fcp=performance.getEntriesByName('first-contentful-paint')[0]?.startTime;return {domContentLoaded:+n.domContentLoadedEventEnd.toFixed(0),fcp:fcp&&+fcp.toFixed(0),modelParsed:+m('model-parsed').toFixed(0),firstFrame:+m('first-frame').toFixed(0)}});
const idle=await pg.evaluate(()=>{const r=window.__app.renderer.info;window.__ft=[];window.__ri=[];return {calls:window.__info.calls,triangles:window.__info.triangles,lights:(()=>{let n=0;window.__app.product.parent.traverse(o=>{if(o.isLight)n++});return n})(),programs:r.programs.length,geometries:r.memory.geometries,textures:r.memory.textures,heapMB:+(performance.memory.usedJSHeapSize/1048576).toFixed(1),longtasksDuringLoad:window.__lt.map(x=>Math.round(x[1]))}});
await pg.waitForTimeout(5000);
const idleFrames=await pg.evaluate(()=>[window.__ft.slice(),window.__ri.slice()]);
// smooth scroll through every chapter, with a live drag in the middle
await pg.evaluate(()=>{window.__lt=[];window.__ft=[];window.__ri=[];});
for(let i=1;i<10;i++){await pg.evaluate(i=>window.__app.lenis.scrollTo(document.querySelectorAll('[data-ch]')[i],{duration:1.2}),i);await pg.waitForTimeout(1600);}
await pg.mouse.move(900,400);await pg.mouse.down();for(let k=1;k<=30;k++){await pg.mouse.move(900+k*12,400+k*4);}await pg.mouse.up();await pg.waitForTimeout(1500);
const sc=await pg.evaluate(()=>({ft:window.__ft.slice(),ri:window.__ri.slice(),lt:window.__lt.map(x=>Math.round(x[1])),cls:+window.__cls.toFixed(4),heapMB:+(performance.memory.usedJSHeapSize/1048576).toFixed(1),perf:window.__perf||null}));
console.log(`\n=== CPU throttle ${throttle}x ===`);
console.log('LOAD ms',JSON.stringify(load));
console.log('SCENE',JSON.stringify(idle));
console.log('IDLE  JS frame cost ms',JSON.stringify(st(idleFrames[0])),' rAF interval ms (software GPU)',JSON.stringify(st(idleFrames[1])));
console.log('SCROLL+DRAG JS frame cost ms',JSON.stringify(st(sc.ft)),' rAF interval ms (software GPU)',JSON.stringify(st(sc.ri)));
console.log('long tasks during scroll+drag',JSON.stringify(sc.lt),'CLS',sc.cls,'heapMB',sc.heapMB,'adaptive',JSON.stringify(sc.perf));
console.log('errors',errs.length?errs:'none');
if(throttle===1){ // accessibility
 await pg.addScriptTag({path:__dirname+'/node_modules/axe-core/axe.min.js'});
 await pg.evaluate(()=>window.__app.lenis.scrollTo(0,{immediate:true}));await pg.waitForTimeout(1500);
 const ax=await pg.evaluate(async()=>{const r=await axe.run(document,{resultTypes:['violations']});return r.violations.map(v=>`${v.impact} ${v.id}: ${v.nodes.length} node(s) — ${v.nodes.slice(0,3).map(n=>n.target.join(' ')).join(', ')}`)});
 console.log('AXE violations',ax.length?'\n  '+ax.join('\n  '):'none');}
await ctx.close();}
await b.close();srv.close()})();
