/* Deterministic, frame-addressable cinematic composition. No wall-clock animation. */
(() => {
  const plan=window.CINEMATIC_PLAN, direction=window.CINEMATIC_DIRECTION;
  const clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
  const lerp=(a,b,t)=>a+(b-a)*t;
  const smooth=t=>t*t*(3-2*t);
  const scenes=plan.shots.map(s=>{const node=document.getElementById(s.id);return {s,d:direction.shots[s.id],node,world:node.querySelector('.world')};});
  const captions=plan.captions.map(c=>{const node=document.getElementById(c.id);return node?{c,node,words:c.words.map(w=>({w,node:node.querySelector('[data-word="'+w.index+'"]')}))}:null;}).filter(Boolean);
  function render(frame) {
    // HTML timestamps round to six decimal seconds and GSAP serializes time.
    // Normalize sub-milliframe noise before every visibility/camera/transition
    // decision, so a newly activated media clip never shows its unposed frame.
    const nearest=Math.round(frame);
    const f=clamp(Math.abs(frame-nearest)<=0.001?nearest:frame,0,plan.duration_frames-0.001);
    let primary=null;
    for(const scene of scenes) {
      const {s,d,node,world}=scene;
      const visible=f>=s.display_start_frame&&f<s.display_end_frame;
      node.style.visibility=visible?'visible':'hidden';
      // Hidden worlds remain transparent even if the media host reveals an
      // ancestor while preparing a frame; no previous seek state may leak.
      world.style.opacity=visible?'1':'0';world.style.clipPath='none';
      if(f>=s.start_frame&&f<s.end_frame)primary=scene;
      if(!visible)continue;
      const p=clamp((f-s.start_frame)/(s.duration_frames-1));
      const q=smooth(p),from=d.camera_from||[1.04,0,0],to=d.camera_to||from;
      const scale=lerp(from[0],to[0],q),x=lerp(from[1],to[1],q),y=lerp(from[2],to[2],q);
      world.style.transform=`translate(${x}px,${y}px) scale(${scale})`;
      if(d.focus){
        const pose=AtlasForgeCinematic.focusCameraAt(f,{startFrame:s.start_frame,endFrame:s.end_frame,...d.focus});
        world.style.transform=`translate(${pose.xPercent}%,${pose.yPercent}%) scale(${pose.scale})`;
      }
      const stroke=node.querySelector('.question-stroke path');
      if(stroke)stroke.style.strokeDashoffset=String(800*(1-smooth(clamp((p-.12)*3))));
      const noteItems=node.querySelectorAll('.note-questions p');
      noteItems.forEach((n,i)=>{n.style.opacity=String(clamp((p-.25-i*.17)*6));n.style.transform=`translateX(${(1-clamp((p-.25-i*.17)*6))*16}px)`;});
      const cursor=node.querySelector('.cursor');if(cursor)cursor.style.opacity=Math.floor((f-s.start_frame)/14)%2?'0':'1';
    }
    for(const t of plan.transitions) {
      if(t.kind==='match_cut'&&Math.abs(f-t.cut_frame)<=10){
        const pose=AtlasForgeCinematic.matchCutAt(f,{cutFrame:t.cut_frame,halfDurationFrames:10,axis:'y',distancePercent:-3,fromScale:1.03,toScale:1.03});
        const active=scenes.find(x=>x.s.id===(f<t.cut_frame?t.from_shot:t.to_shot));
        active.world.style.transform=`translate(${pose.xPercent}%,${pose.yPercent}%) scale(${pose.scale})`;
      }
      if(!t.frames||f<t.start_frame||f>=t.end_frame)continue;
      const p=clamp((f-t.start_frame)/t.frames),q=smooth(p);
      const a=document.getElementById(t.from_shot).querySelector('.world'),b=document.getElementById(t.to_shot).querySelector('.world');
      if(t.kind==='dissolve'){
        const state=AtlasForgeCinematic.dissolveStateAt(f,{startFrame:t.start_frame,endFrame:t.end_frame});
        a.style.opacity=String(state.outgoingOpacity);b.style.opacity=String(state.incomingOpacity);
      }
      if(t.kind==='wipe')b.style.clipPath=`inset(0 ${100*(1-q)}% 0 0)`;
      if(t.kind==='whip'){a.style.transform=`translateX(${-1080*q}px)`;b.style.transform=`translateX(${1080*(1-q)}px)`;}
    }
    for(const {c,node,words} of captions) {
      const show=f>=c.start_frame&&f<c.end_frame&&!primary?.d.hide_captions;
      node.style.visibility=show?'visible':'hidden';
      if(!show)continue;
      node.style.top=`${primary?.d.caption_y||1160}px`;
      for(const {w,node:word} of words)word.classList.toggle('active',f>=w.start_frame&&f<w.end_frame);
    }
    document.documentElement.dataset.frame=String(Math.floor(f));
  }
  window.__timelines=window.__timelines||{};
  const clock={frame:0};
  const timeline=gsap.timeline({paused:true});
  timeline.to(clock,{frame:plan.duration_frames,duration:plan.duration_frames/plan.fps,ease:'none',onUpdate:()=>render(clock.frame)},0);
  window.__timelines.main=timeline;
  window.renderCinematicFrame=render;
  render(0);
})();
