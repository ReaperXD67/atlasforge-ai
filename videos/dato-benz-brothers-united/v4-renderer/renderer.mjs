import * as THREE from './assets/vendor/three.module.js';

const plan=window.V4_PLAN;
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const lerp=(a,b,t)=>a+(b-a)*t;
const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const aspect=plan.width/plan.height;
const canvas=document.getElementById('world');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(1);renderer.setSize(plan.width,plan.height,false);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.NoToneMapping;
renderer.setClearColor(0xe7e0d0,1);
const loader=new THREE.TextureLoader(),textures=new Map();
function texture(src){
 if(!textures.has(src))textures.set(src,loader.loadAsync(src).then(t=>{t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());return t;}));
 return textures.get(src);
}
function mesh(geometry,material,position=[0,0,0]){const object=new THREE.Mesh(geometry,material);object.position.set(...position);return object;}
const solid=(color)=>new THREE.MeshStandardMaterial({color,roughness:.76,metalness:.20});
const artMaterial=t=>new THREE.MeshBasicMaterial({map:t,transparent:true,depthWrite:true,toneMapped:false});

// Explicit keyframes describe an establish / travel / arrival. No idle oscillation.
export function cameraKeys(s){
 if(s.camera?.length)return s.camera;
 const presets={
  traverse:[{at:0,x:-1.15,y:.10,z:12.6,look:[-.6,.1,0]},{at:.78,x:1.0,y:.18,z:11.9,look:[.45,.12,0]},{at:1,x:1.18,y:.18,z:11.9,look:[.55,.12,0]}],
  reveal:[{at:0,x:-1.75,y:-.15,z:13.0,look:[-.65,.0,0]},{at:.7,x:.6,y:.25,z:11.8,look:[.25,.12,0]},{at:1,x:.85,y:.25,z:11.65,look:[.35,.12,0]}],
  arrive:[{at:0,x:.45,y:.65,z:13.2,look:[.0,.15,0]},{at:.75,x:0,y:.1,z:11.6,look:[0,.15,0]},{at:1,x:0,y:.1,z:11.6,look:[0,.15,0]}],
  photo:[{at:0,x:0,y:0,z:12.8,look:[0,0,0]},{at:.74,x:.18,y:.08,z:12.3,look:[.18,.08,0]},{at:1,x:.18,y:.08,z:12.3,look:[.18,.08,0]}],
  hold:[{at:0,x:0,y:0,z:12.8,look:[0,0,0]},{at:1,x:0,y:0,z:12.8,look:[0,0,0]}]
 };
 return presets[s.cameraPreset||'traverse']||presets.traverse;
}
export function cameraAt(keys,p){
 let index=keys.findIndex(k=>k.at>=p);
 if(index<0)index=keys.length-1;if(index===0)return keys[0];
 const a=keys[index-1],b=keys[index],t=clamp((p-a.at)/(b.at-a.at));
 const q=b.ease==='smooth'?smooth(t):b.ease==='in'?t*t*t:b.ease==='out'?1-(1-t)**3:t;
 return {x:lerp(a.x,b.x,q),y:lerp(a.y,b.y,q),z:lerp(a.z,b.z,q),look:(a.look||[0,0,0]).map((v,i)=>lerp(v,(b.look||[0,0,0])[i],q))};
}
function addArch(scene,s){
 const group=new THREE.Group(),r=s.archRadius||5.05;
 const metal=solid(s.archColor||'#6d7663');
 // A physical, open arch passes in front of the art, never a full-frame effect.
 const crown=mesh(new THREE.TorusGeometry(r,.12,8,80,Math.PI),metal,[0,-.5,0]);group.add(crown);
 for(const x of [-r,r])group.add(mesh(new THREE.BoxGeometry(.24,7,.18),metal,[x,-4,0]));
 group.position.set(s.occluderX??-2.0,s.occluderY??0,s.occluderZ??3.4);
 group.rotation.y=.035;scene.add(group);
}
function addPaper(scene,s){
 const shape=new THREE.Shape();
 shape.moveTo(-12,-10);shape.lineTo(-4.75,-10);shape.lineTo(-4.52,-6);shape.lineTo(-4.64,-2);shape.lineTo(-4.34,1.7);shape.lineTo(-4.58,5.2);shape.lineTo(-4.46,10);shape.lineTo(-12,10);shape.closePath();
 const object=mesh(new THREE.ShapeGeometry(shape),new THREE.MeshBasicMaterial({color:s.paperColor||'#e7dfc9',side:THREE.DoubleSide}),[s.occluderX??0,0,s.occluderZ??5.3]);
 scene.add(object);
 const edge=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-4.75,-10,.01),new THREE.Vector3(-4.52,-6,.01),new THREE.Vector3(-4.64,-2,.01),new THREE.Vector3(-4.34,1.7,.01),new THREE.Vector3(-4.58,5.2,.01),new THREE.Vector3(-4.46,10,.01)]);
 const line=new THREE.Line(edge,new THREE.LineBasicMaterial({color:'#bba887',transparent:true,opacity:.5}));line.position.copy(object.position);scene.add(line);
}
function addSilk(scene,s){
 if(s.silk!==true)return null;
 const points=s.silkPath||[[-11,-3.5,1.2],[-7,-2.95,1.5],[-2,-3.1,1.2],[2,-2.72,.8],[7,-2.8,.5],[12,-2.1,.2]];
 const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));
 const geometry=new THREE.TubeGeometry(curve,180,.014,6,false);
 const ribbon=mesh(geometry,new THREE.MeshBasicMaterial({color:'#a63327',transparent:true,opacity:.8}));scene.add(ribbon);
 return ribbon;
}
async function buildScene(s){
 const scene=new THREE.Scene();scene.background=new THREE.Color(s.background||'#e7e0d0');
 const camera=new THREE.PerspectiveCamera(s.fov||45,aspect,.05,100);
 scene.add(new THREE.HemisphereLight(0xfff6df,0x143c39,2.2));
 const key=new THREE.DirectionalLight(0xffedd1,2.5);key.position.set(-3,7,8);scene.add(key);
 const photos=[],movers=[];
 if(s.src){
  const t=await texture(s.src);const h=s.plateHeight||15.4,w=h*aspect;
  const source=t.clone();source.needsUpdate=true;
  const ratio=t.image.width/t.image.height;
  if(ratio>aspect){source.repeat.x=aspect/ratio;source.offset.x=(1-source.repeat.x)/2;}else{source.repeat.y=ratio/aspect;source.offset.y=(1-source.repeat.y)/2;}
  const material=artMaterial(source);
  let geometry=new THREE.PlaneGeometry(w,h);
  if(s.depthSrc){
   const d=(await texture(s.depthSrc)).clone();d.colorSpace=THREE.NoColorSpace;d.repeat.copy(source.repeat);d.offset.copy(source.offset);d.needsUpdate=true;
   geometry.dispose();geometry=new THREE.PlaneGeometry(w,h,160,90);
   material.onBeforeCompile=shader=>{
    shader.uniforms.artDepth={value:d};shader.uniforms.artDepthStrength={value:clamp(s.depthStrength??.4,0,.8)};
    shader.vertexShader='uniform sampler2D artDepth;uniform float artDepthStrength;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\ntransformed.z+=(texture2D(artDepth,vMapUv).r-.5)*artDepthStrength;');
   };
   material.customProgramCacheKey=()=>'art-depth-v1';
  }
  scene.add(mesh(geometry,material,[0,0,s.plateZ??-1]));
 }
 for(const l of s.layers||[]){
  const base=await texture(l.src),t=base.clone();t.needsUpdate=true;
  let w=base.image.width,h=base.image.height;
  if(l.crop){
   const [left,top,cw,ch]=l.crop;
   if(left<0||top<0||cw<=0||ch<=0||left+cw>w||top+ch>h)throw Error(`Out-of-bounds literal crop in ${s.id}/${l.id||'layer'}.`);
   t.repeat.set(cw/w,ch/h);t.offset.set(left/w,1-(top+ch)/h);w=cw;h=ch;
  }
  const height=l.height??(l.kind==='photo'?7:10),width=l.width??height*w/h;
  if(l.kind==='photo'&&l.width&&Math.abs(width/height-w/h)>.002)throw Error(`Photo ${l.id||''} would be stretched. Omit width or preserve its crop aspect ratio.`);
  const card=new THREE.Group();card.position.set(l.x??0,l.y??0,l.z??1.0);
  const picture=mesh(new THREE.PlaneGeometry(width,height),artMaterial(t));
  if(l.kind==='photo'){
   const border=l.border??.09;
   card.add(mesh(new THREE.PlaneGeometry(width+border*2,height+border*2),new THREE.MeshBasicMaterial({color:l.frameColor||'#eee5cd'}),[0,0,-.015]));
   photos.push(card);
  }else card.rotation.set(...(l.rotation||[0,0,0]));
  card.add(picture);scene.add(card);
  movers.push({card,spec:l,base:[l.x??0,l.y??0,l.z??1],baseScale:l.scale??1});
 }
 if(s.occluder==='arch')addArch(scene,s);if(s.occluder==='paper')addPaper(scene,s);
 const silk=addSilk(scene,s);
 return {scene,camera,photos,movers,silk,keys:cameraKeys(s),spec:s};
}
function makeLuma(){
 const width=512,height=288,data=new Uint8Array(width*height*4);
 for(let y=0;y<height;y++)for(let x=0;x<width;x++){
  const u=x/(width-1),v=y/(height-1);
  // Original narrow contour variations give a brush/river-shaped, directional reveal.
  const value=clamp(u+.042*Math.sin(v*14+u*5)+.018*Math.sin(v*41-u*11),.002,.998);
  const i=(y*width+x)*4;data[i]=data[i+1]=data[i+2]=Math.round(value*255);data[i+3]=255;
 }
 const t=new THREE.DataTexture(data,width,height);t.minFilter=t.magFilter=THREE.LinearFilter;t.needsUpdate=true;return t;
}
const targetOptions={minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter,format:THREE.RGBAFormat,type:THREE.UnsignedByteType,depthBuffer:true};
const fromTarget=new THREE.WebGLRenderTarget(plan.width,plan.height,targetOptions),toTarget=new THREE.WebGLRenderTarget(plan.width,plan.height,targetOptions);
fromTarget.texture.colorSpace=THREE.SRGBColorSpace;toTarget.texture.colorSpace=THREE.SRGBColorSpace;
const compositeScene=new THREE.Scene(),compositeCamera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
const compositeMaterial=new THREE.ShaderMaterial({
 uniforms:{fromImage:{value:fromTarget.texture},toImage:{value:toTarget.texture},luma:{value:makeLuma()},progress:{value:0}},
 vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position,1.0);}',
 // Adapted from gre's MIT LumaWipe, pinned under vendor/. Input UVs are not displaced.
 fragmentShader:'uniform sampler2D fromImage;uniform sampler2D toImage;uniform sampler2D luma;uniform float progress;varying vec2 vUv;void main(){float value=texture2D(luma,vUv).r;float edge=max(fwidth(value)*1.25,0.0008);float mask=smoothstep(progress-edge,progress+edge,value);gl_FragColor=mix(texture2D(toImage,vUv),texture2D(fromImage,vUv),mask);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}',
 depthTest:false,depthWrite:false,toneMapped:false
});
compositeScene.add(mesh(new THREE.PlaneGeometry(2,2),compositeMaterial));
let scenes=[];
function renderScene(i,time,target){
 const item=scenes[i],s=item.spec,p=clamp((time-s.start)/(s.end-s.start));
 const pose=cameraAt(item.keys,p);item.camera.position.set(pose.x,pose.y,pose.z);item.camera.lookAt(...(pose.look||[0,0,0]));item.camera.updateMatrixWorld();
 for(const {card,spec:l,base,baseScale}of item.movers){
  const q=clamp((p-(l.motionStart??0))/Math.max(1e-6,(l.motionEnd??1)-(l.motionStart??0)));
  const amount=l.ease==='smooth'?smooth(q):l.ease==='in'?q*q*q:l.ease==='out'?1-(1-q)**3:q;
  const values=v=>Array.isArray(v)?{x:v[0],y:v[1],z:v[2]}:(v||{}),a=values(l.from),b=values(l.to);
  card.position.set(...['x','y','z'].map((axis,j)=>lerp(a[axis]??base[j],b[axis]??base[j],amount)));
  card.scale.setScalar(lerp(a.scale??baseScale,b.scale??baseScale,amount));
  const opacity=lerp(a.opacity??1,b.opacity??1,amount);
  for(const child of card.children){child.material.transparent=true;child.material.opacity=opacity;}
 }
 for(const photo of item.photos)photo.quaternion.copy(item.camera.quaternion);
 if(item.silk){const amount=s.silkReveal===false?1:smooth(clamp(p/.62));item.silk.geometry.setDrawRange(0,Math.floor(180*amount)*6*6);}
 renderer.setRenderTarget(target);renderer.clear();renderer.render(item.scene,item.camera);
}
export function seek(t){
 if(!scenes.length)return null;
 t=clamp(Number(t)||0,0,Math.max(0,plan.duration-1e-7));
 let i=plan.scenes.findIndex(s=>t>=s.start&&t<s.end);if(i<0)i=plan.scenes.length-1;
 const s=plan.scenes[i],transition=s.transition||{},d=Math.min(transition.duration??.65,(s.end-s.start)/3),p=clamp((t-s.start)/Math.max(d,1e-6));
 const blending=i>0&&transition.kind==='luma'&&p<1;
 if(blending){
  renderScene(i-1,Math.min(t,plan.scenes[i-1].end-1/plan.fps),fromTarget);renderScene(i,t,toTarget);
  compositeMaterial.uniforms.progress.value=smooth(p);compositeMaterial.uniforms.luma.value=scenes[i].mask||compositeMaterial.userData.defaultLuma;
  renderer.setRenderTarget(null);renderer.clear();renderer.render(compositeScene,compositeCamera);
 }else renderScene(i,t,null);
 for(let n=0;n<plan.captions.length;n++){
  const c=plan.captions[n],node=document.getElementById(`cue-${n}`);node.style.visibility=t>=c.start&&t<c.end?'visible':'hidden';
 }
 for(const q of plan.scenes){
  const node=document.getElementById(`title-${q.id}`);if(!node)continue;
  const local=t-q.start,duration=q.end-q.start;
  node.style.visibility=local>=0&&local<duration?'visible':'hidden';
  node.querySelector('.title-inner').style.opacity=String(smooth(local/.85)*smooth((duration-local)/.7));
 }
 const result={time:t,frame:Math.floor(t*plan.fps),scene:s.id,scene_index:i,transition:blending?'luma':'none',draw_calls:renderer.info.render.calls,triangles:renderer.info.render.triangles};
 window.V4_LAST_STATE=result;return result;
}
window.seek=seek;
window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
const ready=(async()=>{
 await document.fonts.ready;
 scenes=await Promise.all(plan.scenes.map(buildScene));
 const cssValue=v=>typeof v==='number'?`${v}px`:v;
 for(const s of plan.scenes){
  const node=document.getElementById(`title-${s.id}`);if(!node)continue;
  const style=s.titleStyle||{},hero=node.querySelector('.hero-title'),eyebrow=node.querySelector('.eyebrow'),inner=node.querySelector('.title-inner');
  for(const key of ['left','top','width'])if(style[key]!==undefined)node.style[key]=cssValue(style[key]);
  if(style.width!==undefined)node.style.maxWidth=cssValue(style.width);
  if(style.color){hero.style.color=style.color;eyebrow.style.color=style.color;}
  if(style.fontSize!==undefined)hero.style.fontSize=cssValue(style.fontSize);
  if(style.subtitleSize!==undefined)eyebrow.style.fontSize=cssValue(style.subtitleSize);
  if(style.lineHeight!==undefined)hero.style.lineHeight=String(style.lineHeight);
  if(s.titleAlign)inner.style.textAlign=s.titleAlign;
  if(style.background!==undefined)inner.style.background=style.background;
  if(style.padding!==undefined)inner.style.padding=cssValue(style.padding);
  if(style.border!==undefined)inner.style.border=style.border;
  for(const [key,value]of Object.entries(s.titleEyebrowStyle||{}))eyebrow.style[key]=['fontSize','lineHeight','letterSpacing'].includes(key)&&typeof value==='number'&&key!=='lineHeight'?`${value}px`:String(value);
 }
 compositeMaterial.userData.defaultLuma=compositeMaterial.uniforms.luma.value;
 for(const item of scenes)if(item.spec.transition?.mask){item.mask=await texture(item.spec.transition.mask);item.mask.colorSpace=THREE.NoColorSpace;}
 for(const item of scenes){item.camera.position.set(0,0,12);await renderer.compileAsync(item.scene,item.camera);}
 await renderer.compileAsync(compositeScene,compositeCamera);
 const clock={time:0},timeline=gsap.timeline({paused:true});
 timeline.to(clock,{time:plan.duration,duration:plan.duration,ease:'none',onUpdate:()=>seek(clock.time)},0);
 window.V4_REGISTER(timeline);
 window.addEventListener('hf-seek',e=>seek(e.detail.time));
 seek(0);window.V4_READY=true;
 return {scenes:scenes.length,textures:textures.size};
})();
window.V4_READY_PROMISE=ready;window.__hf.buildReady['v4-world']=ready;
ready.catch(error=>{window.V4_ERROR=String(error.stack||error);console.error(error);});
