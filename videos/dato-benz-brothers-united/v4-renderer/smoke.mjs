import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import os from 'node:os';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
const here=path.dirname(fileURLToPath(import.meta.url));
if(process.argv.includes('--demo')){
 const plan={duration:16,fps:24,width:1920,height:1080,captions:[],scenes:[
  {id:'arch-world',start:0,end:6,src:'assets/art-v4/12-bridge-anchor.png',cameraPreset:'reveal',layers:[{id:'bronze-foreground',src:'assets/art-v4/foreground-arch.png',kind:'art',height:9.5,x:-1.4,z:3.4}]},
  {id:'paper-world',start:6,end:10,src:'assets/art-v4/14-through-arches.png',cameraPreset:'traverse',occluder:'paper',transition:{kind:'luma',duration:.7}},
  {id:'literal-photo',start:10,end:16,src:'assets/art-v4/13-coast.png',cameraPreset:'photo',silk:false,layers:[{id:'original-seaside',src:'assets/photos/seaside.jpg',kind:'photo',height:7.2,x:2,z:1}],title:'有你，兄弟同心',subtitle:'献给拿督斯里谢惠福',transition:{kind:'luma',duration:.7}}
 ]};
 fs.writeFileSync(path.join(here,'smoke-plan.json'),JSON.stringify(plan,null,2));
 const built=spawnSync(process.execPath,[path.join(here,'build.mjs'),'--plan',path.join(here,'smoke-plan.json')],{stdio:'inherit'});if(built.status)process.exit(built.status);
}
if(!fs.existsSync(path.join(here,'index.html')))throw Error('Run build.mjs first or smoke.mjs --demo.');
let ppPath=process.env.V4_PUPPETEER_PATH;
if(!ppPath){
 const cache=path.join(os.homedir(),'AppData/Local/npm-cache/_npx');
 for(const child of fs.readdirSync(cache)){
  const dir=path.join(cache,child,'node_modules/puppeteer-core'),pkg=path.join(dir,'package.json');
  if(fs.existsSync(pkg)){const p=JSON.parse(fs.readFileSync(pkg));const candidate=path.join(dir,p.module||p.main);if(fs.existsSync(candidate)){ppPath=candidate;break;}}
 }
}
if(!ppPath)throw Error('No installed HyperFrames puppeteer-core found. Set V4_PUPPETEER_PATH to its module path.');
const {default:puppeteer}=await import(pathToFileURL(ppPath).href);
const types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.otf':'font/otf','.wav':'audio/wav'};
const server=http.createServer((req,res)=>{
 let filename;
 try{filename=path.resolve(here,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));}catch{res.writeHead(400);res.end();return;}
 if(filename===here)filename=path.join(here,'index.html');
 if(!filename.startsWith(here+path.sep)||!fs.existsSync(filename)){res.writeHead(404);res.end();return;}
 res.writeHead(200,{'Content-Type':types[path.extname(filename)]||'application/octet-stream'});fs.createReadStream(filename).pipe(res);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;
const seamMode=process.argv.includes('--seams');
const selectionArg=process.argv.indexOf('--scene-indices');
const selected=selectionArg>=0?process.argv[selectionArg+1].split(',').map(Number):null;
const labelArg=process.argv.indexOf('--label'),label=labelArg>=0?process.argv[labelArg+1]:null;
if(label&&!/^[a-zA-Z0-9_-]+$/.test(label))throw Error('Label must contain only letters, digits, hyphens or underscores.');
const output=path.join(here,label?`renders/${label}`:selected?'renders/targeted':seamMode?'renders/seams':'renders/smoke');fs.mkdirSync(output,{recursive:true});
try{
 const chrome=process.env.HYPERFRAMES_BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe';
 const hardware=process.argv.includes('--gpu');
 const gpuArgs=hardware?['--use-gl=angle','--use-angle=d3d11']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
 browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage',...gpuArgs]});
 const page=await browser.newPage();await page.setViewport({width:1920,height:1080,deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(`http://127.0.0.1:${server.address().port}/index.html`,{waitUntil:'domcontentloaded',timeout:120000});
 await page.waitForFunction(()=>window.V4_READY||window.V4_ERROR,{timeout:120000});
 const error=await page.evaluate(()=>window.V4_ERROR);if(error)throw Error(error);
 const gpu=await page.evaluate(()=>{const gl=document.getElementById('world').getContext('webgl2');const d=gl.getExtension('WEBGL_debug_renderer_info');return {renderer:d?gl.getParameter(d.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),vendor:d?gl.getParameter(d.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR)};});
 const times=await page.evaluate(({seamMode,selected})=>{
  const p=window.V4_PLAN,t=selected?[]:[0,p.duration-1/p.fps];
  for(const [index,s]of p.scenes.entries()){
   if(selected&&!selected.includes(index))continue;
   if(seamMode){if(s.transition?.kind==='luma')t.push(Math.max(0,s.start-1/p.fps),s.start,s.start+(s.transition.duration??.65)/2,s.start+(s.transition.duration??.65)+1/p.fps);}
   else t.push(s.start+Math.min(.35,(s.end-s.start)/2),s.start+(s.end-s.start)*.73);
  }
  return [...new Set(t)].sort((a,b)=>a-b);
 },{seamMode,selected});
 const samples=[];
 for(const [i,t]of times.entries()){
  const stats=await page.evaluate(t=>{const a=performance.now();const state=window.seek(t);document.getElementById('world').getContext('webgl2').finish();const b=performance.now();return {...state,render_finish_ms:b-a};},t);
  const bytes=await page.screenshot({path:path.join(output,`frame-${String(i).padStart(3,'0')}.png`)});
  samples.push({...stats,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});
 }
 const repeatTime=times[Math.min(2,times.length-1)];
 await page.evaluate(t=>window.seek(t),repeatTime);const a=await page.screenshot();
 await page.evaluate(()=>{window.seek(window.V4_PLAN.duration-.1);window.seek(0);});
 await page.evaluate(t=>window.seek(t),repeatTime);const b=await page.screenshot();
 const repeatEqual=Buffer.compare(Buffer.from(a),Buffer.from(b))===0;
 const buildPlanSha=await page.evaluate(()=>window.V4_BUILD_PLAN_SHA||null);
 const result={schema_version:1,entrypoint:'index.html',build_plan_sha256:buildPlanSha,resolution:[1920,1080],browser:hardware?'Chrome headless ANGLE D3D11':'Chrome headless SwiftShader',gpu,sample_count:samples.length,repeat_time:repeatTime,repeat_seek_identical:repeatEqual,errors,samples};
 fs.writeFileSync(label?path.join(output,'result.json'):path.join(here,selected?'targeted-result.json':seamMode?'seam-result.json':'smoke-result.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify({sample_count:samples.length,repeat_seek_identical:repeatEqual,errors,output:path.relative(here,output),gpu}));
 if(errors.length||!repeatEqual)process.exitCode=1;
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
