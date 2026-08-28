import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..");
const project = path.join(repo, "videos", "biznex-atomy-video-002");
const runRoot = process.env.BIZNEX_VIDEO_002_RUN_ROOT
  ? path.resolve(process.env.BIZNEX_VIDEO_002_RUN_ROOT)
  : path.join(repo, "output", "2026-08-26-2026-08-26-fd928400");
const humanVoiceRoot = process.env.BIZNEX_VIDEO_002_AUDIO_ROOT
  ? path.resolve(process.env.BIZNEX_VIDEO_002_AUDIO_ROOT)
  : path.join(repo, "output", "biznex-video-002", "human-voice");
const narrationSource = path.join(humanVoiceRoot, "narration.wav");
const captionTimingSource = path.join(humanVoiceRoot, "narration.captions.json");
for (const required of [narrationSource, captionTimingSource]) {
  if (!fs.existsSync(required)) throw new Error(`Missing exact narration source: ${required}`);
}
const assetsDir = path.join(project, "assets");
fs.mkdirSync(assetsDir, { recursive: true });
fs.copyFileSync(narrationSource, path.join(assetsDir, "narration.wav"));

const duration = 325.041;
const sceneStarts = [0, 32.145, 64.29, 101.161, 155.985, 216.798, 260.943, 303.707];
const sceneDurations = [32.145, 32.145, 36.871, 54.824, 60.813, 44.145, 42.764, 21.334];
const transitionDuration = 0.55;
const compositionsDir = path.join(project, "compositions");
fs.mkdirSync(compositionsDir, { recursive: true });

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const normalizeGeneratedText = (value) => value.replace(/[ \t]+$/gm, "");

const highlightCaption = (text) => {
  const safe = escapeHtml(text);
  return safe.replace(
    /\b(Atomy|PV|smaller leg|Personal PV|forty-four percent|twenty percent|six percent|thirty-five percent|Sales Master|official mechanics|typical outcomes)\b/i,
    '<span class="caption-key">$1</span>',
  );
};

// Use true neural word boundaries instead of allocating text across storyboard lengths.
// The authored narration remains the text source of truth; only its timing is synthesized.
const captions = JSON.parse(fs.readFileSync(captionTimingSource, "utf8")).map((cue) => ({
  start: cue.start,
  duration: cue.end - cue.start,
  text: highlightCaption(cue.text),
}));

const sharedCss = `
  @font-face { font-family: Impact; src: local("Impact"); }
  @font-face { font-family: "Arial Narrow"; src: local("Arial Narrow"); }
  * { box-sizing: border-box; }
  #root {
    position: absolute;
    inset: 0;
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    background: #0b0a0a;
    color: #fff4dd;
    font-family: "Segoe UI", Arial, sans-serif;
  }
  .backdrop {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at 78% 22%, rgba(244,185,66,.17), transparent 34%),
      radial-gradient(circle at 12% 78%, rgba(117,214,156,.08), transparent 28%),
      linear-gradient(135deg, #0b0a0a 0%, #17120c 52%, #080808 100%);
  }
  .grid {
    position: absolute;
    inset: -100px;
    opacity: .16;
    background-image: linear-gradient(rgba(244,185,66,.22) 1px, transparent 1px), linear-gradient(90deg, rgba(244,185,66,.22) 1px, transparent 1px);
    background-size: 86px 86px;
    transform: rotate(-6deg) translateY(180px) scale(1.32);
    transform-origin: center;
  }
  .grain {
    position: absolute;
    inset: 0;
    opacity: .09;
    background-image: radial-gradient(rgba(255,255,255,.8) .8px, transparent .8px);
    background-size: 6px 6px;
  }
  .ambient {
    position: absolute;
    width: 760px;
    height: 760px;
    border: 2px solid rgba(244,185,66,.16);
    border-radius: 50%;
    right: -260px;
    top: -300px;
    box-shadow: 0 0 100px rgba(244,185,66,.11), inset 0 0 80px rgba(244,185,66,.05);
  }
  .stage { position: absolute; inset: 0; padding: 94px 92px 178px; }
  .eyebrow {
    color: #f4b942;
    font: 700 24px/1 Consolas, monospace;
    letter-spacing: .2em;
    text-transform: uppercase;
  }
  .headline {
    margin-top: 16px;
    font-family: Impact, "Arial Narrow", sans-serif;
    font-size: 116px;
    line-height: .92;
    letter-spacing: .012em;
    text-transform: uppercase;
  }
  .headline .gold { color: #f4b942; }
  .subhead { color: #c8bda7; font-size: 31px; line-height: 1.34; max-width: 920px; }
  .panel {
    border: 1px solid rgba(244,185,66,.28);
    background: linear-gradient(145deg, rgba(31,27,22,.96), rgba(12,11,10,.9));
    border-radius: 28px;
    box-shadow: 0 26px 80px rgba(0,0,0,.42), inset 0 1px rgba(255,255,255,.05);
  }
  .tag {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border-radius: 999px;
    border: 1px solid rgba(244,185,66,.38);
    color: #f4b942;
    font: 700 19px/1 Consolas, monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
  }
  .host-shell { position: absolute; width: 760px; height: 810px; }
  .host-halo {
    position: absolute; width: 610px; height: 610px; border-radius: 50%; left: 92px; top: 75px;
    background: radial-gradient(circle, rgba(244,185,66,.24), transparent 68%);
    border: 2px solid rgba(244,185,66,.25);
  }
  .host-image { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 28px 30px rgba(0,0,0,.55)); }
  .name-plate {
    position: absolute; left: 110px; bottom: 118px; padding: 12px 20px;
    border-radius: 14px; background: #f4b942; color: #0b0a0a;
    font: 900 24px/1 "Segoe UI", sans-serif; letter-spacing: .12em;
  }
  .source-chip { color: #c8bda7; font: 600 19px/1.2 Consolas, monospace; }
  .tiny-rule { height: 2px; background: linear-gradient(90deg,#f4b942,transparent); }
`;

const hostMarkup = (prefix) => `
  <div class="host-shell" id="${prefix}-host">
    <div class="host-halo" data-layout-ignore></div>
    <img class="host-image" src="assets/nexa-toon-v2.png" alt="Nexa, BizNex AI host" />
    <div class="name-plate">NEXA // AI HOST</div>
  </div>`;

const sceneDefinitions = [
  {
    id: "scene-01-hook",
    file: "01-hook.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="copy">
          <div class="eyebrow">THE ATOMY PLAN — FROM ZERO</div>
          <h1 class="headline"><span class="word" data-layout-allow-overlap>TWO LEGS.</span><br><span class="word gold" data-layout-allow-overlap>ONE SMALLER SIDE.</span></h1>
          <p class="subhead">The single picture that makes the official numbers understandable.</p>
          <div class="door-row">
            <div class="door panel big"><span>LEFT</span><strong>1,900,000</strong><small>PV</small></div>
            <div class="versus">VS</div>
            <div class="door panel small"><span>RIGHT</span><strong>700,000</strong><small>PV · SMALLER</small></div>
          </div>
        </div>
        ${hostMarkup("s1")}
        <div class="hook-stamp">WHY THIS SIDE<br>KEEPS MATTERING ↗</div>
      </div>`,
    css: `
      .copy { width: 1080px; position: relative; z-index: 3; }
      .subhead { margin-top: 26px; }
      .door-row { display: flex; align-items: center; gap: 20px; margin-top: 48px; }
      .door { width: 345px; height: 150px; padding: 25px 28px; position: relative; overflow: hidden; }
      .door::after { content:""; position:absolute; inset:0; border-top:4px solid #f4b942; transform-origin:left; }
      .door span { display:block; color:#c8bda7; font:700 18px Consolas,monospace; letter-spacing:.12em; }
      .door strong { display:inline-block; margin-top:8px; font:900 46px/1 "Segoe UI",sans-serif; }
      .door small { margin-left:10px; color:#f4b942; font:700 17px Consolas,monospace; }
      .door.small { border-color:#f4b942; box-shadow:0 0 45px rgba(244,185,66,.2); }
      .versus { font:900 26px Consolas,monospace; color:#f4b942; }
      .host-shell { right:-18px; bottom:95px; z-index:4; }
      .hook-stamp { position:absolute; right:80px; top:100px; transform:rotate(3deg); color:#0b0a0a; background:#f4b942; padding:15px 21px; font:900 21px/1.12 Consolas,monospace; z-index:6; box-shadow:8px 8px 0 #fff4dd; }
    `,
    script: `
      tl.fromTo(q(".eyebrow"), { opacity:0, y:-24 }, { opacity:1, y:0, duration:.45, ease:"power3.out" }, 0.08);
      tl.fromTo(q(".word"), { opacity:0, x:-80 }, { opacity:1, x:0, duration:.7, stagger:.25, ease:"power4.out" }, .3);
      tl.fromTo(q(".subhead"), { opacity:0, y:24 }, { opacity:1, y:0, duration:.55 }, 1.1);
      tl.fromTo(q(".door"), { opacity:0, y:70, rotate:-2 }, { opacity:1, y:0, rotate:0, duration:.75, stagger:.18, ease:"back.out(1.2)" }, 1.55);
      tl.fromTo(q(".versus"), { opacity:0, scale:.4 }, { opacity:1, scale:1, duration:.38, ease:"back.out(2)" }, 2.2);
      tl.fromTo(q(".host-shell"), { opacity:0, x:130 }, { opacity:1, x:0, duration:.9, ease:"power4.out" }, .6);
      tl.fromTo(q(".hook-stamp"), { opacity:0, scale:1.8, rotate:12 }, { opacity:1, scale:1, rotate:3, duration:.5, ease:"back.out(1.6)" }, 2.7);
      tl.to(q(".host-shell"), { y:-7, rotate:.25, duration:6, ease:"sine.inOut" }, 0);
      tl.to(q(".host-shell"), { y:1, rotate:-.18, duration:7, ease:"sine.inOut" }, 6);
      tl.to(q(".host-shell"), { y:-9, rotate:.32, duration:8, ease:"sine.inOut" }, 13);
      tl.to(q(".host-shell"), { y:-2, rotate:0, duration:${sceneDurations[0]-21}, ease:"sine.inOut" }, 21);
    `,
  },
  {
    id: "scene-02-machine",
    file: "02-two-leg-machine.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="eyebrow">THE PICTURE FIRST</div>
        <h2 class="headline">THE <span class="gold">TWO-LEG</span> MACHINE</h2>
        <div class="machine">
          <svg class="connectors" viewBox="0 0 1500 590" aria-hidden="true">
            <path class="line left-line" d="M750 90 C620 170 450 170 350 260 S250 420 160 500"></path>
            <path class="line right-line" d="M750 90 C880 170 1050 170 1150 260 S1250 420 1340 500"></path>
          </svg>
          <div class="you panel"><span>YOU</span><small>CENTER</small></div>
          <div class="lane-label left-label">LEFT LEG <b>1.9M PV</b></div>
          <div class="lane-label right-label">RIGHT LEG <b>700K PV</b></div>
          <div class="node left n1">PV</div><div class="node left n2">PV</div><div class="node left n3">PV</div>
          <div class="node right r1">PV</div><div class="node right r2">PV</div><div class="node right r3">PV</div>
          <div class="smaller-callout panel"><span>GENERAL COMMISSION LOOKS HERE</span><strong>SMALLER LEG</strong><i>↖</i></div>
        </div>
      </div>`,
    css: `
      .headline { font-size:96px; }
      .machine { position:absolute; left:200px; top:310px; width:1520px; height:570px; }
      .connectors { position:absolute; inset:0; width:100%; height:100%; }
      .line { fill:none; stroke:#f4b942; stroke-width:10; stroke-linecap:round; stroke-dasharray:18 18; filter:drop-shadow(0 0 12px rgba(244,185,66,.45)); }
      .right-line { stroke:#75d69c; }
      .you { position:absolute; left:650px; top:30px; width:220px; height:110px; display:grid; place-items:center; border-color:#f4b942; }
      .you span { font:900 42px Impact,sans-serif; letter-spacing:.08em; }
      .you small { position:absolute; bottom:14px; font:700 14px Consolas,monospace; color:#f4b942; }
      .node { position:absolute; width:90px; height:90px; border-radius:50%; display:grid; place-items:center; background:#231d15; border:3px solid #f4b942; font:900 22px Consolas,monospace; box-shadow:0 0 30px rgba(244,185,66,.2); }
      .node.right { border-color:#75d69c; }
      .n1{left:420px;top:175px}.n2{left:250px;top:310px}.n3{left:95px;top:450px}
      .r1{right:420px;top:175px}.r2{right:250px;top:310px}.r3{right:95px;top:450px}
      .lane-label { position:absolute; top:145px; font:700 22px Consolas,monospace; color:#c8bda7; }
      .lane-label b { display:block; color:#fff4dd; font-size:34px; margin-top:6px; }
      .left-label{left:120px}.right-label{right:105px;text-align:right}
      .smaller-callout { position:absolute; right:260px; bottom:-15px; width:420px; padding:22px 25px; border-color:#75d69c; }
      .smaller-callout span { display:block; color:#75d69c; font:700 15px Consolas,monospace; letter-spacing:.08em; }
      .smaller-callout strong { display:block; margin-top:7px; font:900 38px Impact,sans-serif; }
      .smaller-callout i { position:absolute; right:20px; top:22px; font-size:42px; color:#75d69c; }
    `,
    script: `
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, y:-36 }, { opacity:1, y:0, duration:.65, stagger:.16, ease:"power3.out" }, .1);
      tl.fromTo(q(".you"), { opacity:0, scale:.3 }, { opacity:1, scale:1, duration:.55, ease:"back.out(1.8)" }, .8);
      tl.fromTo(q(".line"), { strokeDashoffset:900, opacity:0 }, { strokeDashoffset:0, opacity:1, duration:2.1, stagger:.2, ease:"power2.out" }, 1.1);
      tl.fromTo(q(".node"), { opacity:0, scale:.25 }, { opacity:1, scale:1, duration:.45, stagger:.2, ease:"back.out(1.8)" }, 1.55);
      tl.fromTo(q(".lane-label"), { opacity:0, y:20 }, { opacity:1, y:0, duration:.55, stagger:.2 }, 2.4);
      tl.fromTo(q(".smaller-callout"), { opacity:0, x:90 }, { opacity:1, x:0, duration:.7, ease:"power4.out" }, 4.1);
      tl.to(q(".right-line"), { strokeWidth:16, duration:${sceneDurations[1]-5}, ease:"sine.inOut" }, 5);
    `,
  },
  {
    id: "scene-03-pv",
    file: "03-pv-language.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="eyebrow">STEP 02 — ADD THE TRACKING UNIT</div>
        <h2 class="headline"><span class="gold">PV</span> IS A LANGUAGE,<br>NOT A PAYCHECK</h2>
        <div class="pv-layout">
          <div class="threshold panel">
            <span class="micro">CURRENT ATOMY USA PAGE</span>
            <strong><span class="counter">10,000</span></strong>
            <em>PERSONAL PV FIRST</em>
            <div class="meter"><div class="meter-fill"></div></div>
            <p>before generating downline PV for the plan</p>
          </div>
          <div class="flow">
            <div class="token t1">PV</div><div class="token t2">PV</div><div class="token t3">PV</div>
            <div class="arrow">→</div>
            <div class="destination panel"><span>MAY BE ADDED TO</span><b>THE SMALLER LEG</b></div>
          </div>
          <div class="warning panel"><b>DO NOT INVENT</b><span>$ value per PV</span><small>Check current official material.</small></div>
        </div>
      </div>`,
    css: `
      .headline { font-size:95px; width:1300px; }
      .pv-layout { position:absolute; left:92px; right:92px; top:385px; display:grid; grid-template-columns:620px 1fr; gap:36px; }
      .threshold { height:455px; padding:40px; border-color:#f4b942; }
      .micro { color:#c8bda7; font:700 17px Consolas,monospace; letter-spacing:.12em; }
      .threshold strong { display:block; margin-top:25px; font:900 112px/1 Impact,sans-serif; color:#f4b942; letter-spacing:.03em; }
      .threshold em { display:block; font:900 31px/1 "Segoe UI",sans-serif; font-style:normal; }
      .threshold p { margin-top:22px; color:#c8bda7; font-size:23px; }
      .meter { height:18px; background:#30281e; border-radius:20px; margin-top:30px; overflow:hidden; }
      .meter-fill { width:100%; height:100%; background:linear-gradient(90deg,#f4b942,#fff4dd); transform-origin:left; }
      .flow { height:270px; display:flex; align-items:center; gap:22px; position:relative; }
      .token { width:84px; height:84px; border-radius:50%; display:grid; place-items:center; background:#f4b942; color:#0b0a0a; font:900 22px Consolas,monospace; box-shadow:0 0 30px rgba(244,185,66,.28); }
      .arrow { font-size:76px; color:#75d69c; }
      .destination { width:370px; height:150px; padding:30px; border-color:#75d69c; }
      .destination span { display:block; color:#75d69c; font:700 15px Consolas,monospace; }
      .destination b { display:block; font:900 32px Impact,sans-serif; margin-top:9px; }
      .warning { position:absolute; right:0; bottom:0; width:785px; height:150px; padding:30px 34px; border-color:#ff6b5e; display:grid; grid-template-columns:260px 1fr; align-items:center; }
      .warning b { color:#ff6b5e; font:900 31px Impact,sans-serif; }
      .warning span { font:900 34px Consolas,monospace; text-decoration:line-through 6px #ff6b5e; }
      .warning small { grid-column:2; color:#c8bda7; font-size:18px; }
    `,
    script: `
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, x:-60 }, { opacity:1, x:0, duration:.65, stagger:.18, ease:"power3.out" }, .1);
      tl.fromTo(q(".threshold"), { opacity:0, y:70, rotate:-1.5 }, { opacity:1, y:0, rotate:0, duration:.75, ease:"back.out(1.2)" }, .8);
      tl.fromTo(q(".meter-fill"), { scaleX:0 }, { scaleX:1, duration:2.2, ease:"power2.out" }, 1.7);
      tl.fromTo(q(".token"), { opacity:0, x:-120, scale:.5 }, { opacity:1, x:0, scale:1, duration:.55, stagger:.25, ease:"back.out(1.6)" }, 2.5);
      tl.fromTo(q(".destination"), { opacity:0, x:80 }, { opacity:1, x:0, duration:.7 }, 3.2);
      tl.fromTo(q(".warning"), { opacity:0, y:70 }, { opacity:1, y:0, duration:.7, ease:"power3.out" }, 6.3);
      tl.to(q(".token"), { y:-20, stagger:.15, duration:${sceneDurations[2]-7}, ease:"sine.inOut" }, 7);
    `,
  },
  {
    id: "scene-04-classes",
    file: "04-dealership-ladder.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="eyebrow">THE FIVE DEALERSHIP CLASSES</div>
        <h2 class="headline">A <span class="gold">QUALIFICATION</span> LADDER</h2>
        <div class="ladder">
          <div class="rank"><i>01</i><b>SALES REP</b><span>10K–299,999 PV</span></div>
          <div class="rank"><i>02</i><b>AGENT</b><span>300K+ PV</span></div>
          <div class="rank"><i>03</i><b>SPECIAL AGENT</b><span>700K+ PV</span></div>
          <div class="rank"><i>04</i><b>DEALER</b><span>1.5M+ PV</span></div>
          <div class="rank"><i>05</i><b>EXCLUSIVE DISTRIBUTOR</b><span>2.4M+ PV</span></div>
        </div>
        <div class="not-salary panel"><span>RANK NAME</span><b>≠ SALARY LABEL</b><small>Class can change monthly.</small></div>
        ${hostMarkup("s4")}
      </div>`,
    css: `
      .headline { font-size:88px; }
      .ladder { position:absolute; left:92px; top:340px; width:1120px; display:grid; gap:13px; }
      .rank { height:92px; display:grid; grid-template-columns:85px 1fr 260px; align-items:center; padding:0 28px; border:1px solid rgba(244,185,66,.25); border-left:7px solid #f4b942; border-radius:18px; background:rgba(22,19,15,.94); box-shadow:0 12px 35px rgba(0,0,0,.23); }
      .rank i { color:#f4b942; font:700 20px Consolas,monospace; font-style:normal; }
      .rank b { font:900 30px Impact,sans-serif; letter-spacing:.04em; }
      .rank span { color:#c8bda7; font:700 24px Consolas,monospace; text-align:right; }
      .not-salary { position:absolute; left:930px; bottom:180px; width:350px; padding:22px; transform:rotate(-2deg); border-color:#ff6b5e; z-index:5; }
      .not-salary span { color:#ff6b5e; font:700 16px Consolas,monospace; }
      .not-salary b { display:block; font:900 34px Impact,sans-serif; margin-top:4px; }
      .not-salary small { display:block; color:#c8bda7; margin-top:8px; font-size:18px; }
      .host-shell { right:-70px; bottom:65px; width:720px; height:760px; }
    `,
    script: `
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, y:-30 }, { opacity:1, y:0, duration:.6, stagger:.14 }, .1);
      tl.fromTo(q(".rank"), { opacity:0, x:-110 }, { opacity:1, x:0, duration:.62, stagger:.48, ease:"power4.out" }, 1);
      tl.fromTo(q(".host-shell"), { opacity:0, x:120 }, { opacity:1, x:0, duration:.9, ease:"power4.out" }, 2.1);
      tl.fromTo(q(".not-salary"), { opacity:0, scale:1.5, rotate:8 }, { opacity:1, scale:1, rotate:-2, duration:.55, ease:"back.out(1.7)" }, 5.2);
      tl.to(q(".rank"), { borderLeftWidth:16, stagger:.35, duration:${sceneDurations[3]-7}, ease:"sine.inOut" }, 7);
      tl.to(q(".host-shell"), { y:-8, rotate:.24, duration:11, ease:"sine.inOut" }, 0);
      tl.to(q(".host-shell"), { y:1, rotate:-.16, duration:12, ease:"sine.inOut" }, 11);
      tl.to(q(".host-shell"), { y:-7, rotate:.2, duration:14, ease:"sine.inOut" }, 23);
      tl.to(q(".host-shell"), { y:-2, rotate:0, duration:${sceneDurations[3]-37}, ease:"sine.inOut" }, 37);
    `,
  },
  {
    id: "scene-05-pools",
    file: "05-commission-pools.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="eyebrow">DO NOT ADD THESE LIKE PERSONAL PAYOUTS</div>
        <h2 class="headline">THREE <span class="gold">PLAN POOLS</span></h2>
        <div class="pool-grid">
          <article class="pool p44"><span>GENERAL COMMISSION</span><strong>44%</strong><p>of total sales PV distributed among qualified members, per the official table.</p><i>WEEKLY</i></article>
          <article class="pool p20"><span>MASTERSHIP</span><strong>20%</strong><p>of total sales PV under a separate set of rank and group-PV conditions.</p><i>CONDITIONAL</i></article>
          <article class="pool p6"><span>EDUCATION</span><strong>6%</strong><p>of center total PV, described separately on the current plan page.</p><i>CENTER-LEVEL</i></article>
        </div>
        <div class="cap panel">
          <div class="shield">35%</div>
          <div><b>COMMISSION CAP</b><span>Total commissions do not exceed 35% of total sales income.</span></div>
          <em>ALLOCATION ≠ YOUR FORECAST</em>
        </div>
      </div>`,
    css: `
      .headline { font-size:100px; }
      .pool-grid { position:absolute; left:92px; right:92px; top:330px; display:grid; grid-template-columns:repeat(3,1fr); gap:26px; }
      .pool { height:390px; padding:34px; border-radius:30px; border:1px solid rgba(244,185,66,.3); background:linear-gradient(145deg,rgba(37,31,23,.98),rgba(12,11,10,.96)); position:relative; overflow:hidden; box-shadow:0 24px 70px rgba(0,0,0,.4); }
      .pool::before { content:""; position:absolute; left:0; bottom:0; width:100%; height:9px; background:#f4b942; transform-origin:left; }
      .pool span { font:700 18px Consolas,monospace; letter-spacing:.12em; color:#c8bda7; }
      .pool strong { display:block; margin:24px 0 12px; font:900 118px/1 Impact,sans-serif; color:#f4b942; }
      .pool p { color:#c8bda7; font-size:22px; line-height:1.35; }
      .pool i { position:absolute; right:26px; top:26px; color:#0b0a0a; background:#f4b942; padding:8px 10px; font:900 13px Consolas,monospace; font-style:normal; }
      .p20 strong{color:#75d69c}.p20::before,.p20 i{background:#75d69c}.p6 strong{color:#fff4dd}
      .cap { position:absolute; left:260px; right:260px; bottom:160px; height:160px; display:grid; grid-template-columns:150px 1fr 420px; align-items:center; padding:22px 32px; border-color:#ff6b5e; }
      .shield { width:110px; height:110px; display:grid; place-items:center; background:#ff6b5e; color:#0b0a0a; clip-path:polygon(50% 0,95% 18%,86% 75%,50% 100%,14% 75%,5% 18%); font:900 34px Impact,sans-serif; }
      .cap b { display:block; font:900 31px Impact,sans-serif; }
      .cap span { display:block; color:#c8bda7; margin-top:7px; font-size:20px; }
      .cap em { color:#ff6b5e; font:900 24px Consolas,monospace; font-style:normal; text-align:right; }
    `,
    script: `
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, x:-60 }, { opacity:1, x:0, duration:.65, stagger:.18 }, .1);
      tl.fromTo(q(".pool"), { opacity:0, y:100, rotate:-1.5 }, { opacity:1, y:0, rotate:0, duration:.85, stagger:.36, ease:"back.out(1.15)" }, 1);
      tl.fromTo(q(".cap"), { opacity:0, scale:.85, y:60 }, { opacity:1, scale:1, y:0, duration:.75, ease:"back.out(1.35)" }, 4.3);
      tl.to(q(".shield"), { rotate:4, scale:1.05, duration:${sceneDurations[4]-6}, ease:"sine.inOut" }, 6);
    `,
  },
  {
    id: "scene-06-outcomes",
    file: "06-structure-vs-outcome.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="eyebrow">THE LINE MOST EXPLAINERS BLUR</div>
        <h2 class="headline">STRUCTURE <span class="not-equal">≠</span> OUTCOME</h2>
        <div class="compare">
          <section class="panel fact"><div class="icon">✓</div><span>THE PLAN CAN DESCRIBE</span><b>MECHANICS</b><ul><li>PV thresholds</li><li>Dealership classes</li><li>Score conditions</li><li>Company allocation pools</li></ul></section>
          <div class="boundary"><span>KEEP<br>SEPARATE</span></div>
          <section class="panel unknown"><div class="icon">?</div><span>THE CHART DOES NOT PREDICT</span><b>YOUR RESULT</b><ul><li>Typical participant earnings</li><li>Typical expenses</li><li>Time to reach a level</li><li>Your net outcome</li></ul></section>
        </div>
        <div class="decision tag">BASIC DECISION HYGIENE</div>
      </div>`,
    css: `
      .headline { font-size:112px; }
      .not-equal { display:inline-block; color:#ff6b5e; }
      .compare { position:absolute; left:150px; right:150px; top:355px; display:grid; grid-template-columns:1fr 150px 1fr; align-items:stretch; }
      .compare section { height:450px; padding:38px 44px; }
      .compare section>span { color:#c8bda7; font:700 17px Consolas,monospace; letter-spacing:.1em; }
      .compare section>b { display:block; margin:12px 0 22px; font:900 55px Impact,sans-serif; }
      .compare ul { list-style:none; display:grid; gap:15px; }
      .compare li { color:#c8bda7; font-size:23px; padding-left:28px; position:relative; }
      .compare li::before { content:"•"; position:absolute; left:0; color:#f4b942; }
      .icon { position:absolute; right:34px; top:28px; width:68px; height:68px; display:grid; place-items:center; border-radius:50%; background:#75d69c; color:#0b0a0a; font:900 36px Impact,sans-serif; }
      .unknown { border-color:#ff6b5e; }
      .unknown .icon { background:#ff6b5e; }
      .unknown li::before { color:#ff6b5e; }
      .boundary { display:grid; place-items:center; }
      .boundary::before { content:""; position:absolute; height:440px; width:3px; background:linear-gradient(transparent,#ff6b5e,transparent); }
      .boundary span { z-index:2; padding:13px; background:#0b0a0a; color:#ff6b5e; font:900 15px/1.1 Consolas,monospace; text-align:center; }
      .decision { position:absolute; right:150px; bottom:145px; }
    `,
    script: `
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, y:-38 }, { opacity:1, y:0, duration:.7, stagger:.17 }, .1);
      tl.fromTo(q(".not-equal"), { opacity:0, scale:2.4, rotate:25 }, { opacity:1, scale:1, rotate:0, duration:.55, ease:"back.out(1.8)" }, 1.1);
      tl.fromTo(q(".fact"), { opacity:0, x:-150, rotate:-1 }, { opacity:1, x:0, rotate:0, duration:.85, ease:"power4.out" }, 1.5);
      tl.fromTo(q(".unknown"), { opacity:0, x:150, rotate:1 }, { opacity:1, x:0, rotate:0, duration:.85, ease:"power4.out" }, 1.7);
      tl.fromTo(q(".boundary"), { opacity:0, scaleY:0 }, { opacity:1, scaleY:1, duration:.75 }, 2.2);
      tl.fromTo(q("li"), { opacity:0, x:-22 }, { opacity:1, x:0, duration:.35, stagger:.18 }, 2.7);
      tl.fromTo(q(".decision"), { opacity:0, y:30 }, { opacity:1, y:0, duration:.55 }, 5.1);
      tl.to(q(".not-equal"), { color:"#f4b942", scale:1.12, duration:${sceneDurations[5]-6}, ease:"sine.inOut" }, 6);
    `,
  },
  {
    id: "scene-07-evidence",
    file: "07-claim-vs-chart.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        <div class="eyebrow">A CLEAN RESEARCH HABIT</div>
        <h2 class="headline">SEPARATE THE <span class="gold">CLAIM</span><br>FROM THE CHART</h2>
        <div class="evidence-row">
          <div class="claim-card panel"><span>SOMEONE SAYS</span><b>“THIS MEANS<br>YOU WILL EARN…”</b><div class="strike"></div></div>
          <div class="arrow-large">→</div>
          <div class="chart-card panel"><span>OFFICIAL SOURCE</span><b>WHAT THE PLAN<br>ACTUALLY STATES</b><small>Mechanics, thresholds, conditions</small><div class="verified">SOURCE CHECKED ✓</div></div>
        </div>
        <div class="mental-model">
          <div><i>01</i><b>PV</b><span>tracking language</span></div>
          <div><i>02</i><b>CLASS</b><span>qualification</span></div>
          <div><i>03</i><b>TWO LEGS</b><span>structure</span></div>
          <div><i>04</i><b>POOLS</b><span>allocation, not forecast</span></div>
        </div>
      </div>`,
    css: `
      .headline { font-size:88px; }
      .evidence-row { position:absolute; left:120px; right:120px; top:360px; display:grid; grid-template-columns:1fr 120px 1fr; align-items:center; }
      .evidence-row>div.panel { height:285px; padding:38px; position:relative; }
      .evidence-row span { color:#c8bda7; font:700 16px Consolas,monospace; letter-spacing:.12em; }
      .evidence-row b { display:block; margin-top:17px; font:900 46px/1.08 Impact,sans-serif; }
      .claim-card { border-color:#ff6b5e; }
      .strike { position:absolute; left:25px; right:25px; height:10px; top:150px; background:#ff6b5e; transform:rotate(-7deg); transform-origin:left; }
      .arrow-large { text-align:center; color:#f4b942; font-size:72px; }
      .chart-card { border-color:#75d69c; }
      .chart-card small { display:block; color:#c8bda7; font-size:20px; margin-top:12px; }
      .verified { position:absolute; right:28px; bottom:22px; color:#0b0a0a; background:#75d69c; padding:9px 12px; font:900 14px Consolas,monospace; transform:rotate(-2deg); }
      .mental-model { position:absolute; left:120px; right:120px; bottom:160px; display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }
      .mental-model>div { min-height:130px; padding:22px; border-top:4px solid #f4b942; background:rgba(24,21,18,.94); }
      .mental-model i { color:#f4b942; font:700 15px Consolas,monospace; font-style:normal; }
      .mental-model b { display:block; margin-top:8px; font:900 28px Impact,sans-serif; }
      .mental-model span { color:#c8bda7; font-size:18px; }
    `,
    script: `
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, x:-65 }, { opacity:1, x:0, duration:.65, stagger:.17 }, .1);
      tl.fromTo(q(".claim-card"), { opacity:0, x:-120 }, { opacity:1, x:0, duration:.75, ease:"power4.out" }, 1);
      tl.fromTo(q(".strike"), { scaleX:0 }, { scaleX:1, duration:.5, ease:"power3.out" }, 2);
      tl.fromTo(q(".arrow-large"), { opacity:0, scale:.2 }, { opacity:1, scale:1, duration:.45, ease:"back.out(2)" }, 2.3);
      tl.fromTo(q(".chart-card"), { opacity:0, x:120 }, { opacity:1, x:0, duration:.75, ease:"power4.out" }, 2.5);
      tl.fromTo(q(".verified"), { opacity:0, scale:1.6, rotate:9 }, { opacity:1, scale:1, rotate:-2, duration:.5, ease:"back.out(1.8)" }, 3.6);
      tl.fromTo(q(".mental-model>div"), { opacity:0, y:70 }, { opacity:1, y:0, duration:.55, stagger:.25, ease:"power3.out" }, 4.1);
      tl.to(q(".mental-model>div"), { borderTopWidth:12, stagger:.25, duration:${sceneDurations[6]-6}, ease:"sine.inOut" }, 6);
    `,
  },
  {
    id: "scene-08-cta",
    file: "08-cta.html",
    body: `
      <div class="backdrop"></div><div class="grid" data-layout-ignore></div><div class="grain" data-layout-ignore></div><div class="ambient" data-layout-ignore></div>
      <div class="stage">
        ${hostMarkup("s8")}
        <div class="cta-copy">
          <div class="eyebrow">YOU CHOOSE VIDEO 03</div>
          <h2 class="headline">WHAT SHOULD<br>NEXA <span class="gold">UNPACK NEXT?</span></h2>
          <div class="polls">
            <div class="poll panel"><i>A</i><b>DEALERSHIP SCORE TABLE</b></div>
            <div class="poll panel"><i>B</i><b>SALES MASTER QUALIFICATION</b></div>
            <div class="poll panel"><i>C</i><b>TYPICAL-RESULT EVIDENCE</b></div>
          </div>
          <div class="subscribe"><span>COMMENT A, B, OR C</span><b>SUBSCRIBE TO BIZNEX ↗</b></div>
        </div>
      </div>`,
    css: `
      .host-shell { left:-65px; bottom:62px; width:780px; height:820px; }
      .cta-copy { position:absolute; left:720px; right:90px; top:105px; }
      .headline { font-size:85px; }
      .polls { margin-top:34px; display:grid; gap:14px; }
      .poll { height:95px; display:grid; grid-template-columns:90px 1fr; align-items:center; padding:0 28px; }
      .poll i { width:48px; height:48px; display:grid; place-items:center; border-radius:50%; background:#f4b942; color:#0b0a0a; font:900 24px Impact,sans-serif; font-style:normal; }
      .poll b { font:900 28px Impact,sans-serif; letter-spacing:.04em; }
      .subscribe { margin-top:22px; display:flex; align-items:center; justify-content:space-between; background:#f4b942; color:#0b0a0a; padding:18px 24px; border-radius:17px; }
      .subscribe span { font:900 18px Consolas,monospace; }
      .subscribe b { font:900 25px "Segoe UI",sans-serif; }
    `,
    script: `
      tl.fromTo(q(".host-shell"), { opacity:0, x:-130 }, { opacity:1, x:0, duration:.85, ease:"power4.out" }, .1);
      tl.fromTo(q(".eyebrow,.headline"), { opacity:0, x:80 }, { opacity:1, x:0, duration:.65, stagger:.16, ease:"power3.out" }, .35);
      tl.fromTo(q(".poll"), { opacity:0, x:110 }, { opacity:1, x:0, duration:.55, stagger:.25, ease:"back.out(1.2)" }, 1.3);
      tl.fromTo(q(".subscribe"), { opacity:0, scale:.8, y:50 }, { opacity:1, scale:1, y:0, duration:.62, ease:"back.out(1.5)" }, 2.5);
      tl.to(q(".host-shell"), { y:-7, rotate:.22, duration:6, ease:"sine.inOut" }, 0);
      tl.to(q(".host-shell"), { y:1, rotate:-.16, duration:7, ease:"sine.inOut" }, 6);
      tl.to(q(".host-shell"), { y:-5, rotate:.18, duration:${sceneDurations[7]-13}, ease:"sine.inOut" }, 13);
      tl.to(q(".subscribe"), { boxShadow:"0 0 55px rgba(244,185,66,.5)", duration:${sceneDurations[7]-4}, ease:"sine.inOut" }, 4);
    `,
  },
];

const subComposition = (scene, index) => `<!doctype html>
<html lang="en">
  <head><meta charset="UTF-8" /></head>
  <body>
    <template>
      <style>
        ${sharedCss}
        ${scene.css}
      </style>
      <div id="root" data-composition-id="${scene.id}" data-start="0" data-duration="${sceneDurations[index]}" data-width="1920" data-height="1080">
        ${scene.body}
      </div>
      <script>
        window.__timelines = window.__timelines || {};
        const root = document.querySelector('[data-composition-id="${scene.id}"]');
        const q = gsap.utils.selector(root);
        const tl = gsap.timeline({ paused: true });
        tl.to(q(".ambient"), { rotation:18, scale:1.13, duration:${sceneDurations[index]}, ease:"none" }, 0);
        tl.to(q(".grain"), { backgroundPosition:"32px 18px", duration:${sceneDurations[index]}, ease:"none" }, 0);
        ${scene.script}
        window.__timelines["${scene.id}"] = tl;
      </script>
    </template>
  </body>
</html>
`;

sceneDefinitions.forEach((scene, index) => {
  fs.writeFileSync(
    path.join(compositionsDir, scene.file),
    normalizeGeneratedText(subComposition(scene, index)),
  );
});

const captionMarkup = captions
  .map(
    (caption, index) => `<div id="caption-${String(index + 1).padStart(3, "0")}" class="clip caption" data-start="${caption.start.toFixed(3)}" data-duration="${caption.duration.toFixed(3)}" data-track-index="20" data-layout-allow-caption-zone><span>${caption.text}</span></div>`,
  )
  .join("");

const sceneMarkup = sceneDefinitions
  .map((scene, index) => {
    const visibleDuration = sceneDurations[index] + (index < sceneDefinitions.length - 1 ? transitionDuration : 0);
    return `
      <div id="${scene.id}-slot" class="clip scene-slot" data-composition-id="${scene.id}" data-composition-src="compositions/${scene.file}" data-start="${sceneStarts[index]}" data-duration="${visibleDuration.toFixed(3)}" data-track-index="${index + 1}" data-width="1920" data-height="1080" style="z-index:${10 + index}"></div>`;
  })
  .join("");

const sfxMarkup = sceneStarts
  .slice(1)
  .map(
    (start, index) => `<audio id="transition-sfx-${index + 1}" src=".media/audio/sfx/sfx_001.mp3" data-start="${(start - 0.08).toFixed(3)}" data-duration="0.6" data-track-index="13" data-volume="0.22"></audio>`,
  )
  .join("\n      ");

const transitions = sceneStarts
  .slice(1)
  .map((start, index) => {
    const id = sceneDefinitions[index + 1].id;
    const from = index % 2 === 0 ? "inset(0 100% 0 0 round 50px)" : "inset(100% 0 0 0 round 50px)";
    return `tl.fromTo("#${id}-slot", { clipPath:"${from}", filter:"brightness(1.65)" }, { clipPath:"inset(0 0% 0 0 round 0px)", filter:"brightness(1)", duration:${transitionDuration}, ease:"power3.inOut" }, ${start});`;
  })
  .join("\n      ");

const indexHtml = `<!doctype html>
<html lang="en" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin:0; padding:0; box-sizing:border-box; }
      html, body { width:1920px; height:1080px; overflow:hidden; background:#0b0a0a; }
      body { font-family:"Segoe UI",Arial,sans-serif; }
      #root { position:absolute; inset:0; width:1920px; height:1080px; overflow:hidden; background:#0b0a0a; }
      .clip { position:absolute; inset:0; }
      .scene-slot { overflow:hidden; }
      .brand-rail { position:absolute; left:48px; right:48px; top:34px; height:48px; display:flex; align-items:center; justify-content:space-between; z-index:80; pointer-events:none; }
      .brand-left { display:flex; align-items:center; gap:14px; color:#fff4dd; font:800 18px Consolas,monospace; letter-spacing:.12em; }
      .brand-left img { width:46px; height:46px; border-radius:50%; box-shadow:0 0 24px rgba(244,185,66,.26); }
      .episode-chip { padding:9px 13px; border:1px solid rgba(244,185,66,.35); border-radius:99px; color:#f4b942; font:700 15px Consolas,monospace; letter-spacing:.1em; }
      .caption { inset:auto 165px 42px; min-height:92px; z-index:90; display:flex; align-items:center; justify-content:center; text-align:center; pointer-events:none; }
      .caption span { display:inline; max-width:1500px; padding:14px 27px 17px; border-radius:17px; color:#fff; background:rgba(5,5,5,.91); box-shadow:0 12px 36px rgba(0,0,0,.45); font:700 37px/1.22 "Segoe UI",Arial,sans-serif; text-shadow:0 2px 2px #000; }
      .caption-key { color:#f4b942; }
      .progress-track { position:absolute; left:0; right:0; bottom:0; height:7px; background:rgba(255,255,255,.08); z-index:100; }
      .progress-fill { width:100%; height:100%; background:linear-gradient(90deg,#f4b942,#fff4dd,#75d69c); transform:scaleX(0); transform-origin:left; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="${duration}" data-width="1920" data-height="1080">
      ${sceneMarkup}
      <audio id="narration" src="assets/narration.wav" data-start="0" data-duration="325.03" data-track-index="11" data-volume="1"></audio>
      <audio id="music" src="assets/biznex-bed.m4a" data-start="0" data-duration="325.041" data-track-index="12" data-volume="0.075"></audio>
      ${sfxMarkup}
      ${captionMarkup}
      <div class="brand-rail" data-layout-ignore>
        <div class="brand-left"><img src="assets/biznex-logo.png" alt="BizNex" />BIZNEX // AI-BUILT SERIES</div>
        <div class="episode-chip">EP. 02 · SOURCED EXPLAINER</div>
      </div>
      <div class="progress-track" data-layout-ignore><div id="series-progress" class="progress-fill"></div></div>
    </div>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused:true });
      tl.to("#series-progress", { scaleX:1, duration:${duration}, ease:"none" }, 0);
      ${transitions}
      window.__timelines.main = tl;
    </script>
  </body>
</html>
`;
fs.writeFileSync(path.join(project, "index.html"), normalizeGeneratedText(indexHtml));

const thumbnailHtml = `<!doctype html>
<html lang="en" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      *{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#090909;font-family:"Segoe UI",Arial,sans-serif}
      #root{position:absolute;inset:0;width:1920px;height:1080px;overflow:hidden;background:radial-gradient(circle at 72% 26%,rgba(244,185,66,.3),transparent 32%),linear-gradient(135deg,#090909,#21170c 58%,#070707);color:#fff4dd}
      .rays{position:absolute;inset:-300px;background:repeating-conic-gradient(from 210deg at 73% 43%,rgba(244,185,66,.09) 0 5deg,transparent 5deg 13deg);opacity:.75}
      .copy{position:absolute;left:85px;top:78px;width:1030px;z-index:4}.kicker{display:inline-block;background:#f4b942;color:#0b0a0a;padding:13px 18px;font:900 23px Consolas,monospace;letter-spacing:.08em}.copy h1{margin:31px 0 0;font:900 154px/.83 Impact,"Arial Narrow",sans-serif;letter-spacing:.01em;text-transform:uppercase;text-shadow:0 12px 0 rgba(0,0,0,.45)}.copy h1 span{color:#f4b942}.mini{margin-top:35px;color:#fff4dd;font:800 30px Consolas,monospace}.mini b{color:#75d69c}.balance{position:absolute;left:96px;bottom:90px;width:920px;height:225px;z-index:4}.beam{position:absolute;left:80px;top:80px;width:760px;height:18px;background:#f4b942;transform:rotate(7deg);box-shadow:0 0 28px rgba(244,185,66,.48)}.pivot{position:absolute;left:435px;top:98px;width:0;height:0;border-left:85px solid transparent;border-right:85px solid transparent;border-bottom:125px solid #fff4dd}.weight{position:absolute;width:230px;height:100px;border:3px solid #f4b942;border-radius:18px;background:#17130f;display:grid;place-items:center;font:900 35px Impact,sans-serif}.weight.big{left:28px;top:5px}.weight.small{right:28px;top:80px;border-color:#75d69c;box-shadow:0 0 35px rgba(117,214,156,.3)}.host{position:absolute;right:-10px;bottom:-70px;width:880px;height:1020px;z-index:3}.host img{width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 30px 35px rgba(0,0,0,.55))}.arrow{position:absolute;right:70px;top:95px;font:900 42px Impact,sans-serif;background:#ff6b5e;color:#090909;padding:16px 22px;transform:rotate(4deg);z-index:7;box-shadow:10px 10px 0 #fff4dd}.logo{position:absolute;right:62px;bottom:52px;width:74px;height:74px;border-radius:50%;z-index:8}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="thumbnail" data-start="0" data-duration="2" data-width="1920" data-height="1080">
      <div class="rays"></div>
      <div class="copy"><div class="kicker">ATOMY BUSINESS PLAN 2026</div><h1>THE<br><span>SMALLER</span><br>SIDE?</h1><div class="mini">PV · TWO LEGS · <b>OFFICIAL NUMBERS</b></div></div>
      <div class="balance"><div class="beam"></div><div class="pivot"></div><div class="weight big">1.9M PV</div><div class="weight small">700K PV</div></div>
      <div class="host"><img src="assets/nexa-toon-v2.png" alt="Nexa" /></div>
      <div class="arrow">THIS SIDE DECIDES ↙</div><img class="logo" src="assets/biznex-logo.png" alt="BizNex" />
    </div>
    <script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});tl.fromTo(".copy",{opacity:0,x:-40},{opacity:1,x:0,duration:.5});tl.fromTo(".host",{opacity:0,x:50},{opacity:1,x:0,duration:.5},.1);tl.fromTo(".arrow",{opacity:0,scale:1.4},{opacity:1,scale:1,duration:.4},.3);window.__timelines.thumbnail=tl;</script>
  </body>
</html>`;
const thumbnailDir = path.join(project, "thumbnail");
fs.mkdirSync(thumbnailDir, { recursive: true });
fs.writeFileSync(
  path.join(thumbnailDir, "thumbnail.html"),
  normalizeGeneratedText(thumbnailHtml),
);
const oldThumbnail = path.join(project, "thumbnail.html");
if (fs.existsSync(oldThumbnail)) fs.unlinkSync(oldThumbnail);

const motion = {
  duration,
  assertions: [
    { kind: "appearsBy", selector: "#scene-01-hook-slot", bySec: 0.1 },
    { kind: "appearsBy", selector: "#series-progress", bySec: 1.2 },
    { kind: "staysInFrame", selector: "#series-progress" },
    { kind: "keepsMoving", withinSelector: "#root", maxStaticSec: 8 },
  ],
};
fs.writeFileSync(path.join(project, "index.motion.json"), JSON.stringify(motion, null, 2) + "\n");

const srtTimestamp = (seconds) => {
  const milliseconds = Math.max(0, Math.round(seconds * 1000));
  const hours = Math.floor(milliseconds / 3_600_000);
  const minutes = Math.floor((milliseconds % 3_600_000) / 60_000);
  const secs = Math.floor((milliseconds % 60_000) / 1000);
  const millis = milliseconds % 1000;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
};
const captionOutput = path.join(repo, "output", "biznex-video-002");
fs.mkdirSync(captionOutput, { recursive: true });
const captionSrt = captions.map((caption, index) => {
  const plainText = caption.text
    .replace(/<[^>]+>/g, "")
    .replaceAll("&#039;", "'")
    .replaceAll("&quot;", '"')
    .replaceAll("&gt;", ">")
    .replaceAll("&lt;", "<")
    .replaceAll("&amp;", "&");
  return `${index + 1}\n${srtTimestamp(caption.start)} --> ${srtTimestamp(caption.start + caption.duration)}\n${plainText}`;
}).join("\n\n") + "\n";
fs.writeFileSync(path.join(captionOutput, "video-002-five-second-captions.srt"), captionSrt);
fs.writeFileSync(path.join(captionOutput, "video-002-exact-captions.srt"), captionSrt);

console.log(`Built ${sceneDefinitions.length} scenes and ${captions.length} caption clips.`);
