/* A moving physical foreground for the Bosston / Pragon film.
 * The film clock is the only animation source. No RAF, media control or live fetches.
 * Three.js r187 is reused locally under its accompanying MIT license.
 */
(() => {
  'use strict';
  window.__hf = window.__hf || {};
  window.__hf.buildReady = window.__hf.buildReady || {};
  const ready = import('./assets/vendor/three.module.js').then(async THREE => {
    const canvas = document.getElementById('world3d');
    if (!canvas) throw new Error('Bosston spatial motion requires <canvas id="world3d">.');
    const W = 1920, H = 1080, TOP = 76, PH = 928, TAU = Math.PI * 2;
    const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
    const mix = (a, b, p) => a + (b - a) * p;
    const fract = x => x - Math.floor(x);
    const ease = p => .5 - .5 * Math.cos(clamp(p) * Math.PI);
    function seeded(seed) {
      let state = seed >>> 0;
      return () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
    }
    const random = seeded(18112026);
    const renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:true, preserveDrawingBuffer:true, powerPreference:'high-performance'});
    renderer.setSize(W, H, false); renderer.setPixelRatio(1);
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    const scene = new THREE.Scene();
    const lanternFog = new THREE.FogExp2(0x160a07,.015);
    const camera = new THREE.PerspectiveCamera(44, W / PH, .08, 180);
    camera.position.set(0, 4, 10); camera.lookAt(0, 4, -15);
    const hemisphere=new THREE.HemisphereLight(0xffead0, 0x122329, 1.65);scene.add(hemisphere);
    const key = new THREE.DirectionalLight(0xffd29b, 4.5); key.position.set(-8, 13, 10); scene.add(key);
    const rim = new THREE.DirectionalLight(0xffb94b, 3.2); rim.position.set(7, 7, -20); scene.add(rim);
    const cool = new THREE.DirectionalLight(0x7ba8b2, 1.1); cool.position.set(10, 3, 4); scene.add(cool);
    const warm = new THREE.PointLight(0xff6a27, 42, 38, 2); warm.position.set(-2, 5, -12); scene.add(warm);
    // A frozen light room supplies real material reflections without an external HDRI.
    const room = new THREE.Scene(); room.background = new THREE.Color(0x14100d);
    const panelGeometry = new THREE.PlaneGeometry(10, 7);
    for (const [color, intensity, pos, rot] of [
      [0xffe2b5, 5, [-6, 6, 3], [0, .7, 0]],
      [0xffffff, 7, [4, 9, -2], [-.6, -.4, 0]],
      [0xc45d31, 3, [7, 1, -8], [0, -1.3, 0]],
      [0x72989a, 2, [-8, 1, -7], [0, 1.2, 0]],
    ]) {
      const panel = new THREE.Mesh(panelGeometry, new THREE.MeshBasicMaterial({color, side:THREE.DoubleSide}));
      panel.material.color.multiplyScalar(intensity); panel.position.set(...pos); panel.rotation.set(...rot); room.add(panel);
    }
    const pmrem = new THREE.PMREMGenerator(renderer);
    const environment = pmrem.fromScene(room, .035, .1, 60); scene.environment = environment.texture;
    pmrem.dispose();
    const gold = new THREE.MeshPhysicalMaterial({color:0xe4b969, metalness:.96, roughness:.22, clearcoat:.4, envMapIntensity:1.25});
    const darkGold = new THREE.MeshPhysicalMaterial({color:0x98703e, metalness:.9, roughness:.32, envMapIntensity:1.25});
    const red = new THREE.MeshPhysicalMaterial({color:0x9c1022, metalness:.22, roughness:.35, clearcoat:.75, clearcoatRoughness:.2});
    const ivory = new THREE.MeshStandardMaterial({color:0xf6dcc0, roughness:.58, metalness:.03});
    const threadRed = new THREE.MeshStandardMaterial({color:0x8d0714, roughness:.74});
    const obsidian = new THREE.MeshPhysicalMaterial({color:0x0b0b0c, metalness:.7, roughness:.19, clearcoat:1, envMapIntensity:1.05});
    const groups = Object.fromEntries(['lanterns','ribbons','portal','bridge','drums','water','dragon'].map(name => {
      const group = new THREE.Group(); group.name = name; scene.add(group); return [name, group];
    }));
    function mesh(geometry, material, parent, x = 0, y = 0, z = 0) {
      const object = new THREE.Mesh(geometry, material); object.position.set(x, y, z); parent.add(object); return object;
    }
    function texture(w, h, draw) {
      const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
      const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4; return tex;
    }
    const paper = texture(1024, 1024, (c, w, h) => {
      c.fillStyle='#8d1018';c.fillRect(0,0,w,h);
      // Opaque silk panels have modest panel-to-panel shading, not glossy balloon stripes.
      for(let k=0;k<20;k++){
        const x=k*w/20,g=c.createLinearGradient(x,0,x+w/20,0);
        g.addColorStop(0,'#650c14');g.addColorStop(.2,'#89121b');g.addColorStop(.52,'#a51b20');g.addColorStop(.82,'#89121b');g.addColorStop(1,'#650c14');
        c.fillStyle=g;c.fillRect(x,0,w/20+1,h);
      }
      const end=c.createLinearGradient(0,0,0,h);end.addColorStop(0,'#250309e0');end.addColorStop(.17,'#25030900');end.addColorStop(.8,'#25030900');end.addColorStop(1,'#250309d9');c.fillStyle=end;c.fillRect(0,0,w,h);
      c.strokeStyle='#bf9b5a70';c.lineWidth=2;
      for(const y of [44,52,h-44,h-52]){c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();}
      const r=seeded(903);
      for(let i=0;i<75000;i++){c.fillStyle=r()>.5?'#e7b59a12':'#1701041c';c.fillRect(r()*w,r()*h,1,1+r()*2);}
      c.strokeStyle='#df9b7a0c';c.lineWidth=.6;
      for(let y=0;y<h;y+=3){c.beginPath();c.moveTo(0,y);c.lineTo(w,y+.4);c.stroke();}
      for(let x=0;x<w;x+=3){c.beginPath();c.moveTo(x,0);c.lineTo(x+.6,h);c.stroke();}
    });
    const paperBump=texture(512,512,(c,w,h)=>{
      c.fillStyle='#808080';c.fillRect(0,0,w,h);const r=seeded(34);
      for(let i=0;i<40000;i++){c.fillStyle=r()>.5?'#ffffff0d':'#00000010';c.fillRect(r()*w,r()*h,1,1);}
      c.strokeStyle='#555555';c.lineWidth=2;for(let x=0;x<w;x+=w/20){c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.stroke();}
    });paperBump.colorSpace=THREE.NoColorSpace;
    const innerGlow=texture(256,512,(c,w,h)=>{
      const g=c.createLinearGradient(0,0,0,h);g.addColorStop(0,'#000');g.addColorStop(.15,'#111');g.addColorStop(.4,'#b0b0b0');g.addColorStop(.55,'#d4d4d4');g.addColorStop(.8,'#555');g.addColorStop(1,'#000');c.fillStyle=g;c.fillRect(0,0,w,h);
    });innerGlow.colorSpace=THREE.NoColorSpace;
    const lanternMaterial = new THREE.MeshStandardMaterial({map:paper, color:0xffffff, bumpMap:paperBump, bumpScale:.014, emissive:0xff3b0b, emissiveMap:innerGlow, emissiveIntensity:.19, metalness:0, roughness:.91, envMapIntensity:.32});
    const lanternProfile=Array.from({length:33},(_,i)=>{const u=i/32;return new THREE.Vector2(.22+.76*Math.pow(Math.sin(Math.PI*u),.67),mix(-.88,.88,u));});
    const bodyGeometry = new THREE.LatheGeometry(lanternProfile,64);
    const brass=new THREE.MeshStandardMaterial({color:0xa58245,metalness:.92,roughness:.42,envMapIntensity:.9});
    const bamboo=new THREE.MeshStandardMaterial({color:0x501018,metalness:0,roughness:.9});
    const rope=new THREE.MeshStandardMaterial({color:0x3d2518,metalness:0,roughness:.97});
    const capGeometry = new THREE.LatheGeometry([new THREE.Vector2(.2,-.06),new THREE.Vector2(.255,-.055),new THREE.Vector2(.27,-.035),new THREE.Vector2(.265,.035),new THREE.Vector2(.245,.06),new THREE.Vector2(.19,.07)],40);
    const cordGeometry = new THREE.CylinderGeometry(.012,.012,1,6);
    function mergeLanternGeometry(parts){
      let vertexCount=0,indexCount=0;
      for(const g of parts){vertexCount+=g.attributes.position.count;indexCount+=g.index?g.index.count:g.attributes.position.count;}
      const positions=new Float32Array(vertexCount*3),normals=new Float32Array(vertexCount*3),uvs=new Float32Array(vertexCount*2),indices=new Uint32Array(indexCount);let vo=0,io=0;
      for(const g of parts){positions.set(g.attributes.position.array,vo*3);normals.set(g.attributes.normal.array,vo*3);if(g.attributes.uv)uvs.set(g.attributes.uv.array,vo*2);for(let i=0;i<(g.index?.count??g.attributes.position.count);i++)indices[io++]=(g.index?g.index.array[i]:i)+vo;vo+=g.attributes.position.count;g.dispose();}
      const out=new THREE.BufferGeometry();out.setAttribute('position',new THREE.BufferAttribute(positions,3));out.setAttribute('normal',new THREE.BufferAttribute(normals,3));out.setAttribute('uv',new THREE.BufferAttribute(uvs,2));out.setIndex(new THREE.BufferAttribute(indices,1));return out;
    }
    const ribs=[];
    for(let k=0;k<20;k++){
      const theta=k/20*TAU,points=lanternProfile.map(p=>new THREE.Vector3(Math.sin(theta)*(p.x+.003),p.y,Math.cos(theta)*(p.x+.003)));
      ribs.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),24,.006,4,false));
    }
    const ribGeometry=mergeLanternGeometry(ribs),tasselParts=[];
    for(let k=0;k<17;k++){
      const a=k/17*TAU,r=.04+k%3*.012;
      tasselParts.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
        new THREE.Vector3(Math.sin(a)*.017,.39,Math.cos(a)*.017),
        new THREE.Vector3(Math.sin(a)*r,.02,Math.cos(a)*r),
        new THREE.Vector3(Math.sin(a+.15)*r*1.5,-.4,Math.cos(a+.15)*r*1.5),
      ]),10,.005,3,false));
    }
    const tasselGeometry=mergeLanternGeometry(tasselParts);
    const lanternCount = 96;
    const lanternBody = new THREE.InstancedMesh(bodyGeometry,lanternMaterial,lanternCount);
    const lanternRibs = new THREE.InstancedMesh(ribGeometry,bamboo,lanternCount);
    const lanternCap = new THREE.InstancedMesh(capGeometry,brass,lanternCount*2);
    const lanternCord = new THREE.InstancedMesh(cordGeometry,rope,lanternCount);
    const lanternTassel = new THREE.InstancedMesh(tasselGeometry,threadRed,lanternCount);
    const haloTexture=texture(128,128,(c,w,h)=>{const g=c.createRadialGradient(w/2,h/2,0,w/2,h/2,w/2);g.addColorStop(0,'#fff');g.addColorStop(.2,'#ffffff50');g.addColorStop(.55,'#ffffff0c');g.addColorStop(1,'#ffffff00');c.fillStyle=g;c.fillRect(0,0,w,h);});
    const lanternHalo=new THREE.InstancedMesh(new THREE.PlaneGeometry(1,1),new THREE.MeshBasicMaterial({map:haloTexture,color:0xff4a15,transparent:true,opacity:.035,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide}),lanternCount);lanternHalo.renderOrder=-1;
    groups.lanterns.add(lanternBody,lanternRibs,lanternCap,lanternCord,lanternTassel,lanternHalo);
    const lanternData = Array.from({length:lanternCount},(_,i)=>({
      x:(i%2?1:-1)*(2.6+random()*10.5),y:4.2+random()*5.2,z:12-Math.floor(i/4)*3.9,
      scale:.5+random()*.78,phase:random()*TAU, speed:.3+random()*.7,
    }));
    const overheadWirePositions=[];
    for(let row=0;row<24;row++)overheadWirePositions.push(-18,16,12-row*3.9,18,16,12-row*3.9);
    const overheadWires=new THREE.BufferGeometry();overheadWires.setAttribute('position',new THREE.Float32BufferAttribute(overheadWirePositions,3));
    groups.lanterns.add(new THREE.LineSegments(overheadWires,new THREE.LineBasicMaterial({color:0x493425,transparent:true,opacity:.5})));
    const dummy=new THREE.Object3D();
    function instance(target,index,x,y,z,sx,sy,sz,rz=0){dummy.position.set(x,y,z);dummy.rotation.set(0,0,rz);dummy.scale.set(sx,sy,sz);dummy.updateMatrix();target.setMatrixAt(index,dummy.matrix);}
    function updateLanterns(t, final=false){
      for(let i=0;i<lanternCount;i++){
        const a=lanternData[i],s=a.scale;
        const x=a.x+Math.sin(t*.31+a.phase)*.22, y=a.y+Math.sin(t*.45+a.phase)*.17, z=a.z;
        const r=Math.sin(t*.55+a.phase)*.06;
        instance(lanternBody,i,x,y,z,s*.69,s*1.03,s*.69,r);
        instance(lanternRibs,i,x,y,z,s*.69,s*1.03,s*.69,r);
        instance(lanternCap,i*2,x-Math.sin(r)*s*.92,y+Math.cos(r)*s*.92,z,s,s,s,r);
        instance(lanternCap,i*2+1,x+Math.sin(r)*s*.92,y-Math.cos(r)*s*.92,z,s,s,s,r);
        const ropeBottom=y+Math.cos(r)*s*.97,ropeTop=16;
        instance(lanternCord,i,x-Math.sin(r)*s*.92,(ropeBottom+ropeTop)/2,z,1,ropeTop-ropeBottom,1,0);
        instance(lanternTassel,i,x+Math.sin(r)*s*1.35,y-s*1.35,z,s,s,s,r+.03*Math.sin(t*2+a.phase));
        instance(lanternHalo,i,x,y,z,s*3.3,s*4.6,1,0);
      }
      for(const object of [lanternBody,lanternRibs,lanternCap,lanternCord,lanternTassel,lanternHalo])object.instanceMatrix.needsUpdate=true;
    }
    // Broad satin ribbons are actual moving surfaces: silhouette, specular and occlusion change.
    const ribbonObjects=[];
    for(let k=0;k<7;k++){
      const n=144, positions=new Float32Array((n+1)*2*3),uvs=new Float32Array((n+1)*2*2),indices=[];
      for(let i=0;i<=n;i++){uvs[i*4]=i/n;uvs[i*4+1]=0;uvs[i*4+2]=i/n;uvs[i*4+3]=1;if(i<n){const a=i*2;indices.push(a,a+1,a+2,a+1,a+3,a+2);}}
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('uv',new THREE.BufferAttribute(uvs,2));geometry.setIndex(indices);
      const mat=new THREE.MeshPhysicalMaterial({color:k%3?0xab1023:0xe2b364,metalness:k%3?.18:.95,roughness:k%3?.33:.2,clearcoat:.75,side:THREE.DoubleSide,envMapIntensity:1.4});
      const object=mesh(geometry,mat,groups.ribbons);object.frustumCulled=false;ribbonObjects.push({object,n,k,positions});
    }
    function updateRibbons(t, seed){
      for(const a of ribbonObjects){
        for(let i=0;i<=a.n;i++){
          const u=i/a.n,angle=u*TAU*1.17+a.k*.56+t*.29,rad=3.3+1.8*Math.sin(u*Math.PI)+a.k*.15;
          const x=Math.sin(angle)*rad, y=-.5+u*11+.42*Math.sin(u*13-t*1.2+a.k), z=-14+Math.cos(angle)*rad;
          const width=(.42+.39*Math.sin(Math.PI*u))*(a.k%3?1.4:.5), twist=u*8+t*.65+a.k;
          for(let side=0;side<2;side++){
            const sign=side?1:-1,index=(i*2+side)*3;
            a.positions[index]=x+sign*Math.cos(twist)*width;
            a.positions[index+1]=y+sign*Math.sin(twist)*width;
            a.positions[index+2]=z+sign*Math.sin(angle+.8)*width*.7;
          }
        }
        a.object.geometry.attributes.position.needsUpdate=true;a.object.geometry.computeVertexNormals();
        a.object.rotation.y=Math.sin(seed*.001)*.3;
      }
    }
    const floor=mesh(new THREE.PlaneGeometry(80,120),obsidian,groups.portal,0,-1.4,-26);floor.rotation.x=-Math.PI/2;
    const gateGeometry=new THREE.TorusGeometry(5.5,.09,10,96,Math.PI);
    const gateLeg=new THREE.CylinderGeometry(.085,.085,5,12);
    const gateFaces=[];
    for(let i=0;i<11;i++){
      const g=new THREE.Group();g.position.set(0,3.6,-i*8);groups.portal.add(g);
      mesh(gateGeometry,i%3?gold:red,g,0,0,0);
      for(const x of [-5.5,5.5])mesh(gateLeg,gold,g,x,-2.5,0);
      const band=mesh(new THREE.TorusGeometry(5.85,.018,6,96,Math.PI),gold,g);band.position.z=.12;
      gateFaces.push(g);
    }
    const strip=new THREE.BoxGeometry(.025,.015,105),stripMaterial=new THREE.MeshBasicMaterial({color:0xf2c77b});
    for(const x of [-3.4,-3.3,3.3,3.4])mesh(strip,stripMaterial,groups.portal,x,-1.38,-38);
    const sculpture=new THREE.Group();sculpture.position.set(0,3.2,-15);groups.portal.add(sculpture);
    for(let i=0;i<9;i++){
      const ring=mesh(new THREE.TorusGeometry(3.1+i*.07,.035,8,120),i%3?gold:red,sculpture);
      ring.userData.index=i;
    }
    // A dimensional Chinese dragon: articulated body, antlers, whiskers, jaw and dorsal spines.
    // Its silhouette changes with the deformation and head orientation, not a plate transform.
    const scaleTexture=texture(512,512,(c,w,h)=>{
      c.fillStyle='#ddb263';c.fillRect(0,0,w,h);c.strokeStyle='#95632c';c.lineWidth=1.6;
      for(let y=-25;y<h+30;y+=30)for(let x=-30;x<w+35;x+=44){const ox=(Math.floor(y/30)%2)*22;c.beginPath();c.ellipse(x+ox,y,23,30,0,0,Math.PI);c.stroke();}
      c.strokeStyle='#ffe1a1';c.lineWidth=.8;for(let y=-25;y<h+30;y+=30)for(let x=-30;x<w+35;x+=44){const ox=(Math.floor(y/30)%2)*22;c.beginPath();c.ellipse(x+ox,y+2,20,27,0,0,Math.PI);c.stroke();}
    });scaleTexture.wrapS=scaleTexture.wrapT=THREE.RepeatWrapping;scaleTexture.repeat.set(7,1);
    const dragonGold=new THREE.MeshPhysicalMaterial({map:scaleTexture,color:0xf3c778,metalness:.94,roughness:.26,clearcoat:.4,envMapIntensity:1.5});
    const dragonHead=new THREE.Group();groups.dragon.add(dragonHead);
    mesh(new THREE.SphereGeometry(1,36,24),dragonGold,dragonHead,0,0,0).scale.set(1.03,.76,1.2);
    mesh(new THREE.SphereGeometry(1,32,20),gold,dragonHead,0,-.2,1.15).scale.set(.78,.45,1.4);
    mesh(new THREE.SphereGeometry(1,32,16),darkGold,dragonHead,0,-.67,1.12).scale.set(.77,.16,1.44);
    mesh(new THREE.SphereGeometry(1,24,16),gold,dragonHead,0,-.76,1.05).scale.set(.68,.11,1.32);
    const black=new THREE.MeshStandardMaterial({color:0x100a05,metalness:.12,roughness:.32});
    const eye=new THREE.MeshPhysicalMaterial({color:0x5c2107,emissive:0xe7a02e,emissiveIntensity:.35,metalness:.4,roughness:.12});
    function tube(points,radius,material,parent){return mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p))),44,radius,8,false),material,parent);}
    for(const side of [-1,1]){
      mesh(new THREE.SphereGeometry(.15,20,12),eye,dragonHead,side*.86,.17,.66).scale.set(.45,1,1.2);
      mesh(new THREE.SphereGeometry(.11,16,10),black,dragonHead,side*.27,-.09,2.43).scale.set(.65,.6,1);
      tube([[side*.45,.48,-.2],[side*.8,1.2,-.85],[side*1.2,1.7,-1.6],[side*1.5,2,-2.25]],.105,gold,dragonHead);
      tube([[side*.88,1.27,-1.03],[side*1.45,1.55,-.95],[side*1.75,1.73,-1.4]],.066,gold,dragonHead);
      tube([[side*.8,.25,.2],[side*1.1,.45,.8],[side*.67,.42,1.25]],.105,darkGold,dragonHead);
      tube([[side*.65,-.4,1.9],[side*2,-.5,2.55],[side*3,-.05,1.7],[side*3.55,.5,.6]],.033,gold,dragonHead);
      tube([[side*.75,-.45,1.6],[side*1.6,-.85,2],[side*2.35,-1.3,1.35]],.021,gold,dragonHead);
      for(const z of [1.2,1.8]){const fang=mesh(new THREE.ConeGeometry(.1,.44,12),ivory,dragonHead,side*.62,-.53,z);fang.rotation.z=Math.PI;}
      for(let j=0;j<4;j++){const fin=mesh(new THREE.ConeGeometry(.14,.55,10),gold,dragonHead,side*(.92+j*.08),-.13-j*.15,-.5-j*.35);fin.rotation.z=-side*.85;}
    }
    const dragonSegments=112,dragonSides=16,dragonPositions=new Float32Array((dragonSegments+1)*(dragonSides+1)*3),dragonUV=new Float32Array((dragonSegments+1)*(dragonSides+1)*2),dragonIndices=[];
    for(let i=0;i<=dragonSegments;i++)for(let j=0;j<=dragonSides;j++){
      const uv=(i*(dragonSides+1)+j)*2;dragonUV[uv]=i/dragonSegments;dragonUV[uv+1]=j/dragonSides;
      if(i<dragonSegments&&j<dragonSides){const n=i*(dragonSides+1)+j;dragonIndices.push(n,n+dragonSides+1,n+1,n+1,n+dragonSides+1,n+dragonSides+2);}
    }
    const dragonGeometry=new THREE.BufferGeometry();dragonGeometry.setAttribute('position',new THREE.BufferAttribute(dragonPositions,3));dragonGeometry.setAttribute('uv',new THREE.BufferAttribute(dragonUV,2));dragonGeometry.setIndex(dragonIndices);
    const dragonBody=mesh(dragonGeometry,dragonGold,groups.dragon);dragonBody.frustumCulled=false;
    const spines=new THREE.InstancedMesh(new THREE.ConeGeometry(.13,.7,8),gold,34);groups.dragon.add(spines);
    const headForward=new THREE.Vector3(0,0,1),dragonPoint=new THREE.Vector3(),dragonTangent=new THREE.Vector3(),dragonNormal=new THREE.Vector3(),dragonBinormal=new THREE.Vector3();
    function dragonCurve(u,t,target){
      const a=u*TAU*1.23+t*.34;
      return target.set(mix(12,-16,u),4.1+Math.sin(a)*2.6+u*.7,-17+Math.cos(a)*4.5);
    }
    function updateDragon(t){
      for(let i=0;i<=dragonSegments;i++){
        const u=i/dragonSegments;dragonCurve(u,t,dragonPoint);dragonCurve(Math.min(1,u+.002),t,dragonTangent).sub(dragonPoint);
        if(dragonTangent.lengthSq()<.00001)dragonTangent.set(-1,0,0);dragonTangent.normalize();
        dragonNormal.crossVectors(dragonTangent,new THREE.Vector3(0,1,0)).normalize();dragonBinormal.crossVectors(dragonNormal,dragonTangent).normalize();
        const radius=.64*Math.pow(1-u,.7)+.06;
        for(let j=0;j<=dragonSides;j++){
          const a=j/dragonSides*TAU,p=(i*(dragonSides+1)+j)*3;
          dragonPositions[p]=dragonPoint.x+radius*(dragonNormal.x*Math.cos(a)+dragonBinormal.x*Math.sin(a));
          dragonPositions[p+1]=dragonPoint.y+radius*(dragonNormal.y*Math.cos(a)+dragonBinormal.y*Math.sin(a));
          dragonPositions[p+2]=dragonPoint.z+radius*(dragonNormal.z*Math.cos(a)+dragonBinormal.z*Math.sin(a));
        }
      }
      dragonGeometry.attributes.position.needsUpdate=true;dragonGeometry.computeVertexNormals();
      dragonCurve(0,t,dragonPoint);dragonHead.position.copy(dragonPoint);dragonCurve(.003,t,dragonTangent).sub(dragonPoint).normalize().negate();dragonHead.quaternion.setFromUnitVectors(headForward,dragonTangent);
      for(let i=0;i<34;i++){const u=i/34;dragonCurve(u,t,dragonPoint);const s=1-u*.8;instance(spines,i,dragonPoint.x,dragonPoint.y+.7*s,dragonPoint.z,s,s,s,Math.sin(u*10+t*.3)*.1);}
      spines.instanceMatrix.needsUpdate=true;
    }
    // A bridge built in depth gives the crane shot a moving parapet and true parallax.
    const stoneMap=texture(512,512,(c,w,h)=>{
      c.fillStyle='#77716a';c.fillRect(0,0,w,h);const r=seeded(717);
      for(let i=0;i<40000;i++){const v=Math.floor(75+r()*95);c.fillStyle=`rgba(${v},${v-4},${v-8},.11)`;c.fillRect(r()*w,r()*h,1+r()*4,1+r()*3);}
      c.strokeStyle='#39312b';c.lineWidth=4;for(let y=0;y<h;y+=128){c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();for(let x=(y/128%2)*128;x<w;x+=256)c.strokeRect(x,y,256,128);}
    });stoneMap.wrapS=stoneMap.wrapT=THREE.RepeatWrapping;
    const stone=new THREE.MeshStandardMaterial({map:stoneMap,color:0x8c7a67,roughness:.83,metalness:.05});
    const posts=new THREE.InstancedMesh(new THREE.CylinderGeometry(.1,.13,1.2,10),gold,64);groups.bridge.add(posts);
    const path=[];
    for(let i=0;i<=48;i++){const u=i/48;path.push(new THREE.Vector3(0,3.1*Math.sin(u*Math.PI)-.8,-u*44+5));}
    const bridgeCurve=new THREE.CatmullRomCurve3(path);
    for(let i=0;i<48;i++){
      const u=(i+.5)/48,p=bridgeCurve.getPoint(u),tangent=bridgeCurve.getTangent(u);
      const slab=mesh(new THREE.BoxGeometry(5.8,.24,.95),stone,groups.bridge,p.x,p.y,p.z);
      slab.rotation.x=Math.atan2(tangent.y,-tangent.z);
    }
    for(const side of [-1,1]){
      const railPoints=path.map(p=>new THREE.Vector3(side*2.85,p.y+1.25,p.z));
      mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(railPoints),100,.065,8,false),gold,groups.bridge);
      for(let i=0;i<32;i++){const p=bridgeCurve.getPoint(i/31);instance(posts,(side+1)*16+i,side*2.85,p.y+.6,p.z,1,1,1);}
    }
    posts.instanceMatrix.needsUpdate=true;
    const drumSurface=texture(1024,512,(c,w,h)=>{
      const g=c.createLinearGradient(0,0,w,0);g.addColorStop(0,'#4e0810');g.addColorStop(.3,'#b52327');g.addColorStop(.48,'#8f111f');g.addColorStop(.7,'#e14336');g.addColorStop(1,'#4e0810');c.fillStyle=g;c.fillRect(0,0,w,h);
      c.strokeStyle='#d7a85d';c.lineWidth=5;for(const y of [44,65,h-44,h-65]){c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();}
      c.lineWidth=2.5;c.strokeStyle='#efca7b';for(let i=0;i<12;i++){const x=i*w/12;c.beginPath();c.moveTo(x,120);c.bezierCurveTo(x+70,160,x-5,220,x+60,250);c.bezierCurveTo(x+95,295,x+10,315,x+28,390);c.stroke();}
    });
    const drumMaterial=new THREE.MeshPhysicalMaterial({map:drumSurface,color:0xffffff,roughness:.27,metalness:.25,clearcoat:.85});
    const skinTexture=texture(512,512,(c,w,h)=>{c.fillStyle='#dbc3a0';c.fillRect(0,0,w,h);const r=seeded(8);for(let i=0;i<30000;i++){c.fillStyle=r()>.5?'#6c4b2733':'#ffffff22';c.fillRect(r()*w,r()*h,1,1);}});
    const skin=new THREE.MeshStandardMaterial({map:skinTexture,color:0xf3debb,roughness:.7});
    const drumGroup=new THREE.Group();groups.drums.add(drumGroup);
    const mallets=[];
    for(let d=0;d<3;d++){
      const base=new THREE.Group();base.position.set(d===0?0:d===1?-5.2:5.2,d===0?.2:.55,-10-d*3.2);base.scale.setScalar(d===0?1:.74);drumGroup.add(base);
      const profile=[new THREE.Vector2(1.67,-1.55),new THREE.Vector2(1.92,-1.25),new THREE.Vector2(2.03,0),new THREE.Vector2(1.92,1.25),new THREE.Vector2(1.67,1.55)];
      mesh(new THREE.LatheGeometry(profile,64),drumMaterial,base);
      mesh(new THREE.CylinderGeometry(1.69,1.69,.07,64),skin,base,0,1.56,0);
      for(const y of [-1.45,1.45]){const ring=mesh(new THREE.TorusGeometry(1.74,.055,8,64),gold,base,0,y,0);ring.rotation.x=Math.PI/2;}
      for(let i=0;i<36;i++){const a=i/36*TAU;mesh(new THREE.SphereGeometry(.048,6,4),gold,base,Math.sin(a)*1.76,1.35,Math.cos(a)*1.76);}
      for(const side of [-1,1]){
        const pivot=new THREE.Group();pivot.position.set(side*.9,3.8,.2);base.add(pivot);
        mesh(new THREE.CylinderGeometry(.047,.062,2.12,10),gold,pivot,0,-1.06,0);
        mesh(new THREE.SphereGeometry(.22,20,12),red,pivot,0,-2.16,0);mallets.push({pivot,phase:d*.8+(side>0?Math.PI:0)});
      }
    }
    // Oblique water rings and drifting petals add real depth over koi motion footage.
    const waterRings=[];
    for(let i=0;i<9;i++){
      const ring=mesh(new THREE.TorusGeometry(1+i*.63,.009,5,120),new THREE.MeshBasicMaterial({color:0xe8c477,transparent:true,opacity:.34}),groups.water,0,-.5,-12);
      ring.rotation.x=-Math.PI/2;waterRings.push(ring);
    }
    const petalShape=new THREE.Shape();petalShape.moveTo(0,0);petalShape.bezierCurveTo(-.28,.2,-.25,.64,0,.8);petalShape.bezierCurveTo(.25,.64,.28,.2,0,0);
    const petalMesh=new THREE.InstancedMesh(new THREE.ShapeGeometry(petalShape),new THREE.MeshStandardMaterial({color:0x9b1725,side:THREE.DoubleSide,roughness:.43,metalness:.12}),70);groups.water.add(petalMesh);
    const petalData=Array.from({length:70},()=>({x:(random()-.5)*30,y:random()*7,z:8-random()*58,phase:random()*TAU,scale:.2+random()*.5}));
    const dustCount=370,dustPositions=new Float32Array(dustCount*3),dustBase=[];
    for(let i=0;i<dustCount;i++)dustBase.push({x:(random()-.5)*46,y:random()*17,z:12-random()*78,p:random()*TAU});
    const dustGeometry=new THREE.BufferGeometry();dustGeometry.setAttribute('position',new THREE.BufferAttribute(dustPositions,3));
    const dustMaterial=new THREE.PointsMaterial({color:0xf5cc81,size:.027,transparent:true,opacity:.5,depthWrite:false,blending:THREE.AdditiveBlending});
    const dust=new THREE.Points(dustGeometry,dustMaterial);dust.frustumCulled=false;scene.add(dust);
    const fireCount=3*92,firePositions=new Float32Array(fireCount*3),fireColors=new Float32Array(fireCount*3),fireData=[];
    for(let i=0;i<fireCount;i++){const a=i%92/92*TAU,r=seeded(i*983+12);fireData.push({burst:Math.floor(i/92),theta:a,velocity:2+r()*3.8,depth:(r()-.5)*1.4,phase:r()});}
    const fireGeometry=new THREE.BufferGeometry();fireGeometry.setAttribute('position',new THREE.BufferAttribute(firePositions,3));fireGeometry.setAttribute('color',new THREE.BufferAttribute(fireColors,3));
    const fireworks=new THREE.Points(fireGeometry,new THREE.PointsMaterial({vertexColors:true,size:.055,transparent:true,opacity:.9,depthWrite:false,blending:THREE.AdditiveBlending}));fireworks.frustumCulled=false;scene.add(fireworks);
    const streakPositions=new Float32Array(fireCount*6),streakColors=new Float32Array(fireCount*6);
    const streakGeometry=new THREE.BufferGeometry();streakGeometry.setAttribute('position',new THREE.BufferAttribute(streakPositions,3));streakGeometry.setAttribute('color',new THREE.BufferAttribute(streakColors,3));
    const streaks=new THREE.LineSegments(streakGeometry,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.7,depthWrite:false,blending:THREE.AdditiveBlending}));streaks.frustumCulled=false;scene.add(streaks);
    function updateFireworks(t, enabled){
      fireworks.visible=streaks.visible=enabled;if(!enabled)return;
      const centers=[[-11,8,-31],[10,10,-37],[0,12,-44]];
      for(let i=0;i<fireCount;i++){
        const a=fireData[i],age=fract((t-a.burst*1.9)/6.4)*6.4,live=age<3.1,fade=live?Math.pow(1-age/3.1,1.6):0;
        const center=centers[a.burst],vx=Math.cos(a.theta)*a.velocity,vy=Math.sin(a.theta)*a.velocity;
        const previous=Math.max(0,age-.08),x=center[0]+vx*age,y=center[1]+vy*age-.75*age*age,z=center[2]+a.depth*age;
        firePositions.set([x,y,z],i*3);fireColors.set([fade,fade*.73,fade*.32],i*3);
        streakPositions.set([center[0]+vx*previous,center[1]+vy*previous-.75*previous*previous,center[2]+a.depth*previous,x,y,z],i*6);
        streakColors.set([fade*.3,fade*.19,fade*.07,fade,fade*.74,fade*.34],i*6);
      }
      for(const a of [fireGeometry.attributes.position,fireGeometry.attributes.color,streakGeometry.attributes.position,streakGeometry.attributes.color])a.needsUpdate=true;
    }
    function updateAtmosphere(t){
      for(let i=0;i<dustCount;i++){const a=dustBase[i];dustPositions.set([a.x+Math.sin(t*.22+a.p)*.5,a.y+Math.sin(t*.31+a.p)*.38,a.z],i*3);}dustGeometry.attributes.position.needsUpdate=true;
      for(let i=0;i<petalData.length;i++){
        const a=petalData[i];dummy.position.set(a.x+Math.sin(t*.25+a.phase)*.6,a.y+Math.sin(t*.4+a.phase)*.3,a.z);
        dummy.rotation.set(Math.sin(a.phase+t*.3)*.8,t*.22+a.phase,a.phase);dummy.scale.setScalar(a.scale);dummy.updateMatrix();petalMesh.setMatrixAt(i,dummy.matrix);
      }petalMesh.instanceMatrix.needsUpdate=true;
    }
    const transients=(window.FILM_DATA?.audioMap?.events||[]).filter(e=>/kick|snare|perc/.test(e.drum||'')).map(e=>e.t);
    const drumTimes=transients.length?transients:(window.FILM_DATA?.audioMap?.onsets_sec||[]);
    function malletStroke(t,hand){
      if(!drumTimes.length)return Math.abs(Math.sin(t*TAU*2.14+hand));
      let lo=0,hi=drumTimes.length-1,last=-1;
      while(lo<=hi){const m=(lo+hi)>>1;if(drumTimes[m]<=t){last=m;lo=m+1;}else hi=m-1;}
      const previous=last>=0?drumTimes[last]:-1,next=drumTimes[last+1]??t+2;
      const lift=previous<0?1:1-Math.exp(-(t-previous)*18);
      const approach=clamp((next-t)/.11);
      return clamp(Math.min(lift,approach)+Math.sin(hand)*.035);
    }
    const target=new THREE.Vector3();
    function renderAt(t, shot={}){
      const start=Number(shot.start||0),end=Number(shot.end||185),p=clamp((t-start)/Math.max(.1,end-start)),q=ease(p),seed=Number(shot.seed||1811);
      const world=shot.world||({avenue:'lanterns',dragon:'dragon',ribbon:'ribbons',sunrise:'finale',drums:'drums',koi:'water',bridge:'bridge'}[shot.asset]||'lanterns');
      const active=shot.world3d!==false;
      if(!active){renderer.setViewport(0,0,W,H);renderer.setScissorTest(false);renderer.clear();return;}
      for(const g of Object.values(groups))g.visible=false;
      const lanternShot=world==='lanterns'||world==='finale'||world==='fireworks';
      hemisphere.intensity=lanternShot?.46:1.65;key.intensity=lanternShot?1.15:4.5;rim.intensity=lanternShot?1.55:3.2;cool.intensity=lanternShot?.22:1.1;
      renderer.toneMappingExposure=lanternShot?.91:1.05;
      scene.fog=lanternShot?lanternFog:null;warm.intensity=lanternShot?5:42;
      dustMaterial.opacity=lanternShot?.18:.5;dustMaterial.size=lanternShot?.018:.027;
      const side=seed%2?1:-1,angle=seed*.013;
      camera.fov=world==='drums'?43:world==='portal'?51:45;
      camera.up.set(0,1,0);
      if(world==='lanterns'||world==='finale'||world==='fireworks'){
        groups.lanterns.visible=true;
        camera.position.set(side*(1.8*Math.sin(q*Math.PI)-.7),3.2+q*(world==='finale'?4.4:1.4),mix(10,-9,q));
        target.set(Math.sin(angle)*1.6,world==='finale'?6.5:4.6,-27);
        updateLanterns(t,world==='finale');
      }else if(world==='ribbons'||world==='silk'){
        groups.ribbons.visible=true;updateRibbons(t,seed);
        const az=side*(q*.9-.45)+.15*Math.sin(angle),r=mix(16,11,q);
        camera.position.set(Math.sin(az)*r,mix(3,7,q),-14+Math.cos(az)*r);target.set(0,4.8,-14);
      }else if(world==='dragon'){
        groups.dragon.visible=true;updateDragon(t);
        const az=side*(q*.65-.3),r=mix(26,18,q);
        camera.position.set(Math.sin(az)*r+3,mix(3.6,7.8,q),-18+Math.cos(az)*r);target.set(0,4.8,-17);
      }else if(world==='portal'||world==='runway'){
        groups.portal.visible=true;
        camera.position.set(side*(1.3-2.5*q),mix(1.4,4,q),mix(11,-7,q));target.set(0,4,-29);
        sculpture.rotation.set(t*.12,t*.24,t*.07);
        for(const ring of sculpture.children){const k=ring.userData.index;ring.rotation.set(k*.4+t*.2,k*.71-t*.15,k*.31+t*.14);}
      }else if(world==='bridge'){
        groups.bridge.visible=true;groups.lanterns.visible=true;updateLanterns(t,false);
        camera.position.set(side*mix(5,2.2,q),mix(2,7.5,q),mix(10,-11,q));target.set(0,3.3,-27);
      }else if(world==='drums'){
        groups.drums.visible=true;
        camera.position.set(side*mix(5.6,-2.4,q),mix(3.6,4.5,q),mix(1,-3,q));target.set(0,.8,-11);
        for(const a of mallets){const strike=malletStroke(t+a.phase*.035,a.phase);a.pivot.rotation.x=.02+strike*.72;a.pivot.rotation.z=Math.sin(t*2.4+a.phase)*.12;}
      }else{
        groups.water.visible=true;
        camera.position.set(side*mix(5,-2,q),mix(8,5,q),mix(5,-2,q));target.set(0,0,-13);
        for(let i=0;i<waterRings.length;i++){const a=waterRings[i],s=1+fract(t*.14+i*.105)*.7;a.scale.setScalar(s);a.material.opacity=.24*(1-fract(t*.14+i*.105));}
      }
      if(/rush|dive|impact/.test(shot.motion||''))camera.up.set(Math.sin(side*.045*Math.sin(p*Math.PI)),1,0);
      camera.lookAt(target);camera.updateProjectionMatrix();
      updateAtmosphere(t);updateFireworks(t,world==='finale'||world==='fireworks'||shot.mode==='fireworks'||/final|chorus/.test(shot.section||''));
      warm.position.set(Math.sin(t*.22)*4,4.5,-13+Math.cos(t*.17)*3);
      renderer.setViewport(0,0,W,H);renderer.setScissorTest(false);renderer.clear();
      renderer.setViewport(0,TOP,W,PH);renderer.setScissor(0,TOP,W,PH);renderer.setScissorTest(true);
      renderer.render(scene,camera);renderer.setScissorTest(false);
      window.__bosstonWorld3DTime=t;
    }
    window.renderBosstonWorld3DAt=renderAt;
    window.__bosstonWorld3D={threeRevision:THREE.REVISION,renderer,scene,camera,groups,contract:'absolute soundtrack time, physical depth geometry, no text/audio'};
    updateLanterns(0);updateRibbons(0,1811);updateDragon(0);updateAtmosphere(0);updateFireworks(0,true);
    renderer.compile(scene,camera);renderAt(0,{asset:'avenue',start:0,end:4,seed:1811});
    await document.fonts.ready;
    return window.__bosstonWorld3D;
  });
  window.buildBosstonWorld3D=ready;
  window.__hf.buildReady.bosston3d=ready;
})();
