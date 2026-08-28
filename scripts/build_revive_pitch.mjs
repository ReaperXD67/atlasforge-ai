import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..");
const project = path.join(repo, "videos", "biznex-revive-pitch-001");
const captures = path.join(repo, "output", "revive-pitch", "captures");
const audioSource = path.join(repo, "output", "revive-pitch", "audio", "narration.wav");
const musicSource = path.join(repo, "output", "revive-pitch", "audio", "revive-score.wav");
const expressionSource = path.join(repo, "assets", "biznex", "nexa-expressions");
const assets = path.join(project, "assets");
const compositions = path.join(project, "compositions");
const thumbnailAssets = path.join(project, "thumbnail", "assets");
const deliverables = path.join(repo, "output", "revive-pitch", "deliverables");
for (const directory of [assets, compositions, deliverables, thumbnailAssets]) {
  fs.mkdirSync(directory, { recursive: true });
}

const required = [audioSource, musicSource];
for (const source of required) {
  if (!fs.existsSync(source)) throw new Error(`Missing required source: ${source}`);
}
fs.copyFileSync(audioSource, path.join(assets, "narration.wav"));
fs.copyFileSync(musicSource, path.join(assets, "revive-score.wav"));

const captureFiles = fs.existsSync(captures)
  ? fs.readdirSync(captures).filter((name) => /\.(png|jpe?g|webp)$/i.test(name))
  : [];
for (const name of captureFiles) fs.copyFileSync(path.join(captures, name), path.join(assets, name));

const expressions = ["concerned", "questioning", "idea", "analytical", "explaining", "focused", "warning", "confident", "reassuring", "urgent", "closing"];
for (const expression of expressions) {
  const name = `nexa-v2-${expression}.png`;
  fs.copyFileSync(path.join(expressionSource, name), path.join(assets, name));
}
fs.copyFileSync(path.join(assets, "01-command-center.png"), path.join(thumbnailAssets, "01-command-center.png"));
fs.copyFileSync(path.join(assets, "nexa-v2-confident.png"), path.join(thumbnailAssets, "nexa-v2-confident.png"));

const duration = 300;
const narrationDuration = 294.384;
const narrationStart = 0.7;
// Starts follow the mastered paragraph boundaries so the evidence changes with the spoken topic.
// The final scene absorbs the natural closing hold and the master remains exactly five minutes.
const sceneStarts = [0, 18.14, 40.7, 58.14, 86.86, 111.48, 144.3, 182.25, 204.31, 229.44, 256.11, 279.7];
const sceneDurations = sceneStarts.map((start,index)=>
  (index < sceneStarts.length - 1 ? sceneStarts[index + 1] : duration) - start,
);
const transition = 0.42;

const escapeHtml = (value) => value
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

const sharedCss = `
  *{box-sizing:border-box} #root{position:absolute;inset:0;width:1920px;height:1080px;overflow:hidden;background:#17201d;color:#f4f6f2;font-family:Inter,"Segoe UI",Arial,sans-serif}
  .bg{position:absolute;inset:0;background:radial-gradient(circle at 78% 18%,rgba(216,255,79,.12),transparent 34%),linear-gradient(145deg,#17201d,#101714 65%,#0c110f)}
  .grid{position:absolute;inset:-160px;opacity:.12;background-image:linear-gradient(rgba(216,255,79,.25) 1px,transparent 1px),linear-gradient(90deg,rgba(216,255,79,.25) 1px,transparent 1px);background-size:74px 74px;transform:rotate(-5deg)}
  .chapter{position:absolute;left:74px;top:58px;color:#d8ff4f;font:800 18px/1.1 Consolas,monospace;letter-spacing:.13em;text-transform:uppercase}
  .title{position:absolute;left:74px;top:104px;max-width:1280px;font:820 64px/.98 Inter,"Segoe UI",sans-serif;letter-spacing:-.045em}
  .title em{color:#d8ff4f;font-style:normal}.sub{position:absolute;left:78px;top:245px;max-width:1120px;color:#b8c2bd;font:520 27px/1.35 Inter,"Segoe UI",sans-serif}
  .truth{position:absolute;right:65px;top:58px;padding:11px 16px;border:1px solid rgba(216,255,79,.4);border-radius:999px;background:#111815;color:#d8ff4f;font:750 15px Consolas,monospace;letter-spacing:.06em;text-transform:uppercase}
  .shot-wrap{position:absolute;left:74px;right:400px;top:326px;height:650px;border-radius:25px;overflow:hidden;background:#0a0f0d;border:1px solid rgba(244,246,242,.18);box-shadow:0 36px 90px rgba(0,0,0,.42)}
  .shot{position:absolute;width:100%;height:100%;object-fit:cover;object-position:top left;transform-origin:center top}.shot + .shot{opacity:0}
  .shot-wrap.contain .shot{object-fit:contain;object-position:center;background:#0a0f0d}
  .shot-label{position:absolute;left:24px;top:22px;z-index:5;padding:9px 13px;border-radius:9px;background:rgba(11,18,15,.92);color:#d8ff4f;font:750 14px Consolas,monospace;letter-spacing:.08em}
  .nexa{position:absolute;right:58px;bottom:0;width:440px;height:720px;z-index:7;filter:drop-shadow(0 30px 38px rgba(0,0,0,.48));pointer-events:none}.nexa img{width:100%;height:100%;object-fit:contain;object-position:center bottom}
  .nexa.left{left:50px;right:auto}
  .diagram{position:absolute;left:74px;right:440px;top:350px;height:560px;display:flex;align-items:center;justify-content:center;gap:20px}.card{position:relative;min-width:250px;max-width:340px;padding:30px;border-radius:22px;background:#f4f6f2;color:#17201d;box-shadow:0 24px 55px rgba(0,0,0,.28)}
  .card b{display:block;color:#17201d;font:850 28px/1.1 Inter,"Segoe UI",sans-serif}.card small{display:block;margin-top:12px;color:#46524d;font:600 18px/1.3 Inter,"Segoe UI",sans-serif}.card.danger{border-top:8px solid #ff7a68}.card.safe{border-top:8px solid #d8ff4f}.arrow{font:900 48px Inter;color:#d8ff4f}.path{position:absolute;left:110px;right:110px;bottom:105px;height:5px;background:#39453f}.path::after{content:"";position:absolute;left:0;top:0;width:100%;height:100%;background:#d8ff4f;transform-origin:left;transform:scaleX(0)}
  .metric{font:900 62px/.95 Inter;color:#17201d;letter-spacing:-.04em}.badge{display:inline-block;margin-top:18px;padding:7px 10px;border-radius:8px;background:#17201d;color:#d8ff4f;font:700 13px Consolas,monospace}
  .end{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}.end h1{font:900 94px/.94 Inter;letter-spacing:-.06em}.end h1 em{display:block;color:#d8ff4f;font-style:normal}.end p{margin-top:34px;color:#bac5bf;font:600 25px/1.5 Consolas,monospace}.end .mark{width:124px;height:124px;margin-bottom:32px;border:4px solid #d8ff4f;border-radius:50%;display:grid;place-items:center;color:#d8ff4f;font:900 58px Inter}
`;

const scenes = [
  {id:"cold-open",file:"01-cold-open.html",chapter:"01 · PAYMENT FAILURE",title:"A failed payment should not become a <em>lost customer.</em>",sub:"Route the reason—not the customer—toward the right recovery decision.",expression:"concerned",body:`<div class="diagram"><div class="card danger"><b>Low balance</b><small>Time the retry</small></div><div class="card danger"><b>Mandate revoked</b><small>Repair consent</small></div><div class="card danger"><b>Card expired</b><small>Update method</small></div><div class="arrow">→</div><div class="card safe"><b>Revive</b><small>Explainable next action</small></div></div>`,script:`tl.from(".card",{opacity:0,y:45,duration:.55,stagger:.22,ease:"power3.out"},.4);tl.from(".arrow",{opacity:0,x:-25,duration:.4},1.5);tl.from(".nexa",{opacity:0,x:80,duration:.6},1.8);`},
  {id:"problem",file:"02-problem.html",chapter:"02 · THE PROBLEM",title:"Different failures need different <em>decisions.</em>",sub:"One retry rule cannot safely handle five different causes.",expression:"questioning",body:`<div class="diagram"><div class="card danger"><b>Pending</b><small>Retry window begins</small></div><div class="arrow">→</div><div class="card danger"><b>Retries</b><small>Same treatment repeats</small></div><div class="arrow">→</div><div class="card danger"><b>Halted</b><small>Revenue and trust erode</small></div></div>`,script:`tl.from(".card,.arrow",{opacity:0,x:-35,duration:.5,stagger:.2,ease:"power3.out"},.5);tl.from(".nexa",{opacity:0,x:70,duration:.55},1.3);`},
  {id:"thesis",file:"03-thesis.html",chapter:"03 · THE THESIS",title:"Understand. Decide. Guard. <em>Measure.</em>",sub:"A signed failure event becomes a policy-safe plan and inspectable proof.",expression:"idea",body:`<div class="diagram"><div class="card safe"><b>Understand</b><small>Classify the failure</small></div><div class="arrow">→</div><div class="card safe"><b>Decide</b><small>Rank recovery paths</small></div><div class="arrow">→</div><div class="card safe"><b>Guard</b><small>Enforce hard policies</small></div><div class="arrow">→</div><div class="card safe"><b>Measure</b><small>Prove incrementality</small></div></div>`,script:`tl.from(".card,.arrow",{opacity:0,y:34,duration:.45,stagger:.16,ease:"power3.out"},.45);tl.from(".nexa",{opacity:0,scale:.97,duration:.6},1.4);`},
  {id:"command",file:"04-command.html",chapter:"04 · COMMAND CENTER",title:"Safe autonomy has a <em>visible boundary.</em>",sub:"A messy queue becomes an operating system for recovery.",truth:"Simulated portfolio · live backend",expression:"analytical",shots:["01-command-center.png","02-agent-plan.png"],script:`tl.from(".shot-wrap",{opacity:0,y:40,duration:.65,ease:"power3.out"},.4);tl.from(".nexa",{opacity:0,x:65,duration:.6},1);tl.to(".shot-a",{opacity:0,duration:.35},15);tl.to(".shot-b",{opacity:1,duration:.35},15);`},
  {id:"case",file:"05-case.html",chapter:"05 · EXPLAINABILITY",title:"Every recommendation shows <em>its work.</em>",sub:"Evidence, confidence, policy version, schedule, and override stay inspectable.",truth:"Simulated customer case",expression:"explaining",shots:["03-recovery-case.png"],script:`tl.from(".shot-wrap",{opacity:0,x:-50,duration:.65,ease:"power3.out"},.4);tl.from(".nexa",{opacity:0,x:70,duration:.6},1);tl.to(".shot",{scale:1.07,x:-40,y:-20,duration:27,ease:"none"},1);`},
  {id:"live",file:"06-live.html",chapter:"06 · LIVE API FLOW",title:"The interface waits for <em>valid proof.</em>",sub:"Runtime validation → reasoning → deterministic guardrails → private audit record.",truth:"Simulation · no payment or message",expression:"focused",fit:"contain",shots:["04-live-demo-ready.png","05-live-demo-result.png"],script:`tl.from(".shot-wrap",{opacity:0,y:35,duration:.6},.35);tl.from(".nexa",{opacity:0,x:70,duration:.6},.9);tl.to(".shot-a",{opacity:0,duration:.3},15);tl.to(".shot-b",{opacity:1,duration:.3},15);`},
  {id:"proof",file:"07-proof.html",chapter:"07 · SYSTEM PROOF",title:"Duplicate-safe recovery is <em>inspectable.</em>",sub:"The hosted API stores the first request and suppresses the identical replay.",truth:"Live hosted evidence",expression:"warning",shots:["06-system-proof.png","07-duplicate-proof.png","08-decision-approval.png"],script:`tl.from(".shot-wrap",{opacity:0,scale:.985,duration:.55},.3);tl.from(".nexa",{opacity:0,x:65,duration:.55},.8);tl.to(".shot-a",{opacity:0,duration:.28},12);tl.to(".shot-b",{opacity:1,duration:.28},12);tl.to(".shot-b",{opacity:0,duration:.28},26);tl.to(".shot-c",{opacity:1,duration:.28},26);`},
  {id:"agents",file:"08-agents.html",chapter:"08 · GUARDED AGENTS",title:"Models recommend. <em>Policies authorize.</em>",sub:"Specialist stages have narrow responsibilities and deterministic stops.",truth:"Guardrails enforced",expression:"confident",shots:["10-agent-playbooks.png"],script:`tl.from(".shot-wrap",{opacity:0,x:-45,duration:.6},.3);tl.from(".nexa",{opacity:0,x:70,duration:.55},.9);tl.to(".shot",{scale:1.055,duration:23,ease:"none"},1);`},
  {id:"measure",file:"09-measure.html",chapter:"09 · INCREMENTALITY",title:"Measure uplift—not <em>retry volume.</em>",sub:"Treatment, holdout, confidence, and segment effects stay explicit.",truth:"Experiment values simulated",expression:"reassuring",shots:["11-experiments.png"],script:`tl.from(".shot-wrap",{opacity:0,y:35,duration:.6},.3);tl.from(".nexa",{opacity:0,x:60,duration:.55},.9);tl.to(".shot",{scale:1.06,x:-28,duration:21,ease:"none"},1);`},
  {id:"audit",file:"10-audit.html",chapter:"10 · AUDIT + SECURITY",title:"Trace input → policy → action → <em>proof.</em>",sub:"HMAC verification, immutable records, strict limits, and fail-closed behavior.",truth:"Portfolio totals simulated · live record count",expression:"urgent",shots:["12-audit-trail.png","14-health-api.png"],script:`tl.from(".shot-wrap",{opacity:0,x:-40,duration:.6},.3);tl.from(".nexa",{opacity:0,x:70,duration:.55},.9);tl.to(".shot-a",{opacity:0,duration:.3},12);tl.to(".shot-b",{opacity:1,duration:.3},12);`},
  {id:"architecture",file:"11-architecture.html",chapter:"11 · HONEST BOUNDARY",title:"Strong demo today. <em>Pilot roadmap next.</em>",sub:"Auth, tenant isolation, test-mode adapters, outbox workers, limits, observability, retention, and incident controls.",truth:"Public engineering demonstration",expression:"focused",shots:["13-proof-api.png","15-github-repository.png"],script:`tl.from(".shot-wrap",{opacity:0,y:35,duration:.6},.3);tl.from(".nexa",{opacity:0,x:65,duration:.55},.85);tl.to(".shot-a",{opacity:0,duration:.3},9);tl.to(".shot-b",{opacity:1,duration:.3},9);`},
  {id:"close",file:"12-close.html",chapter:"12 · REVIVE",title:"",sub:"",expression:"closing",body:`<div class="end"><div class="mark">R</div><h1>Recover revenue.<em>Retain trust.</em></h1><p>revive-revenue.vercel.app<br/>github.com/ReaperXD67/revive-ai</p></div>`,script:`tl.from(".mark",{opacity:0,scale:.7,duration:.5,ease:"back.out(1.5)"},.2);tl.from(".end h1,.end p",{opacity:0,y:35,duration:.6,stagger:.2},.55);tl.from(".nexa",{opacity:0,x:70,duration:.6},1.2);`},
];

function sceneHtml(scene,index){
  const durationHere=sceneDurations[index];
  const truth=scene.truth??(index<3?"Customer-first recovery":"Revive product proof");
  const shots=(scene.shots??[]).map((name,i)=>`<img class="shot shot-${String.fromCharCode(97+i)}" src="assets/${name}" alt="Revive product evidence"/>`).join("");
  const shotBlock=shots?`<div class="shot-wrap ${scene.fit??""}" data-layout-allow-overflow><div class="shot-label">${escapeHtml(truth)}</div>${shots}</div>`:"";
  const host=scene.expression?`<div class="nexa"><img src="assets/nexa-v2-${scene.expression}.png" alt="Nexa static presenter"/></div>`:"";
  return `<!doctype html><html><head><meta charset="UTF-8"></head><body><template><style>${sharedCss}</style><div id="root" data-composition-id="${scene.id}" data-start="0" data-duration="${durationHere}" data-width="1920" data-height="1080"><div class="bg"></div><div class="grid"></div><div class="chapter">${scene.chapter}</div>${scene.title?`<div class="title">${scene.title}</div>`:""}${scene.sub?`<div class="sub">${scene.sub}</div>`:""}<div class="truth">${escapeHtml(truth)}</div>${scene.body??shotBlock}${host}</div><script>window.__timelines=window.__timelines||{};const root=document.querySelector('[data-composition-id="${scene.id}"]');const tl=gsap.timeline({paused:true});tl.from(".chapter,.title,.sub,.truth",{opacity:0,y:-20,duration:.48,stagger:.08,ease:"power3.out"},.05);tl.to(".grid",{x:55,y:22,duration:${durationHere},ease:"none"},0);${scene.script}window.__timelines["${scene.id}"]=tl;</script></template></body></html>`;
}
scenes.forEach((scene,index)=>fs.writeFileSync(path.join(compositions,scene.file),sceneHtml(scene,index)));

const narration = fs.readFileSync(path.join(repo,"docs","biznex","revive-pitch-narration.txt"),"utf8").trim();
const words=narration.replace(/\s+/g," ").split(" ");
const groups=[]; for(let i=0;i<words.length;i+=12) groups.push(words.slice(i,i+12).join(" "));
const raw=groups.map((text,i)=>({text,start:narrationStart+narrationDuration*i/groups.length,end:narrationStart+narrationDuration*(i+1)/groups.length}));
const captions=[]; let pending=[];
for(const cue of raw){pending.push(cue);if(cue.end-pending[0].start>=5){captions.push({text:pending.map(x=>x.text).join(" "),start:pending[0].start,end:cue.end});pending=[];}}
if(pending.length){const previous=captions.pop();captions.push({text:[previous.text,...pending.map(x=>x.text)].join(" "),start:previous.start,end:pending.at(-1).end});}

const ts=(seconds,separator=",")=>{const ms=Math.max(0,Math.round(seconds*1000));const h=Math.floor(ms/3600000);const m=Math.floor(ms%3600000/60000);const s=Math.floor(ms%60000/1000);const milli=ms%1000;return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}${separator}${String(milli).padStart(3,"0")}`;};
const srt=captions.map((cue,i)=>`${i+1}\n${ts(cue.start)} --> ${ts(cue.end)}\n${cue.text}`).join("\n\n")+"\n";
fs.writeFileSync(path.join(deliverables,"revive-five-minute-pitch.srt"),srt);

const sceneMarkup=scenes.map((scene,i)=>`<div id="slot-${scene.id}" class="clip scene" data-composition-id="${scene.id}" data-composition-src="compositions/${scene.file}" data-start="${sceneStarts[i]}" data-duration="${sceneDurations[i]+(i<scenes.length-1?transition:0)}" data-track-index="${i+1}" data-width="1920" data-height="1080" style="z-index:${10+i}"></div>`).join("");
const captionMarkup=captions.map((cue,i)=>`<div id="caption-${i+1}" class="clip caption" data-start="${cue.start.toFixed(3)}" data-duration="${(cue.end-cue.start).toFixed(3)}" data-track-index="30" data-layout-allow-caption-zone><span>${escapeHtml(cue.text)}</span></div>`).join("");
const transitions=sceneStarts.slice(1).map((start,i)=>`tl.fromTo("#slot-${scenes[i+1].id}",{clipPath:"inset(0 100% 0 0)",filter:"brightness(1.3)"},{clipPath:"inset(0 0% 0 0)",filter:"brightness(1)",duration:${transition},ease:"power3.inOut"},${start});`).join("");
const index=`<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1920,height=1080"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box}html,body,#root{width:1920px;height:1080px;overflow:hidden;background:#17201d;font-family:Inter,"Segoe UI",sans-serif}.clip{position:absolute;inset:0}.scene{overflow:hidden}.caption{inset:auto 150px 34px;z-index:100;display:flex;justify-content:center;align-items:flex-end;text-align:center;pointer-events:none}.caption span{max-width:1500px;padding:14px 25px 16px;border-radius:15px;background:rgba(8,13,11,.92);box-shadow:0 13px 36px rgba(0,0,0,.4);color:#fff;font:700 34px/1.22 Inter,"Segoe UI",sans-serif}.rail{position:absolute;left:55px;right:55px;top:28px;z-index:95;display:flex;justify-content:space-between;pointer-events:none;color:#d8ff4f;font:750 14px Consolas,monospace;letter-spacing:.1em}.progress{position:absolute;left:0;right:0;bottom:0;height:6px;background:#2c3732;z-index:120}.progress div{height:100%;background:#d8ff4f;transform:scaleX(0);transform-origin:left}</style></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="300" data-width="1920" data-height="1080">${sceneMarkup}<audio id="narration" src="assets/narration.wav" data-start="${narrationStart}" data-duration="${narrationDuration}" data-track-index="40" data-volume="1"></audio><audio id="music" src="assets/revive-score.wav" data-start="0" data-duration="300" data-track-index="41" data-volume="0.055"></audio>${captionMarkup}<div class="rail" data-layout-ignore><span>BIZNEX // PRODUCT PROOF</span><span>REVIVE · BUILDATHON PITCH</span></div><div class="progress" data-layout-ignore><div id="p"></div></div></div><script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});${transitions}tl.to("#p",{scaleX:1,duration:300,ease:"none"},0);window.__timelines.main=tl;</script></body></html>`;
fs.writeFileSync(path.join(project,"index.html"),index);

const thumbnail=`<!doctype html><html><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>*{box-sizing:border-box}html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#17201d;font-family:Inter,"Segoe UI",sans-serif}#root{position:absolute;inset:0;width:1280px;height:720px;overflow:hidden;background:radial-gradient(circle at 74% 25%,rgba(216,255,79,.17),transparent 37%),#17201d;color:#f4f6f2}.shot{position:absolute;left:500px;top:68px;width:720px;height:510px;object-fit:cover;object-position:top left;border-radius:22px;border:2px solid rgba(216,255,79,.45);box-shadow:0 32px 70px rgba(0,0,0,.5);transform:rotate(1.4deg)}.shade{position:absolute;inset:0;background:linear-gradient(90deg,#17201d 0%,#17201d 36%,transparent 67%)}.copy{position:absolute;left:60px;top:94px;width:660px}.eyebrow{color:#d8ff4f;font:800 19px Consolas,monospace;letter-spacing:.12em}.copy h1{margin:24px 0 0;font:900 78px/.92 Inter,"Segoe UI",sans-serif;letter-spacing:-.06em}.copy h1 em{display:block;color:#d8ff4f;font-style:normal}.proof{margin-top:28px;font:700 22px/1.3 Inter;color:#ccd5d0}.nexa{position:absolute;right:42px;bottom:-88px;width:360px;height:560px;object-fit:contain;filter:drop-shadow(0 22px 32px rgba(0,0,0,.48))}.mark{position:absolute;left:60px;bottom:47px;color:#d8ff4f;font:850 18px Consolas,monospace;letter-spacing:.1em}</style></head><body><div id="root" data-composition-id="thumbnail" data-start="0" data-duration="2" data-width="1280" data-height="720"><img class="shot" src="assets/01-command-center.png"><div class="shade"></div><div class="copy"><div class="eyebrow">REVIVE · AUTONOMOUS RECOVERY</div><h1>Recover revenue.<em>Retain trust.</em></h1><div class="proof">Live backend proof. Guarded decisions.</div></div><img class="nexa" src="assets/nexa-v2-confident.png"><div class="mark">BIZNEX // PRODUCT PROOF</div></div><script>window.__timelines=window.__timelines||{};window.__timelines.thumbnail=gsap.timeline({paused:true});</script></body></html>`;
fs.writeFileSync(path.join(project,"thumbnail","index.html"),thumbnail);

console.log(`Built ${scenes.length} scenes, ${captions.length} captions, and thumbnail source.`);
