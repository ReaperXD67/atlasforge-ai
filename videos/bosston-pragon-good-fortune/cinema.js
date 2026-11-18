/* BOSSTON / Pragon — the picture is a pure function of soundtrack time.
 * HyperFrames owns the audio and drives renderFilmAt through its paused clock.
 * Original spatial geometry and optical atmospheres; no render-time networking.
 */
(() => {
  'use strict';
  const D = window.FILM_DATA, W = 1920, H = 1080, TOP = 76, PH = 928, TAU = Math.PI * 2;
  const main = document.getElementById('world').getContext('2d', {alpha: false});
  const clamp = (x, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, x));
  const fract = x => x - Math.floor(x);
  const mix = (a, b, x) => a + (b - a) * x;
  const smooth = x => { x = clamp(x); return x * x * (3 - 2 * x); };
  const ease = x => .5 - .5 * Math.cos(clamp(x) * Math.PI);
  const rgba = (r, g, b, a) => `rgba(${r},${g},${b},${clamp(a)})`;
  function seeded(seed) {
    let state = seed >>> 0;
    return () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
  }
  function surface(w, h) {
    const canvas = document.createElement('canvas'); canvas.width = w; canvas.height = h; return canvas;
  }
  const pictures = Object.create(null), buffers = [surface(W, PH), surface(W, PH)];
  const contexts = buffers.map(c => c.getContext('2d', {alpha: false}));
  const random = seeded(18112026);
  const motes = Array.from({length: 190}, () => ({
    x: random(), y: random(), z: .12 + random() * .88, phase: random() * TAU,
    speed: .2 + random() * .8, size: .6 + random() ** 3 * 3.7,
  }));
  const ribbons = Array.from({length: 9}, (_, i) => ({
    phase: random() * TAU, depth: 1.5 + random() * 3, side: i % 2 ? 1 : -1,
    height: .3 + random() * .7, width: .6 + random() * .7,
  }));
  const confetti = Array.from({length: 125}, () => ({
    x: random(), y: random(), z: .2 + random() * .8, phase: random() * TAU,
    speed: .25 + random() * .7, shape: random(),
  }));
  const lanterns = Array.from({length: 37}, (_, i) => ({
    x: random(), y: random(), z: .18 + random() * .82, phase: random() * TAU,
    speed: .2 + random() * .7, side: i % 2 ? -1 : 1,
  })).sort((a, b) => a.z - b.z);

  function glowSprite(color) {
    const c = surface(96, 96), g = c.getContext('2d');
    const r = g.createRadialGradient(48, 48, 0, 48, 48, 48);
    r.addColorStop(0, rgba(...color, 1)); r.addColorStop(.08, rgba(...color, .85));
    r.addColorStop(.26, rgba(...color, .18)); r.addColorStop(1, rgba(...color, 0));
    g.fillStyle = r; g.fillRect(0, 0, 96, 96); return c;
  }
  const goldGlow = glowSprite([255, 211, 131]), redGlow = glowSprite([233, 57, 31]);
  const lanternSprite = (() => {
    const image = surface(220, 360), c = image.getContext('2d');
    c.drawImage(redGlow, -38, -48, 296, 296);
    let g = c.createLinearGradient(43, 0, 177, 0);
    g.addColorStop(0, '#6b0810'); g.addColorStop(.25, '#cb2b25');
    g.addColorStop(.52, '#ff7140'); g.addColorStop(.77, '#bf1a1e'); g.addColorStop(1, '#54070e');
    c.fillStyle = g; c.beginPath(); c.ellipse(110, 120, 70, 93, 0, 0, TAU); c.fill();
    c.save(); c.beginPath(); c.ellipse(110, 120, 70, 93, 0, 0, TAU); c.clip();
    c.strokeStyle = '#ffcf7f66'; c.lineWidth = 1.3;
    for (let i = -3; i <= 3; i++) {
      c.beginPath(); c.moveTo(110 + i * 6, 23);
      c.bezierCurveTo(110 + i * 30, 70, 110 + i * 30, 170, 110 + i * 6, 218); c.stroke();
    }
    c.fillStyle = '#fff6ae17'; c.fillRect(20, 75, 180, 35); c.restore();
    g = c.createLinearGradient(70, 0, 150, 0);
    g.addColorStop(0, '#6e3d14'); g.addColorStop(.5, '#f4d68e'); g.addColorStop(1, '#7b4116');
    c.fillStyle = g; c.fillRect(81, 22, 58, 10); c.fillRect(81, 209, 58, 10);
    c.strokeStyle = '#cba464'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(110, 22); c.lineTo(110, 0); c.stroke();
    c.fillStyle = '#ac191f'; c.fillRect(108, 219, 4, 36);
    for (let i = 0; i < 13; i++) {
      c.strokeStyle = i % 3 ? '#bf2821' : '#edb55c'; c.lineWidth = 1.4;
      c.beginPath(); c.moveTo(110 + (i - 6) * .9, 248);
      c.quadraticCurveTo(110 + (i - 6) * 2.2, 285, 110 + (i - 6) * 2.6, 317 + Math.abs(i - 6)); c.stroke();
    }
    return image;
  })();
  const vignette = (() => {
    const image = surface(W, PH), c = image.getContext('2d');
    const g = c.createRadialGradient(960, 390, 190, 960, 450, 1120);
    g.addColorStop(0, '#01030500'); g.addColorStop(.55, '#0103050d'); g.addColorStop(1, '#010305b3');
    c.fillStyle = g; c.fillRect(0, 0, W, PH); return image;
  })();
  const grain = (() => {
    const image = surface(256, 256), c = image.getContext('2d'), p = c.createImageData(256, 256), r = seeded(9182);
    for (let i = 0; i < p.data.length; i += 4) {
      const v = r() * 255 | 0; p.data[i] = v; p.data[i + 1] = v; p.data[i + 2] = v; p.data[i + 3] = 255;
    }
    c.putImageData(p, 0, 0); return image;
  })();
  const beats = (D.beats || []).map(b => typeof b === 'number' ? b : Number(b.time ?? b.time_seconds ?? b.t)).filter(Number.isFinite);
  const energyPoints = D.audioMap?.energy_curve || D.audioMap?.energy || [];
  function binaryBefore(array, value, get = x => x) {
    let lo = 0, hi = array.length - 1, found = -1;
    while (lo <= hi) { const mid = lo + hi >> 1; if (get(array[mid]) <= value) { found = mid; lo = mid + 1; } else hi = mid - 1; }
    return found;
  }
  function beatAt(t) {
    const i = binaryBefore(beats, t); return i >= 0 ? Math.exp(-(t - beats[i]) * 10) : 0;
  }
  function energyAt(t, s) {
    if (energyPoints.length && typeof energyPoints[0] === 'object') {
      const getTime = p => Number(p.time_seconds ?? p.time ?? p.t ?? 0);
      const i = Math.max(0, binaryBefore(energyPoints, t, getTime));
      return clamp(Number(energyPoints[i].energy ?? energyPoints[i].value ?? energyPoints[i].rms ?? .55));
    }
    return /chorus/i.test(s.section || '') ? .8 : /bridge/i.test(s.section || '') ? .3 : .5;
  }
  function sprite(c, source, x, y, r, alpha) {
    if (r < .1 || alpha <= 0) return;
    c.save(); c.globalAlpha = clamp(alpha); c.drawImage(source, x - r, y - r, r * 2, r * 2); c.restore();
  }
  function project(x, y, z, cam) {
    const f = 770 / Math.max(.12, z);
    return [960 + (x - cam.x) * f, 370 + (y - cam.y) * f, f];
  }
  function plate(c, s, t) {
    const im = pictures[s.asset]; if (!im) return false;
    const p = clamp((t - s.start) / (s.end - s.start)), e = ease(p);
    const n = Number(s.seed || 0), direction = n % 2 ? 1 : -1;
    let z = mix(1.025, 1.15, e), x = .5, y = .48, roll = 0;
    const motion = s.motion || 'push';
    if (/pull|out/.test(motion)) z = mix(1.17, 1.025, e);
    if (/drift|pan|track/.test(motion)) { z = 1.12; x = mix(.39, .61, direction > 0 ? e : 1 - e); }
    if (/rise|crane/.test(motion)) { z = mix(1.10, 1.045, e); y = mix(.69, .35, e); }
    if (/orbit|roll/.test(motion)) { z = 1.12; roll = mix(-.015, .015, e) * direction; x = mix(.43, .57, e); }
    if (/rush|dive|impact/.test(motion)) { z = 1.035 + .25 * (1 - (1 - p) ** 2); y = .45; }
    if (/hold|float/.test(motion)) { z = 1.055; x = .5 + Math.sin(t * .18) * .012; }
    const scale = Math.max(W / im.width, PH / im.height) * z;
    const iw = im.width * scale, ih = im.height * scale;
    c.save(); c.translate(W / 2, PH / 2); c.rotate(roll);
    c.drawImage(im, (W - iw) * x - W / 2, (PH - ih) * y - PH / 2, iw, ih); c.restore();
    return true;
  }
  function ambient(c, t, s, amount, e) {
    c.save(); c.globalCompositeOperation = 'screen';
    for (let i = 0; i < motes.length; i++) {
      const a = motes[i], z = a.z, speed = s.mode === 'runway' ? 2 : 1;
      const x = fract(a.x + Math.sin(t * .12 + a.phase) * .015 * z + t * .002 * z * speed) * W;
      const y = fract(a.y - t * .008 * a.speed * (1 + z)) * PH;
      const twinkle = .58 + .42 * Math.sin(t * .8 + a.phase);
      const alpha = amount * (.11 + z * .38) * twinkle * (y > 730 ? .3 : 1);
      const radius = a.size * (1 + e * .25);
      sprite(c, goldGlow, x, y, radius * 5.5, alpha * .26);
      c.globalAlpha = alpha; c.fillStyle = '#ffdda0'; c.fillRect(x, y, Math.max(.6, radius * .7), Math.max(.8, radius));
    }
    c.restore();
  }
  function floatingLanterns(c, t, s, strength) {
    c.save();
    const foreground = s.mode === 'lanterns';
    for (let i = 0; i < lanterns.length; i++) {
      const a = lanterns[i];
      if (!foreground && i % 4) continue;
      const scale = foreground ? .10 + a.z ** 4 * 1.2 : .12 + a.z ** 3 * .48;
      let x = a.x * W + Math.sin(t * .22 + a.phase) * 15 * a.z;
      const y = (fract(a.y - t * .009 * a.speed) * (PH + 420)) - 220;
      if (!foreground) x = a.side < 0 ? 50 + a.x * 260 : 1620 + a.x * 260;
      const alpha = strength * (.28 + a.z * .62);
      c.save(); c.globalAlpha = alpha; c.translate(x, y); c.rotate(Math.sin(t * .27 + a.phase) * .055);
      c.drawImage(lanternSprite, -110 * scale, -120 * scale, 220 * scale, 360 * scale); c.restore();
    }
    c.restore();
  }
  function ribbonWorld(c, t, s, amount, e) {
    const local = t - s.start, p = clamp(local / (s.end - s.start)), cam = {x: Math.sin(t * .12) * .24, y: -.05};
    const mode = s.mode || '', hero = mode === 'silk' || mode === 'dragon';
    c.save(); c.globalCompositeOperation = 'screen'; c.lineCap = 'round';
    for (let j = 0; j < (hero ? 7 : 3); j++) {
      const r = ribbons[j], points = [];
      for (let k = 0; k <= 88; k++) {
        const u = k / 88, a = u * TAU * 1.35 + t * .24 + r.phase;
        let x, y, z;
        if (mode === 'dragon') {
          x = (u - .5) * 12; y = -1.25 + Math.sin(u * 7.8 + t * .6) * .65 + Math.sin(u * 15 + t * .4) * .12;
          z = 4.9 + Math.cos(a) * 1.1 + j * .045;
        } else {
          x = Math.sin(a) * (2.4 + u * 1.8); y = -1.6 + u * 3.0 + Math.sin(a * 1.2) * .32;
          z = 4.3 + Math.cos(a) * 2.0 + j * .05;
        }
        const q = project(x, y, z, cam); points.push(q);
      }
      for (let thread = 0; thread < (hero ? 5 : 3); thread++) {
        const width = thread === 0 ? 8 : thread === 1 ? 2.5 : .8;
        c.strokeStyle = thread === 0 ? rgba(255, 127, 53, .07 * amount) : rgba(255, 217, 142, (.23 - thread * .025) * amount);
        c.lineWidth = width * (hero ? 1.5 : 1);
        c.beginPath();
        for (let k = 0; k < points.length; k++) {
          const q = points[k], offset = (thread - 2) * (5 + Math.sin(k * .11 + r.phase + t * .3) * 4);
          if (!k) c.moveTo(q[0], q[1] + offset); else c.lineTo(q[0], q[1] + offset);
        }
        c.stroke();
      }
      const head = points[Math.floor(fract(t * .13 + j * .15) * (points.length - 1))];
      sprite(c, goldGlow, head[0], head[1], hero ? 36 : 21, .6 * amount);
    }
    // A restrained, physically connected trail rather than a full-frame flash.
    c.globalAlpha = 1; c.restore();
  }
  function perspectiveStage(c, t, s, strength, e) {
    const mode = s.mode, p = clamp((t - s.start) / (s.end - s.start));
    const cam = {x: Math.sin((s.seed || 0) + t * .1) * .34, y: -.15};
    const horizon = 362;
    c.save(); c.globalCompositeOperation = 'screen';
    const floor = c.createLinearGradient(0, horizon, 0, PH);
    floor.addColorStop(0, '#b2772a00'); floor.addColorStop(.4, rgba(134, 64, 26, .08 * strength)); floor.addColorStop(1, '#07090b00');
    c.fillStyle = floor; c.fillRect(0, horizon, W, PH - horizon);
    // Continuous movement down the runway: frame phases come from absolute song time.
    if (mode === 'runway' || mode === 'portal') {
      for (let i = 22; i >= 0; i--) {
        const z = .8 + fract(i / 23 - t * (mode === 'runway' ? .07 : .027)) * 24;
        const near = clamp(1 - z / 26), alpha = near * near * .40 * strength;
        const left = project(-3.1, -.5, z, cam), right = project(3.1, -.5, z, cam);
        const bottomL = project(-3.1, 2.3, z, cam), bottomR = project(3.1, 2.3, z, cam);
        c.strokeStyle = rgba(234, 159, 74, alpha); c.lineWidth = Math.max(.5, 2.2 * near);
        c.beginPath(); c.moveTo(bottomL[0], bottomL[1]); c.lineTo(left[0], left[1]);
        c.quadraticCurveTo(960 - cam.x * left[2], left[1] - left[2] * 3.0, right[0], right[1]);
        c.lineTo(bottomR[0], bottomR[1]); c.stroke();
        if (i % 3 === 0) {
          sprite(c, goldGlow, left[0], left[1], 13 + near * 21, alpha * .7);
          sprite(c, goldGlow, right[0], right[1], 13 + near * 21, alpha * .7);
        }
      }
      for (let j = -5; j <= 5; j++) {
        const a = project(j * .8, 2.3, .7, cam), b = project(j * .8, 2.3, 29, cam);
        c.strokeStyle = rgba(250, 171, 82, .075 * strength); c.lineWidth = 1;
        c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
      }
    }
    if (mode === 'portal' || mode === 'fireworks') {
      c.save(); c.translate(960 + Math.sin(t * .1) * 12, 393);
      for (let j = 0; j < 8; j++) {
        c.strokeStyle = rgba(255, 199, 105, (.2 - j * .022) * strength); c.lineWidth = j < 2 ? 2 : 1;
        const r = 236 + j * 11 + (mode === 'portal' ? p * 28 : 0);
        c.beginPath(); c.ellipse(0, 0, r, r * .94, 0, -.95 * Math.PI + t * .018, .8 * Math.PI + t * .018); c.stroke();
      }
      c.restore();
    }
    c.globalAlpha = 1; c.restore();
  }
  function celebration(c, t, s, amount) {
    const local = t - s.start;
    c.save(); c.globalCompositeOperation = 'screen';
    // Firework bursts have finite, analytic ballistic paths with persistent trails.
    const launches = [{at:.35, x:.23, y:.29, seed:57}, {at:1.75, x:.78, y:.20, seed:91}, {at:3.15, x:.5, y:.13, seed:123}];
    for (const launch of launches) {
      const age = local - launch.at;
      if (age < 0 || age > 2.5) continue;
      const r = seeded(launch.seed + Number(s.seed || 0)), fade = (1 - age / 2.5) ** 1.7;
      const cx = W * launch.x, cy = PH * launch.y;
      for (let j = 0; j < 76; j++) {
        const theta = j / 76 * TAU + r() * .04, speed = 55 + r() * 95;
        const vx = Math.cos(theta) * speed, vy = Math.sin(theta) * speed * .8;
        const x = cx + vx * age, y = cy + vy * age + 35 * age * age;
        const back = Math.max(0, age - .09);
        c.strokeStyle = rgba(255, 196 + (j % 4) * 12, 116, .6 * fade * amount); c.lineWidth = .8 + r();
        c.beginPath(); c.moveTo(cx + vx * back, cy + vy * back + 35 * back * back); c.lineTo(x, y); c.stroke();
        if (j % 4 === 0) sprite(c, goldGlow, x, y, 6, fade * .5 * amount);
      }
    }
    c.restore();
    c.save();
    for (let j = 0; j < confetti.length; j++) {
      const a = confetti[j], z = a.z;
      const x = fract(a.x + Math.sin(t * .15 + a.phase) * .035 + t * .004 * z) * W;
      const y = fract(a.y + t * .045 * a.speed) * (PH + 200) - 100;
      const rotate = t * (1 + z) + a.phase, width = (2 + z * 5) * Math.cos(rotate);
      c.globalAlpha = (.22 + z * .5) * amount * (y > 790 ? .12 : 1);
      c.fillStyle = j % 5 === 0 ? '#b82028' : j % 3 === 0 ? '#e1a34b' : '#f8dc9d';
      c.save(); c.translate(x, y); c.rotate(rotate * .25); c.fillRect(-width / 2, -3 * z, width, 7 * z); c.restore();
    }
    c.restore();
  }
  function bareWorld(c, t, s) {
    const g = c.createLinearGradient(0, 0, W, PH);
    g.addColorStop(0, '#0e0508'); g.addColorStop(.35, '#030b0e'); g.addColorStop(.7, '#18060b'); g.addColorStop(1, '#020406');
    c.fillStyle = g; c.fillRect(0, 0, W, PH);
    c.save(); c.globalCompositeOperation = 'screen';
    sprite(c, redGlow, 300, 260, 670, .25); sprite(c, goldGlow, 1240, 290, 590, .12);
    c.restore();
  }
  function picture(c, s, t) {
    c.globalAlpha = 1; c.globalCompositeOperation = 'source-over'; c.fillStyle = '#030507'; c.fillRect(0, 0, W, PH);
    const hasPlate = plate(c, s, t), e = energyAt(t, s), beat = beatAt(t), mode = s.mode || 'plate';
    if (!hasPlate) bareWorld(c, t, s);
    const strength = hasPlate ? .68 : 1;
    if (['runway', 'portal', 'fireworks'].includes(mode)) perspectiveStage(c, t, s, strength, e);
    if (['silk', 'dragon'].includes(mode)) ribbonWorld(c, t, s, strength, e);
    if (mode === 'lanterns' || (mode === 'plate' && s.asset === 'avenue')) floatingLanterns(c, t, s, strength);
    ambient(c, t, s, .7 + e * .35, e);
    if (mode === 'fireworks') celebration(c, t, s, .83);
    // Anamorphic highlight remains tied to a plausible light source near the horizon.
    if (mode === 'portal' || mode === 'runway') {
      c.save(); c.globalCompositeOperation = 'screen';
      const g = c.createLinearGradient(200, 0, 1720, 0), a = (.035 + beat * .025) * strength;
      g.addColorStop(0, '#ffcc7700'); g.addColorStop(.4, rgba(255, 170, 83, a));
      g.addColorStop(.5, rgba(255, 220, 155, a * 2)); g.addColorStop(.6, rgba(255, 170, 83, a)); g.addColorStop(1, '#ffcc7700');
      c.fillStyle = g; c.fillRect(200, 389, 1520, 3); c.restore();
    }
    c.globalAlpha = 1; c.globalCompositeOperation = 'source-over'; c.drawImage(vignette, 0, 0);
    // Keep the vocal line readable without surrounding it with a hard subtitle panel.
    const shade = c.createLinearGradient(0, 640, 0, PH);
    shade.addColorStop(0, '#02040500'); shade.addColorStop(.5, '#02040526'); shade.addColorStop(1, '#020405ba');
    c.fillStyle = shade; c.fillRect(0, 640, W, PH - 640);
    const phase = Math.floor(t * 12), ox = phase * 17 % 256, oy = phase * 29 % 256;
    c.save(); c.globalAlpha = .021;
    for (let y = -256 + oy; y < PH; y += 256) for (let x = -256 + ox; x < W; x += 256) c.drawImage(grain, x, y);
    c.restore();
  }
  function renderAt(time) {
    const offset = Number.isFinite(window.BOSSTON_TIME_OFFSET) ? window.BOSSTON_TIME_OFFSET : 0;
    const t = clamp(time + offset, 0, D.duration - .000001);
    const i = Math.max(0, binaryBefore(D.scenes, t, s => s.start)), s = D.scenes[i];
    const age = t - s.start, transition = s.transition || 'cut';
    main.globalAlpha = 1; main.globalCompositeOperation = 'source-over'; main.fillStyle = '#020305'; main.fillRect(0, 0, W, H);
    picture(contexts[0], s, t);
    const duration = transition === 'iris' ? .34 : transition === 'wipe' ? .25 : .18;
    if (i > 0 && age < duration && (transition === 'wipe' || transition === 'iris')) {
      picture(contexts[1], D.scenes[i - 1], Math.min(s.start - .001, D.scenes[i - 1].end - .001));
      main.drawImage(buffers[1], 0, TOP);
      main.save(); const p = smooth(age / duration);
      main.beginPath();
      if (transition === 'iris') main.arc(960, TOP + 400, Math.max(.01, p * 1250), 0, TAU);
      else {
        const x = p * (W + 600) - 300;
        main.moveTo(0, TOP); main.lineTo(x + 220, TOP); main.lineTo(x - 100, TOP + PH); main.lineTo(0, TOP + PH); main.closePath();
      }
      main.clip(); main.drawImage(buffers[0], 0, TOP); main.restore();
    } else main.drawImage(buffers[0], 0, TOP);
    if (i > 0 && age < .15 && transition === 'flash') {
      main.fillStyle = rgba(255, 226, 166, .14 * (1 - age / .15) ** 2); main.fillRect(0, TOP, W, PH);
    }
    const opening = smooth(t / 1.05), ending = smooth((D.duration - t) / 1.2);
    const black = 1 - Math.min(opening, ending);
    if (black > .0001) { main.fillStyle = rgba(2, 3, 5, black); main.fillRect(0, 0, W, H); }
    window.__bosstonTime = t;
  }
  window.renderFilmAt = renderAt;
  window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
  window.__hf.buildReady.bosston = Promise.all(Object.entries(D.assets).map(([id, url]) => new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => { pictures[id] = im; resolve(); };
    im.onerror = () => reject(new Error('Required BOSSTON film image is missing: ' + url)); im.src = url;
  }))).then(() => document.fonts.ready).then(() => {
    window.addEventListener('hf-seek', event => renderAt(event.detail.time)); renderAt(0);
  });
})();
