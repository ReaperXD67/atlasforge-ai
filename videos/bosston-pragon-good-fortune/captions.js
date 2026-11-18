/* Text remains editable HTML. Line entrances follow measured vocal cues. */
(() => {
  const D=window.FILM_DATA,clamp=x=>Math.max(0,Math.min(1,x));
  const lines=D.captions.map((c,i)=>({cue:c,node:document.querySelector(`#lyric-${String(i).padStart(3,'0')} .lyric-inner`)}));
  lines.forEach(({cue,node})=>{if(/副歌|chorus/i.test(cue.section||''))node.parentElement.classList.add('chorus');if(cue.text.length>23)node.style.fontSize='43px';});
  const opening=document.querySelector('#opening-title .title-inner');
  const closing=document.querySelector('#closing-title .closing-inner');
  const brand=document.getElementById('brand');
  window.renderLyricsAt=t=>{
    for(const {cue:c,node} of lines){
      const a=clamp((t-c.start)/.1)*clamp((c.end-t)/.13);
      node.style.opacity=a;
      node.style.clipPath=`inset(0 ${100*(1-clamp((t-c.start)/.16))}% 0 0)`;
    }
    opening.style.opacity=clamp((t-.35)/.65)*clamp((4.5-t)/.6);
    closing.style.opacity=clamp((t-176.4)/1.1)*clamp((185-t)/1.1);
    brand.style.opacity=clamp(t/.9)*clamp((185-t)/1.1)*(t>176.4?1-clamp((t-176.4)/1):1);
  };
})();
