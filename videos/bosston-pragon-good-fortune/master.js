/* One soundtrack clock controls the authored footage windows and lyric poses. */
(() => {
  const D=window.FILM_DATA, clamp=x=>Math.max(0,Math.min(1,x));
  const fade=document.getElementById('render-fade');
  const windows=new Map(D.scenes.filter(s=>s.media==='video').map(s=>[s.id,document.getElementById(`footage-${s.id}`)]));
  window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
  window.__hf.buildReady.bosston=Promise.all([document.fonts.ready,...Array.from(document.images,img=>img.decode())]);
  window.renderBosstonMasterAt=t=>{
    const time=Math.max(0,Math.min(D.duration-.000001,t));
    const shot=D.scenes.find(s=>time>=s.start&&time<s.end)||D.scenes[D.scenes.length-1];
    for(const [id,node] of windows){
      node.style.opacity=id===shot.id?'1':'0';
      if(id===shot.id){
        const p=clamp((time-shot.start)/(shot.end-shot.start));
        // Footage provides the subject motion; the tiny reframe is lens breathing.
        node.style.transform=`scale(${1.008+p*.014})`;
      }
    }
    window.renderLyricsAt(time);
    fade.style.opacity=1-Math.min(clamp(time/.55),clamp((D.duration-time)/.8));
    window.__bosstonCurrentShot=shot.id;
  };
})();
