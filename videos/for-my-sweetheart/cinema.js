/* Every picture derives from absolute film time; HyperFrames owns audio. */
(() => {
  const D=window.FILM_DATA,W=1920,H=1080,TOP=112,PH=804;
  const ctx=document.getElementById('world').getContext('2d',{alpha:false});
  const layers=[document.createElement('canvas'),document.createElement('canvas')];
  for(const c of layers){c.width=W;c.height=PH;}
  const lc=layers.map(c=>c.getContext('2d',{alpha:false}));
  const images={},clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
  const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
  const caption=document.getElementById('caption-text'),capBox=document.getElementById('caption');
  const dedication=document.getElementById('dedication');
  const eyebrow=document.getElementById('dedication-eyebrow');
  const title=document.getElementById('dedication-title'),note=document.getElementById('dedication-note');
  const grain=document.querySelector('.grain-texture');
  // Rasterize the registry's grain layer once; SVG turbulence on every frame is costly.
  const noise=document.createElement('canvas');noise.width=256;noise.height=256;
  const nc=noise.getContext('2d'),pixels=nc.createImageData(256,256);let seed=713;
  for(let i=0;i<pixels.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;
    const value=seed>>>24;pixels.data[i]=value;pixels.data[i+1]=value;pixels.data[i+2]=value;pixels.data[i+3]=255;}
  nc.putImageData(pixels,0,0);grain.style.backgroundImage=`url(${noise.toDataURL()})`;grain.style.backgroundSize='256px 256px';
  let lastCaption=-1;

  function energy(t){
    const e=D.audioMap.energy_curve || [];
    if(Array.isArray(e) && e.length && typeof e[0]==='object'){
      const step=e[1] ? e[1].time_seconds-e[0].time_seconds : .25;
      const i=Math.min(e.length-1,Math.max(0,Math.floor(t/step))),j=Math.min(e.length-1,i+1);
      const u=clamp((t-e[i].time_seconds)/Math.max(.001,e[j].time_seconds-e[i].time_seconds));
      return clamp(e[i].energy+(e[j].energy-e[i].energy)*u);
    }
    return t>202&&t<262?.22:t>262&&t<315?.83:.5;
  }
  function drawImage(c,im,s,t){
    const p=clamp((t-s.start)/(s.end-s.start)),e=smooth(p);
    if(s.asset==='original'){
      window.SweetheartAtmosphere.draw(c,t,'memory',.1,W,PH,{strength:.45});
      const close=s.motion==='hands';
      const ih=close?PH*3.35:PH*(1.48+.10*e),iw=ih*im.width/im.height;
      const x=(W-iw)/2+(e-.5)*24,y=close?-PH*1.72:-PH*.13;
      c.drawImage(im,x,y,iw,ih);
      const fade=120;
      let g=c.createLinearGradient(x,0,x+fade,0);g.addColorStop(0,'#030406');g.addColorStop(1,'#03040600');
      c.fillStyle=g;c.fillRect(x-1,0,fade+1,PH);
      g=c.createLinearGradient(x+iw-fade,0,x+iw,0);g.addColorStop(0,'#03040600');g.addColorStop(1,'#030406');
      c.fillStyle=g;c.fillRect(x+iw-fade,0,fade+1,PH);
      return;
    }
    let zoom=s.motion==='pull'?1.18-.13*e:1.03+.13*e;
    if(s.motion==='drift')zoom=1.12;
    const ratio=Math.max(W/im.width,PH/im.height)*zoom,iw=im.width*ratio,ih=im.height*ratio;
    let px=.5,py=s.asset==='intimate'?.42:.46;
    if(s.motion==='drift')px=.47+.065*e;
    if(s.motion==='rise')py=.58-.15*e;
    c.drawImage(im,(W-iw)*px,(PH-ih)*py,iw,ih);
  }
  function drawScene(c,s,t){
    c.globalAlpha=1;c.globalCompositeOperation='source-over';c.fillStyle='#030406';c.fillRect(0,0,W,PH);
    if(s.asset)drawImage(c,images[s.asset],s,t);
    window.SweetheartAtmosphere.draw(c,t,s.theme,energy(t),W,PH,{full:!!s.full,strength:s.asset==='original'?.25:.65});
  }
  function dedicationAt(t){
    let a=0,e='',h='',n='';
    if(t<4.3){a=smooth(t/.8)*smooth((4.3-t)/.7);e='A film for Priya';h='Five months.';n='One beautiful, imperfect us.';}
    else if(t>18.05&&t<20.8){a=smooth((t-18.05)/.6)*smooth((20.8-t)/.6);h='For my sweetheart';}
    else if(t>353&&t<362){a=smooth((t-353)/1.8)*smooth((362-t)/1.6);e='Happy fifth month anniversary';h='Still choosing you.';n='Through every storm. In every universe.';}
    else if(t>=363){a=smooth((t-363)/2);e='My honey. My wifey.';h='Priya';n='Five months down. A lifetime of choosing you.';}
    dedication.style.opacity=a;
    if(a>0){eyebrow.textContent=e;title.textContent=h;note.textContent=n;}
  }
  function renderAt(t){
    t=clamp(t,0,D.duration);
    let i=D.scenes.findIndex(s=>t>=s.start&&t<s.end);if(i<0)i=D.scenes.length-1;
    const s=D.scenes[i];drawScene(lc[0],s,t);
    ctx.globalAlpha=1;ctx.fillStyle='#030406';ctx.fillRect(0,0,W,H);ctx.drawImage(layers[0],0,TOP);
    const fade=Math.min(1.15,(s.end-s.start)/5);
    if(i>0&&t<s.start+fade){
      drawScene(lc[1],D.scenes[i-1],t);
      ctx.globalAlpha=1-smooth((t-s.start)/fade);ctx.drawImage(layers[1],0,TOP);ctx.globalAlpha=1;
    }
    const ci=D.captions.findIndex(c=>t>=c.start&&t<c.end);
    if(ci!==lastCaption){caption.textContent=ci>=0?D.captions[ci].text:'';lastCaption=ci;}
    if(ci>=0){const c=D.captions[ci];capBox.style.opacity=Math.min(1,(t-c.start)/.10,(c.end-t)/.10);}else capBox.style.opacity=0;
    if(t<4.3 || t>353){
      const veil=ctx.createRadialGradient(W/2,H/2,70,W/2,H/2,820);
      veil.addColorStop(0,'rgba(1,3,7,.52)');veil.addColorStop(1,'rgba(1,3,7,0)');
      ctx.fillStyle=veil;ctx.fillRect(0,TOP,W,PH);
    }
    dedicationAt(t);
    const q=Math.floor(t*12);grain.style.transform=`translate(${(q*17%37)-18}px,${(q*23%31)-15}px)`;
    window.__sweetheartTime=t;
  }
  window.renderSweetheartAt=renderAt;
  window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
  window.__hf.buildReady.sweetheart=Promise.all(Object.entries(D.assets).map(([id,url])=>new Promise((resolve,reject)=>{
    const im=new Image();im.onload=()=>{images[id]=im;resolve();};im.onerror=()=>reject(new Error('Missing film asset: '+url));im.src=url;
  }))).then(()=>document.fonts.ready).then(()=>{
    window.addEventListener('hf-seek',event=>renderAt(event.detail.time));
    renderAt(0);
  });
})();
