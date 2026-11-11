import * as THREE from "./assets/vendor/three.module.js";
import {
  makeQuestionState,
  ribbonSection,
} from "./assets/vendor/question_story_state.mjs";

const plan = window.PROCEDURAL_PLAN,
  direction = window.PROCEDURAL_DIRECTION,
  recipe = window.PROCEDURAL_WORLD;
const stateAt = makeQuestionState(plan, direction);
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
const scene = new THREE.Scene(),
  camera = new THREE.PerspectiveCamera(38, 1080 / 1920, 0.06, 50);
scene.add(new THREE.HemisphereLight(0xfff4df, 0x6c617e, 1.8));
const key = new THREE.DirectionalLight(0xffdfb7, 3.5);
key.position.set(-4, 7, 4);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
Object.assign(key.shadow.camera, {
  left: -7,
  right: 7,
  top: 7,
  bottom: -7,
  near: 0.1,
  far: 22,
});
key.shadow.bias = -0.0003;
key.shadow.normalBias = 0.014;
scene.add(key);
const fill = new THREE.DirectionalLight(0xe2d8ff, 1.4);
fill.position.set(4, 4, -4);
scene.add(fill);
const mat = Object.fromEntries(
  Object.entries(recipe.palette).map(([n, c]) => [
    n,
    new THREE.MeshStandardMaterial({
      color: c,
      roughness: n === "gold" ? 0.42 : 0.64,
      metalness: n === "gold" ? 0.3 : 0,
      side: THREE.DoubleSide,
    }),
  ]),
);
function mesh(g, m, parent = scene) {
  const o = new THREE.Mesh(g, m);
  o.castShadow = true;
  o.receiveShadow = true;
  parent.add(o);
  return o;
}
const floor = mesh(new THREE.BoxGeometry(20, 0.18, 16), mat.floor);
floor.position.y = -0.24;
const endpoints = [];
for (const [x, color] of [
  [-2.75, "blush"],
  [2.75, "endpoint"],
]) {
  const group = new THREE.Group();
  group.position.x = x;
  scene.add(group);
  const base = mesh(
    new THREE.CylinderGeometry(0.72, 0.8, 0.45, 64),
    mat.porcelain,
    group,
  );
  base.position.y = 0.05;
  const ring = mesh(
    new THREE.TorusGeometry(0.54, 0.07, 12, 64),
    mat[color],
    group,
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.31;
  const orb = mesh(new THREE.SphereGeometry(0.27, 32, 20), mat[color], group);
  orb.position.set(0, 0.48, 0);
  endpoints.push(group);
}
function letterMaterial() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = recipe.palette.porcelain;
  ctx.fillRect(0, 0, 512, 512);
  ctx.fillStyle = recipe.palette.ink;
  ctx.font = "800 360px Montserrat";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("?", 256, 280);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: texture, roughness: 0.6 });
}
const core = new THREE.Group();
scene.add(core);
mesh(new THREE.SphereGeometry(0.42, 48, 32), mat.porcelain, core);
const question = mesh(
  new THREE.CircleGeometry(0.32, 48),
  letterMaterial(),
  core,
);
question.position.z = 0.435;
const ribs = [];
const count = recipe.geometry.segments;
for (let v = 0; v < 3; v++) {
  const geometry = new THREE.BufferGeometry(),
    positions = new Float32Array((count + 1) * 4 * 3),
    indices = [];
  for (let i = 0; i < count; i++)
    for (let face = 0; face < 4; face++) {
      const a = i * 4 + face,
        b = i * 4 + ((face + 1) % 4),
        c = (i + 1) * 4 + face,
        d = (i + 1) * 4 + ((face + 1) % 4);
      indices.push(a, b, c, b, d, c);
    }
  geometry.setAttribute(
    "position",
    new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage),
  );
  geometry.setIndex(indices);
  const object = mesh(
    geometry,
    mat[v === 0 ? "ribbon" : v === 1 ? "gold" : "blush"],
  );
  object.frustumCulled = false;
  ribs.push({ geometry, positions, object, variant: v });
}
function poseRibbon(rib, unroll, reveal, shift) {
  const width = recipe.geometry.ribbon_width * (rib.variant === 0 ? 1 : 0.62),
    half = recipe.geometry.ribbon_thickness / 2;
  const tangent = new THREE.Vector3(),
    side = new THREE.Vector3(),
    normal = new THREE.Vector3();
  for (let i = 0; i <= count; i++) {
    const u = i / count,
      p = ribbonSection(u, unroll, rib.variant),
      p0 = ribbonSection(Math.max(0, u - 0.001), unroll, rib.variant),
      p1 = ribbonSection(Math.min(1, u + 0.001), unroll, rib.variant);
    tangent
      .set(...p1.center)
      .sub(new THREE.Vector3(...p0.center))
      .normalize();
    side.set(...p.side);
    normal.crossVectors(tangent, side).normalize();
    for (let j = 0; j < 4; j++) {
      const w = ((j === 0 || j === 3 ? -1 : 1) * width) / 2,
        h = (j < 2 ? 1 : -1) * half,
        index = (i * 4 + j) * 3;
      rib.positions[index] = p.center[0] + side.x * w + normal.x * h + shift;
      rib.positions[index + 1] = p.center[1] + side.y * w + normal.y * h;
      rib.positions[index + 2] = p.center[2] + side.z * w + normal.z * h;
    }
  }
  rib.geometry.attributes.position.needsUpdate = true;
  rib.geometry.computeVertexNormals();
  rib.geometry.setDrawRange(0, Math.floor(count * reveal) * 24);
  rib.object.visible = reveal > 0;
}
const root = document.getElementById("root"),
  heading = document.getElementById("heading"),
  disclosure = document.getElementById("disclosure"),
  context = document.getElementById("end-context");
const captions = plan.captions.map((cue) => ({
  cue,
  node: document.getElementById(cue.id),
}));
let lastTitle;
function paint(frame) {
  const s = stateAt(frame);
  root.dataset.mode = s.mode;
  for (const rib of ribs)
    poseRibbon(
      rib,
      s.unroll,
      rib.variant === 0
        ? s.opening_wrap
        : rib.variant === 1
          ? s.compliment
          : s.apology,
      s.knot_shift * (1 - s.unroll),
    );
  core.position.set(
    (1 - s.unroll) * s.knot_shift + s.unroll * (-2.75 + 5.5 * s.travel),
    (1 - s.unroll) * 1.75 +
      s.unroll * (0.99 + 0.2 * Math.sin(Math.PI * s.travel)),
    0.05,
  );
  core.scale.setScalar(s.core_scale * (1 - 0.3 * s.unroll));
  core.rotation.y = s.unroll * 0.15;
  camera.position.set(...s.camera);
  camera.lookAt(...s.look_at);
  const title = s.heading
    .split("|")
    .map((x) =>
      x.replace(
        /[&<>]/g,
        (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c],
      ),
    )
    .join("<br>");
  if (title !== lastTitle) {
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
    unroll: s.unroll,
    travel: s.travel,
    triangles: renderer.info.render.triangles,
    draw_calls: renderer.info.render.calls,
  };
}
window.renderProceduralFrame = paint;
const clock = { frame: 0 },
  timeline = gsap.timeline({ paused: true });
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
