import * as THREE from "./assets/vendor/three.module.js";
import {
  makeStoryState,
  ease,
} from "./assets/vendor/procedural_story_state.mjs";

const plan = window.PROCEDURAL_PLAN,
  direction = window.PROCEDURAL_DIRECTION,
  recipe = window.PROCEDURAL_WORLD;
const stateAt = makeStoryState(plan, direction),
  palette = recipe.palette,
  g = recipe.geometry,
  light = recipe.lighting;
await document.fonts.ready;
const canvas = document.getElementById("machine-canvas");
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: false,
  preserveDrawingBuffer: true,
});
renderer.setSize(plan.width, plan.height);
renderer.setPixelRatio(1);
renderer.setClearColor(palette.background);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = light.exposure;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(palette.background, 16, 30);
const camera = new THREE.PerspectiveCamera(
  35,
  plan.width / plan.height,
  0.08,
  45,
);
scene.add(new THREE.HemisphereLight(0xd1e0e6, 0x0a131d, 1.1));
const key = new THREE.DirectionalLight(light.key_color, light.key_intensity);
key.position.set(...light.key_position);
key.castShadow = true;
key.shadow.mapSize.set(light.shadow_map_size, light.shadow_map_size);
Object.assign(key.shadow.camera, {
  left: -5,
  right: 5,
  top: 5,
  bottom: -5,
  near: 0.1,
  far: 18,
});
key.shadow.bias = -0.0005;
key.shadow.normalBias = 0.015;
scene.add(key);
const rim = new THREE.DirectionalLight(light.rim_color, light.rim_intensity);
rim.position.set(4, 4, -5);
scene.add(rim);
const materials = {};
for (const [name, color] of Object.entries(palette))
  materials[name] = new THREE.MeshStandardMaterial({
    color,
    roughness: name === "steel" ? 0.4 : 0.55,
    metalness: name === "steel" ? 0.55 : 0.07,
  });
const world = new THREE.Group();
world.position.y = -0.15;
scene.add(world);
const mechanism = new THREE.Group();
world.add(mechanism);
function add(geometry, material, parent = mechanism) {
  const obj = new THREE.Mesh(geometry, material);
  obj.castShadow = true;
  obj.receiveShadow = true;
  parent.add(obj);
  return obj;
}
function box(w, h, d, material, parent = mechanism) {
  return add(new THREE.BoxGeometry(w, h, d), material, parent);
}
function shape(w, h, r) {
  const s = new THREE.Shape();
  s.moveTo(-w / 2 + r, -h / 2);
  s.lineTo(w / 2 - r, -h / 2);
  s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
  s.lineTo(w / 2, h / 2 - r);
  s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
  s.lineTo(-w / 2 + r, h / 2);
  s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
  s.lineTo(-w / 2, -h / 2 + r);
  s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
  return s;
}
function bevel(w, h, d, r = 0.06) {
  const geo = new THREE.ExtrudeGeometry(shape(w, h, r), {
    depth: d,
    bevelEnabled: true,
    bevelSize: 0.025,
    bevelThickness: 0.025,
    bevelSegments: 3,
    steps: 1,
    curveSegments: 4,
  });
  geo.translate(0, 0, -d / 2);
  return geo;
}
function texture(text, background, foreground, size = 145) {
  const c = document.createElement("canvas");
  c.width = 1024;
  c.height = 1024;
  const x = c.getContext("2d");
  x.fillStyle = background;
  x.fillRect(0, 0, 1024, 1024);
  x.fillStyle = foreground;
  x.textAlign = "center";
  x.textBaseline = "middle";
  x.font = `800 ${size}px Montserrat,Arial`;
  x.fillText(text, 512, 526);
  const map = new THREE.CanvasTexture(c);
  map.colorSpace = THREE.SRGBColorSpace;
  map.anisotropy = 4;
  return new THREE.MeshStandardMaterial({
    map,
    roughness: 0.56,
    metalness: 0.03,
  });
}
function button(label, color, radius = g.button_radius) {
  const group = new THREE.Group();
  const ring = add(
    new THREE.CylinderGeometry(radius + 0.1, radius + 0.15, 0.19, 64),
    materials.steel,
    group,
  );
  ring.position.y = 0.11;
  const cap = add(
    new THREE.CylinderGeometry(radius, radius, g.button_depth, 64),
    materials[color],
    group,
  );
  cap.position.y = 0.34;
  const face = add(
    new THREE.CircleGeometry(radius - 0.04, 64),
    texture(
      label,
      palette[color],
      palette.background,
      label === "NOT NOW" ? 150 : 260,
    ),
    cap,
  );
  face.rotation.x = -Math.PI / 2;
  face.position.y = g.button_depth / 2 + 0.002;
  group.userData.cap = cap;
  return group;
}
const platform = add(
  new THREE.BoxGeometry(g.platform_width, 0.18, g.platform_depth),
  materials.platform,
  world,
);
platform.position.y = -0.12;
for (const x of [-3.35, 3.35])
  for (const z of [-1.85, 1.85]) {
    const screw = add(
      new THREE.CylinderGeometry(0.055, 0.055, 0.02, 12),
      materials.steel,
      world,
    );
    screw.position.set(x, -0.019, z);
  }
const yes = button("YES", "coral");
yes.position.set(-2, 0, 0.65);
world.add(yes);
const notNow = button("NOT NOW", "cream");
notNow.position.set(0.86, 0, 0.65);
world.add(notNow);
const dominoes = [];
const dominoGeometry = bevel(g.domino_width, g.domino_height, 0.11, 0.045);
dominoGeometry.translate(0, g.domino_height / 2, 0);
for (let i = 0; i < g.domino_count; i++) {
  const pivot = new THREE.Group();
  pivot.position.set(-1.35 + i * 0.27, 0.01, -0.47 + Math.sin(i * 0.27) * 0.14);
  mechanism.add(pivot);
  add(dominoGeometry, i > 7 ? materials.coral : materials.cream, pivot);
  dominoes.push(pivot);
}
const railPoints = Array.from(
  { length: 42 },
  (_, i) =>
    new THREE.Vector3(
      -2.5 + i * 0.125,
      0.02,
      -0.85 + Math.sin(i * 0.08) * 0.23,
    ),
);
const rail = new THREE.CatmullRomCurve3(railPoints);
add(new THREE.TubeGeometry(rail, 64, 0.021, 6), materials.accent);
const ball = add(new THREE.SphereGeometry(0.085, 18, 12), materials.coral);
const coinGroup = new THREE.Group();
coinGroup.position.set(-2.12, 0, -1.16);
mechanism.add(coinGroup);
const coinMaterial = texture("₹", palette.accent, palette.background, 390),
  coins = [];
for (let i = 0; i < g.coin_count; i++) {
  const coin = new THREE.Group();
  add(
    new THREE.CylinderGeometry(0.24, 0.24, 0.055, 40),
    materials.accent,
    coin,
  );
  const stamp = add(new THREE.CircleGeometry(0.21, 40), coinMaterial, coin);
  stamp.rotation.x = -Math.PI / 2;
  stamp.position.y = 0.029;
  coinGroup.add(coin);
  coins.push(coin);
}
const coinTray = box(1.2, 0.05, 0.9, materials.steel, coinGroup);
coinTray.position.y = 0.02;
const dial = new THREE.Group();
dial.position.set(1.72, 0.12, 0.72);
mechanism.add(dial);
add(new THREE.CylinderGeometry(0.68, 0.72, 0.18, 64), materials.steel, dial);
add(new THREE.CylinderGeometry(0.6, 0.6, 0.195, 64), materials.cream, dial);
for (let i = 0; i < 48; i++) {
  const a = (i * Math.PI) / 24;
  const mark = box(
    i % 4 === 0 ? 0.025 : 0.012,
    0.012,
    i % 4 === 0 ? 0.1 : 0.045,
    materials.platform,
    dial,
  );
  mark.position.set(Math.sin(a) * 0.5, 0.104, Math.cos(a) * 0.5);
  mark.rotation.y = a;
}
const minute = new THREE.Group(),
  hour = new THREE.Group();
dial.add(minute, hour);
box(0.035, 0.035, 0.43, materials.coral, minute).position.set(0, 0.13, -0.16);
box(0.045, 0.032, 0.3, materials.platform, hour).position.set(0, 0.12, -0.1);
add(new THREE.SphereGeometry(0.06, 12, 8), materials.steel, dial).position.y =
  0.14;
const bin = new THREE.Group();
bin.position.set(2.25, 0, -1.08);
mechanism.add(bin);
box(1.25, 0.06, 1.1, materials.steel, bin).position.y = 0.03;
for (const x of [-0.61, 0.61])
  box(0.045, 0.42, 1.1, materials.steel, bin).position.set(x, 0.23, 0);
for (const z of [-0.53, 0.53])
  box(1.25, 0.42, 0.045, materials.steel, bin).position.set(0, 0.23, z);
const packages = [];
for (let i = 0; i < g.package_count; i++) {
  const item = new THREE.Group();
  if (i % 3 === 0) {
    add(
      new THREE.CylinderGeometry(0.11, 0.12, 0.38, 24),
      materials.cream,
      item,
    ).position.y = 0.19;
    add(
      new THREE.CylinderGeometry(0.075, 0.075, 0.08, 18),
      materials.coral,
      item,
    ).position.y = 0.42;
  } else {
    box(
      0.26,
      0.35,
      0.22,
      i % 2 ? materials.cream : materials.coral,
      item,
    ).position.y = 0.18;
    box(0.28, 0.018, 0.045, materials.accent, item).position.y = 0.36;
  }
  bin.add(item);
  packages.push(item);
}
const brake = new THREE.Group();
brake.position.set(0, 0.05, 1.28);
mechanism.add(brake);
box(0.9, 0.12, 0.54, materials.steel, brake).position.y = 0.07;
const brakePivot = new THREE.Group();
brake.add(brakePivot);
const lever = box(0.085, 0.65, 0.08, materials.platform, brakePivot);
lever.position.y = 0.34;
const grip = add(
  new THREE.CylinderGeometry(0.105, 0.105, 0.5, 24),
  materials.coral,
  brakePivot,
);
grip.rotation.z = Math.PI / 2;
grip.position.y = 0.68;
const gates = [];
for (let i = 0; i < g.gate_count; i++) {
  const gate = new THREE.Group();
  gate.position.set(-1.5 + i * 1.5, 0, 1.37);
  world.add(gate);
  box(0.16, 0.82, 0.2, materials.steel, gate).position.set(-0.52, 0.4, 0);
  const hinge = new THREE.Group();
  hinge.position.set(-0.52, 0.82, 0);
  gate.add(hinge);
  box(1.05, 0.095, 0.095, materials.coral, hinge).position.x = 0.5;
  const plate = add(
    new THREE.PlaneGeometry(0.6, 0.6),
    texture(["COST", "USE", "FIT"][i], palette.platform, palette.cream, 200),
    gate,
  );
  plate.rotation.x = -Math.PI / 2;
  plate.position.set(0.1, 0.015, 0.25);
  gates.push({ gate, hinge });
}
const headings = document.getElementById("heading"),
  disclosure = document.getElementById("disclosure"),
  context = document.getElementById("end-context");
const captions = plan.captions.map((c) => ({
  c,
  node: document.getElementById(c.id),
}));
let lastHeading = null;
window.renderProceduralFrame = (frame) => {
  const s = stateAt(frame),
    count = dominoes.length;
  yes.position.x = -2 + s.choice * 1.16;
  yes.userData.cap.position.y = 0.34 - s.press * 0.14;
  notNow.visible = s.choice > 0;
  notNow.scale.setScalar(Math.max(0.001, s.choice));
  notNow.userData.cap.position.y = 0.34 - s.not_now_press * 0.13;
  mechanism.position.y = -2.2 * s.choice;
  mechanism.visible = s.choice < 1;
  for (let i = 0; i < count; i++)
    dominoes[i].rotation.z = -1.15 * ease(s.chain * count - i);
  ball.position.copy(rail.getPoint(Math.min(1, s.chain)));
  ball.position.y = 0.12;
  for (let i = 0; i < coins.length; i++) {
    const p = ease(s.money * coins.length - i);
    coins[i].visible = p > 0;
    coins[i].position.set(
      ((i % 3) - 1) * 0.3,
      0.09 + Math.floor(i / 3) * 0.062 + (1 - p) * 0.9,
      ((i % 2) - 0.5) * 0.24,
    );
    coins[i].rotation.y = i * 0.61;
  }
  minute.rotation.y = -s.clock * 4.8;
  hour.rotation.y = -s.clock * 0.8;
  for (let i = 0; i < packages.length; i++) {
    const p = ease(s.packages * packages.length - i);
    const item = packages[i];
    item.visible = p > 0;
    item.position.set(
      ((i % 3) - 1) * 0.27,
      0.07 + Math.floor(i / 3) * 0.2 + (1 - p) * 1.15,
      ((Math.floor(i / 3) % 2) - 0.5) * 0.3,
    );
    item.rotation.set(
      ((i % 2) - 0.5) * 0.35 * p,
      i * 0.83,
      ((i % 3) - 1) * 0.15 * p,
    );
  }
  brakePivot.rotation.x = -0.72 + s.brake * 1.25;
  for (let i = 0; i < gates.length; i++) {
    const { gate, hinge } = gates[i];
    gate.visible = s.gates[i].rise > 0 && s.choice < 0.98;
    gate.position.y = -1.2 * (1 - s.gates[i].rise) - s.choice;
    hinge.rotation.z = s.gates[i].open * Math.PI * 0.49;
  }
  camera.position.set(...s.camera);
  camera.lookAt(...s.look_at);
  const title = s.heading
    .split("|")
    .map((part) =>
      part.replace(
        /[&<>]/g,
        (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[ch],
      ),
    )
    .join("<br>");
  if (lastHeading !== title) {
    headings.innerHTML = title;
    lastHeading = title;
  }
  headings.classList.toggle("choice", s.mode === "choice");
  disclosure.style.visibility = s.disclosure ? "visible" : "hidden";
  context.style.visibility = s.end_context ? "visible" : "hidden";
  for (const { c, node } of captions) {
    const show =
      !s.hide_captions && s.frame >= c.start_frame && s.frame < c.end_frame;
    node.style.visibility = show ? "visible" : "hidden";
    if (show)
      for (const w of c.words)
        node
          .querySelector('[data-word="' + w.index + '"]')
          .classList.toggle(
            "active",
            s.frame >= w.start_frame && s.frame < w.end_frame,
          );
  }
  renderer.render(scene, camera);
  document.documentElement.dataset.frame = String(s.frame);
  return {
    frame: s.frame,
    shot: s.shot_id,
    mode: s.mode,
    triangles: renderer.info.render.triangles,
    draw_calls: renderer.info.render.calls,
  };
};
const clock = { frame: 0 },
  timeline = gsap.timeline({ paused: true });
timeline.to(
  clock,
  {
    frame: plan.duration_frames,
    duration: plan.duration_frames / 30,
    ease: "none",
    onUpdate: () => window.renderProceduralFrame(clock.frame),
  },
  0,
);
window.__timelines = { main: timeline };
window.addEventListener("hf-seek", (event) =>
  window.renderProceduralFrame(event.detail.time * 30),
);
window.renderProceduralFrame(0);
window.proceduralReady = true;
