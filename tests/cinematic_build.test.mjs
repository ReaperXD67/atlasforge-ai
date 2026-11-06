import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {assetUrl,projectFile,motionClipTiming,probeMotionSource} from '../scripts/lib/cinematic_build.mjs';

const require=createRequire(import.meta.url);
const primitives=require('../scripts/lib/cinematic_primitives.js');
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const shot={id:'motion',asset:'assets/motion.mp4',display_start_frame:30,display_end_frame:150};
const source=duration=>({streams:[{codec_type:'video',duration:String(duration),avg_frame_rate:'20/1',nb_read_frames:'65'}]});
function cleanupTemp(dir){
  const resolved=fs.realpathSync(dir),temporaryRoot=fs.realpathSync(os.tmpdir());
  assert.equal(path.dirname(resolved),temporaryRoot);
  assert.match(path.basename(resolved),/^cinematic-(path|symlink|probe)-/);
  fs.rmSync(resolved,{recursive:true,force:true});
}

test('motion fills its complete displayed range without freezing or speeding up',()=>{
  const result=motionClipTiming(shot,30,source(3.25));
  assert.equal(result.edit_duration_seconds,4);
  assert.equal(result.playback_rate,0.8125);
  assert.equal(result.source_consumed_seconds,3.25);
  const lastVisibleSource=((shot.display_end_frame-1-shot.display_start_frame)/30)*result.playback_rate;
  assert.ok(lastVisibleSource<result.source_duration_seconds);
  assert.equal(motionClipTiming(shot,30,source(8)).playback_rate,1);
});

test('exact20percent slowdown is accepted and larger slowdown rejected',()=>{
  assert.equal(motionClipTiming(shot,30,source(3.2)).playback_rate,0.8);
  assert.throws(()=>motionClipTiming(shot,30,source(3.19)),/needs more motion/);
});

test('transition handles count towards motion duration',()=>{
  const withHandles={...shot,start_frame:30,end_frame:150,display_start_frame:24,display_end_frame:156};
  assert.throws(()=>motionClipTiming(withHandles,30,source(3.25)),/needs more motion/);
});

test('longer container audio cannot disguise a short video stream',()=>{
  const media=source(3.25);media.format={duration:'99'};
  media.streams.push({codec_type:'audio',duration:'99'});
  assert.equal(motionClipTiming(shot,30,media).playback_rate,0.8125);
});

test('missing video duration falls back to counted frames, never container duration',()=>{
  const media={format:{duration:'99'},streams:[{codec_type:'video',duration:'N/A',nb_read_frames:'65',avg_frame_rate:'20/1'}]};
  const result=motionClipTiming(shot,30,media);
  assert.equal(result.source_duration_seconds,3.25);
  assert.equal(result.source_duration_basis,'video-frame-count');
  delete media.streams[0].nb_read_frames;
  assert.throws(()=>motionClipTiming(shot,30,media),/no reliable video duration/);
});

test('invalid frame range and unprobed video fail closed',()=>{
  assert.throws(()=>motionClipTiming({...shot,display_end_frame:30},30,source(3.25)),/Invalid displayed/);
  assert.throws(()=>motionClipTiming({...shot,display_start_frame:-1},30,source(3.25)),/Invalid displayed/);
  assert.throws(()=>motionClipTiming(shot,30,{streams:[{codec_type:'audio',duration:'4'}]}),/video stream/);
  assert.throws(()=>motionClipTiming(shot,30,{streams:[{codec_type:'video',duration:'NaN'}]}),/no reliable/);
});

test('rate serialization cannot round upward beyond available picture',()=>{
  const result=motionClipTiming({...shot,display_end_frame:151},30,source(3.25));
  assert.equal(Number(result.playback_rate.toFixed(8)),result.playback_rate);
  assert.ok(result.source_consumed_seconds<=result.source_duration_seconds+1e-8);
  assert.ok(result.playback_rate>=0.8);
});

test('local asset URLs preserve spaces, unicode and URL metacharacters',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'cinematic-path-'));
  t.after(()=>cleanupTemp(dir));
  fs.mkdirSync(path.join(dir,'assets'));
  const name='assets/café #&%.wav';fs.writeFileSync(path.join(dir,name),'fixture');
  assert.equal(assetUrl(dir,name),'assets/caf%C3%A9%20%23%26%25.wav');
  assert.equal(fs.readFileSync(projectFile(dir,name),'utf8'),'fixture');
  for(const invalid of ['../outside.wav','C:/outside.wav','/outside.wav','assets\\outside.wav','https://example.com/file']) {
    assert.throws(()=>projectFile(dir,invalid),/project-relative/);
  }
});

test('symlink to an outside asset cannot pass local path validation',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'cinematic-symlink-'));
  t.after(()=>cleanupTemp(dir));
  const project=path.join(dir,'project');fs.mkdirSync(project);
  const outside=path.join(dir,'outside.wav');fs.writeFileSync(outside,'outside');
  try{fs.symlinkSync(outside,path.join(project,'escape.wav'));}
  catch(error){if(error.code==='EPERM'){t.skip('Windows symlink privilege unavailable');return;}throw error;}
  assert.throws(()=>projectFile(project,'escape.wav'),/escaping project asset/);
});

test('dissolve states preserve coverage at exact boundaries and midpoint',()=>{
  const options={startFrame:24,endFrame:36};
  for(const frame of [23,24,30,35.999,36,37]){
    const state=primitives.dissolveStateAt(frame,options);
    const compositeAlpha=state.incomingOpacity+state.outgoingOpacity*(1-state.incomingOpacity);
    assert.equal(compositeAlpha,1);
    assert.equal(state.outgoingVisible,frame<36);
    assert.equal(state.incomingVisible,frame>=24);
  }
  assert.equal(primitives.dissolveStateAt(30,options).incomingOpacity,0.5);
});

test('actual scene callback fades inner incoming world over opaque outgoing world',()=>{
  const nodes=new Map();
  for(const id of ['s1','s2']){
    const world={style:{}};
    nodes.set(id,{style:{},world,querySelector:selector=>selector==='.world'?world:null,querySelectorAll:()=>[]});
  }
  const plan={duration_frames:60,fps:30,captions:[],shots:[
    {id:'s1',start_frame:0,end_frame:30,duration_frames:30,display_start_frame:0,display_end_frame:36},
    {id:'s2',start_frame:30,end_frame:60,duration_frames:30,display_start_frame:24,display_end_frame:60},
  ],transitions:[{kind:'dissolve',frames:12,from_shot:'s1',to_shot:'s2',cut_frame:30,start_frame:24,end_frame:36}]};
  const window={CINEMATIC_PLAN:plan,CINEMATIC_DIRECTION:{shots:{s1:{camera_from:[1.11,3,-5],camera_to:[1.2,8,-9]},s2:{camera_from:[1.08,-4,7],camera_to:[1.16,3,11]}}}};
  const document={getElementById:id=>nodes.get(id),documentElement:{dataset:{}}};
  const context={window,document,AtlasForgeCinematic:primitives,gsap:{timeline:()=>({to(){return this;}})}};
  vm.runInNewContext(fs.readFileSync(path.join(root,'scripts/templates/cinematic/cinematic.js'),'utf8'),context);
  window.renderCinematicFrame(24);
  assert.equal(nodes.get('s1').world.style.opacity,'1');
  assert.equal(nodes.get('s2').world.style.opacity,'0');
  window.renderCinematicFrame(30);
  assert.equal(nodes.get('s1').world.style.opacity,'1');
  assert.equal(nodes.get('s2').world.style.opacity,'0.5');
  window.renderCinematicFrame(36);
  assert.equal(nodes.get('s1').style.visibility,'hidden');
  assert.equal(nodes.get('s2').world.style.opacity,'1');
  window.renderCinematicFrame(23);
  assert.equal(nodes.get('s1').style.visibility,'visible');
  assert.equal(nodes.get('s1').world.style.opacity,'1');
  assert.equal(nodes.get('s2').style.visibility,'hidden');
  assert.equal(nodes.get('s2').world.style.opacity,'0');
  for(const epsilon of [-0.00001,0,0.00001]){
    // HyperFrames data-start and GSAP's clock may straddle the same frame by
    // several microframes. Every decision must use the same normalized clock.
    window.renderCinematicFrame(24+epsilon);
    assert.equal(nodes.get('s2').style.visibility,'visible');
    assert.equal(nodes.get('s2').world.style.opacity,'0');
    assert.equal(nodes.get('s2').world.style.transform,'translate(-4px,7px) scale(1.08)');
    window.renderCinematicFrame(30+epsilon);
    assert.equal(nodes.get('s2').world.style.opacity,'0.5');
    window.renderCinematicFrame(36+epsilon);
    assert.equal(nodes.get('s1').style.visibility,'hidden');
    assert.equal(nodes.get('s1').world.style.opacity,'0');
    assert.equal(nodes.get('s2').world.style.opacity,'1');
    window.renderCinematicFrame(epsilon);
    assert.equal(nodes.get('s1').style.visibility,'visible');
    assert.equal(nodes.get('s1').world.style.transform,'translate(3px,-5px) scale(1.11)');
  }
  // Ordinary subframe preview interpolation is retained outside the tiny
  // serialization tolerance rather than rounding the entire preview clock.
  window.renderCinematicFrame(30.01);
  assert.ok(Number(nodes.get('s2').world.style.opacity)>0.5);
  // A hard cut has no transition loop to initialize the incoming camera.
  plan.transitions=[];
  plan.shots[0].display_end_frame=30;plan.shots[1].display_start_frame=30;
  for(const epsilon of [-0.00001,0,0.00001]){
    window.renderCinematicFrame(50);
    window.renderCinematicFrame(30+epsilon);
    assert.equal(nodes.get('s1').style.visibility,'hidden');
    assert.equal(nodes.get('s1').world.style.opacity,'0');
    assert.equal(nodes.get('s2').style.visibility,'visible');
    assert.equal(nodes.get('s2').world.style.opacity,'1');
    assert.equal(nodes.get('s2').world.style.transform,'translate(-4px,7px) scale(1.08)');
  }
  const css=fs.readFileSync(path.join(root,'scripts/templates/cinematic/cinematic.css'),'utf8');
  assert.match(css,/\.shot\{[^}]*background:transparent/);
  assert.match(css,/\.world\{[^}]*background:#101a1b/);
  assert.equal([...css.matchAll(/font-size:(\d+)px/g)].some(match=>Number(match[1])<28),false);
});

test('real probe uses picture duration despite longer container audio',t=>{
  if(spawnSync('ffmpeg',['-version']).status!==0||spawnSync('ffprobe',['-version']).status!==0){t.skip('FFmpeg unavailable');return;}
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'cinematic-probe-'));
  t.after(()=>cleanupTemp(dir));
  const file=path.join(dir,'long-audio.mp4');
  const encoded=spawnSync('ffmpeg',['-v','error','-f','lavfi','-i','color=c=navy:s=64x64:r=20:d=1',
    '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-y',file],{encoding:'utf8',timeout:30000});
  assert.equal(encoded.status,0,encoded.stderr);
  const media=probeMotionSource(file),timing=motionClipTiming({id:'s1',asset:'motion.mp4',display_start_frame:0,display_end_frame:36},30,media);
  assert.equal(timing.source_duration_seconds,1);
  assert.ok(Math.abs(timing.playback_rate-1/1.2)<1e-8);
});

test('prepared film gives the host timing only for media, not a second scene clock',()=>{
  const html=fs.readFileSync(path.join(root,'videos/biznex-second-question/index.html'),'utf8');
  const sections=[...html.matchAll(/<section\b[^>]*class="[^"]*\bshot\b[^>]*>/g)];
  const captions=[...html.matchAll(/<div\b[^>]*class="[^"]*\bcaption\b[^>]*>/g)];
  assert.equal(sections.length,18);assert.ok(captions.length>0);
  for(const [tag] of [...sections,...captions]){
    assert.doesNotMatch(tag,/\bdata-(?:start|duration)=/);
    assert.doesNotMatch(tag,/class="[^"]*\bclip\b/);
  }
  for(const [tag] of html.matchAll(/<img\b[^>]*>/g))assert.doesNotMatch(tag,/\bdata-start=/);
  const media=[...html.matchAll(/<(?:audio|video)\b[^>]*>/g)];
  assert.equal(media.length,3);
  for(const [tag] of media){assert.match(tag,/\bdata-start=/);assert.match(tag,/\bdata-duration=/);}
});
