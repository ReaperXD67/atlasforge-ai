import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import os from 'node:os';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
const here=path.dirname(fileURLToPath(import.meta.url));
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const receiptBytes=fs.readFileSync(path.join(here,'build-receipt.json'));
const receipt=JSON.parse(receiptBytes);
const sourceChecks=receipt.sources.map(s=>({path:s.path,expected_sha256:s.sha256,actual_sha256:digest(fs.readFileSync(path.join(here,s.path)))}));
if(sourceChecks.some(s=>s.expected_sha256!==s.actual_sha256))throw Error('Renderer source changed after the build; rebuild before capturing references.');
if(!fs.existsSync(path.join(here,'index.html')))throw Error('Run build.mjs first.');
let ppPath=process.env.BENZ_PUPPETEER_PATH;
if(!ppPath){
 const cache=path.join(os.homedir(),'AppData/Local/npm-cache/_npx');
 for(const child of fs.readdirSync(cache)){
  const dir=path.join(cache,child,'node_modules/puppeteer-core'),pkg=path.join(dir,'package.json');
  if(fs.existsSync(pkg)){const p=JSON.parse(fs.readFileSync(pkg));const candidate=path.join(dir,p.module||p.main);if(fs.existsSync(candidate)){ppPath=candidate;break;}}
 }
}
if(!ppPath)throw Error('No installed HyperFrames puppeteer-core found. Set BENZ_PUPPETEER_PATH to its module path.');
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
const bindingMode=process.argv.includes('--bindings');
const timesArg=process.argv.indexOf('--times');
const requested=timesArg>=0?process.argv[timesArg+1].split(',').map(Number):null;
if(requested?.some(t=>!Number.isFinite(t)||t<0||t>=receipt.duration))throw Error('Requested times must be finite and within the recording.');
if(bindingMode&&!requested)throw Error('--bindings requires explicit --times for exact frame references.');
const selectionArg=process.argv.indexOf('--scene-indices');
const selected=selectionArg>=0?process.argv[selectionArg+1].split(',').map(Number):null;
const labelArg=process.argv.indexOf('--label'),label=labelArg>=0?process.argv[labelArg+1]:null;
if(label&&!/^[a-zA-Z0-9_-]+$/.test(label))throw Error('Label must contain only letters, digits, hyphens or underscores.');
const output=path.join(here,label?`renders/${label}`:bindingMode?'renders/bindings':selected?'renders/targeted':seamMode?'renders/seams':'renders/smoke');fs.mkdirSync(output,{recursive:true});
try{
 const chrome=process.env.HYPERFRAMES_BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe';
 const hardware=process.argv.includes('--gpu');
 const gpuArgs=hardware?['--use-gl=angle','--use-angle=d3d11']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
 browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--disable-dev-shm-usage',...gpuArgs]});
 const page=await browser.newPage();await page.setViewport({width:1920,height:1080,deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(`http://127.0.0.1:${server.address().port}/index.html`,{waitUntil:'domcontentloaded',timeout:120000});
 await page.waitForFunction(()=>window.BENZ_READY||window.BENZ_ERROR,{timeout:120000});
 const error=await page.evaluate(()=>window.BENZ_ERROR);if(error)throw Error(error);
 const gpu=await page.evaluate(()=>{const gl=document.getElementById('world').getContext('webgl2');const d=gl.getExtension('WEBGL_debug_renderer_info');return {renderer:d?gl.getParameter(d.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),vendor:d?gl.getParameter(d.UNMASKED_VENDOR_WEBGL):gl.getParameter(gl.VENDOR)};});
 const times=await page.evaluate(({seamMode,selected,requested,bindingMode})=>{
  const p=window.BENZ_PLAN,t=selected?[]:[0,p.duration-1/p.fps];
  if(requested)return requested.map(t=>bindingMode?Math.floor(t*p.fps)/p.fps:t);
  for(const [index,s]of p.scenes.entries()){
   if(selected&&!selected.includes(index))continue;
   if(seamMode){if(s.transition?.kind==='luma')t.push(Math.max(0,s.start-1/p.fps),s.start,s.start+(s.transition.duration??.65)/2,s.start+(s.transition.duration??.65)+1/p.fps);}
   else t.push(s.start+Math.min(.35,(s.end-s.start)/2),s.start+(s.end-s.start)*.73);
  }
  return [...new Set(t)].sort((a,b)=>a-b);
 },{seamMode,selected,requested,bindingMode});
 const samples=[];
 for(const [i,t]of times.entries()){
  const stats=await page.evaluate(t=>{const a=performance.now();const state=window.seek(t);document.getElementById('world').getContext('webgl2').finish();const b=performance.now();return {...state,render_finish_ms:b-a};},t);
  const name=bindingMode?`frame-${String(Math.round(t*receipt.fps)).padStart(5,'0')}.png`:`frame-${String(i).padStart(3,'0')}.png`;
  const bytes=await page.screenshot({path:path.join(output,name)});
  samples.push({...stats,path:name,requested_seconds:requested?.[i]??t,sha256:digest(bytes)});
 }
 const repeatTime=times[Math.min(2,times.length-1)];
 await page.evaluate(t=>window.seek(t),repeatTime);const a=await page.screenshot();
 await page.evaluate(()=>{window.seek(window.BENZ_PLAN.duration-.1);window.seek(0);});
 await page.evaluate(t=>window.seek(t),repeatTime);const b=await page.screenshot();
 const repeatEqual=Buffer.compare(Buffer.from(a),Buffer.from(b))===0;
 const buildPlanSha=await page.evaluate(()=>window.BENZ_BUILD_PLAN_SHA||null);
 const contracts=await page.evaluate(async()=>({build:await window.BENZ_READY_PROMISE,face:window.BENZ_FRAME_CHECKS,coverage:window.BENZ_COVERAGE_CHECKS}));
 const result={schema_version:2,entrypoint:'index.html',build_plan_sha256:buildPlanSha,resolution:[1920,1080],browser:hardware?'Chrome headless ANGLE D3D11':'Chrome headless SwiftShader',gpu,sample_count:samples.length,repeat_time:repeatTime,repeat_seek_identical:repeatEqual,contracts,errors,samples};
 fs.writeFileSync(label||bindingMode?path.join(output,'result.json'):path.join(here,selected?'targeted-result.json':seamMode?'seam-result.json':'smoke-result.json'),JSON.stringify(result,null,2)+'\n');
 if(bindingMode){
  const references=samples.map(s=>({requested_seconds:s.requested_seconds,frame:Math.round(s.time*receipt.fps),time_seconds:s.time,path:s.path,sha256:s.sha256,scene:s.scene}));
  const manifest={schema_version:1,scope:'Exact frame-aligned expected pictures from the current frozen Benz build.',plan_sha256:buildPlanSha,build_receipt_sha256:digest(receiptBytes),build_sources_sha256:digest(Buffer.from(JSON.stringify(sourceChecks))),build_sources:sourceChecks,resolution:[1920,1080],fps:receipt.fps,duration:receipt.duration,gpu:gpu.renderer,errors,references};
  fs.writeFileSync(path.join(output,'reference-bindings.json'),JSON.stringify(manifest,null,2)+'\n');
 }
 console.log(JSON.stringify({sample_count:samples.length,repeat_seek_identical:repeatEqual,errors,output:path.relative(here,output),gpu}));
 if(errors.length||!repeatEqual)process.exitCode=1;
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
