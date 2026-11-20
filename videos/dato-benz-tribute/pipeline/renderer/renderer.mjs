import * as THREE from './assets/vendor/three.module.js';

const plan=window.BENZ_PLAN;
const identityPolicy=plan.identityPolicy??'integrated';
const identityExcluded=identityPolicy==='excluded';
function validateIdentityPolicy(){
 if(!['integrated','excluded'].includes(identityPolicy))throw Error('identityPolicy must be integrated or excluded.');
 if(!identityExcluded)return;
 const fields=['faceBounds','subjectBounds','subjectPadding','faceMargin','faceSafeMargin','identity','identityReference','person','portrait','photo'];
 for(const s of [null,...plan.scenes]){
  const records=s?[[s,`scene ${s.id}`],...(s.layers||[]).map(l=>[l,`layer in ${s.id}`])]:[[plan,'plan']];
  for(const [record,label]of records){
   if(record.containsIdentity!==undefined&&typeof record.containsIdentity!=='boolean')throw Error(`identityPolicy excluded requires boolean containsIdentity: ${label}`);
   if(record.containsIdentity===true||fields.some(key=>Object.hasOwn(record,key)))throw Error(`identityPolicy excluded forbids identity, face or subject metadata: ${label}`);
   if(['photo','portrait','person','identity','card'].includes(record.kind))throw Error(`identityPolicy excluded forbids identity/card layers: ${label}`);
  }
 }
}
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const lerp=(a,b,t)=>a+(b-a)*t;
const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const aspect=plan.width/plan.height;
const canvas=document.getElementById('world');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(1);renderer.setSize(plan.width,plan.height,false);
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
renderer.setClearColor(plan.background,1);
const loader=new THREE.TextureLoader(),textures=new Map(),geometries=new Map();
function texture(src,linear=false){
 const key=`${linear?'linear':'srgb'}:${src}`;
 if(!textures.has(key))textures.set(key,loader.loadAsync(src).then(t=>{
  t.colorSpace=linear?THREE.NoColorSpace:THREE.SRGBColorSpace;
  t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
  t.premultiplyAlpha=false;return t;
 }));
 return textures.get(key);
}
function plane(w,h,sx=1,sy=1){
 const key=[w,h,sx,sy].join(':');
 if(!geometries.has(key))geometries.set(key,new THREE.PlaneGeometry(w,h,sx,sy));
 return geometries.get(key);
}
function mesh(geometry,material,position=[0,0,0]){const m=new THREE.Mesh(geometry,material);m.position.set(...position);return m;}
const artMaterial=(t,transparent=false)=>new THREE.MeshBasicMaterial({map:t,transparent,depthWrite:!transparent,alphaTest:transparent?.001:0,side:THREE.DoubleSide,toneMapped:false});

function focusPose(rect,s){
 const h=s.plateHeight||15.4,w=h*aspect;
 const r=rect||[.02,.02,.96,.96];
 const viewH=Math.min(h*.995,Math.max(r[3]*h,r[2]*w/aspect));
 const viewW=viewH*aspect;
 const x=clamp((r[0]+r[2]/2-.5)*w,-w/2+viewW/2,w/2-viewW/2);
 const y=clamp((.5-r[1]-r[3]/2)*h,-h/2+viewH/2,h/2-viewH/2);
 const z=viewH/(2*Math.tan(THREE.MathUtils.degToRad((s.fov||45)/2)))+(s.plateZ??-1);
 return {x,y,z,look:[x,y,s.plateZ??-1]};
}
export function cameraKeys(s){
 if(s.camera?.length)return s.camera;
 if(s.focalRect){return [{at:0,...focusPose(s.focalRect,s)},{at:1,...focusPose(s.focalRectEnd||s.focalRect,s)}];}
 return [{at:0,...focusPose([.03,.02,.94,.94],s)},{at:1,...focusPose([.06,.02,.92,.92],s)}];
}
export function cameraAt(keys,p){
 let index=keys.findIndex(k=>k.at>=p);if(index<0)index=keys.length-1;if(index===0)return keys[0];
 const a=keys[index-1],b=keys[index],t=clamp((p-a.at)/(b.at-a.at));
 const q=b.ease==='smooth'?smooth(t):b.ease==='in'?t*t*t:b.ease==='out'?1-(1-t)**3:t;
 return {x:lerp(a.x,b.x,q),y:lerp(a.y,b.y,q),z:lerp(a.z,b.z,q),look:(a.look||[0,0,0]).map((v,i)=>lerp(v,(b.look||[0,0,0])[i],q))};
}

// Small original source-coordinate keep-out shader. It does not move or relight
// identity pixels. The rectangle's transition is entirely OUTSIDE its given bounds.
const fxFunctions=`
uniform float filmTime;uniform float filmPhase;uniform float filmFx;uniform float filmStrength;
uniform float filmWaterLine;uniform vec4 filmProtect;uniform float filmProtectOn;
float filmHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float filmAllowed(vec2 uv){
 float f=.018;
 float x=smoothstep(filmProtect.x-f,filmProtect.x,uv.x)*(1.-smoothstep(filmProtect.z,filmProtect.z+f,uv.x));
 float y=smoothstep(filmProtect.y-f,filmProtect.y,uv.y)*(1.-smoothstep(filmProtect.w,filmProtect.w+f,uv.y));
 return 1.-filmProtectOn*x*y;
}
`;
const fxMap=`
#ifdef USE_MAP
 vec2 filmUv=vMapUv;float allowed=filmAllowed(vMapUv);
 float water=1.-smoothstep(filmWaterLine-.025,filmWaterLine+.025,vMapUv.y);
 if(filmFx>2.5){
  float wave=sin(vMapUv.y*180.+filmTime*2.0)*sin(vMapUv.x*75.-filmTime*.7);
  filmUv.x+=wave*.0022*filmStrength*allowed*water;
 }
 vec4 sampledDiffuseColor=texture2D(map,filmUv);
 diffuseColor*=sampledDiffuseColor;
 if(filmFx>.5&&filmFx<1.5){
  vec2 q=vec2(vMapUv.x*90.+vMapUv.y*30.,vMapUv.y*70.+filmTime*13.);
  float h=filmHash(floor(q));
  float width=max(fwidth(q.x)*.8,.018);
  float line=(1.-smoothstep(.004,width,abs(fract(q.x)-.5)))*(1.-smoothstep(.02,.30,fract(q.y+h)));
  float rain=line*step(.42,h)*filmStrength*.24*allowed;
  diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.64,.73,.77),rain);
 }else if(filmFx>1.5&&filmFx<2.5){
  float centre=mix(-.35,1.35,filmPhase);
  float sweep=exp(-pow((vMapUv.x+vMapUv.y*.15-centre)/.19,2.));
  diffuseColor.rgb+=vec3(.15,.10,.045)*sweep*filmStrength*allowed;
 }
#endif
`;
function protectRect(s){
 const b=s.subjectBounds||s.faceBounds||[0,0,0,0],padding=clamp(s.subjectPadding??.015,0,.06);
 return new THREE.Vector4(clamp(b[0]-padding),clamp(1-b[1]-b[3]-padding),clamp(b[0]+b[2]+padding),clamp(1-b[1]+padding));
}
async function mainPlate(s,scene){
 const t=await texture(s.src),source=t.clone();source.needsUpdate=true;
 const h=s.plateHeight||15.4,w=h*aspect,ratio=t.image.width/t.image.height;
 if(ratio>aspect){source.repeat.x=aspect/ratio;source.offset.x=(1-source.repeat.x)/2;}
 else{source.repeat.y=ratio/aspect;source.offset.y=(1-source.repeat.y)/2;}
 const material=artMaterial(source),atmo=s.atmosphere||{};
 const kind={rain:1,light:2,water:3}[atmo.kind]||0;
 if(s.containsIdentity&&s.depthSrc)throw Error(`Identity depth is excluded: ${s.id}`);
 if(s.containsIdentity&&kind&&!s.subjectBounds)throw Error(`Subject keep-out bounds required for ${s.id}`);
 const uniforms={filmTime:{value:0},filmPhase:{value:0},filmFx:{value:kind},filmStrength:{value:clamp(atmo.strength??.25,0,.5)},filmWaterLine:{value:1-(atmo.waterLine??.60)},filmProtect:{value:protectRect(s)},filmProtectOn:{value:s.containsIdentity?1:0}};
 let d=null;
 if(s.depthSrc){d=(await texture(s.depthSrc,true)).clone();d.repeat.copy(source.repeat);d.offset.copy(source.offset);d.needsUpdate=true;uniforms.artDepth={value:d};uniforms.artDepthStrength={value:clamp(s.depthStrength??.3,0,.6)};}
 material.onBeforeCompile=shader=>{
  Object.assign(shader.uniforms,uniforms);
  shader.fragmentShader=fxFunctions+shader.fragmentShader;
  shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',fxMap);
  if(d){
   shader.vertexShader='uniform sampler2D artDepth;uniform float artDepthStrength;\n'+shader.vertexShader;
   shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\ntransformed.z+=(texture2D(artDepth,vMapUv).r-.5)*artDepthStrength;');
  }
 };
 material.customProgramCacheKey=()=>d?'benz-keepout-depth1':'benz-keepout-flat1';
 scene.add(mesh(plane(w,h,d?160:1,d?90:1),material,[0,0,s.plateZ??-1]));
 return {width:w,height:h,texture:source,uniforms};
}
async function buildScene(s){
 const scene=new THREE.Scene();scene.background=new THREE.Color(s.background||plan.background);
 const camera=new THREE.PerspectiveCamera(s.fov||45,aspect,.05,100);
 const plate=await mainPlate(s,scene),movers=[];
 for(const l of s.layers||[]){
  const base=await texture(l.src),t=base.clone();t.needsUpdate=true;let w=base.image.width,h=base.image.height;
  if(l.crop){const [left,top,cw,ch]=l.crop;if(left<0||top<0||cw<=0||ch<=0||left+cw>w||top+ch>h)throw Error(`Invalid layer crop ${s.id}`);t.repeat.set(cw/w,ch/h);t.offset.set(left/w,1-(top+ch)/h);w=cw;h=ch;}
  const height=l.height??12,width=l.width??height*w/h;
  const object=mesh(plane(width,height),artMaterial(t,true),[l.x??0,l.y??0,l.z??3]);
  object.rotation.set(...(l.rotation||[0,0,0]));scene.add(object);
  movers.push({object,spec:l,base:[l.x??0,l.y??0,l.z??3],baseScale:l.scale??1});
 }
 return {scene,camera,plate,movers,keys:cameraKeys(s),spec:s};
}
function projectRect(item,rect){
 const [x,y,w,h]=rect,t=item.plate.texture;
 const points=[[x,y],[x+w,y],[x,y+h],[x+w,y+h]].map(([u,v])=>{
  const gu=(u-t.offset.x)/t.repeat.x,gv=((1-v)-t.offset.y)/t.repeat.y;
  const p=new THREE.Vector3((gu-.5)*item.plate.width,(gv-.5)*item.plate.height,item.spec.plateZ??-1).project(item.camera);
  return [.5+p.x*.5,.5-p.y*.5];
 });
 return [Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1]))];
}
function setCamera(item,p){const a=cameraAt(item.keys,p);item.camera.position.set(a.x,a.y,a.z);item.camera.lookAt(...a.look);item.camera.updateMatrixWorld();}
function faceCheck(item,p){
 if(identityExcluded||!item.spec.containsIdentity)return null;
 setCamera(item,p);const r=projectRect(item,item.spec.faceBounds),margin=item.spec.faceMargin??item.spec.faceSafeMargin??.10,eps=1e-5;
 return {at:p,face_screen_bounds:r,face_safe_margin:margin,passed:r[0]>=margin-eps&&r[1]>=margin-eps&&r[2]<=1-margin+eps&&r[3]<=1-margin+eps};
}
function coverageCheck(item,p){
 setCamera(item,p);const camera=item.camera,halfW=item.plate.width/2,halfH=item.plate.height/2,z=item.spec.plateZ??-1;
 const corners=[[-1,-1],[1,-1],[-1,1],[1,1]].map(([x,y])=>{
  const point=new THREE.Vector3(x,y,.5).unproject(camera),direction=point.sub(camera.position).normalize();
  const distance=(z-camera.position.z)/direction.z;
  const hit=camera.position.clone().addScaledVector(direction,distance);
  return {x:hit.x,y:hit.y,inside:distance>0&&Math.abs(hit.x)<=halfW+.002&&Math.abs(hit.y)<=halfH+.002};
 });
 return {at:p,passed:corners.every(x=>x.inside),corners};
}
function makeLuma(){
 const w=512,h=288,data=new Uint8Array(w*h*4);
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const u=x/(w-1),v=y/(h-1),value=clamp(u+.035*Math.sin(v*12+u*4)+.014*Math.sin(v*34-u*9),.002,.998),i=(y*w+x)*4;
  data[i]=data[i+1]=data[i+2]=Math.round(value*255);data[i+3]=255;
 }
 const t=new THREE.DataTexture(data,w,h);t.minFilter=t.magFilter=THREE.LinearFilter;t.needsUpdate=true;return t;
}
const options={minFilter:THREE.LinearFilter,magFilter:THREE.LinearFilter,format:THREE.RGBAFormat,type:THREE.UnsignedByteType,depthBuffer:true};
const fromTarget=new THREE.WebGLRenderTarget(plan.width,plan.height,options),toTarget=new THREE.WebGLRenderTarget(plan.width,plan.height,options);
fromTarget.texture.colorSpace=THREE.SRGBColorSpace;toTarget.texture.colorSpace=THREE.SRGBColorSpace;
const compositeScene=new THREE.Scene(),compositeCamera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
// Adapted from gre's MIT LumaWipe, preserved under vendor/ with its full license.
const compositeMaterial=new THREE.ShaderMaterial({uniforms:{fromImage:{value:fromTarget.texture},toImage:{value:toTarget.texture},luma:{value:makeLuma()},progress:{value:0}},vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position,1.0);}',fragmentShader:'uniform sampler2D fromImage;uniform sampler2D toImage;uniform sampler2D luma;uniform float progress;varying vec2 vUv;void main(){float v=texture2D(luma,vUv).r;float edge=max(fwidth(v)*1.25,.0008);gl_FragColor=mix(texture2D(toImage,vUv),texture2D(fromImage,vUv),smoothstep(progress-edge,progress+edge,v));\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}',depthTest:false,depthWrite:false,toneMapped:false});
compositeScene.add(mesh(plane(2,2),compositeMaterial));
let scenes=[];
function renderScene(i,time,target){
 const item=scenes[i],s=item.spec,p=clamp((time-s.start)/(s.end-s.start));setCamera(item,p);
 item.plate.uniforms.filmTime.value=time;
 const a=s.atmosphere||{};item.plate.uniforms.filmPhase.value=clamp((p-(a.start??0))/Math.max(1e-6,(a.end??1)-(a.start??0)));
 for(const {object,spec:l,base,baseScale}of item.movers){
  const q=clamp((p-(l.motionStart??0))/Math.max(1e-6,(l.motionEnd??1)-(l.motionStart??0))),amount=l.ease==='smooth'?smooth(q):l.ease==='in'?q*q*q:l.ease==='out'?1-(1-q)**3:q;
  const values=v=>Array.isArray(v)?{x:v[0],y:v[1],z:v[2]}:(v||{}),a=values(l.from),b=values(l.to);
  object.position.set(...['x','y','z'].map((axis,j)=>lerp(a[axis]??base[j],b[axis]??base[j],amount)));
  object.scale.setScalar(lerp(a.scale??baseScale,b.scale??baseScale,amount));object.material.opacity=lerp(a.opacity??1,b.opacity??1,amount);
 }
 renderer.setRenderTarget(target);renderer.clear();renderer.render(item.scene,item.camera);
}
export function seek(t){
 if(!scenes.length)return null;t=clamp(Number(t)||0,0,Math.max(0,plan.duration-1e-7));
 let i=plan.scenes.findIndex(s=>t>=s.start&&t<s.end);if(i<0)i=plan.scenes.length-1;
 const s=plan.scenes[i],transition=s.transition||{},d=Math.min(transition.duration??.45,(s.end-s.start)/3),p=clamp((t-s.start)/Math.max(d,1e-6));
 const blending=i>0&&transition.kind==='luma'&&p<1;
 if(blending){renderScene(i-1,Math.min(t,plan.scenes[i-1].end-1/plan.fps),fromTarget);renderScene(i,t,toTarget);compositeMaterial.uniforms.progress.value=smooth(p);compositeMaterial.uniforms.luma.value=scenes[i].mask||compositeMaterial.userData.defaultLuma;renderer.setRenderTarget(null);renderer.clear();renderer.render(compositeScene,compositeCamera);}
 else renderScene(i,t,null);
 for(let n=0;n<plan.captions.length;n++){
  const c=plan.captions[n],node=document.getElementById(`cue-${n}`);node.style.visibility=t>=c.start&&t<c.end?'visible':'hidden';
  const dark=s.captionTheme==='dark';node.style.color=s.captionColor||(dark?'#173b3d':'#fff9ed');
  node.style.textShadow=dark?'0 1px 4px rgba(255,246,223,.98),0 0 12px rgba(255,246,223,.9)':'0 2px 5px rgba(0,0,0,.97),0 0 15px rgba(0,0,0,.9)';
 }
 document.querySelector('.caption-shade').style.opacity=String(s.captionShade??(s.captionTheme==='dark'?0:.8));
 for(const q of plan.scenes){const node=document.getElementById(`title-${q.id}`);if(!node)continue;const local=t-q.start,duration=q.end-q.start;node.style.visibility=local>=0&&local<duration?'visible':'hidden';node.querySelector('.title-inner').style.opacity=String(smooth(local/.65)*smooth((duration-local)/.5));}
 const face=s.containsIdentity?faceCheck(scenes[i],clamp((t-s.start)/(s.end-s.start))):null;
 const result={time:t,frame:Math.floor(t*plan.fps),scene:s.id,scene_index:i,transition:blending?'luma':'none',face,draw_calls:renderer.info.render.calls,triangles:renderer.info.render.triangles};
 window.BENZ_LAST_STATE=result;return result;
}
window.seek=seek;window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
const ready=(async()=>{
 validateIdentityPolicy();window.BENZ_IDENTITY_POLICY=identityPolicy;
 await document.fonts.ready;scenes=await Promise.all(plan.scenes.map(buildScene));
 const frameChecks=[],coverageChecks=[];
 for(const item of scenes){
  const times=[...new Set([0,.25,.5,.75,1,...item.keys.map(k=>k.at)])];
  for(const p of times){const f=faceCheck(item,p);if(f)frameChecks.push({scene:item.spec.id,...f});coverageChecks.push({scene:item.spec.id,allow_matte:item.spec.allowMatte===true,...coverageCheck(item,p)});}
 }
 window.BENZ_FRAME_CHECKS=frameChecks;
 window.BENZ_COVERAGE_CHECKS=coverageChecks;
 const failed=frameChecks.filter(x=>!x.passed);if(failed.length)throw Error(`Safe-face framing failed: ${JSON.stringify(failed)}`);
 const uncovered=coverageChecks.filter(x=>!x.passed&&!x.allow_matte);if(uncovered.length)throw Error(`Image plane leaves the frame: ${JSON.stringify(uncovered)}`);
 const cssValue=v=>typeof v==='number'?`${v}px`:v;
 for(const s of plan.scenes){const node=document.getElementById(`title-${s.id}`);if(!node)continue;const style=s.titleStyle||{},hero=node.querySelector('.hero-title'),eyebrow=node.querySelector('.eyebrow'),inner=node.querySelector('.title-inner');for(const key of ['left','top','width'])if(style[key]!==undefined)node.style[key]=cssValue(style[key]);if(style.width!==undefined)node.style.maxWidth=cssValue(style.width);if(style.color)inner.style.color=style.color;if(style.fontSize!==undefined)hero.style.fontSize=cssValue(style.fontSize);if(style.subtitleSize!==undefined)eyebrow.style.fontSize=cssValue(style.subtitleSize);if(style.lineHeight!==undefined)hero.style.lineHeight=String(style.lineHeight);if(s.titleAlign)inner.style.textAlign=s.titleAlign;}
 compositeMaterial.userData.defaultLuma=compositeMaterial.uniforms.luma.value;
 for(const item of scenes)if(item.spec.transition?.mask)item.mask=await texture(item.spec.transition.mask,true);
 for(const item of scenes){setCamera(item,0);await renderer.compileAsync(item.scene,item.camera);}await renderer.compileAsync(compositeScene,compositeCamera);
 const clock={time:0},timeline=gsap.timeline({paused:true});timeline.to(clock,{time:plan.duration,duration:plan.duration,ease:'none',onUpdate:()=>seek(clock.time)},0);window.BENZ_REGISTER(timeline);window.addEventListener('hf-seek',e=>seek(e.detail.time));seek(0);window.BENZ_READY=true;
 return {scenes:scenes.length,textures:textures.size,shared_geometries:geometries.size,face_checks:frameChecks.length,identity_policy:identityPolicy,identity_scene_count:scenes.filter(s=>s.spec.containsIdentity).length};
})();
window.BENZ_READY_PROMISE=ready;window.__hf.buildReady['benz-world']=ready;ready.catch(error=>{window.BENZ_ERROR=String(error.stack||error);console.error(error);});
