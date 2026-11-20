import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const FILM=path.dirname(HERE);
const REPO=path.resolve(FILM,'../..');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const args=process.argv.slice(2);
const option=(name,fallback)=>{let i=args.indexOf(name);return i<0?fallback:args[i+1];};
const planFile=path.resolve(process.cwd(),option('--plan',path.join(FILM,'edit-plan-v4.json')));
const plan=JSON.parse(fs.readFileSync(planFile,'utf8').replace(/^\uFEFF/,''));
const number=(x,fallback)=>Number.isFinite(Number(x))?Number(x):fallback;
plan.duration=number(plan.duration,196.760);plan.fps=number(plan.fps,24);
plan.width=number(plan.width,1920);plan.height=number(plan.height,1080);
if(plan.width!==1920||plan.height!==1080)throw Error('V4 composition must be 1920x1080.');
if(!Array.isArray(plan.scenes)||!plan.scenes.length)throw Error('Plan needs scenes.');
const inputs=[];
function freeze(source){
 if(typeof source!=='string'||!source)throw Error('Every media source must be a non-empty path.');
 if(/^[a-z]+:\/\//i.test(source))throw Error('Remote render-time media is not permitted.');
 const original=path.resolve(FILM,source),data=fs.readFileSync(original),sha256=digest(data);
 const ext=path.extname(original).toLowerCase();
 const local=`assets/media/${sha256.slice(0,20)}${ext}`;
 const target=path.join(HERE,local);fs.mkdirSync(path.dirname(target),{recursive:true});
 if(!fs.existsSync(target)||digest(fs.readFileSync(target))!==sha256)fs.writeFileSync(target,data);
 inputs.push({source:path.relative(FILM,original).replaceAll('\\','/'),local,sha256,bytes:data.length});
 return local;
}
const ids=new Set();let previousEnd=0;
for(const s of plan.scenes){
 if(!s.id||ids.has(s.id))throw Error('Unique scene id is required.');ids.add(s.id);
 if(!Number.isFinite(s.start)||!Number.isFinite(s.end)||s.end<=s.start)throw Error(`Invalid interval ${s.id}.`);
 if(Math.abs(s.start-previousEnd)>1/plan.fps+0.00001)throw Error(`Scene ${s.id} leaves a gap or overlap after ${previousEnd}.`);
 previousEnd=s.end;
 if(s.src)s.src=freeze(s.src);
  if(s.depthSrc)s.depthSrc=freeze(s.depthSrc);
  if(s.depthSrc&&!s.src)throw Error(`Scene ${s.id} depthSrc requires a non-human background plate.`);
 if(!s.src&&!(s.layers||[]).length)throw Error(`Scene ${s.id} needs a plate or layer.`);
 for(const layer of s.layers||[]){
  if(!['art','photo'].includes(layer.kind||'art'))throw Error(`Unknown layer kind in ${s.id}.`);
  if(layer.crop&&(!Array.isArray(layer.crop)||layer.crop.length!==4||layer.crop.some(v=>!Number.isFinite(v))))throw Error(`Invalid pixel crop in ${s.id}.`);
  layer.src=freeze(layer.src);
 }
 if(s.transition?.mask)s.transition.mask=freeze(s.transition.mask);
}
if(Math.abs(previousEnd-plan.duration)>1/plan.fps+0.00001)throw Error('Scenes must cover declared duration.');
if(plan.audio)plan.audio=freeze(plan.audio);
let captions=[];
if(typeof plan.captions==='string'){
 const source=path.resolve(FILM,plan.captions),data=fs.readFileSync(source);
 captions=JSON.parse(data.toString('utf8').replace(/^\uFEFF/,''));
 inputs.push({source:path.relative(FILM,source).replaceAll('\\','/'),sha256:digest(data),bytes:data.length,canonical_cues:true});
}else if(Array.isArray(plan.captions))captions=plan.captions;
plan.captions=captions;
const vendorSource=path.join(REPO,'videos/biznex-the-question-that-stayed/assets/vendor');
const vendorTarget=path.join(HERE,'assets/vendor');fs.mkdirSync(vendorTarget,{recursive:true});
const vendors=[];
for(const name of ['three.module.js','three.core.js','gsap.min.js','THREE-LICENSE.txt']){
 const data=fs.readFileSync(path.join(vendorSource,name));fs.writeFileSync(path.join(vendorTarget,name),data);
 vendors.push({path:`assets/vendor/${name}`,sha256:digest(data),bytes:data.length});
}
const fontSource=path.join(FILM,'assets/fonts/NotoSerifCJKsc-Regular.otf');
if(fs.existsSync(fontSource)){
 fs.mkdirSync(path.join(HERE,'assets/fonts'),{recursive:true});
 const data=fs.readFileSync(fontSource);fs.writeFileSync(path.join(HERE,'assets/fonts/NotoSerifCJKsc-Regular.otf'),data);
 vendors.push({path:'assets/fonts/NotoSerifCJKsc-Regular.otf',sha256:digest(data),bytes:data.length});
}
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const captionTags=captions.map((c,i)=>`<div id="cue-${i}" class="clip cue" data-start="${c.start}" data-duration="${c.end-c.start}" data-track-index="2" data-track-kind="captions"><span>${escape(c.text)}</span></div>`).join('\n');
const titles=plan.scenes.filter(s=>s.title||s.subtitle).map(s=>`<div id="title-${escape(s.id)}" class="clip scene-title" data-start="${s.start}" data-duration="${s.end-s.start}" data-track-index="3" data-track-kind="graphics"><span class="title-inner"><span class="eyebrow">${escape(s.subtitle)}</span><span class="hero-title">${escape(s.title)}</span></span></div>`).join('\n');
const audio=plan.audio?`<audio id="canonical-song" class="clip" data-start="0" data-duration="${plan.duration}" data-track-index="0" data-track-kind="audio" src="${plan.audio}"></audio>`:'';
const json=JSON.stringify(plan).replaceAll('<','\\u003c');
const html=`<!doctype html><html lang="zh-Hans"><head><meta charset="utf-8"><meta name="viewport" content="width=1920,height=1080"><link rel="icon" href="data:,"><title>有你，兄弟同心 · V4 image film</title><link rel="stylesheet" href="film.css"><script src="assets/vendor/gsap.min.js"></script></head><body><div id="root" data-composition-id="main" data-width="1920" data-height="1080" data-fps="${plan.fps}" data-duration="${plan.duration}"><div class="opaque-stage" data-layout-ignore></div><canvas id="world" data-layout-ignore></canvas><div class="caption-shade" data-layout-ignore></div>${audio}${captionTags}${titles}</div><script>window.V4_PLAN=${json};window.V4_BUILD_PLAN_SHA=${JSON.stringify(digest(fs.readFileSync(planFile)))};window.V4_REGISTER=function(timeline){window.__timelines=window.__timelines||{};window.__timelines["main"]=timeline;};</script><script type="module" src="renderer.mjs"></script></body></html>`;
fs.writeFileSync(path.join(HERE,'index.html'),html);
const sources=['renderer.mjs','film.css','build.mjs','vendor/LumaWipe.glsl'].map(name=>({path:name,sha256:digest(fs.readFileSync(path.join(HERE,name)))}));
const receipt={schema_version:1,plan:path.relative(FILM,planFile).replaceAll('\\','/'),plan_sha256:digest(fs.readFileSync(planFile)),duration:plan.duration,fps:plan.fps,width:plan.width,height:plan.height,scene_count:plan.scenes.length,cue_count:captions.length,inputs,vendors,sources,identity_policy:'Original photo bytes copied unchanged; pixel crop and camera-facing flat card only; no generated anatomy, displacement or retouching.',native_ai_video:false};
fs.writeFileSync(path.join(HERE,'build-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({built:'index.html',scenes:plan.scenes.length,cues:captions.length,media:inputs.length,duration:plan.duration}));
