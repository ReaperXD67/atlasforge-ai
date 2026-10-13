/* For My Sweetheart — deterministic optical atmosphere and impossible worlds.
 * All movement is an analytic function of the supplied ROOT film time.
 * draw(ctx, seconds, theme, energy, width, height, {full:false, strength:1})
 * Transparent mode does not clear the canvas or change the underlying plate.
 * Complete worlds are available for eclipse, cosmos and fracture.
 */
(function (global) {
  'use strict';

  const W = 1920, H = 1080, TAU = Math.PI * 2;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const fract = v => v - Math.floor(v);
  const mix = (a, b, p) => a + (b - a) * p;
  const smooth = p => { p = clamp(p, 0, 1); return p * p * (3 - 2 * p); };
  function rng(seed) {
    let s = seed >>> 0;
    return function () {
      s += 0x6D2B79F5;
      let v = Math.imul(s ^ (s >>> 15), 1 | s);
      v ^= v + Math.imul(v ^ (v >>> 7), 61 | v);
      return ((v ^ (v >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = rng(14102026);
  const stars = Array.from({length: 620}, () => ({
    x: (rand() - 0.5) * 6.2, y: (rand() - 0.5) * 3.8,
    z: rand(), radius: 0.35 + rand() ** 5 * 1.6,
    lum: 0.18 + rand() * 0.66, phase: rand() * TAU, warm: rand() > 0.71
  }));
  const motes = Array.from({length: 170}, () => ({
    x: rand(), y: rand(), z: 0.12 + rand() * 0.88,
    r: 0.35 + rand() ** 4 * 2.8, p: rand() * TAU, speed: 0.18 + rand() * 0.7
  }));
  const drops = Array.from({length: 115}, () => ({
    x: rand(), y: rand(), z: 0.1 + rand() * 0.9, p: rand() * TAU
  }));
  const shards = Array.from({length: 27}, (_, i) => {
    const a = rand() * TAU;
    const r = 0.55 + rand() * 1.85;
    return {
      x: Math.cos(a) * r * 1.25, y: Math.sin(a) * r * 0.78,
      z: 0.7 + rand() * 2.8, size: 0.17 + rand() * 0.38,
      roll: rand() * TAU, tilt: 0.3 + rand() * 0.85,
      p: rand() * TAU, k: i,
      shape: [[-0.64, -1], [0.66 + rand() * 0.45, -0.22],
        [0.24 + rand() * 0.2, 0.95], [-0.72, 0.22 + rand() * 0.28]]
    };
  }).sort((a, b) => b.z - a.z);
  const cache = Object.create(null);
  const colors = {
    eclipse: [224, 144, 111], cathedral: [176, 152, 111], ocean: [134, 172, 181],
    memory: [233, 204, 166], fracture: [205, 65, 81], cosmos: [177, 151, 196],
    lily: [189, 189, 215], dawn: [250, 212, 162]
  };
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${clamp(a, 0, 1)})`;

  function surface(w, h) {
    if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(w, h);
    const c = document.createElement('canvas'); c.width = w; c.height = h; return c;
  }
  function glow(c, x, y, radius, color, alpha, inner) {
    if (radius <= 0 || alpha <= 0) return;
    const g = c.createRadialGradient(x, y, inner || 0, x, y, radius);
    g.addColorStop(0, rgba(color, alpha));
    g.addColorStop(0.23, rgba(color, alpha * 0.46));
    g.addColorStop(0.65, rgba(color, alpha * 0.10));
    g.addColorStop(1, rgba(color, 0));
    c.fillStyle = g; c.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  }
  function polygon(c, pts) {
    c.beginPath(); c.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]);
    c.closePath();
  }

  // Small, seeded photographic cloud plates. They are computed once, never per frame.
  function nebula(kind) {
    const key = `nebula-${kind}`;
    if (cache[key]) return cache[key];
    const img = surface(1200, 720), c = img.getContext('2d');
    const r = rng(kind === 'red' ? 899 : 1551);
    const a = kind === 'red' ? [104, 20, 34] : [53, 39, 86];
    const b = kind === 'red' ? [216, 69, 63] : [165, 93, 141];
    c.globalCompositeOperation = 'screen';
    for (let i = 0; i < 330; i++) {
      const u = r();
      const x = u * 1500 - 150;
      const y = 510 - u * 390 + 88 * Math.sin(u * 7.6) + (r() - 0.5) * 145;
      const size = 18 + r() ** 2 * 165;
      glow(c, x, y, size, i % 5 === 0 ? b : a, 0.012 + r() * 0.037);
    }
    c.globalCompositeOperation = 'destination-out';
    for (let i = 0; i < 75; i++) {
      const u = r(), x = u * 1360 - 80;
      const y = 497 - u * 375 + 89 * Math.sin(u * 7.6) + (r() - 0.5) * 45;
      glow(c, x, y, 20 + r() * 96, [0, 0, 0], 0.05 + r() * 0.22);
    }
    c.globalCompositeOperation = 'screen';
    for (let i = 0; i < 95; i++) {
      const u = r(), x = u * 1440 - 120;
      const y = 510 - u * 390 + 88 * Math.sin(u * 7.6) + (r() - 0.5) * 100;
      glow(c, x, y, 3 + r() * 29, b, 0.025 + r() * 0.065);
    }
    cache[key] = img; return img;
  }

  function corona() {
    if (cache.corona) return cache.corona;
    const img = surface(1000, 1000), c = img.getContext('2d'), r = rng(99812);
    const cx = 500, cy = 500, radius = 240;
    glow(c, cx, cy, 495, [191, 39, 30], 0.28, 230);
    const g = c.createRadialGradient(cx, cy, 228, cx, cy, 398);
    g.addColorStop(0, 'rgba(255,246,214,0)');
    g.addColorStop(0.066, 'rgba(255,244,214,.87)');
    g.addColorStop(0.095, 'rgba(255,206,145,.74)');
    g.addColorStop(0.19, 'rgba(244,119,78,.18)');
    g.addColorStop(0.48, 'rgba(188,42,36,.038)');
    g.addColorStop(1, 'rgba(90,10,24,0)');
    c.fillStyle = g; c.fillRect(0, 0, 1000, 1000);
    c.globalCompositeOperation = 'screen';
    for (let i = 0; i < 1850; i++) {
      const a = r() * TAU;
      const stream = 0.28 + (0.5 + 0.5 * Math.sin(a * 3.4 + 2.7)) ** 5;
      const length = 5 + r() ** 3 * 134 * stream;
      const start = radius + r() * 3;
      const turn = (r() - 0.5) * 0.15;
      const x = cx + Math.cos(a) * start, y = cy + Math.sin(a) * start;
      const ex = cx + Math.cos(a + turn) * (start + length);
      const ey = cy + Math.sin(a + turn) * (start + length);
      const fade = c.createLinearGradient(x, y, ex, ey);
      fade.addColorStop(0, `rgba(255,${190 + (r() * 60 | 0)},156,${0.10 + r() * 0.25})`);
      fade.addColorStop(1, 'rgba(190,35,21,0)');
      c.strokeStyle = fade; c.lineWidth = 0.35 + r() * 1.0;
      c.beginPath(); c.moveTo(x, y);
      c.quadraticCurveTo(cx + Math.cos(a - turn) * (start + length * 0.58),
        cy + Math.sin(a - turn) * (start + length * 0.58), ex, ey); c.stroke();
    }
    // An irregular photosphere rather than a perfect vector-circle edge.
    for (let j = 0; j < 6; j++) {
      c.beginPath();
      for (let i = 0; i <= 860; i++) {
        const a = i / 860 * TAU;
        const rr = radius + j * 0.72 + Math.sin(a * 67) * 0.48 + Math.sin(a * 113) * 0.28;
        const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
        if (!i) c.moveTo(x, y); else c.lineTo(x, y);
      }
      c.strokeStyle = `rgba(255,233,190,${0.16 - j * 0.019})`;
      c.lineWidth = 0.8; c.stroke();
    }
    cache.corona = img; return img;
  }

  function accretion() {
    if (cache.ring) return cache.ring;
    const img = surface(1600, 760), c = img.getContext('2d'), r = rng(41021);
    c.translate(800, 380); c.scale(1, 0.36);
    c.globalCompositeOperation = 'screen';
    for (let i = 0; i < 380; i++) {
      const radius = 265 + r() ** 1.5 * 420;
      const start = r() * TAU, span = 0.18 + r() * 1.25;
      const heat = (1 - (radius - 265) / 420) ** 2;
      c.strokeStyle = `rgba(${198 + heat * 57 | 0},${67 + heat * 159 | 0},${53 + heat * 106 | 0},${0.015 + heat * 0.13})`;
      c.lineWidth = 0.6 + r() * 3.5;
      c.beginPath(); c.arc(0, 0, radius, start, start + span); c.stroke();
    }
    for (let i = 0; i < 40; i++) {
      const radius = 268 + i * 1.5;
      c.strokeStyle = `rgba(255,226,182,${0.041 * (1 - i / 40)})`;
      c.lineWidth = 1.4; c.beginPath(); c.arc(0, 0, radius, 0, TAU); c.stroke();
    }
    cache.ring = img; return img;
  }

  function starfield(c, t, energy, amount, camera) {
    const cam = camera || 1;
    const ox = Math.sin(t * 0.011) * 0.14 * cam;
    const oy = Math.cos(t * 0.009 + 1) * 0.07 * cam;
    c.save(); c.globalCompositeOperation = 'screen';
    for (let i = 0; i < stars.length; i++) {
      const p = stars[i];
      const q = fract(p.z - t * 0.0023 * cam);
      const z = 0.65 + q * 3.2;
      const depthFade = smooth(q / 0.07) * smooth((1 - q) / 0.08);
      const f = 730 / z;
      const x = 960 + (p.x - ox) * f, y = 510 + (p.y - oy) * f;
      if (x < -10 || x > W + 10 || y < -10 || y > H + 10) continue;
      const rr = p.radius * (0.75 + 0.58 / z);
      const lum = p.lum * depthFade * amount * (0.86 + 0.14 * Math.sin(t * 0.4 + p.phase));
      c.fillStyle = rgba(p.warm ? [244, 191, 156] : [194, 209, 232], lum);
      c.beginPath(); c.arc(x, y, rr, 0, TAU); c.fill();
      if (p.radius > 1.35) {
        glow(c, x, y, rr * 6, p.warm ? [255, 163, 118] : [159, 187, 231], lum * 0.28);
        if (i % 3 === 0) {
          c.fillStyle = rgba([226, 211, 215], lum * 0.12);
          c.fillRect(x - rr * 9, y - 0.25, rr * 18, 0.5);
        }
      }
    }
    c.restore();
  }

  function cloudField(c, t, energy, kind, alpha) {
    c.save(); c.globalCompositeOperation = 'screen'; c.globalAlpha *= alpha;
    const dx = 28 * Math.sin(t * 0.012), dy = 16 * Math.cos(t * 0.015);
    c.drawImage(nebula(kind), -230 + dx, -155 + dy, 2440, 1464);
    c.globalAlpha *= 0.34;
    c.translate(960, 540); c.rotate(-0.12 + Math.sin(t * 0.006) * 0.025);
    c.drawImage(nebula(kind), -1460, -560, 2440, 1464);
    c.restore();
  }

  function vignette(c, amount) {
    const g = c.createRadialGradient(960, 490, 300, 960, 500, 1120);
    g.addColorStop(0, 'rgba(0,0,0,0)');
    g.addColorStop(0.55, `rgba(0,0,0,${amount * 0.16})`);
    g.addColorStop(1, `rgba(0,0,0,${amount})`);
    c.fillStyle = g; c.fillRect(0, 0, W, H);
  }

  function opticalStreak(c, x, y, color, alpha, width) {
    c.save(); c.globalCompositeOperation = 'screen';
    const g = c.createLinearGradient(x - width, y, x + width, y);
    g.addColorStop(0, rgba(color, 0)); g.addColorStop(0.45, rgba(color, alpha * 0.35));
    g.addColorStop(0.5, rgba(color, alpha)); g.addColorStop(0.55, rgba(color, alpha * 0.35));
    g.addColorStop(1, rgba(color, 0));
    c.fillStyle = g; c.fillRect(x - width, y - 1, width * 2, 2);
    glow(c, x, y, 30, color, alpha * 0.38); c.restore();
  }

  function eclipse(c, t, energy) {
    c.fillStyle = '#030407'; c.fillRect(0, 0, W, H);
    cloudField(c, t, energy, 'red', 0.58);
    starfield(c, t, energy, 0.72, 0.7);
    const x = 974 + Math.sin(t * 0.009) * 52;
    const y = 455 + Math.cos(t * 0.013) * 22;
    const size = 0.94 + Math.sin(t * 0.007) * 0.075 + energy * 0.018;
    c.save(); c.translate(x, y); c.scale(size, size);
    c.save(); c.globalCompositeOperation = 'screen';
    glow(c, -55, 30, 600, [157, 26, 31], 0.09);
    c.rotate(-0.115 + Math.sin(t * 0.009) * 0.026);
    c.globalAlpha *= 0.9; c.drawImage(accretion(), -800, -380);
    c.restore();
    c.save(); c.rotate(t * 0.004); c.drawImage(corona(), -500, -500); c.restore();
    const disc = c.createRadialGradient(-90, -120, 20, 0, 0, 241);
    disc.addColorStop(0, '#030306'); disc.addColorStop(0.82, '#020204');
    disc.addColorStop(0.985, '#080408'); disc.addColorStop(1, '#2b1111');
    c.fillStyle = disc; c.beginPath(); c.arc(0, 0, 240, 0, TAU); c.fill();
    // Only the near edge crosses the silhouette; most light remains off the faces/text.
    c.save(); c.rotate(-0.115 + Math.sin(t * 0.009) * 0.026);
    c.beginPath(); c.rect(-800, 10, 1600, 370); c.clip();
    c.globalCompositeOperation = 'screen'; c.globalAlpha *= 0.8;
    c.drawImage(accretion(), -800, -380); c.restore();
    c.globalCompositeOperation = 'screen';
    glow(c, -225, -79, 69, [255, 224, 171], 0.17 + energy * 0.08);
    c.restore();
    opticalStreak(c, x - size * 229, y - size * 64, [227, 120, 97], 0.1, 430);
    vignette(c, 0.72);
  }

  function cosmos(c, t, energy) {
    c.fillStyle = '#040408'; c.fillRect(0, 0, W, H);
    cloudField(c, t, energy, 'violet', 1.4);
    starfield(c, t, energy, 0.95, 1.1);
    const px = -270 + Math.sin(t * 0.012) * 46, py = 930;
    const radius = 675 + Math.cos(t * 0.008) * 18;
    c.save(); c.globalCompositeOperation = 'screen';
    const rim = c.createRadialGradient(px, py, radius - 10, px, py, radius + 45);
    rim.addColorStop(0, 'rgba(53,34,81,0)'); rim.addColorStop(0.18, 'rgba(159,108,172,.17)');
    rim.addColorStop(0.32, 'rgba(188,140,179,.3)'); rim.addColorStop(1, 'rgba(43,26,61,0)');
    c.fillStyle = rim; c.fillRect(0, 0, 800, H); c.restore();
    const planet = c.createRadialGradient(px + 280, py - 360, 20, px - 130, py + 100, radius * 1.25);
    planet.addColorStop(0, '#15101d'); planet.addColorStop(0.34, '#080811'); planet.addColorStop(0.73, '#020306');
    c.fillStyle = planet; c.beginPath(); c.arc(px, py, radius, 0, TAU); c.fill();
    // Thin orbital dust, interrupted and defocused: physical trails rather than graphic rings.
    c.save(); c.translate(1050, 507); c.rotate(-0.33); c.scale(1, 0.32);
    for (let j = 0; j < 8; j++) {
      c.strokeStyle = `rgba(163,124,161,${0.016 - j * 0.0015})`;
      c.lineWidth = 1.7 + j * 0.4;
      c.beginPath(); c.arc(0, 0, 600 + j * 8, 3.42, 5.41); c.stroke();
    }
    c.restore();
    glow(c, 1330 + Math.sin(t * 0.023) * 22, 322, 245, [215, 139, 134], 0.1);
    opticalStreak(c, 1340, 321, [215, 168, 166], 0.18, 310);
    vignette(c, 0.68);
  }

  function fracture(c, t, energy) {
    c.fillStyle = '#030407'; c.fillRect(0, 0, W, H);
    cloudField(c, t, energy, 'red', 1.02);
    starfield(c, t, energy, 0.46, 0.65);
    glow(c, 1240, 345, 570, [133, 24, 37], 0.13);
    const light = c.createLinearGradient(530, 130, 1450, 820);
    light.addColorStop(0, 'rgba(165,47,57,0)'); light.addColorStop(0.46, 'rgba(178,46,57,.065)');
    light.addColorStop(0.52, 'rgba(211,77,80,.12)'); light.addColorStop(1, 'rgba(133,20,48,0)');
    c.fillStyle = light; c.fillRect(0, 0, W, H);
    for (const s of shards) {
      const sway = Math.sin(t * 0.07 + s.p) * 0.07;
      const depth = s.z + Math.sin(t * 0.024 + s.p) * 0.13;
      const perspective = 765 / depth;
      const x = 960 + (s.x + Math.sin(t * 0.012) * 0.11) * perspective;
      const y = 510 + (s.y + Math.cos(t * 0.014) * 0.045) * perspective;
      const sz = s.size * perspective;
      const angle = s.roll + t * (0.003 + s.k % 4 * 0.0007);
      const tilt = s.tilt + Math.sin(t * 0.026 + s.p) * 0.17;
      const ca = Math.cos(angle), sa = Math.sin(angle);
      const pts = s.shape.map(p => {
        const xx = p[0] * sz * tilt, yy = p[1] * sz;
        return [x + xx * ca - yy * sa, y + xx * sa + yy * ca];
      });
      c.save(); polygon(c, pts); c.clip();
      const glass = c.createLinearGradient(x - sz, y - sz, x + sz, y + sz);
      glass.addColorStop(0, 'rgba(129,77,104,.10)');
      glass.addColorStop(0.4, 'rgba(22,29,42,.32)');
      glass.addColorStop(0.73, 'rgba(174,43,65,.075)');
      glass.addColorStop(1, 'rgba(224,150,166,.18)');
      c.fillStyle = glass; c.fillRect(x - sz * 2, y - sz * 2, sz * 4, sz * 4);
      c.save(); c.globalCompositeOperation = 'screen';
      c.globalAlpha *= 0.22 + 0.16 * (0.5 + 0.5 * Math.sin(t * 0.07 + s.p));
      c.translate(x, y); c.rotate(-angle * 0.3 + sway);
      c.drawImage(nebula('red'), -780 + s.k * 17, -440, 1680, 1000); c.restore();
      // A broad moving specular reflection gives each fragment a solid optical plane.
      const spec = c.createLinearGradient(x - sz, y, x + sz, y + sz * 0.5);
      const p = 0.42 + Math.sin(t * 0.025 + s.p) * 0.2;
      spec.addColorStop(0, 'rgba(222,197,206,0)');
      spec.addColorStop(Math.max(0.02, p - 0.12), 'rgba(222,197,206,0)');
      spec.addColorStop(p, `rgba(239,210,206,${0.025 + energy * 0.028})`);
      spec.addColorStop(Math.min(0.98, p + 0.14), 'rgba(222,197,206,0)');
      spec.addColorStop(1, 'rgba(222,197,206,0)');
      c.fillStyle = spec; c.fillRect(x - sz * 2, y - sz * 2, sz * 4, sz * 4);
      c.restore();
      // Just the light-facing bevel, never a neon wireframe outline.
      const edge = c.createLinearGradient(pts[0][0], pts[0][1], pts[1][0], pts[1][1]);
      edge.addColorStop(0, 'rgba(224,186,193,0)');
      edge.addColorStop(0.5, `rgba(226,170,180,${0.12 + 0.13 / depth})`);
      edge.addColorStop(1, 'rgba(236,129,147,0)');
      c.strokeStyle = edge; c.lineWidth = Math.min(1.5, 1.1 / depth);
      c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); c.lineTo(pts[1][0], pts[1][1]);
      c.lineTo(pts[2][0], pts[2][1]); c.stroke();
    }
    opticalStreak(c, 1290, 352, [227, 96, 116], 0.12, 350);
    vignette(c, 0.69);
  }

  function particles(c, t, theme, energy, strength) {
    const color = colors[theme] || colors.memory;
    c.save(); c.globalCompositeOperation = 'screen';
    for (let i = 0; i < motes.length; i++) {
      const p = motes[i];
      const z = p.z;
      const speed = p.speed * (0.7 + z * 1.6);
      const x = fract(p.x + t * 0.0022 * speed + Math.sin(t * 0.035 + p.p) * 0.015) * (W + 140) - 70;
      const y = fract(p.y - t * 0.0018 * speed + Math.sin(t * 0.026 + p.p) * 0.014) * (H + 100) - 50;
      const edge = smooth(Math.min(x / 110, (W - x) / 110, y / 100, (H - y) / 100));
      const alpha = (0.05 + z * 0.21) * (0.65 + 0.35 * Math.sin(p.p + t * 0.22) ** 2) * strength * edge;
      const rr = p.r * (0.55 + z);
      if (rr > 2.4) glow(c, x, y, rr * 3, color, alpha * 0.55);
      c.fillStyle = rgba(theme === 'fracture' && i % 4 === 0 ? [223, 66, 88] : color, alpha);
      c.beginPath(); c.ellipse(x, y, rr * 0.6, rr, -0.4, 0, TAU); c.fill();
    }
    c.restore();
  }

  function rain(c, t, theme, strength) {
    c.save(); c.globalCompositeOperation = 'screen';
    const color = theme === 'lily' ? [176, 185, 216] : [141, 170, 184];
    for (const p of drops) {
      const x = fract(p.x - t * (0.006 + p.z * 0.006)) * (W + 120) - 60;
      const y = fract(p.y + t * (0.065 + p.z * 0.11)) * (H + 140) - 70;
      const length = 8 + p.z ** 3 * 34;
      c.strokeStyle = rgba(color, (0.014 + p.z * 0.055) * strength);
      c.lineWidth = 0.38 + p.z * 0.55;
      c.beginPath(); c.moveTo(x, y); c.lineTo(x - length * 0.22, y + length); c.stroke();
    }
    c.restore();
  }

  function veils(c, t, theme, energy, strength) {
    const color = colors[theme] || colors.memory;
    c.save(); c.globalCompositeOperation = 'screen';
    if (theme === 'cosmos' || theme === 'eclipse' || theme === 'fracture') {
      c.globalAlpha *= strength * 0.29;
      c.drawImage(nebula(theme === 'cosmos' ? 'violet' : 'red'),
        -180 + Math.sin(t * 0.015) * 38, 20 + Math.cos(t * 0.013) * 20, 2260, 1300);
    } else if (theme === 'cathedral') {
      // Pale oblique volumes of light; enough texture to feel like dust in a real room.
      c.translate(1350 + Math.sin(t * 0.02) * 28, -120); c.rotate(0.34);
      for (let i = 0; i < 4; i++) {
        const x = i * 143 - 290;
        const g = c.createLinearGradient(x - 80, 0, x + 80, 0);
        g.addColorStop(0, rgba(color, 0)); g.addColorStop(0.5, rgba(color, strength * 0.022));
        g.addColorStop(1, rgba(color, 0)); c.fillStyle = g;
        c.beginPath(); c.moveTo(x - 45, 0); c.lineTo(x + 45, 0);
        c.lineTo(x + 180, 1450); c.lineTo(x - 180, 1450); c.closePath(); c.fill();
      }
    } else {
      const warm = theme === 'dawn' || theme === 'memory';
      const x = (warm ? 1540 : 250) + Math.sin(t * 0.017) * 110;
      glow(c, x, warm ? 245 : 630, warm ? 700 : 540, color, strength * (warm ? 0.035 : 0.014));
    }
    c.restore();
  }

  function draw(ctx, t, theme, energy, width, height, opts) {
    if (!ctx || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return;
    opts = opts || {};
    t = Number.isFinite(t) ? Math.max(0, t) : 0;
    energy = Number.isFinite(energy) ? clamp(energy, 0, 1) : 0.4;
    theme = Object.prototype.hasOwnProperty.call(colors, theme) ? theme : 'memory';
    const strength = Number.isFinite(opts.strength) ? clamp(opts.strength, 0, 2) : 1;
    const scale = Math.max(width / W, height / H);
    ctx.save(); ctx.translate((width-W*scale)/2,(height-H*scale)/2); ctx.scale(scale,scale);
    ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
    if (opts.full) {
      if (theme === 'eclipse') eclipse(ctx, t, energy);
      else if (theme === 'fracture') fracture(ctx, t, energy);
      else cosmos(ctx, t, energy);
    } else {
      veils(ctx, t, theme, energy, strength);
    }
    particles(ctx, t, theme, energy, strength * (opts.full ? 0.56 : 1));
    if (theme === 'ocean' || theme === 'lily') rain(ctx, t, theme, strength);
    ctx.restore();
  }

  global.SweetheartAtmosphere = Object.freeze({draw});
})(window);
