import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const FILM=path.resolve(HERE,'../..');
const REPO=path.resolve(FILM,'../..');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const args=process.argv.slice(2);
const option=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:args[i+1];};
const validateOnly=args.includes('--validate-only');
const planFile=path.resolve(process.cwd(),option('--plan',path.join(FILM,'edit-plan.json')));
const plan=JSON.parse(fs.readFileSync(planFile,'utf8').replace(/^\uFEFF/,''));
if(!Number.isFinite(plan.duration)||plan.duration<=0)throw Error('The measured recording duration is required. No inherited song-length default.');
plan.fps=plan.fps??24;plan.width=plan.width??1920;plan.height=plan.height??1080;
plan.background=plan.background||'#071319';
if(plan.fps!==24||plan.width!==1920||plan.height!==1080)throw Error('This verified delivery contract is 1920x1080 at24fps.');
if(!Array.isArray(plan.scenes)||!plan.scenes.length)throw Error('Plan needs scenes.');
plan.identityPolicy=plan.identityPolicy??'integrated';
if(!['integrated','excluded'].includes(plan.identityPolicy))throw Error('identityPolicy must be integrated or excluded.');
const identityExcluded=plan.identityPolicy==='excluded';
const identityFields=['faceBounds','subjectBounds','subjectPadding','faceMargin','faceSafeMargin','identity','identityReference','person','portrait','photo'];
function enforceExclusion(record,label){
 if(!identityExcluded)return;
 if(record.containsIdentity!==undefined&&typeof record.containsIdentity!=='boolean')throw Error(`identityPolicy excluded requires a boolean containsIdentity declaration: ${label}`);
 if(record.containsIdentity===true||identityFields.some(key=>Object.hasOwn(record,key)))throw Error(`identityPolicy excluded forbids identity, face or subject metadata: ${label}`);
 if(['photo','portrait','person','identity','card'].includes(record.kind))throw Error(`identityPolicy excluded forbids identity/card layers: ${label}`);
}
enforceExclusion(plan,'plan');
const inputs=[];
function localInput(source){
 if(typeof source!=='string'||!source||/^[a-z]+:\/\//i.test(source))throw Error('Only local project media paths are accepted.');
 const original=path.resolve(FILM,source),relative=path.relative(FILM,original);
 if(relative.startsWith('..')||path.isAbsolute(relative))throw Error(`Media must remain inside this Benz project: ${source}`);
 return original;
}
function freeze(source){
 const original=localInput(source),data=fs.readFileSync(original),sha256=digest(data);
 const ext=path.extname(original).toLowerCase();
 if(['.mp4','.webm','.mov','.mkv','.gif'].includes(ext))throw Error('Benz composition is image-only; no video/animated media inputs.');
 const local=`assets/media/${sha256.slice(0,20)}${ext}`,target=path.join(HERE,local);
 if(!validateOnly){
  fs.mkdirSync(path.dirname(target),{recursive:true});
  if(!fs.existsSync(target)||digest(fs.readFileSync(target))!==sha256)fs.writeFileSync(target,data);
 }
 inputs.push({source:path.relative(FILM,original).replaceAll('\\','/'),local,sha256,bytes:data.length});
 return local;
}
const normalizedRect=(r,label)=>{
 if(!Array.isArray(r)||r.length!==4||r.some(x=>!Number.isFinite(x))||r[0]<0||r[1]<0||r[2]<=0||r[3]<=0||r[0]+r[2]>1.00001||r[1]+r[3]>1.00001)throw Error(`${label} must be normalized [left,top,width,height] within the source image.`);
};
const ids=new Set();let previousEnd=0;
for(const s of plan.scenes){
 enforceExclusion(s,`scene ${s.id||'unnamed'}`);
 if(!s.id||ids.has(s.id))throw Error('Unique scene id is required.');ids.add(s.id);
 if(!Number.isFinite(s.start)||!Number.isFinite(s.end)||s.end<=s.start)throw Error(`Invalid scene interval ${s.id}.`);
 if(Math.abs(s.start-previousEnd)>1e-6)throw Error(`Scene ${s.id} leaves a gap or overlap after ${previousEnd}.`);
 previousEnd=s.end;
 if(!s.src)throw Error(`Scene ${s.id} needs a finished, integrated environment plate.`);
 if(s.containsIdentity&&s.depthSrc)throw Error(`Never depth-displace an integrated face/body: ${s.id}`);
 if(s.containsIdentity&&!s.faceBounds)throw Error(`Identity plate ${s.id} needs normalized faceBounds for safe framing.`);
 if(s.faceBounds)normalizedRect(s.faceBounds,`${s.id}.faceBounds`);
 if(s.subjectBounds)normalizedRect(s.subjectBounds,`${s.id}.subjectBounds`);
 for(const key of ['focalRect','focalRectEnd'])if(s[key])normalizedRect(s[key],`${s.id}.${key}`);
 if(s.camera?.some(k=>!Number.isFinite(k.at)||!Number.isFinite(k.z)))throw Error(`Invalid camera key in ${s.id}.`);
 if(s.camera&&(s.camera[0].at!==0||s.camera.at(-1).at!==1))throw Error(`Camera keys must cover0..1 in ${s.id}.`);
 if(s.camera?.some((k,i)=>i&&k.at<=s.camera[i-1].at))throw Error(`Camera key times must increase in ${s.id}.`);
 s.src=freeze(s.src);
 if(s.depthSrc)s.depthSrc=freeze(s.depthSrc);
 for(const layer of s.layers||[]){
  enforceExclusion(layer,`layer in ${s.id}`);
  if(!['art','foreground'].includes(layer.kind||'art'))throw Error(`Only integrated art/foreground layers, never photo/card overlays: ${s.id}`);
  if(layer.containsIdentity||layer.faceBounds)throw Error(`Human identity belongs in the integrated main plate, not a layer: ${s.id}`);
  if(layer.border||layer.frameColor)throw Error(`Photo-frame styling is excluded from this film: ${s.id}`);
  if(layer.crop&&(!Array.isArray(layer.crop)||layer.crop.length!==4||layer.crop.some(x=>!Number.isFinite(x))))throw Error(`Invalid crop ${s.id}`);
  layer.src=freeze(layer.src);
 }
 if(s.transition?.mask)s.transition.mask=freeze(s.transition.mask);
}
if(Math.abs(previousEnd-plan.duration)>1e-6)throw Error('Scenes must exactly cover measured recording duration.');
let measuredAudio=null;
if(plan.audio){
 const audioFile=localInput(plan.audio);
 const result=spawnSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',audioFile],{encoding:'utf8'});
 if(result.status!==0)throw Error(`Unable to probe the supplied recording: ${result.stderr||result.error}`);
 const metadata=JSON.parse(result.stdout),stream=metadata.streams.find(x=>x.codec_type==='audio');
 measuredAudio={duration_seconds:Number(stream?.duration||metadata.format.duration),sample_rate:Number(stream?.sample_rate),channels:stream?.channels};
 if(!Number.isFinite(measuredAudio.duration_seconds)||Math.abs(measuredAudio.duration_seconds-plan.duration)>.002)throw Error(`Plan duration ${plan.duration} must equal the actual trimmed recording ${measuredAudio.duration_seconds}.`);
 plan.audio=freeze(plan.audio);
}
let captions=[];
if(typeof plan.captions==='string'){
 const source=localInput(plan.captions),data=fs.readFileSync(source);
 captions=JSON.parse(data.toString('utf8').replace(/^\uFEFF/,''));
 inputs.push({source:path.relative(FILM,source).replaceAll('\\','/'),sha256:digest(data),bytes:data.length,canonical_cues:true});
}else if(Array.isArray(plan.captions))captions=plan.captions;
let lastCueEnd=0;
for(const cue of captions){
 if(!Number.isFinite(cue.start)||!Number.isFinite(cue.end)||cue.start<0||cue.start<lastCueEnd-1e-6||cue.end<=cue.start||cue.end>plan.duration+.001||typeof cue.text!=='string')throw Error('Canonical cue intervals/text must be valid, ordered and inside the trimmed recording.');
 lastCueEnd=cue.end;
}
plan.captions=captions;
const vendorSource=path.join(REPO,'videos/biznex-the-question-that-stayed/assets/vendor');
const vendorTarget=path.join(HERE,'assets/vendor');if(!validateOnly)fs.mkdirSync(vendorTarget,{recursive:true});
const vendors=[];
for(const name of ['three.module.js','three.core.js','gsap.min.js','THREE-LICENSE.txt']){
 const data=fs.readFileSync(path.join(vendorSource,name));if(!validateOnly)fs.writeFileSync(path.join(vendorTarget,name),data);
 vendors.push({path:`assets/vendor/${name}`,sha256:digest(data),bytes:data.length});
}
const fontName='NotoSerifCJKsc-Regular.otf';
const fontCandidates=[path.join(FILM,'assets/fonts',fontName),path.join(REPO,'videos/dato-benz-brothers-united/assets/fonts',fontName)];
const fontSource=fontCandidates.find(x=>fs.existsSync(x));
if(!fontSource)throw Error('The licensed local Mandarin font is required; no runtime font download.');
if(!validateOnly)fs.mkdirSync(path.join(HERE,'assets/fonts'),{recursive:true});
const fontData=fs.readFileSync(fontSource);if(!validateOnly)fs.writeFileSync(path.join(HERE,'assets/fonts',fontName),fontData);
vendors.push({path:`assets/fonts/${fontName}`,sha256:digest(fontData),bytes:fontData.length});
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const captionTags=captions.map((c,i)=>`<div id="cue-${i}" class="clip cue" data-start="${c.start}" data-duration="${c.end-c.start}" data-track-index="2" data-track-kind="captions"><span>${escape(c.text)}</span></div>`).join('\n');
const titles=plan.scenes.filter(s=>s.title||s.subtitle).map(s=>`<div id="title-${escape(s.id)}" class="clip scene-title" data-start="${s.start}" data-duration="${s.end-s.start}" data-track-index="3" data-track-kind="graphics"><span class="title-inner"><span class="eyebrow">${escape(s.subtitle)}</span><span class="hero-title">${escape(s.title)}</span></span></div>`).join('\n');
const audio=plan.audio?`<audio id="canonical-song" class="clip" data-start="0" data-duration="${plan.duration}" data-track-index="0" data-track-kind="audio" src="${plan.audio}"></audio>`:'';
const json=JSON.stringify(plan).replaceAll('<','\\u003c');
const html=`<!doctype html><html lang="zh-Hans"><head><meta charset="utf-8"><meta name="viewport" content="width=1920,height=1080"><link rel="icon" href="data:,"><title>Dato Benz · integrated image music film</title><link rel="stylesheet" href="film.css"><script src="assets/vendor/gsap.min.js"></script></head><body><div id="root" data-composition-id="main" data-width="1920" data-height="1080" data-fps="${plan.fps}" data-duration="${plan.duration}"><div class="opaque-stage" data-layout-ignore></div><canvas id="world" data-layout-ignore></canvas><div class="caption-shade" data-layout-ignore></div>${audio}${captionTags}${titles}</div><script>window.BENZ_PLAN=${json};window.BENZ_BUILD_PLAN_SHA=${JSON.stringify(digest(fs.readFileSync(planFile)))};window.BENZ_REGISTER=function(timeline){window.__timelines=window.__timelines||{};window.__timelines["main"]=timeline;};</script><script type="module" src="renderer.mjs"></script></body></html>`;
if(!validateOnly)fs.writeFileSync(path.join(HERE,'index.html'),html);
const sources=['renderer.mjs','film.css','build.mjs','vendor/LumaWipe.glsl'].map(name=>({path:name,sha256:digest(fs.readFileSync(path.join(HERE,name)))}));
const receipt={schema_version:2,plan:path.relative(FILM,planFile).replaceAll('\\','/'),plan_sha256:digest(fs.readFileSync(planFile)),duration:plan.duration,fps:plan.fps,width:plan.width,height:plan.height,scene_count:plan.scenes.length,cue_count:captions.length,first_cue_start:captions[0]?.start??null,measured_audio:measuredAudio,inputs,vendors,sources,identity_policy_mode:plan.identityPolicy,identity_scene_count:plan.scenes.filter(s=>s.containsIdentity).length,identity_policy:identityExcluded?'All identity/person declarations and framing metadata are excluded. Source artwork requires a separate face-free content review.':'Identity is integrated in the scene plate; no photo/card layers or depth on identity plates. Normalized face bounds are inspected in browser framing checks.',native_ai_video:false};
if(!validateOnly)fs.writeFileSync(path.join(HERE,'build-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({built:validateOnly?null:'index.html',validated:true,identity_policy:plan.identityPolicy,scenes:plan.scenes.length,cues:captions.length,media:inputs.length,duration:plan.duration,integrated_identity_scenes:plan.scenes.filter(s=>s.containsIdentity).length}));
