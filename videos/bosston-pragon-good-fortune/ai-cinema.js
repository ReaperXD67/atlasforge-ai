/* Bosston / Pragon — image-preserving AI-depth cinema.
 * The supplied artwork remains the subject. Depth parallax, lens travel, selective
 * material motion and atmosphere are evaluated from absolute soundtrack time.
 * This animates AI artwork; it does not claim native AI-generated video motion.
 */
(() => {
  'use strict';
  window.__hf = window.__hf || {};
  window.__hf.buildReady = window.__hf.buildReady || {};
  const ready = (async () => {
    const D = window.FILM_DATA;
    const canvas = document.getElementById('ai-world');
    if (!D || !canvas) throw new Error('AI cinema requires FILM_DATA and #ai-world.');
    const W = 1920, H = 1080, TOP = 76, PH = 928, TAU = Math.PI * 2;
    canvas.width = W; canvas.height = H;
    const gl = canvas.getContext('webgl', {
      alpha: false, antialias: false, depth: false, stencil: false,
      preserveDrawingBuffer: true, powerPreference: 'high-performance',
    });
    if (!gl) throw new Error('A working WebGL context is required for AI-depth cinema.');
    const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
    const mix = (a, b, t) => a + (b - a) * t;
    const fract = x => x - Math.floor(x);
    const ease = p => .5 - .5 * Math.cos(clamp(p) * Math.PI);
    const smooth = p => { p = clamp(p); return p * p * (3 - 2 * p); };
    function seeded(seed) {
      let state = seed >>> 0;
      return () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
    }
    const vertex = `
      attribute vec2 aPosition;
      varying vec2 vUv;
      void main(){vUv=aPosition*.5+.5;gl_Position=vec4(aPosition,0.,1.);}
    `;
    const fragment = `
      precision highp float;
      varying vec2 vUv;
      uniform sampler2D uColorA,uColorB,uDepthA,uDepthB;
      uniform vec2 uSizeA,uSizeB;
      uniform vec4 uCameraA,uCameraB;
      uniform vec4 uParamsA,uParamsB;
      uniform vec2 uFocusA,uFocusB;
      uniform float uTime,uSeedA,uSeedB,uMix,uTransition,uTransitionPhase;
      const vec2 RES=vec2(1920.,928.);
      float sat(float x){return clamp(x,0.,1.);}
      float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453123);}
      float noise(vec2 p){
        vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
        return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);
      }
      vec2 cover(vec2 uv,vec2 size){
        float imageAspect=size.x/size.y,targetAspect=RES.x/RES.y;
        vec2 frame=vec2(1.);
        if(imageAspect<targetAspect)frame.y=imageAspect/targetAspect;
        else frame.x=targetAspect/imageAspect;
        return (uv-.5)*frame+.5;
      }
      vec2 rotateUv(vec2 uv,float angle){
        float s=sin(angle),c=cos(angle);
        vec2 p=(uv-.5)*vec2(RES.x/RES.y,1.);
        return vec2(p.x*c-p.y*s,p.x*s+p.y*c)/vec2(RES.x/RES.y,1.)+.5;
      }
      vec3 sampleScene(sampler2D col,sampler2D dep,vec2 size,vec4 cam,vec4 params,vec2 focus,float seed,vec2 screen){
        vec2 uv=cover(rotateUv(screen,cam.w),size);
        uv=(uv-.5)/cam.z+.5+cam.xy;
        // Inverse depth warp, with conservative displacement at discontinuities.
        // A neutral map gives an honest flat camera fallback rather than invented depth.
        float d=texture2D(dep,clamp(uv,.002,.998)).r;
        vec2 ray=cam.xy*params.y;
        float dx=texture2D(dep,clamp(uv+vec2(1.5/size.x,0.),.002,.998)).r-d;
        float dy=texture2D(dep,clamp(uv+vec2(0.,1.5/size.y),.002,.998)).r-d;
        float edge=1.-smoothstep(.015,.11,length(vec2(dx,dy)));
        vec2 displacement=clamp(ray*(d-.46),vec2(-.018),vec2(.018));
        displacement*=mix(.25,1.,edge);
        uv-=displacement;
        float d2=texture2D(dep,clamp(uv,.002,.998)).r;
        uv-=ray*(d2-d)*.35*edge;
        vec3 probe=texture2D(col,clamp(uv,.001,.999)).rgb;
        float style=params.x;
        float red=sat((probe.r-probe.g*1.12-probe.b*.12)*4.2);
        float gold=sat((probe.r*.8+probe.g*.4-probe.b*1.25-.16)*3.);
        // Human silhouettes live around the center/horizon in the supplied plates.
        // Material motion avoids that area and never warps whole architecture.
        float protectedCenter=1.-smoothstep(.08,.21,length((uv-vec2(.5,.47))*vec2(1.1,1.)));
        float upper=smoothstep(.42,.62,uv.y);
        float lower=1.-smoothstep(.32,.52,uv.y);
        vec2 flow=vec2(0.);
        if(style>.5&&style<1.5){
          float ripples=sin(uv.y*88.-uTime*2.2+sin(uv.x*11.+uTime*.4));
          flow.x=ripples*.0020*lower*(1.-protectedCenter*.9);
          flow.y=sin(uv.x*39.+uv.y*31.-uTime*1.35)*.00065*lower;
        }else if(style>1.5&&style<2.5){
          float cloth=red*(1.-protectedCenter);
          flow.x=(sin(uv.y*10.+uTime*.8+seed)*.0025+sin(uv.y*25.-uTime*1.25)*.00065)*cloth;
          flow.y=sin(uv.x*13.+uTime*1.15+seed)*.0017*cloth;
        }else if(style>2.5&&style<3.5){
          float hanging=red*upper;
          flow.x=sin(uv.y*19.+seed+uTime*.68)*.0016*hanging;
          flow.y=sin(uv.x*23.+seed*.3+uTime*.42)*.00055*hanging;
        }else if(style>3.5&&style<4.5){
          float body=gold*upper*(1.-protectedCenter);
          flow.y=sin(uv.x*13.-uTime*.95+seed)*.0015*body;
          flow.x=sin(uv.x*21.+uv.y*9.-uTime*.8)*.0007*body;
        }else if(style>4.5&&style<5.5){
          float clouds=(1.-smoothstep(.30,.62,d))*smoothstep(.2,.5,uv.y);
          flow.x=sin(uv.y*12.+uTime*.21+seed)*.0012*clouds;
          flow.y=sin(uv.x*8.-uTime*.28)*.0007*clouds;
        }
        uv=clamp(uv+flow*params.z,.002,.998);
        vec3 color=texture2D(col,uv).rgb;
        // A restrained focus plane, not a full-picture blur or CSS filter.
        float blur=smoothstep(.10,.58,abs(d2-focus.x))*focus.y;
        vec2 px=vec2(1.)/size*blur;
        vec3 soft=(texture2D(col,uv+vec2(px.x,px.y)).rgb+
          texture2D(col,uv+vec2(-px.x,px.y)).rgb+
          texture2D(col,uv+vec2(px.x,-px.y)).rgb+
          texture2D(col,uv-px).rgb)*.25;
        color=mix(color,soft,sat(blur*.38));
        // Photographic highlights travel along the material instead of replacing it.
        if(style>1.5&&style<4.5){
          float glint=pow(max(0.,sin(uv.x*23.+uv.y*9.-uTime*.85+seed)),22.);
          color+=vec3(1.,.69,.28)*glint*gold*upper*.022;
        }
        if(style>.5&&style<1.5){
          float caustic=pow(sat(sin(uv.x*54.+sin(uv.y*18.+uTime*.8)*2.2-uTime*.7)),10.);
          color+=vec3(.9,.62,.23)*caustic*lower*.018;
        }
        // Thin flowing mist is limited to distant image depth and the horizon.
        float far=1.-smoothstep(.22,.62,d2);
        float fog=noise(uv*vec2(7.,11.)+vec2(uTime*.018,-uTime*.009)+seed);
        float horizon=exp(-pow((screen.y-.51)*5.8,2.));
        color=mix(color,vec3(.88,.69,.44),fog*far*horizon*.035*params.z);
        float vignette=smoothstep(.25,.83,length((screen-.5)*vec2(.85,1.)));
        color*=1.-vignette*.105;
        color=(color-.5)*1.018+.5;
        return clamp(color*params.w,0.,1.);
      }
      void main(){
        vec2 uvA=vUv,uvB=vUv;
        float blend=uMix;
        if(uTransition>2.5&&uTransition<3.5){
          float travel=1.-uTransitionPhase;
          uvA.x+=uTransitionPhase*.14;
          uvB.x-=travel*.14;
        }
        vec3 b=sampleScene(uColorB,uDepthB,uSizeB,uCameraB,uParamsB,uFocusB,uSeedB,uvB);
        vec3 color=b;
        if(uMix<.9999){
          vec3 a=sampleScene(uColorA,uDepthA,uSizeA,uCameraA,uParamsA,uFocusA,uSeedA,uvA);
          if(uTransition>.5&&uTransition<1.5){
            float sweep=vUv.x*.88+vUv.y*.12+.028*sin(vUv.y*8.);
            float threshold=mix(-.10,1.13,uTransitionPhase);
            blend=1.-smoothstep(threshold-.075,threshold+.075,sweep);
          }
          color=mix(a,b,sat(blend));
          if(uTransition>1.5&&uTransition<2.5){
            float leak=sin(uTransitionPhase*3.14159265);
            float gate=exp(-pow((vUv.x-uTransitionPhase)*2.3,2.));
            color+=vec3(1.,.43,.13)*leak*gate*.055;
          }
        }
        float grain=hash(gl_FragCoord.xy+floor(uTime*12.)*vec2(17.,29.))-.5;
        color+=grain*.005;
        gl_FragColor=vec4(clamp(color,0.,1.),1.);
      }
    `;
    const pointVertex = `
      attribute vec2 aPosition;
      attribute float aSize;
      attribute vec4 aColor;
      attribute vec2 aShape;
      varying vec4 vColor;
      varying vec2 vShape;
      void main(){gl_Position=vec4(aPosition,0.,1.);gl_PointSize=aSize;vColor=aColor;vShape=aShape;}
    `;
    const pointFragment = `
      precision mediump float;
      varying vec4 vColor;
      varying vec2 vShape;
      void main(){
        vec2 p=gl_PointCoord-.5;
        float s=sin(vShape.y),c=cos(vShape.y);
        p=vec2(c*p.x-s*p.y,s*p.x+c*p.y);
        float alpha;
        if(vShape.x>.5){
          float leaf=length(p*vec2(2.1,.9));
          alpha=(1.-smoothstep(.24,.43,leaf))*.76;
        }else{
          float r=length(p);
          alpha=exp(-r*r*24.)*(1.-smoothstep(.25,.5,r));
        }
        gl_FragColor=vec4(vColor.rgb,vColor.a*alpha);
      }
    `;
    function shader(type, source) {
      const item = gl.createShader(type); gl.shaderSource(item, source); gl.compileShader(item);
      if (!gl.getShaderParameter(item, gl.COMPILE_STATUS)) {
        const message = gl.getShaderInfoLog(item); gl.deleteShader(item); throw new Error('AI cinema shader: ' + message);
      }
      return item;
    }
    function program(vs, fs) {
      const item = gl.createProgram(); gl.attachShader(item, shader(gl.VERTEX_SHADER, vs));
      gl.attachShader(item, shader(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(item);
      if (!gl.getProgramParameter(item, gl.LINK_STATUS)) throw new Error('AI cinema program: ' + gl.getProgramInfoLog(item));
      return item;
    }
    const mainProgram = program(vertex, fragment), particleProgram = program(pointVertex, pointFragment);
    const quad = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const U = Object.fromEntries(['uColorA','uColorB','uDepthA','uDepthB','uSizeA','uSizeB','uCameraA','uCameraB',
      'uParamsA','uParamsB','uFocusA','uFocusB','uTime','uSeedA','uSeedB','uMix','uTransition','uTransitionPhase']
      .map(name => [name, gl.getUniformLocation(mainProgram, name)]));
    const pointBuffer = gl.createBuffer(), STRIDE = 9 * 4;
    const attributes = Object.fromEntries(['aPosition','aSize','aColor','aShape'].map(name => [name, gl.getAttribLocation(particleProgram, name)]));
    const pointData = new Float32Array(1800 * 9);
    function texture(image, isDepth = false) {
      const item = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, item);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      // Restore the color policy on every upload: asynchronous image/depth loads
      // may interleave. Depth values must stay linear, independent of PNG profiles.
      gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, isDepth ? gl.NONE : gl.BROWSER_DEFAULT_WEBGL);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return item;
    }
    const neutral = document.createElement('canvas'); neutral.width = neutral.height = 2;
    const nc = neutral.getContext('2d'); nc.fillStyle = '#808080'; nc.fillRect(0, 0, 2, 2);
    const neutralDepth = texture(neutral, true), images = Object.create(null), depths = Object.create(null);
    const assetIds = [...new Set(D.scenes.map(s => s.asset).filter(Boolean))];
    function loadImage(url) {
      return new Promise((resolve, reject) => {
        const im = new Image(); im.onload = () => resolve(im);
        im.onerror = () => reject(new Error('Missing AI film asset: ' + url)); im.src = url;
      });
    }
    await Promise.all(assetIds.map(async id => {
      const url = D.assets[id]; if (!url) throw new Error('AI shot references an undeclared asset: ' + id);
      const im = await loadImage(url); images[id] = {texture: texture(im), width: im.width, height: im.height};
      const path = D.depths?.[id];
      if (path) { const depth = await loadImage(typeof path === 'string' ? path : path.path); depths[id] = texture(depth, true); }
    }));
    if (D.requireDepth && assetIds.some(id => !depths[id])) {
      throw new Error('AI-depth delivery is missing maps for: ' + assetIds.filter(id => !depths[id]).join(', '));
    }
    function before(t) {
      let lo = 0, hi = D.scenes.length - 1, found = 0;
      while (lo <= hi) { const mid = (lo + hi) >> 1; if (D.scenes[mid].start <= t) { found = mid; lo = mid + 1; } else hi = mid - 1; }
      return found;
    }
    function styleFor(s) {
      if (Number.isFinite(s.flowStyle)) return s.flowStyle;
      const label = `${s.world || ''} ${s.asset || ''} ${s.theme || ''}`;
      if (/water|koi|pond|lake|river|ocean|reflection/i.test(label)) return 1;
      if (/silk|ribbon|fabric/i.test(label)) return 2;
      if (/lantern|avenue|street|palace|festival/i.test(label)) return 3;
      if (/dragon|arena|firework|gold/i.test(label)) return 4;
      if (/cloud|sunrise|sky|bridge|mountain|dawn/i.test(label)) return 5;
      return 0;
    }
    function cameraAt(s, t) {
      const duration = Math.max(.1, s.end - s.start);
      const rawProgress = (t - s.start) / duration, p = clamp(rawProgress), e = ease(p);
      if (s.cameraFrom !== undefined || s.cameraTo !== undefined) {
        const validPose = pose => Array.isArray(pose) && pose.length === 4 && pose.every(Number.isFinite) && pose[2] > 0;
        if (!validPose(s.cameraFrom) || !validPose(s.cameraTo)) {
          throw new Error('AI cameraFrom/cameraTo require finite [x,y,positive zoom,roll] poses.');
        }
        // The outgoing picture keeps its authored velocity while a short incoming
        // wipe still exposes it. Bound extrapolation to the transition-sized tail.
        const q = s.cameraEase === 'linear' ? clamp(rawProgress, 0, 1 + .35 / duration) : e;
        return s.cameraFrom.map((value, index) => mix(value, s.cameraTo[index], q));
      }
      const seed = Number(s.seed || 1811), side = seed % 2 ? 1 : -1;
      const motion = String(s.motion || 'push').toLowerCase();
      let x = 0, y = 0, z = mix(1.075, 1.16, e), roll = 0;
      if (/pull|release|wide/.test(motion)) z = mix(1.17, 1.075, e);
      else if (/orbit|arc/.test(motion)) { x = Math.sin((p - .5) * 1.55) * .026 * side; y = Math.cos((p - .5) * 1.6) * .008; z = 1.12 + .025 * Math.sin(p * Math.PI); roll = Math.sin(p * Math.PI) * .004 * side; }
      else if (/crane|rise|reveal/.test(motion)) { y = mix(-.022, .022, e); x = side * mix(-.008, .009, e); z = mix(1.13, 1.085, e); }
      else if (/rush|dive|impact/.test(motion)) { const q = 1 - Math.pow(1 - p, 2.2); z = mix(1.065, 1.2, q); x = side * .009 * Math.sin(q * Math.PI); roll = side * .003 * Math.sin(q * Math.PI); }
      else if (/macro|close/.test(motion)) { z = mix(1.25, 1.34, e); x = side * mix(-.014, .017, e); y = .008 * Math.sin(p * Math.PI); }
      else if (/track|sweep|pan|glide|drift/.test(motion)) { x = side * mix(-.026, .026, e); y = mix(-.006, .008, e); z = 1.125 + .008 * Math.sin(p * Math.PI); }
      else if (/hold|float|breathe/.test(motion)) { z = 1.085 + .016 * e; x = side * .006 * Math.sin((p - .5) * 1.5); y = .003 * e; }
      else { x = side * .009 * Math.sin((p - .5) * 1.4); y = mix(-.004, .007, e); }
      const focal = s.focal || s.focusPoint;
      if (Array.isArray(focal)) { x += (focal[0] - .5) * (1 - 1 / z); y += (.5 - focal[1]) * (1 - 1 / z); }
      return [x, y, z, roll];
    }
    function bindScene(s, t, slot) {
      const im = images[s.asset]; if (!im) throw new Error('Unloaded AI image: ' + s.asset);
      const seed = Number(s.seed || 1811) % 997;
      const phase = clamp((t - s.start) / Math.max(.1, s.end - s.start));
      const focus = Number.isFinite(s.focusDepth) ? s.focusDepth : .49 + Math.sin(phase * Math.PI) * .12;
      const depthStrength = Number.isFinite(s.parallax) ? clamp(s.parallax, 0, 1.5) : .72;
      const flow = Number.isFinite(s.flow) ? clamp(s.flow, 0, 1.5) : .8;
      gl.activeTexture(gl.TEXTURE0 + slot); gl.bindTexture(gl.TEXTURE_2D, im.texture);
      gl.activeTexture(gl.TEXTURE0 + slot + 2); gl.bindTexture(gl.TEXTURE_2D, depths[s.asset] || neutralDepth);
      const key = slot === 0 ? 'A' : 'B';
      gl.uniform2f(U['uSize' + key], im.width, im.height);
      gl.uniform4fv(U['uCamera' + key], cameraAt(s, t));
      gl.uniform4f(U['uParams' + key], styleFor(s), depthStrength, flow, Number(s.exposure || 1));
      gl.uniform2f(U['uFocus' + key], focus, Number.isFinite(s.dof) ? clamp(s.dof, 0, 1.8) : .65);
      gl.uniform1f(U['uSeed' + key], seed * .031);
    }
    const random = seeded(18112026);
    const dust = Array.from({length: 125}, (_, i) => ({
      x: random(), y: random(), depth: .15 + random() * .85, phase: random() * TAU,
      speed: .3 + random() * .7, petal: i < 15,
    }));
    function drawAtmosphere(s, t) {
      let count = 0;
      const side = Number(s.seed || 0) % 2 ? 1 : -1;
      const strength = Number.isFinite(s.atmosphere) ? clamp(s.atmosphere, 0, 1.5) : .65;
      const age = t - s.start, total = s.end - s.start;
      const enter = smooth(Math.min(age / .6, (total - age) / .35));
      function point(x, y, size, r, g, b, a, shape, angle) {
        if (count >= 1800 || a < .001 || x < -.1 || x > 1.1 || y < -.1 || y > 1.1) return;
        const o = count++ * 9; pointData[o] = x * 2 - 1; pointData[o + 1] = y * 2 - 1;
        pointData[o + 2] = size; pointData[o + 3] = r; pointData[o + 4] = g; pointData[o + 5] = b;
        pointData[o + 6] = a; pointData[o + 7] = shape; pointData[o + 8] = angle;
      }
      for (let i = 0; i < dust.length; i++) {
        const a = dust[i], z = a.depth;
        const x = fract(a.x + Math.sin(t * .16 + a.phase) * .019 * z + t * .002 * side * z);
        const y = fract(a.y + t * .018 * a.speed * (a.petal ? -.6 : 1));
        const protectedLyrics = y < .21 ? .2 : 1;
        if (a.petal) point(x, y, 5 + 13 * z, .68, .07, .10, .19 * strength * enter * protectedLyrics, 1, t * .32 + a.phase);
        else point(x, y, 2 + Math.pow(z, 4) * 12, 1, .72, .34, (.06 + z * .17) * strength * enter * protectedLyrics, 0, 0);
      }
      if (s.celebration || /firework|finale|celebration/.test(`${s.world || ''} ${s.theme || ''}`)) {
        for (let burst = 0; burst < 3; burst++) {
          const life = age - (.35 + burst * 1.55);
          if (life < 0 || life > 1.9) continue;
          const r = seeded(Number(s.seed || 1811) + 71 * burst), cx = .2 + r() * .6, cy = .62 + r() * .2;
          const fade = Math.pow(1 - life / 1.9, 1.6) * .63;
          for (let j = 0; j < 62; j++) {
            const angle = j / 62 * TAU + r() * .04, speed = 45 + r() * 95;
            for (let trail = 0; trail < 3; trail++) {
              const a = Math.max(0, life - trail * .035);
              const x = cx + Math.cos(angle) * speed * a / W;
              const y = cy + (Math.sin(angle) * speed * a - 30 * a * a) / PH;
              point(x, y, trail ? 2.5 : 5.5, 1, .69 + j % 3 * .04, .28, fade * (trail ? .35 : .8), 0, 0);
            }
          }
        }
      }
      gl.useProgram(particleProgram); gl.bindBuffer(gl.ARRAY_BUFFER, pointBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, pointData.subarray(0, count * 9), gl.DYNAMIC_DRAW);
      for (const [name, size, offset] of [['aPosition',2,0],['aSize',1,8],['aColor',4,12],['aShape',2,28]]) {
        gl.enableVertexAttribArray(attributes[name]); gl.vertexAttribPointer(attributes[name], size, gl.FLOAT, false, STRIDE, offset);
      }
      gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.drawArrays(gl.POINTS, 0, count); gl.disable(gl.BLEND);
      for (const index of Object.values(attributes)) gl.disableVertexAttribArray(index);
    }
    function renderAt(time) {
      if (gl.isContextLost()) throw new Error('AI cinema WebGL context was lost.');
      const offset = Number.isFinite(window.BOSSTON_AI_TIME_OFFSET) ? window.BOSSTON_AI_TIME_OFFSET : 0;
      const t = clamp(time + offset, 0, D.duration - .000001), index = before(t), current = D.scenes[index];
      const transition = String(current.transition || 'cut').toLowerCase(), age = t - current.start;
      const duration = Number(current.transitionDuration || (/whip/.test(transition) ? .22 : /silk|wipe/.test(transition) ? .3 : .2));
      const active = index > 0 && age < duration && !/^cut$|^none$/.test(transition);
      const previous = active ? D.scenes[index - 1] : current;
      const phase = active ? clamp(age / duration) : 1;
      const kind = /whip/.test(transition) ? 3 : /light|leak|flash/.test(transition) ? 2 : /silk|wipe/.test(transition) ? 1 : 0;
      gl.viewport(0, 0, W, H); gl.disable(gl.SCISSOR_TEST); gl.clearColor(.008, .01, .014, 1); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.viewport(0, TOP, W, PH); gl.useProgram(mainProgram); gl.bindBuffer(gl.ARRAY_BUFFER, quad);
      const position = gl.getAttribLocation(mainProgram, 'aPosition');
      gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1i(U.uColorA, 0); gl.uniform1i(U.uColorB, 1); gl.uniform1i(U.uDepthA, 2); gl.uniform1i(U.uDepthB, 3);
      bindScene(previous, t, 0); bindScene(current, t, 1);
      gl.uniform1f(U.uTime, t); gl.uniform1f(U.uMix, active ? smooth(phase) : 1);
      gl.uniform1f(U.uTransition, kind); gl.uniform1f(U.uTransitionPhase, phase);
      gl.drawArrays(gl.TRIANGLES, 0, 6); gl.disableVertexAttribArray(position);
      drawAtmosphere(current, t);
      window.__bosstonAiTime = t;
      window.__bosstonAiShot = current.id || index;
    }
    window.renderAiCinemaAt = renderAt;
    window.__bosstonAi = {
      renderer: 'Local WebGL 2.5D AI-depth parallax', assetCount: assetIds.length,
      depthCount: Object.keys(depths).length, depthFallbacks: assetIds.filter(id => !depths[id]),
      depthConvention: '0 far, 1 near', canvas,
      limits: 'Procedural animation of AI-generated artwork; not native generated-video footage.',
    };
    renderAt(0);
    return window.__bosstonAi;
  })();
  window.__hf.buildReady.bosstonAi = ready;
})();
