import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

// Original, deterministic tabletop compositions. Audio and measured timing are
// prepared separately; this builder never synthesizes or guesses speech timing.
const repo = process.cwd();
const briefSet = JSON.parse(fs.readFileSync(path.join(repo, 'config/social/first-six-briefs.json'), 'utf8'));
const episodes = briefSet.episodes.slice(3);
const only = process.argv.indexOf('--only');
const selected = only >= 0 ? episodes.filter(ep => ep.id === process.argv[only + 1]) : episodes;
if (!selected.length) throw new Error('No matching last-three episode');
if (process.argv.includes('--capture-thumbnails')) {
  const chrome = process.env.HYPERFRAMES_BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  if (!fs.existsSync(chrome)) throw new Error('Set HYPERFRAMES_BROWSER_PATH to installed Chrome');
  for (const ep of selected) {
    const project = path.join(repo,'videos',ep.id);
    const input = path.join(project,'thumbnail/index.html');
    const output = path.join(project,'assets/thumbnails/thumbnail.png');
    if (!fs.existsSync(input)) throw new Error('Build the thumbnail composition first');
    fs.mkdirSync(path.dirname(output),{recursive:true});
    const result = spawnSync(chrome,['--headless=new','--disable-gpu','--no-first-run','--hide-scrollbars','--run-all-compositor-stages-before-draw','--virtual-time-budget=2500',`--user-data-dir=${path.join(project,'.hyperframes/thumbnail-profile')}`,'--window-size=1080,1920',`--screenshot=${output}`,pathToFileURL(input).href],{encoding:'utf8',windowsHide:true,timeout:90000});
    if (result.error || result.status !== 0 || !fs.existsSync(output) || !fs.statSync(output).size) throw new Error(`${ep.id}: local thumbnail capture failed`);
    console.log(`${ep.id}: ${output}`);
  }
  process.exit(0);
}
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const save = (file, content) => { fs.mkdirSync(path.dirname(file), {recursive:true}); fs.writeFileSync(file, content, 'utf8'); };

const hand = id => `<svg id="${id}" class="hand" viewBox="0 0 390 230" aria-label="Original illustrated adult hand moving a paper prop"><defs><linearGradient id="${id}-skin" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#dca57d"/><stop offset=".52" stop-color="#c68a66"/><stop offset="1" stop-color="#a66b51"/></linearGradient></defs><path d="M389 49 C334 49 304 46 274 47 L189 23 C170 18 153 25 152 39 C150 53 168 61 183 64 L226 76 L111 69 C91 68 80 76 82 89 C84 101 101 106 119 107 L216 114 L94 110 C74 109 64 119 68 132 C72 144 89 146 108 147 L219 151 L122 154 C103 155 96 164 102 176 C108 187 125 186 141 186 L239 184 C207 198 199 207 206 219 C216 231 235 225 260 215 L305 198 C331 189 361 190 390 194 Z" fill="url(#${id}-skin)"/><path d="M346 38 L390 38 L390 213 L340 211 Q324 125 346 38" fill="#465248"/><path d="M347 42 L344 208" stroke="#788376" stroke-width="5"/><path d="M120 91 L181 95 M112 131 L184 134 M142 173 L193 172" fill="none" stroke="#9f6851" stroke-width="2" stroke-linecap="round" opacity=".5"/><path d="M162 30 Q174 27 184 34" fill="none" stroke="#e9c2a0" stroke-width="9" stroke-linecap="round"/></svg>`;

const commonCss = `
@font-face{font-family:Fraunces;src:url('assets/fonts/Fraunces.ttf') format('truetype');font-weight:100 900;font-display:block}
@font-face{font-family:Montserrat;src:url('assets/fonts/Montserrat.ttf') format('truetype');font-weight:100 900;font-display:block}
@font-face{font-family:PlexMono;src:url('assets/fonts/PlexMono.ttf') format('truetype');font-weight:400;font-display:block}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:#2a211d;color:#f4ead8;font-family:Montserrat,sans-serif}
#root{position:relative;width:100%;height:100%;overflow:hidden}.clip{position:absolute;inset:0;width:100%;height:100%}
.desk-scene{position:relative;width:100%;height:100%;overflow:hidden;background:#2a211d}
.desk-ground{position:absolute;inset:0;background:radial-gradient(ellipse at 20% 30%,#544134 0%,#352a23 48%,#211c19 95%)}
.wood-grain{position:absolute;inset:0;background-image:url('assets/wood-lines.svg');background-size:1080px 1920px;opacity:.45}
.window-light{position:absolute;width:1600px;height:600px;left:-200px;top:1300px;background:repeating-linear-gradient(90deg,rgba(255,221,159,.04) 0 170px,transparent 170px 230px);pointer-events:none}
.scene-vignette{position:absolute;inset:0;box-shadow:inset 0 0 240px 70px rgba(9,7,6,.25);pointer-events:none}
.opening-label{position:absolute;left:108px;top:186px;display:flex;gap:15px;align-items:center;font-size:28px;font-weight:650;letter-spacing:2px;color:#dfc6a5}
.opening-label:before{content:'';width:25px;height:3px;background:#ca6b4b;display:block}
.title-stack{position:absolute;left:104px;top:244px;width:820px;height:152px;z-index:4}
.scene-title{position:absolute;inset:0;margin:0;font-family:Fraunces,serif;font-size:77px;font-weight:650;line-height:1.04;letter-spacing:-2.2px;max-width:800px}
.scene-title.later{opacity:0}.scene-title .accent{color:#e39a72}
.world-window{position:absolute;left:90px;top:405px;width:850px;height:650px;overflow:visible;perspective:1800px}
.camera{width:850px;height:650px;position:absolute;inset:0;transform-style:preserve-3d;transform-origin:50% 50%}
.paper{position:absolute;color:#28231f;background:#f4ead8 url('assets/paper-fibers.svg');box-shadow:0 6px 3px rgba(12,9,6,.2),19px 29px 35px rgba(12,9,6,.30),inset 0 0 1px 1px #fff4df;border-radius:2px}
.paper .small{font-family:Montserrat,sans-serif;font-size:28px;font-weight:550;color:#67554b;letter-spacing:1px}.paper .medium{font-family:Montserrat,sans-serif;font-size:31px;font-weight:600;line-height:1.3}.paper .large{font-family:Fraunces,serif;font-size:54px;font-weight:650;line-height:1.05}
.paper-rim{position:absolute;inset:0;box-shadow:inset 2px 2px 1px #fff7e8,inset -3px -3px 4px rgba(113,78,51,.15);pointer-events:none}
.hand{position:absolute;width:390px;height:230px;filter:drop-shadow(-5px 15px 8px rgba(28,18,10,.25));z-index:20;pointer-events:none}
.pencil{position:absolute;width:515px;height:29px;left:170px;top:1500px;border-radius:2px;background:linear-gradient(#a15435 0 23%,#c27845 24% 55%,#844126 56% 100%);box-shadow:0 9px 13px #191310;transform:rotate(-19deg)}
.pencil:before{content:'';position:absolute;left:-68px;border-top:14px solid transparent;border-bottom:15px solid transparent;border-right:68px solid #d9b086}.pencil:after{content:'';position:absolute;left:-68px;top:9px;border-top:5px solid transparent;border-bottom:6px solid transparent;border-right:23px solid #302923}
.source-credit{position:absolute;left:108px;top:1080px;width:802px;font-size:28px;font-weight:500;line-height:1.3;color:#e2d0b5}.source-credit strong{font-weight:750;color:#f8eddb}
.closing-brand{position:absolute;left:108px;top:1390px;font-family:Fraunces,serif;font-size:94px;font-weight:600;letter-spacing:-3px;color:#dfc6a5;opacity:0}
.paperclip{position:absolute;width:40px;height:101px;border:6px solid #a39270;border-radius:22px;box-shadow:2px 3px 4px #0004;transform:rotate(13deg)}
.paperclip:after{content:'';position:absolute;inset:9px 4px 17px;border:4px solid #d2c3a2;border-radius:13px}
.captions-root{position:relative;width:100%;height:100%;pointer-events:none}.caption-clip{position:absolute;left:108px;top:1170px;width:810px;height:145px;display:flex;align-items:flex-start;justify-content:flex-start}
.caption-inner{display:block;width:100%;font-family:Montserrat,sans-serif;font-weight:650;font-size:51px;line-height:1.23;letter-spacing:-.6px;color:#fff5e5;text-shadow:0 2px 2px #1b1412;opacity:0}
.thumb-title{position:absolute;left:108px;top:230px;width:810px;font-family:Fraunces,serif;font-weight:700;font-size:90px;line-height:1.02;color:#f4ead8;letter-spacing:-2px}.thumb-label{position:absolute;left:108px;top:1320px;width:810px;font-size:32px;font-weight:700;letter-spacing:2px;color:#e3a27c}.thumb-brand{position:absolute;left:108px;top:1465px;font-family:Fraunces,serif;font-size:90px;color:#f4ead8}
`;

const ribbonCss = `
.source-card{left:85px;top:0;width:660px;height:240px;padding:34px 42px;background-color:#f2e3c9;z-index:4}
.source-card .large{font-size:56px;margin-top:12px}.source-card .source-options{display:flex;gap:25px;align-items:center;margin-top:19px;font-size:28px;font-weight:650}.source-card .source-options span{border-bottom:3px solid #ba4e35;padding-bottom:5px}
.source-card .paperclip{right:28px;top:-29px}.ribbon-paths{position:absolute;inset:0;width:850px;height:650px;z-index:5;overflow:visible}
.ribbon-shadow{fill:none;stroke:#150e09;stroke-width:29;stroke-linecap:round;opacity:.27}.ribbon-main{fill:none;stroke:#ba4e35;stroke-width:20;stroke-linecap:round}.ribbon-stitch{fill:none;stroke:#dfaa8b;stroke-width:2;stroke-dasharray:4 6;opacity:.7}.ribbon-other{stroke:#bd9b66}.ribbon-travel{fill:none;stroke:#f6d2ae;stroke-width:5;stroke-linecap:round}
.notebook{position:absolute;left:30px;top:345px;width:770px;height:285px;background:#805746;border-radius:8px;box-shadow:10px 21px 30px #100b0780;z-index:3}
.notebook-page{position:absolute;top:8px;width:371px;height:267px;background:#e9d6b3 url('assets/paper-fibers.svg');color:#28231f;padding:27px 30px;box-shadow:inset -6px 0 12px #56452c18;overflow:hidden}
.page-left{left:9px}.page-right{right:9px;box-shadow:inset 8px 0 12px #56452c25}.notebook-spine{position:absolute;left:379px;top:0;width:12px;height:285px;background:#9e7b59;box-shadow:inset 3px 0 4px #4d3429;z-index:4}
.page-rules{position:absolute;left:25px;right:20px;top:82px;height:164px;background:repeating-linear-gradient(transparent 0 35px,#896f4924 36px 38px);z-index:0}
.note-label{font-size:28px;font-weight:650;color:#6b4f3c;letter-spacing:1px}.old-note{position:relative;font-family:Fraunces,serif;font-size:38px;line-height:1.25;margin-top:35px;max-width:270px}
.replacement{position:absolute;left:435px;top:395px;width:320px;height:194px;background:#d7b981;color:#2a211d;padding:25px 30px;box-shadow:4px 12px 18px #2b1b0933;z-index:9}
.replacement .question{font-family:Fraunces,serif;font-size:35px;font-weight:650;line-height:1.15;margin-top:10px}.ink-line{position:absolute;left:42px;top:98px;width:250px;height:26px;z-index:8}.ink-line path{fill:none;stroke:#ba4e35;stroke-width:5;stroke-linecap:round}.ribbon-pin{position:absolute;width:15px;height:15px;background:#735242;border:4px solid #d8c3a1;border-radius:50%;box-shadow:2px 3px 5px #2d1e16;z-index:9}.pin-a{left:265px;top:223px}.pin-b{left:609px;top:223px}
#ribbon-hand{left:575px;top:405px}
`;
const ribbonMarkup = `
<div class="paper source-card" id="source-card"><div class="small">ATOMY USA · SOURCE SUMMARY</div><div class="large">Sponsor required</div><div class="source-options"><span>Automatic</span><span>Manual</span></div><div class="paper-rim"></div><div class="paperclip"></div></div>
<svg class="ribbon-paths" viewBox="0 0 850 650" aria-label="Two fabric ribbons connect the guide to the notebook"><path class="ribbon-shadow" d="M271 238 C225 300 109 265 132 332 S227 330 222 361"/><path class="ribbon-shadow" d="M616 238 C635 297 790 268 752 322 S669 328 663 361"/><path id="ribbon-a" class="ribbon-main" d="M271 231 C225 293 109 258 132 325 S227 323 222 354"/><path id="ribbon-b" class="ribbon-main ribbon-other" d="M616 231 C635 290 790 261 752 315 S669 321 663 354"/><path class="ribbon-stitch" d="M271 231 C225 293 109 258 132 325 S227 323 222 354"/><path class="ribbon-stitch" d="M616 231 C635 290 790 261 752 315 S669 321 663 354"/><path id="ribbon-trace-a" class="ribbon-travel" d="M222 354 C227 323 155 392 132 325 S225 293 271 231"/><path id="ribbon-trace-b" class="ribbon-travel" d="M663 354 C669 321 714 382 752 315 S635 290 616 231"/></svg>
<div class="notebook" id="notebook"><div class="notebook-page page-left"><div class="note-label">MY QUICK NOTES</div><div class="page-rules"></div><div class="old-note" id="old-note">Finish signup</div><svg class="ink-line" viewBox="0 0 250 26"><path id="strike-line" d="M4 18 Q110 4 244 10"/></svg></div><div class="notebook-page page-right"><div class="note-label" id="better-question">THE BETTER QUESTION</div><div class="page-rules"></div></div><div class="notebook-spine"></div></div>
<div class="replacement" id="replacement"><div class="note-label">SOURCE CHECK</div><div class="question">How does the sponsor step work?</div></div><div class="ribbon-pin pin-a"></div><div class="ribbon-pin pin-b"></div>${hand('ribbon-hand')}`;

const foldCss = `
.comparison-paper{position:absolute;left:120px;top:13px;width:590px;height:610px;transform-style:preserve-3d;perspective:1600px;color:#28231f}
.sheet-top{left:0;top:0;width:590px;height:280px;padding:31px 38px;z-index:4;background-color:#f0e0c4;box-shadow:18px 18px 27px #150c0755}
.sheet-top .large{font-size:48px;margin-top:12px}.price-mark{position:absolute;left:40px;top:159px;font-size:41px;font-weight:700;color:#7e3f2d;letter-spacing:1px}.price-circle{position:absolute;left:30px;top:136px;width:430px;height:110px;overflow:visible}.price-circle path{fill:none;stroke:#ba4e35;stroke-width:5;stroke-linecap:round}
.sheet-bottom{position:absolute;left:0;top:280px;width:590px;height:315px;transform-origin:50% 0;transform-style:preserve-3d;z-index:5}.sheet-front{position:absolute;inset:0;padding:17px 38px;background-color:#f7ead2;backface-visibility:hidden;transform:translateZ(.2px);box-shadow:18px 22px 26px #150c0755}
.sheet-back{position:absolute;inset:0;background:#cdb38f url('assets/paper-fibers.svg');backface-visibility:hidden;transform:rotateX(180deg);box-shadow:inset 0 12px 35px #7250364a;z-index:1}
.fold-rule{position:absolute;left:0;top:276px;width:590px;height:7px;background:linear-gradient(#ab8f67,#fff1d7);z-index:8;box-shadow:0 3px 5px #40291633}
.cost-row{display:flex;align-items:center;justify-content:space-between;min-height:64px;border-bottom:2px solid #bca68266;font-size:30px;font-weight:600}.cost-row .marks{font-family:PlexMono,monospace;font-size:27px;color:#6d5c49;letter-spacing:5px}.cost-row.total{height:82px;font-family:Fraunces,serif;font-size:43px;border-bottom:0;color:#993e28;margin-top:5px}.total-underline{position:absolute;left:37px;top:220px;width:350px;height:20px;overflow:visible}.total-underline path{fill:none;stroke:#ba4e35;stroke-width:5;stroke-linecap:round}
.match-tag{position:absolute;left:34px;top:525px;width:230px;height:64px;padding:18px 18px;background:#d3b07c;color:#2a211d;font-family:Montserrat,sans-serif;font-size:28px;line-height:1.2;font-weight:700;box-shadow:7px 12px 15px #21130944;z-index:9}.match-tag:before{content:'';position:absolute;left:14px;top:9px;width:9px;height:9px;border-radius:50%;background:#866a43;box-shadow:inset 1px 2px 2px #432e20}.match-tag.right{left:322px;top:525px;background:#c89a73}
.fold-pencil{position:absolute;left:373px;top:215px;width:365px;height:22px;background:linear-gradient(#be754b 0 25%,#d09259 26% 55%,#8b4e2f 56% 100%);z-index:17;box-shadow:0 9px 12px #1c100a55}.fold-pencil:before{content:'';position:absolute;left:-51px;border-top:11px solid transparent;border-bottom:11px solid transparent;border-right:51px solid #d9b086}.fold-pencil:after{content:'';position:absolute;left:-51px;top:7px;border-top:4px solid transparent;border-bottom:4px solid transparent;border-right:18px solid #302923}
#fold-hand{left:553px;top:333px}
`;
const foldMarkup = `
<div class="comparison-paper" id="comparison-paper"><div class="paper sheet-top"><div class="small">MY COMPARISON SHEET</div><div class="large">Look past the price</div><div class="price-mark">ITEM PRICE</div><svg class="price-circle" viewBox="0 0 430 110"><path id="price-circle-path" d="M412 57 C391 4 44 0 11 53 C-18 113 379 116 418 64"/></svg><div class="paper-rim"></div></div><div class="sheet-bottom" id="sheet-bottom"><div class="paper sheet-front" id="sheet-front"><div class="cost-row"><span>Delivery</span><span class="marks" data-layout-ignore>+ …</span></div><div class="cost-row"><span>Other fees</span><span class="marks" data-layout-ignore>+ …</span></div><div class="cost-row total"><span>Full cost</span><span class="marks" data-layout-ignore>= …</span></div><svg class="total-underline" viewBox="0 0 350 20"><path id="total-line" d="M3 12 Q170 0 343 9"/></svg><div class="paper-rim"></div></div><div class="sheet-back" data-layout-ignore data-layout-allow-occlusion></div></div><div class="fold-rule"></div></div><div class="fold-pencil" id="fold-pencil"></div>${hand('fold-hand')}`;

const boxesCss = `
.shopping-sheet{left:211px;top:1px;width:545px;height:630px;padding:28px 33px;z-index:2;background-color:#f0e0c2}
.shopping-sheet .large{font-size:51px;margin-top:13px}.shop-note{margin-top:18px;color:#8a4d34;font-size:29px;font-weight:650;letter-spacing:1px}.sheet-lines{position:absolute;left:31px;right:30px;top:172px;height:400px;background:repeating-linear-gradient(transparent 0 109px,#c4ac8428 110px 112px)}
.comparison-row{position:absolute;left:34px;width:476px;height:116px;display:flex;align-items:center;gap:22px}.row-1{top:181px}.row-2{top:314px}.row-3{top:447px}.row-number{width:39px;height:39px;border:2px solid #b39872;border-radius:50%;font-family:PlexMono,monospace;font-size:28px;display:grid;place-items:center;color:#7b654b}.row-copy{font-family:Fraunces,serif;font-size:38px;font-weight:600}.row-value{display:block;font-family:Montserrat,sans-serif;font-size:28px;font-weight:500;color:#715c43;margin-top:4px;opacity:0}
.frame-prop{position:absolute;width:540px;height:119px;border:15px solid #a77450;border-left-color:#d1aa78;border-top-color:#e0bd8c;box-shadow:5px 10px 13px #180f0966,inset 3px 3px 5px #3b24183a;z-index:8;background:transparent}.frame-prop:before{content:'';position:absolute;left:-13px;top:-13px;width:536px;height:115px;border:2px solid #f3d8a9;opacity:.65}.frame-prop .frame-label{position:absolute;left:13px;top:18px;font-family:Montserrat,sans-serif;font-size:32px;font-weight:750;color:#f6e6c8;letter-spacing:2px;background:#70503a;padding:4px 12px;line-height:1.2}.frame-a{left:37px;top:145px}.frame-b{left:21px;top:301px}.frame-c{left:2px;top:458px}
.tick-svg{position:absolute;left:644px;top:208px;width:72px;height:345px;z-index:10;overflow:visible}.tick-svg path{fill:none;stroke:#a3452d;stroke-width:8;stroke-linecap:round;stroke-linejoin:round}
.loose-label{position:absolute;left:4px;top:45px;width:230px;height:110px;padding:13px 18px;background:#c89c72;color:#35261e;font-size:28px;font-weight:700;line-height:1.25;box-shadow:5px 10px 12px #1a0e0966;z-index:5}.shopping-sheet .paperclip{right:25px;top:-28px}#boxes-hand{left:532px;top:315px}
`;
const boxesMarkup = `
<div class="paper shopping-sheet" id="shopping-sheet"><div class="small">MY SHOPPING COMPARISON</div><div class="large">A complete picture</div><div class="shop-note" id="shop-price">A BOLD PRICE?</div><div class="sheet-lines"></div><div class="comparison-row row-1"><span class="row-number">1</span><div class="row-copy">Exact item<span id="value-1" class="row-value">Same model or product</span></div></div><div class="comparison-row row-2"><span class="row-number">2</span><div class="row-copy">Size<span id="value-2" class="row-value">Same amount</span></div></div><div class="comparison-row row-3"><span class="row-number">3</span><div class="row-copy">Full cost<span id="value-3" class="row-value">Delivery + other fees</span></div></div><div class="paperclip"></div><div class="paper-rim"></div></div><div class="frame-prop frame-a" id="frame-a"><div class="frame-label" id="frame-label-a">ITEM</div></div><div class="frame-prop frame-b" id="frame-b"><div class="frame-label" id="frame-label-b">SIZE</div></div><div class="frame-prop frame-c" id="frame-c"><div class="frame-label" id="frame-label-c">TOTAL</div></div><svg class="tick-svg" viewBox="0 0 72 345"><path id="tick-1" d="M9 24 L29 43 L61 4"/><path id="tick-2" d="M9 157 L29 176 L61 137"/><path id="tick-3" d="M9 290 L29 309 L61 270"/></svg><div class="loose-label" id="loose-label">STILL MISSING?</div>${hand('boxes-hand')}`;

function motion(kind, timing, thumbnail = false) {
  const beats = timing.beats;
  const b = n => Number(beats[n]?.start ?? 0);
  const end = timing.duration_seconds;
  // Explicit pure-time poses; no timer or render-time I/O.
  const common = `const tl=gsap.timeline({paused:true});const T=${JSON.stringify({b1:b(1),b2:b(2),b3:b(3),b4:b(4),end})};
  const draw=(selector,at,duration)=>{document.querySelectorAll(selector).forEach(p=>{const length=p.getTotalLength();tl.fromTo(p,{strokeDasharray:length,strokeDashoffset:length},{strokeDashoffset:0,duration,ease:'power2.out'},at);});};
  tl.fromTo('#camera',{scale:1.025,x:0,y:0},{scale:1.00,x:0,y:0,duration:Math.max(1,T.b1),ease:'power2.inOut'},0);
  tl.to('#camera',{scale:1.065,x:-12,y:-14,duration:1.25,ease:'power3.inOut'},T.b2);
  tl.to('#camera',{scale:.99,x:0,y:0,duration:1.25,ease:'power2.inOut'},T.b3);
  tl.fromTo('#window-light',{x:-40,rotation:-27},{x:55,rotation:-27,duration:T.end,ease:'none'},0);
  tl.to('#title-opening',{opacity:0,duration:.18,ease:'power1.in'},T.b3);
  tl.fromTo('#title-payoff',{opacity:0,y:8},{opacity:1,y:0,duration:.32,ease:'power2.out'},T.b3+.18);
  tl.fromTo('#closing-brand',{opacity:0},{opacity:.9,duration:.5,ease:'power1.out'},T.b4);
  `;
  const ribbon = `
  tl.fromTo('#source-card',{rotation:-2.5},{rotation:-1,duration:1.2,ease:'power2.out'},0);
  tl.fromTo('#notebook',{rotation:3},{rotation:1,duration:1.3,ease:'power2.out'},T.b1);
  tl.fromTo('#replacement',{x:225,y:145,rotation:9,opacity:0},{x:0,y:0,rotation:-3,opacity:1,duration:.85,ease:'power3.out'},T.b3+.15);
  tl.fromTo('#ribbon-hand',{x:420,y:10,rotation:8,opacity:0},{x:0,y:0,rotation:0,opacity:1,duration:.5,ease:'power2.out'},T.b3-.25);
  tl.to('#ribbon-hand',{x:375,y:30,opacity:0,duration:.55,ease:'power2.in'},T.b3+.72);
  draw('#ribbon-trace-a',T.b1+.3,1.15);draw('#ribbon-trace-b',T.b1+1.65,1.15);
  draw('#strike-line',T.b3+.25,.48);
  tl.to('#old-note',{opacity:.42,duration:.35},T.b3+.45);tl.to('#better-question',{opacity:0,duration:.12},T.b3);
  `;
  const fold = `
  
  tl.fromTo('#comparison-paper',{rotation:-4},{rotation:-2,duration:1.4,ease:'power2.out'},0);
  tl.fromTo('#sheet-bottom',{rotationX:-146},{rotationX:-136,duration:.7,ease:'power2.inOut'},T.b1+.5);
  tl.to('#sheet-bottom',{rotationX:0,duration:1.55,ease:'power3.inOut'},T.b2+.12);tl.fromTo('#sheet-front',{opacity:0},{opacity:1,duration:.15,ease:'none'},T.b2+1.35);
  tl.fromTo('#fold-pencil',{rotation:-18,x:140,y:25,opacity:0},{rotation:-18,x:0,y:0,opacity:1,duration:.5,ease:'power2.out'},T.b1+.05);
  tl.to('#fold-pencil',{x:-130,y:12,duration:.55,ease:'power1.inOut'},T.b1+.55);
  tl.to('#fold-pencil',{x:230,y:90,opacity:0,duration:.55,ease:'power2.in'},T.b1+1.2);
  draw('#price-circle-path',T.b1+.42,.9);
  tl.fromTo('#fold-hand',{x:400,y:0,opacity:0},{x:0,y:0,opacity:1,duration:.5,ease:'power2.out'},T.b2-.35);
  tl.to('#fold-hand',{x:70,y:130,duration:1.3,ease:'power3.inOut'},T.b2+.15);
  tl.to('#fold-hand',{x:440,y:190,opacity:0,duration:.5,ease:'power2.in'},T.b2+1.45);
  draw('#total-line',T.b3+1.4,.7);
  `;
  const boxes = `
  tl.fromTo('#shopping-sheet',{rotation:3},{rotation:1.5,duration:1.1,ease:'power2.out'},0);
  tl.fromTo('#frame-a',{rotation:-6},{rotation:-4,duration:.7,ease:'power2.out'},0);
  tl.fromTo('#frame-b',{rotation:3},{rotation:1,duration:.7,ease:'power2.out'},.45);
  tl.fromTo('#frame-c',{rotation:-3},{rotation:-1,duration:.7,ease:'power2.out'},.9);
  tl.fromTo('#loose-label',{rotation:-7,opacity:0,y:15},{rotation:-7,opacity:1,y:0,duration:.45,ease:'power2.out'},T.b1+.3);
  tl.to('#shop-price',{opacity:.35,duration:.35},T.b2);
  [['a',T.b2+.15,174,36],['b',T.b2+1.6,190,13],['c',T.b3+.15,209,-11]].forEach(([id,at,x,y],i)=>{
    tl.to('#frame-'+id,{x,y,rotation:1.5,duration:.85,ease:'power3.inOut'},at);
    tl.to('#frame-label-'+id,{opacity:0,duration:.2},at+.2);
    tl.fromTo('#value-'+(i+1),{opacity:0,y:4},{opacity:1,y:0,duration:.35,ease:'power1.out'},at+.65);
    draw('#tick-'+(i+1),at+.75,.45);
  });
  tl.fromTo('#boxes-hand',{x:450,y:0,opacity:0},{x:0,y:0,opacity:1,duration:.5,ease:'power2.out'},T.b2-.2);
  tl.to('#boxes-hand',{x:180,y:130,duration:1.3,ease:'power2.inOut'},T.b2+.3);
  tl.to('#boxes-hand',{x:445,y:150,opacity:0,duration:.5,ease:'power2.in'},T.b2+1.7);
  tl.to('#loose-label',{x:-80,opacity:0,duration:.5,ease:'power2.in'},T.b3+.7);
  `;
  let selectedMotion = ({ribbon,fold,boxes})[kind];
  if (thumbnail) {
    // Thumbnail poses are authored final states, not a promise of rendered media.
    selectedMotion = kind === 'ribbon' ? `tl.set('#replacement',{rotation:-3});tl.set('#ribbon-hand',{opacity:0});tl.set('#old-note',{opacity:.4});tl.set('#better-question',{opacity:0});` : kind === 'fold' ? `tl.set('#sheet-bottom',{rotationX:0});tl.set('#comparison-paper',{rotation:-3});tl.set('#fold-pencil,#fold-hand',{opacity:0});` : `tl.set('#shopping-sheet',{rotation:1.5});tl.set('#frame-a',{x:174,y:36,rotation:1.5});tl.set('#frame-b',{x:190,y:13,rotation:1.5});tl.set('#frame-c',{x:209,y:-11,rotation:1.5});tl.set('.frame-label,#boxes-hand,#loose-label',{opacity:0});tl.set('.row-value',{opacity:1});`;
    return `const tl=gsap.timeline({paused:true});${selectedMotion.replaceAll('tl.set(', 'gsap.set(')}window.__timelines=window.__timelines||{};window.__timelines['main']=tl;`;
  }
  return `${common}${selectedMotion}window.__timelines['desk']=tl;`;
}

for (const ep of selected) {
  const project = path.join(repo,'videos',ep.id);
  const timingPath = path.join(project,'timing.json');
  if (!fs.existsSync(timingPath)) { console.log(`WAITING ${ep.id}: measured timing.json is required`); continue; }
  const timing = JSON.parse(fs.readFileSync(timingPath,'utf8'));
  if (!(timing.duration_seconds >= 20 && timing.duration_seconds <= 35)) throw new Error(`${ep.id}: invalid duration`);
  if (!timing.captions?.length || timing.beats?.length !== 5) throw new Error(`${ep.id}: incomplete timing`);
  const duration = timing.duration_seconds;
  const kind = ep.id.includes('ribbons')?'ribbon':ep.id.includes('receipt')?'fold':'boxes';
  const config = {
    ribbon:{css:ribbonCss,markup:ribbonMarkup,heading:'Follow the source',payoff:'A better question',source:'Atomy USA · Registration guide',detail:'Membership guide'},
    fold:{css:foldCss,markup:foldMarkup,heading:'What did she miss?',payoff:'The full cost',source:'FTC · Online Shopping',detail:'U.S. shopping guidance'},
    boxes:{css:boxesCss,markup:boxesMarkup,heading:'Three checks',payoff:'Now compare',source:'FTC · Online Shopping',detail:'U.S. shopping guidance'},
  }[kind];
  const assets = path.join(project,'assets');
  fs.mkdirSync(path.join(assets,'fonts'),{recursive:true});fs.mkdirSync(path.join(assets,'vendor'),{recursive:true});
  const shared = path.join(repo,'videos/biznex-unsent-message/assets');
  for (const name of ['Fraunces.ttf','Montserrat.ttf','PlexMono.ttf','Fraunces-OFL.txt','Montserrat-OFL.txt','PlexMono-OFL.txt']) fs.copyFileSync(path.join(shared,'fonts',name),path.join(assets,'fonts',name));
  fs.copyFileSync(path.join(shared,'vendor/gsap.min.js'),path.join(assets,'vendor/gsap.min.js'));
  const fibers = Array.from({length:110},(_,i)=>{const x=(i*47)%320,y=(i*71)%320;return `<path d="M${x} ${y}l${4+i%12} ${i%3-1}" stroke="#765c42" opacity=".${6+i%5}" stroke-width=".4"/>`;}).join('');
  save(path.join(assets,'paper-fibers.svg'),`<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">${fibers}</svg>`);
  const grain=Array.from({length:55},(_,i)=>`<path d="M-80 ${i*38}Q470 ${i*38+40} 1160 ${i*38-15}" fill="none" stroke="#9b7650" stroke-width="${.6+i%3*.3}" opacity=".11"/>`).join('');
  save(path.join(assets,'wood-lines.svg'),`<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">${grain}</svg>`);
  const css=commonCss+config.css;
  save(path.join(assets,'desk.css'),css);
  const stage = `<div class="desk-ground"></div><div class="wood-grain"></div><div class="window-light" id="window-light" data-layout-ignore></div><div class="scene-vignette"></div><div class="opening-label">A FICTIONAL SCENE · U.S. GUIDE</div><div class="title-stack"><h1 class="scene-title" id="title-opening">${esc(config.heading)}</h1><h1 class="scene-title later" id="title-payoff">${esc(config.payoff)}</h1></div><div class="world-window" data-layout-allow-overflow><div class="camera" id="camera">${config.markup}</div></div><div class="source-credit"><strong>${esc(config.source)}</strong><div>${esc(config.detail)} · checked 6 Nov 2026</div></div><div class="pencil"></div><div class="closing-brand" id="closing-brand">BizNex</div>`;
  save(path.join(project,'compositions/desk.html'),`<template><div id="root" class="desk-scene" data-composition-id="desk" data-start="0" data-duration="${duration}" data-width="1080" data-height="1920">${stage}</div><script>${motion(kind,timing)}</script></template>`);
  const captions = timing.captions.map((c,i)=>`<div id="caption-${i}" class="clip caption-clip" data-start="${Number(c.start).toFixed(4)}" data-duration="${Math.max(.04,c.end-c.start).toFixed(4)}" data-track-index="3"><span id="caption-inner-${i}" class="caption-inner">${esc(c.text)}</span></div>`).join('');
  const capMotion = timing.captions.map((c,i)=>`tl.fromTo('#caption-inner-${i}',{opacity:0},{opacity:1,duration:.06,ease:'none'},${Number(c.start).toFixed(4)});tl.set('#caption-inner-${i}',{opacity:0},${Number(c.end).toFixed(4)});`).join('');
  save(path.join(project,'compositions/captions.html'),`<template><div id="root" class="captions-root" data-composition-id="captions" data-start="0" data-duration="${duration}" data-width="1080" data-height="1920">${captions}</div><script>const tl=gsap.timeline({paused:true});${capMotion}window.__timelines['captions']=tl;</script></template>`);
  save(path.join(project,'index.html'),`<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>${esc(ep.title)}</title><style>${css}</style><script src="assets/vendor/gsap.min.js"></script></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="${duration}" data-width="1080" data-height="1920"><section id="desk" class="clip" data-composition-id="desk" data-composition-src="compositions/desk.html" data-start="0" data-duration="${duration}" data-track-index="0" data-track-kind="graphics"></section><section id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="${duration}" data-track-index="3" data-track-kind="captions"></section><audio id="final-audio" class="clip" src="assets/audio/final_mix.wav" data-start="0" data-duration="${duration}" data-track-index="2" data-volume="1"></audio></div><script>const tl=gsap.timeline({paused:true});window.__timelines['main']=tl;</script></body></html>`);
  const thumb = `<div class="desk-ground"></div><div class="wood-grain"></div><div class="scene-vignette"></div><div class="opening-label">AN ORIGINAL BIZNEX STORY</div><div class="thumb-title">${esc(ep.thumbnail_copy)}</div><div class="world-window" style="top:525px" data-layout-allow-overflow><div class="camera" id="camera">${config.markup}</div></div><div class="thumb-label">A SMALL CHOICE. A CLEARER QUESTION.</div><div class="thumb-brand">BizNex</div><div class="pencil" style="top:1740px"></div>`;
  save(path.join(project,'thumbnail/index.html'),`<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>${esc(ep.thumbnail_copy)}</title><style>${css.replaceAll('assets/', '../assets/')}</style><script src="../assets/vendor/gsap.min.js"></script></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="1" data-width="1080" data-height="1920">${thumb}</div><script>${motion(kind,timing,true)}</script></body></html>`);
  if (fs.existsSync(path.join(project,'thumbnail.html'))) fs.unlinkSync(path.join(project,'thumbnail.html'));
  save(path.join(project,'frame.md'),`# ${ep.title}\n\nWalnut desk #2a211d, warm paper #f4ead8, ink #28231f, cinnabar #ba4e35. Original physical paper objects, not stock business slides. Fraunces650 77px titles; Montserrat650 51px captions; minimum reading size28px for source citation. Essential content x108–918/y186–1320; lower region is decor. 1080x1920 at30fps. One continuous tabletop camera. No footage or logos copied.\n`);
  save(path.join(project,'BRIEF.md'),`---\nworkflow: hyperframes\nflow: automation\nstoryboard: no\nformat: vertical\n---\n# ${ep.title}\n\nUser requests all six finished videos now with no confirmation stops. Follow the authored pilot script exactly. ${ep.premise}\n\nMeasured duration: ${duration}s. Narration and full mix provided by the audio pipeline. Source and experiment assignment remain in EDITORIAL.json and first-six-briefs.json. The continuous original desk scene uses no render-time network assets. Fiction disclosure is spoken and visible.\n`);
  save(path.join(project,'SPEC.md'),`# Film specification\n\nGOAL: ${ep.payoff}\nOUTPUT: HyperFrames1080x1920,30fps. TIME:${duration}s.\nLOOK: walnut ground #2a211d; paper #f4ead8 with0.4px fibers; ink #28231f; cinnabar #ba4e35 used only for source/reveal marks. Fraunces650 77px titles, Montserrat650 51px captions. Key light upper-left; paper shadow19px29px35px at0.30 opacity.\nOBJECTS: ${ep.premise}\nMOTION: single continuous camera, power2.inOut/power3.inOut on reframing(1.25s), power3.out on paper landing(0.65–0.85s), power2.out on stroke draws(0.45–1.15s). Every event anchored to measured beat starts in timing.json.\nSHOTS: first source/question state, notebook/paper problem, source detail, physical completed decision tool, held payoff.\nBANNED: particles, glow, decorative HUDs, copied reel assets, fake prices/testimonials, generic slide swaps, repeated entrance for every object, ongoing title drift, illegible captions, unmeasured speech timing. The warm paper/serif medium is intentional for this authored physical-paper story, not a generic infographic ground.\nQA: inspect0.2s, each timing.beats midpoint, reveal±0.4s and final0.2s. All important words remain above1330px. Thumbnail is a separately authored final prop arrangement.\n`);
  save(path.join(project,'STORYBOARD.md'),`# ${ep.title}\n\nSingle continuous scene, no hard-cut montage. Root mounts desk and measured caption tracks. Motion rules: multi-phase-camera, svg-path-draw, split-tilt-cards adapted to physical props.\n\n${timing.beats.map((beat,i)=>`## Frame ${i+1}\nstatus: built\nsrc: compositions/desk.html\nstart: ${beat.start}\nend: ${beat.end}\nBeat: ${beat.text}\nMove: ${ep.shot_beats[i].visual}\n`).join('\n')}\n`);
  save(path.join(assets,'VISUAL_PROVENANCE.json'),JSON.stringify({schema_version:1,created_on:'2026-11-06',original_art:['HTML/CSS paper constructions','SVG illustrated hand','SVG ribbon paths and handwriting strokes','paper-fibers.svg','wood-lines.svg'],fonts:{source:'Existing repository licensed font assets',licenses:['fonts/Fraunces-OFL.txt','fonts/Montserrat-OFL.txt','fonts/PlexMono-OFL.txt']},gsap:{source:'Existing repository bundled GSAP',file:'vendor/gsap.min.js',license_notice:'Preserved upstream banner in vendored file.'},reference_reuse:'No creator reel footage, voice, music or script reused.'},null,2)+'\n');
  console.log(`BUILT ${ep.id}: ${duration}s, ${timing.captions.length} measured caption groups`);
}
