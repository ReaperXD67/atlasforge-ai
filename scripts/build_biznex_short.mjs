import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..");
const specPath = path.resolve(
  process.env.BIZNEX_SHORT_SPEC || path.join(repo, "docs", "biznex", "video-003", "short-spec.json"),
);
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const project = path.resolve(repo, spec.project);
const audioRoot = path.resolve(
  process.env.BIZNEX_SHORT_AUDIO_ROOT || path.join(repo, "output", "biznex-video-003", "audio"),
);
const scriptPath = path.join(project, "SCRIPT.md");
const wordsPath = path.join(audioRoot, "narration.words.json");
const captionsPath = path.join(audioRoot, "narration.captions.json");
const narrationPath = path.join(audioRoot, "narration.wav");

for (const required of [scriptPath, wordsPath, captionsPath, narrationPath]) {
  if (!fs.existsSync(required)) throw new Error(`Missing short input: ${required}`);
}

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const spokenBlocks = fs
  .readFileSync(scriptPath, "utf8")
  .split(/\r?\n/)
  .reduce((blocks, line) => {
    if (line.startsWith("    ") && line.trim()) {
      const last = blocks.at(-1);
      if (last?.open) last.text += ` ${line.trim()}`;
      else blocks.push({ open: true, text: line.trim() });
    } else if (blocks.at(-1)?.open) {
      blocks.at(-1).open = false;
    }
    return blocks;
  }, [])
  .map((block) => block.text);

if (spokenBlocks.length !== spec.scenes.length) {
  throw new Error(`SCRIPT.md has ${spokenBlocks.length} spoken blocks for ${spec.scenes.length} scenes`);
}

const words = JSON.parse(fs.readFileSync(wordsPath, "utf8"));
const captions = JSON.parse(fs.readFileSync(captionsPath, "utf8"));
const narrationSeconds = Number(
  execFileSync(
    "ffprobe",
    ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", narrationPath],
    { encoding: "utf8" },
  ).trim(),
);

let wordCursor = 0;
const wordStarts = spokenBlocks.map((block) => {
  const startIndex = wordCursor;
  wordCursor += block.trim().split(/\s+/).length;
  return startIndex;
});
if (wordCursor !== words.length) {
  throw new Error(`SCRIPT.md token count ${wordCursor} does not match exact word rail ${words.length}`);
}

const starts = wordStarts.map((index) => Number(words[index].start));
const totalDuration = narrationSeconds + Number(spec.tail_seconds || 0.8);
const durations = starts.map((start, index) => {
  const end = index + 1 < starts.length ? starts[index + 1] : totalDuration;
  return Number((end - start).toFixed(3));
});

const mediaDuration = (file) =>
  Number(
    execFileSync(
      "ffprobe",
      ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file],
      { encoding: "utf8" },
    ).trim(),
  );

const publicDir = path.join(project, "public");
const framesDir = path.join(project, "compositions", "frames");
fs.mkdirSync(publicDir, { recursive: true });
fs.mkdirSync(framesDir, { recursive: true });
fs.mkdirSync(path.join(project, "thumbnail"), { recursive: true });
for (const name of ["narration.wav", "narration.words.json", "narration.captions.json", "narration.exact.srt", "narration.caption-verification.json", "original-music.wav"]) {
  const source = path.join(audioRoot, name);
  if (fs.existsSync(source)) fs.copyFileSync(source, path.join(publicDir, name));
}

const commonCss = `
  @font-face{font-family:BizImpact;src:local("Impact");font-weight:400 900}
  @font-face{font-family:BizSans;src:local("Segoe UI");font-weight:400 900}
  *{box-sizing:border-box}
  #root{position:absolute;inset:0;width:1080px;height:1920px;overflow:hidden;color:#fff4dd;font-family:BizSans,Arial,sans-serif;container-type:size}
  .clip{position:absolute;inset:0}
  .ground{background:#0b0a0a;overflow:hidden}
  .ground::before{content:"";position:absolute;inset:-100px;background-image:linear-gradient(rgba(244,185,66,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(244,185,66,.1) 1px,transparent 1px);background-size:62px 62px;opacity:.65}
  .ground::after{content:"";position:absolute;left:-160px;top:260px;width:920px;height:920px;border:1px solid rgba(244,185,66,.18);border-radius:50%}
  .stage{position:absolute;inset:0;padding:150px 68px 350px;overflow:hidden}
  .label{font:800 20px/1.2 Consolas,monospace;letter-spacing:.12em;text-transform:uppercase;color:#f4b942}
  .hero{font:900 150px/.86 BizImpact,Impact,sans-serif;letter-spacing:-.035em;text-transform:lowercase}
  .hero .caps,.caps{text-transform:uppercase}
  .gold{color:#f4b942}.coral{color:#ff6b5e}.ivory{color:#fff4dd}.ink{color:#0b0a0a}
  .hairline{height:1px;background:#282726}
  .pack{position:relative;width:340px;height:430px;border:5px solid currentColor;color:#f4b942;padding:34px 28px;background:#111}
  .pack::before{content:"";position:absolute;left:26px;right:26px;top:96px;height:230px;background:repeating-linear-gradient(90deg,currentColor 0 5px,transparent 5px 15px);opacity:.5}
  .pack strong{font:900 120px/.8 BizImpact,Impact,sans-serif}.pack span{position:absolute;left:28px;bottom:28px;font:900 43px/1 BizImpact,Impact,sans-serif;text-transform:uppercase}
  .stat{font:900 132px/.84 BizImpact,Impact,sans-serif;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
  .unit{font:800 25px/1 Consolas,monospace;letter-spacing:.1em;text-transform:uppercase}
  .source{font:700 17px/1.35 Consolas,monospace;letter-spacing:.08em;color:#fff4dd;border-top:1px solid #504d48;padding-top:16px}
  .bar{height:24px;border-left:1px solid #504d48;background:#1a1918;overflow:hidden}.bar>i{display:block;height:100%;background:#f4b942;transform-origin:left}
  .nexa{position:absolute;width:520px;height:660px;object-fit:contain;filter:drop-shadow(0 24px 18px rgba(0,0,0,.55));z-index:8}
  .stamp{display:inline-block;padding:16px 20px;background:#f4b942;color:#0b0a0a;font:900 31px/1 BizImpact,Impact,sans-serif;text-transform:uppercase}
  .reaction{position:absolute;z-index:10;font:900 46px/1 BizImpact,Impact,sans-serif;text-transform:uppercase;padding:14px 18px;background:#ff6b5e;color:#0b0a0a}
`;

// The master composition owns the brand rail. Keeping branding out of nested
// scenes prevents duplicate logos and labels during cross-track transitions.
const chrome = () => "";
const nexa = (file, cls = "") => `<img class="nexa ${cls}" src="public/${file}" alt="Nexa, BizNex AI host"/>`;
const bg = (duration) => `<div class="clip ground" data-start="0" data-duration="${duration}" data-track-index="1"></div>`;

const sceneFactories = {
  hook: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<div id="h-wait" class="label" style="margin-top:95px">WAIT—</div><div id="h-pack" class="pack" style="margin-top:36px"><strong>30</strong><span>packets</span></div><div id="h-half" class="hero" style="position:absolute;left:65px;top:760px;width:900px">half the<br/>packets.</div><div id="h-more" class="hero gold" style="position:absolute;left:65px;top:1085px;width:950px"><span class="caps">more PV?</span></div><div id="h-typo" class="reaction" style="left:650px;top:1350px">typo?</div>${nexa(scene.expression, "h-nexa")}</div>`,
    css: `.h-nexa{right:-130px;top:360px}`,
    script: `
      tl.fromTo("#h-wait",{opacity:0,y:-30},{opacity:1,y:0,duration:.42,ease:"power3.out"},.05);
      tl.fromTo("#h-pack",{opacity:0,scale:.45,y:70},{opacity:1,scale:1,y:0,duration:.68,ease:"power3.out"},.22);
      tl.fromTo(".h-nexa",{opacity:0,x:130},{opacity:1,x:0,duration:.75,ease:"power3.out"},.65);
      tl.fromTo("#h-half",{opacity:0,x:-100},{opacity:1,x:0,duration:.65,ease:"power3.out"},1.25);
      const victim=document.getElementById("h-pack"),intruder=document.getElementById("h-more"),driver={p:0};
      gsap.set(intruder,{x:1080,opacity:0,rotation:8});
      tl.to(driver,{p:1,duration:.9,ease:"power3.out",onUpdate:()=>{const p=driver.p;intruder.style.transform="translateX("+(1080*(1-p))+"px) rotate("+(8*(1-p))+"deg)";intruder.style.opacity=String(Math.min(1,p*5));const vp=Math.min(1,p/.46);victim.style.transform="translateX("+(-720*vp)+"px) rotate("+(-12*vp)+"deg)";victim.style.opacity=String(1-vp);}},3.38);
      tl.fromTo("#h-typo",{opacity:0,scale:1.8,rotation:9},{opacity:1,scale:1,rotation:-3,duration:.5,ease:"power3.out"},5.2);
    `,
  }),
  thirty_pack: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<div class="label" style="margin-top:88px">ATOMY USA · CURRENT LISTING</div><div id="t-pack" class="pack" style="position:absolute;left:70px;top:310px"><strong>30</strong><span>pack</span></div><div id="t-price" style="position:absolute;left:470px;top:360px"><div class="label" data-layout-allow-overlap>price</div><div class="stat">$<b id="t-price-num">0</b></div><div class="bar" style="width:420px"><i id="t-price-bar"></i></div></div><div id="t-pv" style="position:absolute;left:70px;top:900px;width:840px"><div class="label" data-layout-allow-overlap>listed plan volume</div><div class="stat gold"><b id="t-pv-num">0</b> <span class="unit">PV</span></div><div class="bar"><i id="t-pv-bar"></i></div></div><div id="t-source" class="source" style="position:absolute;left:70px;right:70px;top:1360px">SOURCE / us.atomy.com/shop/HemoHIM<br/>CHECKED 2026-08-28</div>${nexa(scene.expression, "t-nexa")}</div>`,
    css: `.t-nexa{right:-120px;top:820px;width:440px;height:580px}`,
    script: `
      tl.fromTo("#t-pack",{opacity:0,y:150,rotateY:24},{opacity:1,y:0,rotateY:0,duration:.82,ease:"power3.out"},.15);
      tl.fromTo("#t-source",{opacity:0,scaleX:.1,transformOrigin:"left"},{opacity:1,scaleX:1,duration:.7,ease:"power3.out"},.7);
      const p={v:0};tl.to(p,{v:80,duration:1.6,ease:"power3.out",onUpdate:()=>document.getElementById("t-price-num").textContent=Math.round(p.v)},1.7);
      tl.fromTo("#t-price",{opacity:0,x:70},{opacity:1,x:0,duration:.5,ease:"power3.out"},1.65);tl.fromTo("#t-price-bar",{scaleX:0},{scaleX:.62,duration:1.6,ease:"power3.out"},1.7);
      const pv={v:0};tl.fromTo("#t-pv",{opacity:0,y:70},{opacity:1,y:0,duration:.5,ease:"power3.out"},3.75);tl.to(pv,{v:75000,duration:1.8,ease:"power3.out",onUpdate:()=>document.getElementById("t-pv-num").textContent=Math.round(pv.v).toLocaleString()},3.8);tl.fromTo("#t-pv-bar",{scaleX:0},{scaleX:.9,duration:1.8,ease:"power3.out"},3.8);
      tl.fromTo(".t-nexa",{opacity:0,x:100},{opacity:1,x:0,duration:.65,ease:"power3.out"},4.5);
    `,
  }),
  sixty_pack: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<div class="label" style="margin-top:88px">NOW COMPARE</div><div id="s-old" class="pack" style="position:absolute;left:72px;top:270px;width:210px;height:260px;opacity:.28"><strong style="font-size:75px">30</strong><span style="font-size:28px">pack</span></div><div id="s-pack" class="pack ivory" style="position:absolute;left:330px;top:260px;width:390px;height:500px"><strong>60</strong><span>standard pack</span></div><div id="s-price" style="position:absolute;left:70px;top:840px"><div class="label" data-layout-allow-overlap>price</div><div class="stat">$<b id="s-price-num">0</b></div></div><div id="s-pv" style="position:absolute;left:70px;top:1110px"><div class="label coral" data-layout-allow-overlap>but only</div><div class="stat"><b id="s-pv-num">0</b> <span class="unit">PV</span></div></div><div id="s-only" class="reaction" style="left:620px;top:1270px">less PV</div>${nexa(scene.expression, "s-nexa")}</div>`,
    css: `.s-nexa{right:-135px;top:700px}`,
    script: `
      tl.fromTo("#s-old",{opacity:0,scale:1.4},{opacity:.28,scale:1,duration:.55,ease:"power3.out"},.1);
      tl.fromTo("#s-pack",{opacity:0,y:420,rotateY:-25,scale:.82},{opacity:1,y:0,rotateY:-8,scale:1,duration:1.05,ease:"power3.out"},.35);
      const pr={v:0};tl.fromTo("#s-price",{opacity:0,x:-70},{opacity:1,x:0,duration:.45,ease:"power3.out"},1.85);tl.to(pr,{v:105,duration:1.65,ease:"power3.out",onUpdate:()=>document.getElementById("s-price-num").textContent=Math.round(pr.v)},1.9);
      const pv={v:0};tl.fromTo("#s-pv",{opacity:0,y:80},{opacity:1,y:0,duration:.45,ease:"power3.out"},4.05);tl.to(pv,{v:66000,duration:1.45,ease:"power3.out",onUpdate:()=>document.getElementById("s-pv-num").textContent=Math.round(pv.v).toLocaleString()},4.1);
      tl.fromTo("#s-only",{opacity:0,scale:1.7,rotation:7},{opacity:1,scale:1,rotation:-3,duration:.42,ease:"power3.out"},5.15);tl.fromTo(".s-nexa",{opacity:0,x:110},{opacity:1,x:0,duration:.65,ease:"power3.out"},4.6);
    `,
  }),
  pv_density: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<div id="d-plus" class="hero gold" style="margin-top:110px">+9,000 <span class="caps">PV</span></div><div id="d-token-row" style="display:flex;gap:15px;margin-top:35px">${Array.from({ length: 9 }, (_, i) => `<i class="d-token" style="width:72px;height:72px;background:#f4b942;color:#0b0a0a;display:grid;place-items:center;font:900 23px Consolas">PV</i>`).join("")}</div><div class="density-grid"><div id="d-small" class="density"><div class="label">30-pack / each packet</div><div class="stat gold"><b id="d-small-num">0</b></div><div class="unit">PV per packet</div><div class="bar"><i id="d-small-bar"></i></div></div><div id="d-large" class="density"><div class="label">60-pack / each packet</div><div class="stat"><b id="d-large-num">0</b></div><div class="unit">PV per packet</div><div class="bar"><i id="d-large-bar"></i></div></div></div><div id="d-sign" class="reaction" style="left:630px;top:1300px">more than 2×</div>${nexa(scene.expression, "d-nexa")}</div>`,
    css: `.density-grid{position:absolute;left:68px;right:68px;top:690px;display:grid;gap:75px}.density{border-top:1px solid #504d48;padding-top:22px}.d-nexa{right:-110px;top:1000px;width:420px;height:550px}`,
    script: `
      tl.fromTo("#d-plus",{opacity:0,scale:1.7,filter:"blur(12px)"},{opacity:1,scale:1,filter:"blur(0px)",duration:.62,ease:"power3.out"},.15);tl.fromTo(".d-token",{opacity:0,scale:.2,y:80},{opacity:1,scale:1,y:0,duration:.45,stagger:.07,ease:"power3.out"},.65);
      const a={v:0};tl.fromTo("#d-small",{opacity:0,x:-80},{opacity:1,x:0,duration:.5,ease:"power3.out"},2.05);tl.to(a,{v:2500,duration:1.9,ease:"power3.out",onUpdate:()=>document.getElementById("d-small-num").textContent=Math.round(a.v).toLocaleString()},2.1);tl.fromTo("#d-small-bar",{scaleX:0},{scaleX:1,duration:1.9,ease:"power3.out"},2.1);
      const b={v:0};tl.fromTo("#d-large",{opacity:0,x:80},{opacity:1,x:0,duration:.5,ease:"power3.out"},4.65);tl.to(b,{v:1100,duration:1.6,ease:"power3.out",onUpdate:()=>document.getElementById("d-large-num").textContent=Math.round(b.v).toLocaleString()},4.7);tl.fromTo("#d-large-bar",{scaleX:0},{scaleX:.44,duration:1.6,ease:"power3.out"},4.7);
      tl.fromTo("#d-sign",{opacity:0,scale:1.5,rotation:8},{opacity:1,scale:1,rotation:-2,duration:.45,ease:"power3.out"},6.15);tl.fromTo(".d-nexa",{opacity:0,x:100},{opacity:1,x:0,duration:.6,ease:"power3.out"},5.6);
    `,
  }),
  price_twist: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<div id="p-deal" class="hero gold" style="margin-top:115px"><span class="caps">better deal?</span></div><div id="p-stop" class="reaction" style="left:610px;top:490px">don't rush</div>${nexa(scene.expression, "p-nexa")}<div class="price-grid"><div id="p-large"><div class="label">60-pack</div><div class="stat gold">$1.75</div><div class="unit">per packet</div><div class="bar"><i id="p-large-bar"></i></div></div><div id="p-small"><div class="label">30-pack</div><div class="stat">≈ $2.67</div><div class="unit">per packet</div><div class="bar"><i id="p-small-bar"></i></div></div></div><div id="p-winner" class="stamp" style="position:absolute;left:70px;top:1390px">shopping value → 60-pack</div></div>`,
    css: `.p-nexa{right:-105px;top:350px}.price-grid{position:absolute;left:70px;right:70px;top:790px;display:grid;gap:90px}.price-grid>div{border-top:1px solid #504d48;padding-top:24px}`,
    script: `
      tl.fromTo("#p-deal",{opacity:0,y:-100,scale:.7},{opacity:1,y:0,scale:1,duration:.65,ease:"power3.out"},.15);tl.fromTo("#p-deal",{y:0},{y:-32,duration:.35,ease:"power2.in"},1.65);
      tl.fromTo(".p-nexa",{opacity:0,x:130},{opacity:1,x:0,duration:.72,ease:"power3.out"},2.05);tl.fromTo("#p-stop",{opacity:0,x:470,rotation:10},{opacity:1,x:0,rotation:-3,duration:.62,ease:"power3.out"},2.2);tl.to("#p-deal",{x:-940,opacity:0,rotation:-11,duration:.5,ease:"power3.in"},2.2);
      tl.fromTo("#p-large",{opacity:0,x:-100},{opacity:1,x:0,duration:.5,ease:"power3.out"},4.6);tl.fromTo("#p-large-bar",{scaleX:0},{scaleX:.66,duration:1.7,ease:"power3.out"},4.65);
      tl.fromTo("#p-small",{opacity:0,x:100},{opacity:1,x:0,duration:.5,ease:"power3.out"},7.05);tl.fromTo("#p-small-bar",{scaleX:0},{scaleX:1,duration:1.45,ease:"power3.out"},7.1);tl.fromTo("#p-winner",{opacity:0,y:60},{opacity:1,y:0,duration:.48,ease:"power3.out"},8.65);
    `,
  }),
  scoreboards: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<div id="b-family" class="label" style="margin-top:90px">SAME PRODUCT FAMILY</div><div id="b-title" class="hero" style="margin-top:28px">two<br/><span class="gold">scoreboards.</span></div><div class="boards"><div id="b-shop" class="board"><div class="label">shopping value</div><div class="board-main">cost / packet</div><div class="stat gold">$1.75</div></div><div id="b-plan" class="board orange"><div class="label ink">plan tracking</div><div class="board-main ink"><span class="caps">PV</span></div><div class="unit ink">market-specific</div></div></div><div id="b-warning" class="warning"><b><span class="caps">PV</span> is not cash</b><span>or guaranteed income</span></div><div id="b-market" class="source" style="position:absolute;left:70px;right:70px;top:1430px">MARKET + LISTING CAN CHANGE · VERIFY CURRENT LOCAL MATERIAL</div>${nexa(scene.expression, "b-nexa")}</div>`,
    css: `.boards{position:absolute;left:70px;right:70px;top:650px;display:grid;gap:38px;perspective:1600px}.board{height:310px;border:1px solid #504d48;padding:35px;background:#0b0a0a;transform-style:preserve-3d}.board.orange{background:#f4b942;color:#0b0a0a}.board-main{font:900 75px/.95 BizImpact,Impact,sans-serif;text-transform:lowercase;margin-top:30px}.warning{position:absolute;left:70px;right:70px;top:1250px;background:#ff6b5e;color:#0b0a0a;padding:22px 30px}.warning b{display:block;font:900 56px/1 BizImpact,Impact,sans-serif;text-transform:lowercase}.warning>span{display:block;margin-top:12px;font:800 23px Consolas,monospace;text-transform:uppercase}.b-nexa{right:-160px;top:1010px;width:380px;height:500px}`,
    script: `
      tl.fromTo("#b-family",{opacity:0,y:-30},{opacity:1,y:0,duration:.5,ease:"power3.out"},.1);tl.fromTo("#b-title",{opacity:0,x:-100},{opacity:1,x:0,duration:.75,ease:"power3.out"},.55);
      tl.fromTo("#b-shop",{opacity:0,x:-500,rotateY:24,scale:.88},{opacity:1,x:0,rotateY:8,scale:1,duration:.9,ease:"power3.out"},2.05);tl.fromTo("#b-plan",{opacity:0,x:500,rotateY:-24,scale:.88},{opacity:.78,x:0,rotateY:-8,scale:1,duration:.9,ease:"power3.out"},2.25);
      tl.to("#b-shop",{borderColor:"#f4b942",duration:.45,ease:"power3.out"},4.65);tl.to("#b-plan",{opacity:1,duration:.5,ease:"power3.out"},7.25);
      tl.fromTo("#b-warning",{opacity:0,x:900,rotation:6},{opacity:1,x:0,rotation:-1,duration:.7,ease:"power3.out"},9.55);tl.fromTo(".b-nexa",{opacity:0,x:140},{opacity:1,x:0,duration:.65,ease:"power3.out"},9.75);tl.fromTo("#b-market",{opacity:0,y:40},{opacity:1,y:0,duration:.45,ease:"power3.out"},11.35);
    `,
  }),
  loop_cta: (scene, duration, index) => ({
    body: `${bg(duration)}<div class="stage">${chrome(index + 1)}<img id="c-logo" src="public/biznex-logo.png" alt="BizNex"/><div id="c-follow" class="hero" style="position:absolute;left:70px;top:410px">follow<br/><span class="gold">biznex.</span></div><div id="c-next" class="label" style="position:absolute;left:70px;top:920px;font-size:30px">THE NEXT ODD DETAIL STARTS WITH…</div><div id="c-half" class="hero" style="position:absolute;left:70px;top:1070px">half the<br/>packets.</div><div id="c-more" class="reaction" style="left:590px;top:1370px"><span class="caps">more PV?</span></div>${nexa(scene.expression, "c-nexa")}</div>`,
    css: `#c-logo{position:absolute;left:70px;top:240px;width:150px;height:150px;object-fit:contain}.c-nexa{right:-120px;top:450px}`,
    script: `
      tl.fromTo("#c-logo",{opacity:0,scale:.2,rotation:-25},{opacity:1,scale:1,rotation:0,duration:.65,ease:"power3.out"},.1);tl.fromTo("#c-follow",{opacity:0,x:-130,filter:"blur(14px)"},{opacity:1,x:0,filter:"blur(0px)",duration:.7,ease:"power3.out"},.35);tl.fromTo(".c-nexa",{opacity:0,x:130},{opacity:1,x:0,duration:.7,ease:"power3.out"},.7);
      tl.fromTo("#c-next",{opacity:0,scaleX:0,transformOrigin:"left"},{opacity:1,scaleX:1,duration:1.5,ease:"steps(16)"},2.0);tl.fromTo("#c-half",{opacity:0,y:160},{opacity:1,y:0,duration:.55,ease:"power3.out"},4.15);tl.fromTo("#c-more",{opacity:0,scale:1.8,rotation:7},{opacity:1,scale:1,rotation:-3,duration:.42,ease:"power3.out"},5.55);
      tl.to("#c-follow,#c-next,#c-logo,.c-nexa",{opacity:0,duration:.18,ease:"none"},4.12);
    `,
  }),
};

const makeFrame = (scene, index) => {
  const duration = durations[index];
  const factory = sceneFactories[scene.kind];
  if (!factory) throw new Error(`Unknown BizNex Short scene kind: ${scene.kind}`);
  const shot = factory(scene, duration, index);
  const body = shot.body.replace('<div class="clip ground"', `<div id="frame-${scene.id}-ground" class="clip ground"`);
  const sceneScript = shot.script.trim();
  return `<template>
  <style>${commonCss}${shot.css}</style>
  <div id="root" data-composition-id="${scene.id}" data-start="0" data-duration="${duration}" data-width="1080" data-height="1920">
    ${body}
  </div>
  <script>
    window.__timelines=window.__timelines||{};
    const tl=gsap.timeline({paused:true});
    ${sceneScript}
    window.__timelines["${scene.id}"]=tl;
  </script>
</template>`;
};

spec.scenes.forEach((scene, index) => {
  fs.writeFileSync(path.join(framesDir, `${scene.id}.html`), makeFrame(scene, index));
});

const captionHtml = captions
  .map((cue, index) => {
    const highlighted = escapeHtml(cue.text).replace(
      /\b(HemoHIM|Atomy|PV|30-pack|60-pack|cash|guaranteed income)\b/gi,
      '<span class="caption-key">$1</span>',
    );
    return `<div id="caption-${String(index + 1).padStart(3, "0")}" class="clip caption" data-start="${Number(cue.start).toFixed(4)}" data-duration="${(Number(cue.end) - Number(cue.start)).toFixed(4)}" data-track-index="30" data-layout-allow-caption-zone><span>${highlighted}</span></div>`;
  })
  .join("\n");

const sceneHtml = spec.scenes
  .map(
    (scene, index) => `<div id="el-${scene.id}" class="clip scene-slot" data-composition-id="${scene.id}" data-composition-src="compositions/frames/${scene.id}.html" data-start="${starts[index].toFixed(4)}" data-duration="${durations[index].toFixed(4)}" data-track-index="${index + 1}" data-width="1080" data-height="1920"></div>`,
  )
  .join("\n");

const sfxHtml = spec.scenes
  .flatMap((scene, index) =>
    scene.sfx.map((file, cueIndex) => {
      const offset = cueIndex === 0 ? 0.08 : Math.min(Math.max(1.2, durations[index] * 0.55), durations[index] - 0.4);
      const duration = mediaDuration(path.join(publicDir, file));
      return `<audio id="sfx-${index + 1}-${cueIndex + 1}" src="public/${file}" data-start="${(starts[index] + offset).toFixed(3)}" data-duration="${duration.toFixed(3)}" data-track-index="22" data-volume="0.16"></audio>`;
    }),
  )
  .join("\n");

const indexHtml = `<!doctype html>
<html lang="en" data-resolution="portrait">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=1080,height=1920"/><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>
*{margin:0;padding:0;box-sizing:border-box}html,body{width:1080px;height:1920px;overflow:hidden;background:#0b0a0a}#root{position:absolute;inset:0;width:1080px;height:1920px;overflow:hidden;background:#0b0a0a}.clip{position:absolute;inset:0}.scene-slot{overflow:hidden}.brand-rail{position:absolute;left:34px;right:34px;top:24px;height:74px;z-index:80;display:flex;align-items:center;justify-content:space-between;color:#fff4dd;font:800 17px Consolas,monospace;letter-spacing:.1em;pointer-events:none}.episode{border:1px solid rgba(244,185,66,.45);padding:10px 14px;color:#f4b942}.caption{left:48px;right:120px;top:auto;bottom:205px;min-height:130px;z-index:100;display:flex;align-items:center;justify-content:center;text-align:center;pointer-events:none}.caption>span{display:inline-block;max-width:890px;padding:18px 24px 21px;background:rgba(5,5,5,.94);border-left:7px solid #f4b942;color:#fff;font:800 48px/1.18 "Segoe UI",Arial,sans-serif;text-shadow:0 2px 2px #000}.caption-key{color:#f4b942}.progress{position:absolute;left:34px;right:34px;top:106px;height:5px;background:rgba(255,255,255,.12);z-index:90}.progress i{display:block;width:100%;height:100%;background:#f4b942;transform:scaleX(0);transform-origin:left}
</style></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="${totalDuration.toFixed(3)}" data-width="1080" data-height="1920">
${sceneHtml}
<audio id="narration" src="public/narration.wav" data-start="0" data-duration="${narrationSeconds.toFixed(3)}" data-track-index="20" data-volume="1"></audio>
<audio id="music" src="public/original-music.wav" data-start="0" data-duration="${totalDuration.toFixed(3)}" data-track-index="21" data-volume="0.16"></audio>
${sfxHtml}
${captionHtml}
<div class="brand-rail"><span>BIZNEX // AI-BUILT SERIES</span><span class="episode">${escapeHtml(spec.episode_label)}</span></div><div class="progress"><i id="progress-fill"></i></div>
</div><script>window.__timelines=window.__timelines||{};
window.__timelines["main"] = gsap.timeline({ paused: true });
const tl=window.__timelines["main"];tl.to("#progress-fill",{scaleX:1,duration:${totalDuration.toFixed(3)},ease:"none"},0);</script></body></html>`;
fs.writeFileSync(path.join(project, "index.html"), indexHtml);

const thumbnailHtml = `<!doctype html><html lang="en"><head><meta charset="UTF-8"/><style>*{box-sizing:border-box}html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#0b0a0a}.thumb{position:absolute;inset:0;background:#0b0a0a;color:#fff4dd;font-family:Impact,"Arial Narrow",sans-serif;overflow:hidden}.thumb::before{content:"";position:absolute;inset:-100px;background:repeating-linear-gradient(90deg,rgba(244,185,66,.09) 0 1px,transparent 1px 56px)}.copy{position:absolute;left:52px;top:50px;width:760px}.kicker{font:800 20px Consolas,monospace;letter-spacing:.12em;color:#f4b942}.copy h1{margin:28px 0 0;font-size:112px;line-height:.82;letter-spacing:-.03em;text-transform:lowercase}.copy h1 b{color:#f4b942}.pack{position:absolute;left:550px;bottom:48px;width:195px;height:230px;border:5px solid #f4b942;color:#f4b942;padding:18px}.pack strong{font-size:86px}.pack span{position:absolute;left:18px;bottom:16px;font-size:28px;text-transform:uppercase}.nexa{position:absolute;right:-30px;bottom:-80px;width:580px;height:720px;object-fit:contain;filter:drop-shadow(0 20px 18px #000)}.stamp{position:absolute;right:48px;top:50px;background:#ff6b5e;color:#0b0a0a;padding:14px 18px;font:900 26px Impact;transform:rotate(3deg)}.logo{position:absolute;left:52px;bottom:46px;width:64px;height:64px}</style></head><body><div class="thumb"><div class="copy"><div class="kicker">ATOMY HEMOHIM · SOURCE CHECK</div><h1>half the packs.<br/><b>more PV?</b></h1></div><div class="pack"><strong>30</strong><span>packets</span></div><img class="nexa" src="../public/nexa-v2-surprised.png"/><div class="stamp">THIS LOOKS BACKWARDS</div><img class="logo" src="../public/biznex-logo.png"/></div></body></html>`;
fs.writeFileSync(path.join(project, "thumbnail", "thumbnail.html"), thumbnailHtml);

fs.writeFileSync(
  path.join(project, "index.motion.json"),
  JSON.stringify(
    {
      duration: totalDuration,
      assertions: [
        { kind: "appearsBy", selector: "#el-01-half-the-packs", bySec: 0.1 },
        { kind: "appearsBy", selector: "#progress-fill", bySec: 1 },
        { kind: "staysInFrame", selector: "#progress-fill" },
        { kind: "keepsMoving", withinSelector: "#root", maxStaticSec: 5.2 },
      ],
    },
    null,
    2,
  ) + "\n",
);

const timingOutput = spec.scenes.map((scene, index) => ({
  id: scene.id,
  start: starts[index],
  duration: durations[index],
  end: Number((starts[index] + durations[index]).toFixed(3)),
}));
fs.writeFileSync(path.join(project, "scene-timings.json"), JSON.stringify(timingOutput, null, 2) + "\n");
console.log(`Built ${spec.scenes.length} vertical scenes, ${captions.length} exact caption cues, ${totalDuration.toFixed(3)}s total.`);
