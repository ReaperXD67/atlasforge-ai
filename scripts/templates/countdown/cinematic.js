import * as THREE from "./assets/vendor/three.module.js";
import {
  makeCountdownState,
  ease,
} from "./assets/vendor/countdown_story_state.mjs";

const plan = window.PROCEDURAL_PLAN;
const direction = window.PROCEDURAL_DIRECTION;
const recipe = window.PROCEDURAL_WORLD;
const stateAt = makeCountdownState(plan, direction);
await document.fonts.ready;
const renderer = new THREE.WebGLRenderer({
  canvas: document.getElementById("machine-canvas"),
  antialias: true,
  preserveDrawingBuffer: true,
});
renderer.setSize(1080, 1920);
renderer.setPixelRatio(1);
renderer.setClearColor(recipe.palette.background);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = recipe.lighting.exposure;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
scene.fog = new THREE.Fog(recipe.palette.background, 17, 35);
const camera = new THREE.PerspectiveCamera(38, 1080 / 1920, 0.06, 50);
scene.add(new THREE.HemisphereLight(0xffefd5, 0x40554e, 1.55));
const key = new THREE.DirectionalLight(0xffe1b4, 3.7);
key.position.set(-4.5, 6, -0.2);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
Object.assign(key.shadow.camera, {
  left: -6,
  right: 6,
  top: 6,
  bottom: -6,
  near: 0.1,
  far: 20,
});
key.shadow.bias = -0.0003;
key.shadow.normalBias = 0.012;
scene.add(key);
const fill = new THREE.DirectionalLight(0xd5e2dd, 1.7);
fill.position.set(4, 4, 5);
scene.add(fill);
const material = Object.fromEntries(
  Object.entries(recipe.palette).map(([name, color]) => [
    name,
    new THREE.MeshStandardMaterial({
      color,
      roughness: name === "steel" ? 0.48 : 0.6,
      metalness: name === "brass" ? 0.55 : name === "steel" ? 0.4 : 0.05,
    }),
  ]),
);
function mesh(geometry, mat, parent = scene) {
  const m = new THREE.Mesh(geometry, mat);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}
function box(w, h, d, mat, parent) {
  return mesh(new THREE.BoxGeometry(w, h, d), mat, parent);
}
function cylinder(radius, height, mat, parent) {
  return mesh(
    new THREE.CylinderGeometry(radius, radius, height, 48),
    mat,
    parent,
  );
}
function line(points, radius, mat, parent) {
  return mesh(
    new THREE.TubeGeometry(
      new THREE.CatmullRomCurve3(points),
      80,
      radius,
      8,
      false,
    ),
    mat,
    parent,
  );
}
function textMaterial(text, background, foreground, fontSize = 210) {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 1024;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, 1024, 1024);
  ctx.fillStyle = foreground;
  ctx.font = "800 " + fontSize + "px Montserrat";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 512, 530);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: texture, roughness: 0.7 });
}

// A shallow theatrical machine. Its thin construction becomes the story's reveal.
const floor = box(18, 0.22, 16, material.floor);
floor.position.y = -0.15;
const tower = new THREE.Group();
tower.position.z = -0.25;
scene.add(tower);
const footing = box(3.65, 0.12, 0.85, material.ink, tower);
footing.position.set(0, 0.03, -0.2);
const topRail = box(3.34, 0.11, 0.13, material.brass, tower);
topRail.position.set(0, 3.18, -0.18);
for (const x of [-1.58, 1.58]) {
  box(0.07, 3.13, 0.08, material.steel, tower).position.set(x, 1.61, -0.18);
  const brace = box(0.045, 2.9, 0.045, material.brass, tower);
  brace.position.set(x, 1.36, -0.67);
  brace.rotation.x = -0.27;
  cylinder(0.08, 0.04, material.brass, tower).position.set(x, 0.12, -0.65);
}
const SEGMENTS = [
  "abcedf",
  "bc",
  "abged",
  "abgcd",
  "fgbc",
  "afgcd",
  "afgecd",
  "abc",
  "abcdefg",
  "abfgcd",
].map((s) => new Set(s));
// Names are conventional: a top, b upper-right, c lower-right, d bottom,
// e lower-left, f upper-left, g middle. The seven beams have actual thickness.
SEGMENTS[0] = new Set("abcdef");
const segmentPositions = {
  a: [0, 1.02, false],
  b: [0.49, 0.51, true],
  c: [0.49, -0.51, true],
  d: [0, -1.02, false],
  e: [-0.49, -0.51, true],
  f: [-0.49, 0.51, true],
  g: [0, 0, false],
};
const digits = [];
for (let index = 0; index < 2; index++) {
  const group = new THREE.Group();
  group.position.set((index - 0.5) * 1.48, 1.75, 0);
  tower.add(group);
  const plate = box(1.32, 2.5, 0.055, material.ink, group);
  plate.position.z = -0.09;
  // Backside cross-braces stay visibly much thinner than the looming face.
  for (const y of [-1.05, 1.05])
    box(1.3, 0.035, 0.035, material.brass, group).position.set(0, y, -0.14);
  const beams = {};
  for (const [name, [x, y, vertical]] of Object.entries(segmentPositions)) {
    const hinge = new THREE.Group();
    hinge.position.set(x, y, 0.02);
    group.add(hinge);
    const beam = box(
      vertical ? 0.15 : 0.86,
      vertical ? 0.86 : 0.15,
      recipe.geometry.segment_depth,
      [
        material.steel,
        material.steel,
        material.steel,
        material.steel,
        material.coral,
        material.ink,
      ],
      hinge,
    );
    beams[name] = { hinge, vertical, beam };
    for (const sign of [-1, 1]) {
      const axle = mesh(
        new THREE.SphereGeometry(0.026, 8, 6),
        material.brass,
        group,
      );
      axle.position.set(
        x + (vertical ? 0 : sign * 0.46),
        y + (vertical ? sign * 0.46 : 0),
        0.02,
      );
    }
  }
  digits.push(beams);
}
// Recessed approach rails and an understated independent side route.
for (const x of [-0.37, 0.37])
  line(
    [new THREE.Vector3(x, 0, 2.65), new THREE.Vector3(x, 0, 0.3)],
    0.018,
    material.brass,
  );
for (let i = 0; i < 6; i++) {
  const tie = box(0.68, 0.015, 0.025, material.steel);
  tie.position.set(0, -0.015, 0.45 + i * 0.36);
}
const sideMaterial = new THREE.MeshStandardMaterial({
  color: recipe.palette.token,
  roughness: 0.8,
  transparent: true,
  opacity: 0.3,
});
const sidePoints = Array.from({ length: 50 }, (_, i) => {
  const p = i / 49;
  return new THREE.Vector3(2.28 * p, 0, 1.07 + Math.sin(p * Math.PI) * 0.37);
});
line(sidePoints, 0.024, sideMaterial);
const endRing = mesh(
  new THREE.TorusGeometry(0.42, 0.015, 8, 60),
  material.brass,
);
endRing.rotation.x = Math.PI / 2;
endRing.position.set(2.28, 0.01, 1.07);
const token = new THREE.Group();
scene.add(token);
cylinder(
  recipe.geometry.token_radius + 0.025,
  0.1,
  material.brass,
  token,
).position.y = -0.025;
cylinder(recipe.geometry.token_radius, 0.14, material.token, token);
const face = mesh(
  new THREE.CircleGeometry(recipe.geometry.token_radius - 0.025, 48),
  textMaterial("WHY?", recipe.palette.cream, recipe.palette.ink, 245),
  token,
);
face.rotation.x = -Math.PI / 2;
face.position.y = 0.072;
// A restrained ticking pointer makes the clock's continued movement unambiguous.
const pendulum = new THREE.Group();
pendulum.position.set(0, 1.0, -0.62);
tower.add(pendulum);
box(0.035, 0.68, 0.035, material.brass, pendulum).position.y = -0.34;
mesh(
  new THREE.SphereGeometry(0.1, 20, 12),
  material.coral,
  pendulum,
).position.y = -0.74;

const heading = document.getElementById("heading");
const disclosure = document.getElementById("disclosure");
const context = document.getElementById("end-context");
const captions = plan.captions.map((cue) => ({
  cue,
  node: document.getElementById(cue.id),
}));
let lastTitle = "";
function paint(frame) {
  const s = stateAt(frame);
  document.getElementById("root").dataset.mode = s.mode;
  const numbers = [Math.floor(s.countdown / 10), s.countdown % 10];
  const previous = Math.min(10, s.countdown + 1);
  const previousNumbers = [Math.floor(previous / 10), previous % 10];
  for (let index = 0; index < 2; index++)
    for (const [name, beam] of Object.entries(digits[index])) {
      const currentOn = SEGMENTS[numbers[index]].has(name);
      const previousOn = SEGMENTS[previousNumbers[index]].has(name);
      const p =
        s.ticks === 0 || s.countdown === 0 ? 1 : ease(s.tick_phase / 0.22);
      const angle =
        ((previousOn ? 0 : 1) +
          ((currentOn ? 0 : 1) - (previousOn ? 0 : 1)) * p) *
          Math.PI +
        (index === 1 && name === "a" ? -0.55 * (1 - ease(s.frame / 10)) : 0);
      beam.hinge.rotation.set(
        beam.vertical ? 0 : angle,
        beam.vertical ? angle : 0,
        0,
      );
    }
  token.position.set(...s.token);
  token.rotation.y = -s.exit * 0.16;
  sideMaterial.opacity = 0.28 + 0.72 * s.exit;
  pendulum.rotation.z =
    s.countdown > 0 ? Math.sin((s.frame / 30) * Math.PI * 2) * 0.2 : 0;
  key.position.x = -4.5 + s.shadow_pressure * 1.25;
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
  if (lastTitle !== title) {
    heading.innerHTML = title;
    lastTitle = title;
  }
  disclosure.style.visibility = s.disclosure ? "visible" : "hidden";
  context.style.visibility = s.end_context ? "visible" : "hidden";
  for (const { cue, node } of captions) {
    const visible =
      !s.hide_captions && s.frame >= cue.start_frame && s.frame < cue.end_frame;
    node.style.visibility = visible ? "visible" : "hidden";
    if (visible)
      for (const word of cue.words)
        node
          .querySelector('[data-word="' + word.index + '"]')
          .classList.toggle(
            "active",
            s.frame >= word.start_frame && s.frame < word.end_frame,
          );
  }
  renderer.render(scene, camera);
  return {
    frame: s.frame,
    shot: s.shot_id,
    countdown: s.countdown,
    token: s.token,
    triangles: renderer.info.render.triangles,
    draw_calls: renderer.info.render.calls,
  };
}
window.renderProceduralFrame = paint;
const clock = { frame: 0 };
const timeline = gsap.timeline({ paused: true });
timeline.to(
  clock,
  {
    frame: plan.duration_frames,
    duration: plan.duration_seconds,
    ease: "none",
    onUpdate: () => paint(clock.frame),
  },
  0,
);
window.__timelines = { main: timeline };
window.addEventListener("hf-seek", (event) => paint(event.detail.time * 30));
paint(0);
window.proceduralReady = true;
