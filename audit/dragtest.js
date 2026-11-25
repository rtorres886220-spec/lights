const http=require('http'),fs=require('fs'),path=require('path');const {chromium}=require('playwright');
const D='/home/user/lynar-landing', GF=__dirname+'/gf';
const srv=http.createServer((q,s)=>{const p=path.join(D,q.url.split('?')[0]==='/'?'/index.html':q.url.split('?')[0]);fs.readFile(p,(e,d)=>{if(e){s.writeHead(404);return s.end()}s.writeHead(200,{'Content-Type':'text/html'});s.end(d)})}).listen(8767);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const pg=await b.newPage({viewport:{width:960,height:600}});
await pg.route('https://fonts.**',r=>r.abort());
const errs=[];pg.on('pageerror',e=>errs.push(e.message));
await pg.goto('http://localhost:8767/');await pg.waitForFunction(()=>document.documentElement.dataset.ready==='1',null,{timeout:240000});
const q=()=>pg.evaluate(()=>{const p=window.__app.product.quaternion;return [p.x,p.y,p.z,p.w].map(v=>+v.toFixed(3))});
const rd=()=>pg.evaluate(()=>['rx','ry','rz'].map(i=>document.getElementById(i).textContent).join(' '));
console.log('start',await q(),await rd());
// horizontal drag (yaw)
await pg.mouse.move(600,300);await pg.mouse.down();for(let i=1;i<=10;i++)await pg.mouse.move(600+i*25,300);await pg.mouse.up();
await pg.waitForTimeout(2500);console.log('after horizontal',await q(),await rd());
// vertical drag (pitch) then diagonal
await pg.mouse.move(600,200);await pg.mouse.down();for(let i=1;i<=10;i++)await pg.mouse.move(600,200+i*20);await pg.mouse.up();
await pg.mouse.move(500,400);await pg.mouse.down();for(let i=1;i<=10;i++)await pg.mouse.move(500+i*20,400-i*20);await pg.mouse.up();
await pg.waitForTimeout(2500);console.log('after vertical+diag',await q(),await rd());
// keyboard
await pg.focus('#gl');await pg.keyboard.press('ArrowLeft');await pg.waitForTimeout(1500);console.log('after key',await q());
// light toggle + kelvin
await pg.click('#lightBtn');await pg.waitForTimeout(2000);console.log('pressed',await pg.getAttribute('#lightBtn','aria-pressed'),'biba spot',await pg.evaluate(()=>window.__app.rigs.biba.lights[0].l.intensity.toFixed(2)));
await pg.click('#lightBtn');await pg.waitForTimeout(2000);
await pg.evaluate(()=>window.__app.applyKelvin(4000));await pg.waitForTimeout(1500);console.log('lamp css',await pg.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--lamp')));
// chapter change returns orientation
await pg.evaluate(()=>window.__app.lenis.scrollTo(document.querySelectorAll('[data-ch]')[1],{immediate:true,force:true}));await pg.waitForTimeout(4000);console.log('ch',await pg.evaluate(()=>window.__app.current),'q after chapter',await q());
console.log('perf',await pg.evaluate(()=>JSON.stringify(window.__perf||null)),'errors',errs.length?errs:'none');
await b.close();srv.close()})();
