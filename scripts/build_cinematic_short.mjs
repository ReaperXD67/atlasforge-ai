#!/usr/bin/env node
/** Build a real HyperFrames composition from a verified frame edit and art direction. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {assetUrl,projectFile,motionClipTiming,probeMotionSource} from './lib/cinematic_build.mjs';

const repository = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const project = path.resolve(process.argv[2] || 'videos/biznex-second-question');
const python = path.join(repository, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const check = spawnSync(python, [path.join(repository, 'scripts/compile_edit_plan.py'), path.join(project,'EDIT_PLAN.json'), '--check'], {encoding:'utf8'});
if (check.status !== 0) throw new Error(`Edit plan is stale or invalid: ${check.stdout}\n${check.stderr}`);
const plan = JSON.parse(fs.readFileSync(path.join(project, 'EDIT_PLAN.compiled.json'), 'utf8'));
if(plan.width!==1080||plan.height!==1920||plan.fps!==30)throw new Error('This cinematic scene template requires 1080x1920 at30fps');
const direction = JSON.parse(fs.readFileSync(path.join(project, 'DIRECTION.json'), 'utf8'));
const escape = x => String(x).replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const sec = frames => (frames / plan.fps).toFixed(6);
const motionTiming=[];
const relativeFile = name => escape(assetUrl(project,name));
for (const shot of plan.shots) {
  if (!direction.shots[shot.id]) throw new Error(`No visual direction for ${shot.id}`);
  const d=direction.shots[shot.id];
  if (!['photo','phone','signup','notes','note-question','question','terms','thought','ending'].includes(d.mode)) throw new Error(`Unknown scene mode ${d.mode}`);
}
const lines = text => escape(text || '').replaceAll('|', '<br>');
const sceneMarkup = (shot, d) => {
  const asset = relativeFile(shot.asset);
  const video = /\.(mp4|webm|mov)$/i.test(shot.asset);
  const duration = sec(shot.display_end_frame-shot.display_start_frame);
  let playbackRate=1;
  if(video){
    const timing=motionClipTiming(shot,plan.fps,probeMotionSource(projectFile(project,shot.asset)));
    playbackRate=timing.playback_rate;
    motionTiming.push(timing);
  }
  const plate = video
    ? `<video id="plate-${shot.id}" class="plate clip" src="${asset}" data-start="${sec(shot.display_start_frame)}" data-duration="${duration}" data-playback-rate="${playbackRate.toFixed(8)}" data-track-index="1" data-volume="0" muted playsinline preload="auto"></video>`
    : `<img id="plate-${shot.id}" class="plate" src="${asset}" alt="${escape(shot.action)}" data-layout-ignore>`;
  let overlay='';
  if (d.mode==='phone') overlay=`<div class="phone-copy"><div class="phone-label">A NEW BEGINNING</div><h2>${lines(d.heading || 'Ready?')}</h2><div class="phone-button">${escape(d.button || 'Create account')}</div><div class="phone-small">${escape(d.small || 'Take a moment first.')}</div></div>`;
  if (d.mode==='signup') overlay='<div class="app-screen signup-screen"><div class="app-status">9:41 <span>● ▰</span></div><div class="app-nav">←</div><div class="app-kicker">A NEW CHAPTER</div><h1>Create<br>an account.</h1><div class="form-label">Your name</div><div class="input-line">Mira</div><div class="form-label">Your email</div><div class="input-line"><span class="placeholder">Enter your email</span></div><div class="app-continue">Continue <span>↗</span></div><div class="illustration-label">Fictional interface</div></div>';
  if (d.mode==='notes'||d.mode==='note-question') overlay=`<div class="app-screen note-screen"><div class="app-status">9:42 <span>● ▰</span></div><div class="note-toolbar">‹ Notes <span>Done</span></div><div class="note-date">A moment to think.</div><h1>Before I<br>begin<span class="cursor">|</span></h1><div class="note-rule"></div>${d.mode==='note-question'?'<div class="note-answer">What do<br>I need?<svg viewBox="0 0 740 42" class="question-stroke"><path d="M6 26 Q340 4 728 19"/></svg></div>':''}<div class="illustration-label">Mira’s fictional note</div></div>`;
  if (d.mode==='question') overlay=`<div class="question-panel"><span class="question-prefix">${escape(d.prefix || 'ASK YOURSELF')}</span><h1>${lines(d.heading)}</h1><svg class="question-stroke" viewBox="0 0 740 42"><path d="M6 26 Q340 4 728 19"/></svg><div class="question-detail">${escape(d.detail || '')}</div></div>`;
  if (d.mode==='terms') overlay='<div class="research-panel"><div class="research-label">HER NEXT STEP</div><h1>Read.<br>Understand.<br>Then decide.</h1><div class="research-divider"></div><div class="research-name">Atomy</div><p>Current terms for your country.</p><div class="research-foot">Use the official local website.</div></div>';
  if (d.mode==='thought') overlay=`<div class="thought"><span>${escape(d.prefix || 'A FRESH START…')}</span><h1>${lines(d.heading || 'doing|what?')}</h1></div>`;
  if (d.mode==='ending') overlay='<div class="ending-copy"><h1>Ask the<br><em>second</em><br>question.</h1><div class="ending-brand">BizNex Stories</div><p>Small stories. Informed choices.</p></div>';
  const label = d.disclosure ? '<div class="fiction-disclosure">Fiction · AI visuals & voice</div>' : '';
  // GSAP owns scene visibility for both stills and videos. A second HyperFrames
  // clip clock on these wrappers can hide the incoming shot after our callback
  // at fractional-second boundaries. Only actual audio/video retain media time.
  return `<section id="${shot.id}" class="shot mode-${d.mode}"><div class="world" data-layout-allow-overflow>${plate}<div class="shot-shade"></div>${overlay}</div>${d.hook?`<div class="hook">${lines(d.hook)}</div>`:''}${label}</section>`;
};
const captions=plan.captions.filter(c=>!plan.shots.some(s=>c.start_frame>=s.start_frame&&c.start_frame<s.end_frame&&direction.shots[s.id].hide_captions)).map(c=>`<div id="${c.id}" class="caption"><span class="caption-inner">${c.words.map(w=>`<span data-word="${w.index}">${escape(w.text)}</span>`).join(' ')}</span></div>`).join('\n');
const master = relativeFile(direction.audio_master || 'assets/audio/master.wav');
const mix=JSON.parse(fs.readFileSync(path.join(project,'AUDIO_MIX.json'),'utf8'));
const masterHash=createHash('sha256').update(fs.readFileSync(path.join(project,direction.audio_master||'assets/audio/master.wav'))).digest('hex');
if(mix.master_sha256!==masterHash||Math.abs(mix.duration_seconds-plan.duration_seconds)>1/48000)throw new Error('Audio master receipt is stale or has the wrong duration');
const compiledHash=createHash('sha256').update(fs.readFileSync(path.join(project,'EDIT_PLAN.compiled.json'))).digest('hex');
if(mix.compiled_plan_sha256!==compiledHash)throw new Error('Audio mix belongs to a different compiled plan; run mix_cinematic_audio.py again');
const jsonForHtml = object => JSON.stringify(object).replaceAll('<', '\\u003c');
const html=`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920"><title>${escape(direction.title)}</title><link rel="stylesheet" href="cinematic.css"><script src="assets/vendor/gsap.min.js"></script></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="${sec(plan.duration_frames)}" data-width="${plan.width}" data-height="${plan.height}">
${plan.shots.map(s=>sceneMarkup(s,direction.shots[s.id])).join('\n')}
<div class="film-grain" data-layout-ignore></div>${captions}
<audio id="master-audio" src="${master}" data-start="0" data-duration="${sec(plan.duration_frames)}" data-track-index="5" data-volume="1"></audio>
</div><script src="assets/vendor/cinematic_primitives.js"></script><script>window.CINEMATIC_PLAN=${jsonForHtml(plan)};window.CINEMATIC_DIRECTION=${jsonForHtml(direction)};</script><script src="cinematic.js"></script></body></html>`;
fs.copyFileSync(path.join(repository,'scripts/lib/cinematic_primitives.js'),path.join(project,'assets/vendor/cinematic_primitives.js'));
for(const name of ['cinematic.css','cinematic.js']) {
  fs.copyFileSync(path.join(repository,'scripts/templates/cinematic',name),path.join(project,name));
}
fs.writeFileSync(path.join(project,'index.html'),html,'utf8');
const hashed = {};
for (const name of ['index.html','cinematic.css','cinematic.js','DIRECTION.json','EDIT_PLAN.compiled.json','AUDIO_MIX.json','assets/vendor/cinematic_primitives.js','assets/vendor/gsap.min.js',direction.audio_master || 'assets/audio/master.wav']) {
  hashed[name] = createHash('sha256').update(fs.readFileSync(path.join(project,name))).digest('hex');
}
fs.writeFileSync(path.join(project,'CINEMATIC_BUILD.json'),JSON.stringify({schema_version:1,project_id:plan.project_id,duration_frames:plan.duration_frames,fps:plan.fps,files:hashed,motion_timing:motionTiming,rendered:false},null,2)+'\n');
console.log(`Built ${plan.project_id}: ${plan.shots.length} shots, ${plan.duration_frames} frames, ${plan.captions.length} caption groups.`);
