/* Read-only native Chrome QA and an optional actual-composition motion proof.
 * Usage: node verify_ai_motion.mjs --project . --output ../../output/bosston-ai-v3/qa
 *   --proof-start 46.6 --proof-duration 14 --fps 30
 * This serves local inputs; production files are never modified.
 */
import fs from 'node:fs/promises';
import fsSync from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {spawn, spawnSync} from 'node:child_process';
import {once} from 'node:events';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
function options(argv) {
  const out = {};
  for (let i=0;i<argv.length;i++) {
    if (!argv[i].startsWith('--')) throw new Error('Unknown positional argument: '+argv[i]);
    const key=argv[i].slice(2), value=argv[i+1];
    if (value===undefined || value.startsWith('--')) out[key]=true;
    else {out[key]=value;i++;}
  }
  return out;
}
const args=options(process.argv.slice(2));
if (args.help) {
  process.stdout.write('Read-only AI composition QA. Options: --project DIR --output DIR --at t,t --max-cuts 6 --render-function renderBosstonMasterAt --proof-start 46.6 --proof-duration 14 --fps 30 --chrome EXE --puppeteer PACKAGE_DIR --ffmpeg EXE\n');
  process.exit(0);
}
const project=path.resolve(String(args.project||HERE));
const output=path.resolve(String(args.output||path.join(project,'../../output/bosston-ai-v3/qa')));
const fps=Number(args.fps||30), renderFunction=String(args['render-function']||'renderBosstonMasterAt');
if (!(fps>0&&fps<=60)) throw new Error('QA fps must be 1..60.');
await fs.mkdir(output,{recursive:true});
const errors=[], externalRequests=[], failedRequests=[];
const report={
  passed:false, project, output, renderFunction,
  method:'Raw local composition in native Chrome; direct absolute-time master seeks, WebGL pixel measurements and full-composition screenshots.',
  limits:'This supplements HyperFrames checks. Black edge candidates are review flags, not automatically absent content. Timings are local samples, not sustained export benchmarks.',
};

function requireThat(ok,message){if(!ok)throw new Error(message);}
async function puppeteer() {
  const supplied=args.puppeteer||process.env.PUPPETEER_MODULE_DIR;
  if(!supplied){
    try{
      const req=createRequire(path.join(project,'package.json'));
      const resolved=req.resolve('puppeteer-core'),loaded=req('puppeteer-core');
      report.puppeteer={path:resolved,resolution:'project-local dependency'};
      return loaded.launch?loaded:loaded.default;
    }catch{/* An existing HyperFrames cache is the zero-install fallback below. */}
  }
  const candidates=[];
  if(supplied)candidates.push(path.join(String(supplied),'package.json'));
  const root=process.env.npm_config_cache||path.join(process.env.LOCALAPPDATA||path.join(process.env.USERPROFILE,'AppData/Local'),'npm-cache');
  const preferred=path.join(root,'_npx','5b41d52cc12ea726','node_modules','puppeteer-core','package.json');
  candidates.push(preferred);
  const dirs=await fs.readdir(path.join(root,'_npx'),{withFileTypes:true}).catch(()=>[]);
  for(const d of dirs)if(d.isDirectory())candidates.push(path.join(root,'_npx',d.name,'node_modules','puppeteer-core','package.json'));
  for(const p of candidates)if(fsSync.existsSync(p)){
    const req=createRequire(p), loaded=req('puppeteer-core');
    report.puppeteer={path:p,version:JSON.parse(await fs.readFile(p,'utf8')).version};
    return loaded.launch?loaded:loaded.default;
  }
  throw new Error('No installed puppeteer-core found; pass --puppeteer PACKAGE_DIR. No dependency is downloaded by this helper.');
}
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8',
  '.json':'application/json; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp',
  '.otf':'font/otf','.ttf':'font/ttf','.woff':'font/woff','.woff2':'font/woff2','.wav':'audio/wav','.mp4':'video/mp4'};
const server=http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    if(url.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}
    const relative=decodeURIComponent(url.pathname).replace(/^\/+/,''), file=path.resolve(project,relative||'index.html');
    if(!file.toLowerCase().startsWith(project.toLowerCase()+path.sep)){res.writeHead(403);res.end();return;}
    const stat=await fs.stat(file);if(!stat.isFile())throw new Error('not a file');
    res.writeHead(200,{'Content-Type':mime[path.extname(file).toLowerCase()]||'application/octet-stream','Content-Length':stat.size,'Cache-Control':'no-store'});
    fsSync.createReadStream(file).pipe(res);
  }catch{res.writeHead(404);res.end('Not found');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
let browser;
try{
  const api=await puppeteer();
  const chrome=String(args.chrome||process.env.HYPERFRAMES_BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe');
  requireThat(fsSync.existsSync(chrome),'Chrome executable is unavailable: '+chrome);
  browser=await api.launch({executablePath:chrome,headless:true,defaultViewport:{width:1920,height:1080,deviceScaleFactor:1},
    args:['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-background-networking',
      '--force-color-profile=srgb','--enable-gpu','--use-gl=angle','--use-angle=d3d11','--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage();
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('requestfailed',r=>failedRequests.push({url:r.url(),error:r.failure()?.errorText}));
  page.on('response',r=>{if(r.status()>=400)errors.push(`HTTP ${r.status()} ${r.url()}`);});
  await page.setRequestInterception(true);
  page.on('request',r=>{
    if(r.url().startsWith(base)||/^(data:|blob:|about:)/.test(r.url()))r.continue();
    else{externalRequests.push(r.url());r.abort();}
  });
  await page.evaluateOnNewDocument(()=>{
    window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
    window.__timelines=window.__timelines||{};
  });
  await page.goto(base+'/index.html',{waitUntil:'networkidle0',timeout:120000});
  await page.waitForFunction(name=>typeof window[name]==='function'&&window.__bosstonAi,{timeout:120000},renderFunction);
  await page.evaluate(async()=>{await Promise.all(Object.values(window.__hf.buildReady));await document.fonts.ready;});
  report.browser=await browser.version();
  const state=await page.evaluate(()=>{
    const c=document.getElementById('ai-world'),g=c.getContext('webgl'),ext=g.getExtension('WEBGL_debug_renderer_info');
    return{assetCount:window.__bosstonAi.assetCount,depthCount:window.__bosstonAi.depthCount,
      depthFallbacks:window.__bosstonAi.depthFallbacks,depthConvention:window.__bosstonAi.depthConvention,
      width:c.width,height:c.height,glError:g.getError(),contextLost:g.isContextLost(),
      gpu:ext?{vendor:g.getParameter(ext.UNMASKED_VENDOR_WEBGL),renderer:g.getParameter(ext.UNMASKED_RENDERER_WEBGL)}:null,
      duration:window.FILM_DATA.duration,scenes:window.FILM_DATA.scenes.map(s=>({id:s.id,start:s.start,end:s.end,transition:s.transition,
        transitionDuration:s.transitionDuration,cameraEase:s.cameraEase,cameraFrom:s.cameraFrom,cameraTo:s.cameraTo}))};
  });
  report.ready=state;
  requireThat(state.width===1920&&state.height===1080,'Unexpected AI canvas size.');
  requireThat(state.depthCount===state.assetCount&&state.depthFallbacks.length===0,'Missing AI depth maps.');
  requireThat(!state.contextLost&&state.glError===0,'WebGL did not initialize cleanly.');
  // A performance timer measures the helper, never supplies animation state.
  async function seek(t){
    return page.evaluate(({time,name})=>{
      const started=performance.now();window[name](time);
      const canvas=document.getElementById('ai-world'),g=canvas.getContext('webgl');g.finish();
      const renderMs=performance.now()-started,rgba=new Uint8Array(1920*1080*4);g.readPixels(0,0,1920,1080,g.RGBA,g.UNSIGNED_BYTE,rgba);
      let hash=2166136261,black=0,total=0;
      for(let i=0;i<rgba.length;i++){hash^=rgba[i];hash=Math.imul(hash,16777619);}
      function band(x0,y0,x1,y1){let dark=0,n=0,sum=0;for(let y=y0;y<y1;y+=3)for(let x=x0;x<x1;x+=3){const i=(y*1920+x)*4,v=Math.max(rgba[i],rgba[i+1],rgba[i+2]);dark+=v<=4;n++;sum+=v;}return{blackFraction:dark/n,meanMaxRgb:sum/n};}
      const active=band(4,80,1916,1000);
      const edges={left:band(0,180,5,900),right:band(1915,180,1920,900),top:band(220,76,1700,81),bottom:band(220,999,1700,1004)};
      const candidates=Object.entries(edges).filter(([,v])=>v.blackFraction>.995&&active.blackFraction<.85).map(([k])=>k);
      return{time,shot:window.__bosstonAiShot,renderMs,canvasHash:(hash>>>0).toString(16),active,edges,edgeReviewCandidates:candidates,
        contextLost:g.isContextLost(),glError:g.getError()};
    },{time:t,name:renderFunction});
  }
  const at=args.at?String(args.at).split(',').map(Number):[1.2,8.7,24,38.5,50,59,94,120,141,167.7,179];
  const maxCuts=Number(args['max-cuts']||6),scenes=state.scenes;
  const selectedCuts=[];
  for(let i=0;i<Math.min(maxCuts,scenes.length-1);i++){
    const index=1+Math.floor(i*(scenes.length-1)/Math.min(maxCuts,scenes.length-1));selectedCuts.push(scenes[index]);
  }
  for(const s of selectedCuts)at.push((Math.ceil(s.start*fps)-1)/fps,s.start,s.start+Math.min(.15,(s.end-s.start)/3),s.start+(s.transitionDuration||.2)+1/fps);
  const times=[...new Set(at.filter(t=>Number.isFinite(t)&&t>=0&&t<state.duration).map(t=>Math.round(t*1000000)/1000000))].sort((a,b)=>a-b);
  report.samples=[];
  for(const t of times){
    const sample=await seek(t),filename=`frame-${String(report.samples.length).padStart(3,'0')}-${t.toFixed(3)}s.png`;
    await page.screenshot({path:path.join(output,filename),type:'png',captureBeyondViewport:false});
    sample.screenshot=filename;report.samples.push(sample);
  }
  const repeatAt=[times[Math.floor(times.length*.25)],times[Math.floor(times.length*.6)],times.at(-2)];
  report.determinism=[];
  for(const t of repeatAt){const a=await seek(t);await seek(Math.min(state.duration-.1,t+.537));const b=await seek(t);report.determinism.push({time:t,first:a.canvasHash,repeated:b.canvasHash,passed:a.canvasHash===b.canvasHash});}
  const sorted=report.samples.map(x=>x.renderMs).sort((a,b)=>a-b);
  report.performance={sampleCount:sorted.length,medianRenderMs:sorted[Math.floor(sorted.length/2)],p95RenderMs:sorted[Math.min(sorted.length-1,Math.floor(sorted.length*.95))],maximumRenderMs:sorted.at(-1),note:'Direct seek plus GPU finish; excludes screenshot/readback statistics and is not an export-speed benchmark.'};
  report.cutSamples=selectedCuts;
  report.edgeReviewTimes=report.samples.filter(s=>s.edgeReviewCandidates.length).map(s=>({time:s.time,edges:s.edgeReviewCandidates,screenshot:s.screenshot}));
  requireThat(report.samples.every(s=>!s.contextLost&&s.glError===0),'A sampled render produced a WebGL error.');
  requireThat(report.samples.every(s=>s.active.blackFraction<.995),'A sampled active picture is effectively blank.');
  requireThat(report.determinism.every(s=>s.passed),'Repeated absolute timestamps changed canvas pixels.');
  await fs.writeFile(path.join(output,'ai-motion-qa-interim.json'),JSON.stringify({...report,passed:true,proofPending:!!args['proof-duration']},null,2)+'\n');
  if(args['proof-duration']){
    const start=Number(args['proof-start']||0),duration=Number(args['proof-duration']),frames=Math.round(duration*fps);
    requireThat(start>=0&&duration>0&&start+duration<=state.duration,'Proof range is outside the composition.');
    const ffmpeg=String(args.ffmpeg||path.join(project,'../../.venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'));
    requireThat(fsSync.existsSync(ffmpeg),'Compatible FFmpeg executable not found: '+ffmpeg);
    const target=path.join(output,'Bosston-Pragon-AI-Cinema-Motion-Proof.mp4');
    const command=['-y','-hide_banner','-loglevel','error','-f','image2pipe','-framerate',String(fps),'-vcodec','png','-i','pipe:0',
      '-ss',String(start),'-i',path.join(project,'assets/bgm.wav'),'-map','0:v:0','-map','1:a:0','-frames:v',String(frames),'-t',String(duration),
      '-c:v','h264_nvenc','-preset','p5','-rc','vbr','-cq','18','-b:v','12M','-maxrate','20M','-bufsize','40M','-pix_fmt','yuv420p',
      '-c:a','aac','-b:a','320k','-ar','48000','-movflags','+faststart',target];
    const child=spawn(ffmpeg,command,{windowsHide:true,stdio:['pipe','ignore','pipe']});
    let encoderErrors='';child.stderr.on('data',d=>encoderErrors+=d.toString());
    const exited=once(child,'exit');
    const proofStills=new Set([0,Math.floor(frames*.2),Math.floor(frames*.4),Math.floor(frames*.6),Math.floor(frames*.8),frames-1]);
    const begin=Date.now();
    for(let frame=0;frame<frames;frame++){
      await page.evaluate(({t,name})=>{window[name](t);document.getElementById('ai-world').getContext('webgl').finish();}, {t:start+frame/fps,name:renderFunction});
      const png=await page.screenshot({type:'png',captureBeyondViewport:false});
      if(proofStills.has(frame))await fs.writeFile(path.join(output,`proof-${String(frame).padStart(4,'0')}.png`),png);
      if(!child.stdin.write(png))await once(child.stdin,'drain');
      if(frame%60===0)process.stdout.write(`Proof ${frame}/${frames}\n`);
    }
    child.stdin.end();const [code]=await exited;
    await fs.writeFile(path.join(output,'proof-encoder.log'),encoderErrors);
    requireThat(code===0,'Proof encoder failed: '+encoderErrors.slice(-1800));
    const probe=spawnSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json',target],{encoding:'utf8',windowsHide:true});
    requireThat(probe.status===0,'Proof metadata probe failed.');
    const meta=JSON.parse(probe.stdout),v=meta.streams.find(s=>s.codec_type==='video'),a=meta.streams.find(s=>s.codec_type==='audio');
    requireThat(v.width===1920&&v.height===1080&&Number(v.nb_frames)===frames,'Proof frame count/size mismatch.');
    requireThat(v.avg_frame_rate===`${fps}/1`&&a.channels===2&&Number(a.sample_rate)===48000,'Proof frame clock/audio format mismatch.');
    const decode=spawnSync(ffmpeg,['-v','error','-xerror','-i',target,'-f','null','-'],{encoding:'utf8',windowsHide:true,timeout:120000});
    requireThat(decode.status===0,'Proof full decoding failed: '+decode.stderr);
    report.proof={path:target,start,duration,frames,fps,width:v.width,height:v.height,fullDecode:true,
      captureWallSeconds:(Date.now()-begin)/1000,sizeBytes:(await fs.stat(target)).size,sha256:crypto.createHash('sha256').update(await fs.readFile(target)).digest('hex'),
      audio:'Exact requested original-master segment, stereo AAC320k; encoding is lossy. No independent listening claim.',encoder:ffmpeg};
    function decodedAudio(file,sourceStart=0){
      const command=['-v','error'];
      if(sourceStart)command.push('-ss',String(sourceStart));
      command.push('-i',file,'-t',String(duration),'-map','0:a:0','-ac','2','-ar','8000','-f','f32le','-');
      const decoded=spawnSync(ffmpeg,command,{windowsHide:true,maxBuffer:64*1024*1024});
      requireThat(decoded.status===0,'Proof audio decoding failed.');
      const b=decoded.stdout;return new Float32Array(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));
    }
    const original=decodedAudio(path.join(project,'assets/bgm.wav'),start),encoded=decodedAudio(target);
    const count=Math.floor(Math.min(original.length,encoded.length)/2),correlation=[];
    for(let channel=0;channel<2;channel++){
      let sx=0,sy=0,sxx=0,syy=0,sxy=0;
      for(let i=0;i<count;i++){const x=original[i*2+channel],y=encoded[i*2+channel];sx+=x;sy+=y;sxx+=x*x;syy+=y*y;sxy+=x*y;}
      correlation.push((sxy-sx*sy/count)/Math.sqrt((sxx-sx*sx/count)*(syy-sy*sy/count)));
    }
    requireThat(correlation.every(c=>c>=.98),'Proof original-audio correlation failed.');
    report.proof.audioComparison={offsetSamples:0,sampleRate:8000,comparedSamplesPerChannel:count,perChannelCorrelation:correlation};
  }
  requireThat(errors.length===0,'Browser reported page/shader/resource errors: '+errors.join('\n'));
  requireThat(externalRequests.length===0,'Composition requested nonlocal resources.');
  report.passed=true;
}catch(e){report.error=String(e.stack||e);process.exitCode=1;}
finally{
  report.errors=errors;report.externalRequests=externalRequests;report.failedRequests=failedRequests;
  if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));
  await fs.writeFile(path.join(output,'ai-motion-qa.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify({passed:report.passed,report:path.join(output,'ai-motion-qa.json'),performance:report.performance,proof:report.proof,error:report.error},null,2)+'\n');
}
