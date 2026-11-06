/*
 * Frame-pure cinematic camera and match-cut primitives.
 * Adapted from HyperFrames ui-focus-zoom and text-match-cut, Apache-2.0.
 * Copyright 2026 HeyGen, Inc. Modifications copyright 2026 AtlasForge contributors.
 * Inspected upstream: de2d21a8abd786ef3d63a6818eda3cad844ea46f.
 * Changes: extracted pure frame functions; removed DOM, CDN, GSAP, skeleton UI,
 * gradient effects and callbacks; added strict inputs, bounded camera coverage,
 * configurable frame handles and exact measured-caption lookup.
 * See docs/licenses/HYPERFRAMES-APACHE-2.0.txt and docs/CINEMATIC_EDIT_PLANS.md.
 */
(function expose(root) {
  "use strict";
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  function number(value, name, low = -Infinity, high = Infinity) {
    if (!Number.isFinite(value) || value < low || value > high) {
      throw new RangeError(`${name} must be finite and within [${low}, ${high}]`);
    }
    return value;
  }
  function integer(value, name, low = 0) {
    number(value, name, low);
    if (!Number.isInteger(value)) throw new RangeError(`${name} must be an integer`);
    return value;
  }
  function progressAt(frame, start, end) {
    number(frame, "frame");
    integer(start, "startFrame");
    integer(end, "endFrame", start + 1);
    return clamp((frame - start) / (end - start), 0, 1);
  }
  function easePeak(value) {
    const x = clamp(number(value, "progress"), 0, 1);
    if (x === 0 || x === 1 || x === 0.5) return x;
    // Same symmetric velocity-peak curve as the inspected match-cut primitive.
    let low = 0;
    let high = 1;
    for (let i = 0; i < 32; i += 1) {
      const t = (low + high) / 2;
      const bx = 3 * (1 - t) ** 2 * t * 0.85 + 3 * (1 - t) * t ** 2 * 0.15 + t ** 3;
      if (bx < x) low = t;
      else high = t;
    }
    const t = (low + high) / 2;
    return 3 * (1 - t) * t ** 2 + t ** 3;
  }
  function focusCameraAt(frame, options) {
    const {
      startFrame, endFrame, anchorX = 50, anchorY = 50,
      startZoom = 1, endZoom = 1.16, driftX = 0, driftY = 0, cycles = 2,
    } = options;
    const p = progressAt(frame, startFrame, endFrame);
    number(anchorX, "anchorX", 0, 100);
    number(anchorY, "anchorY", 0, 100);
    number(startZoom, "startZoom", 1, 4);
    number(endZoom, "endZoom", 1, 4);
    number(driftX, "driftX", 0, 2);
    number(driftY, "driftY", 0, 2);
    integer(cycles, "cycles", 1);
    if (cycles > 8) throw new RangeError("cycles must be at most 8");
    const eased = p * p * (3 - 2 * p);
    const scale = startZoom + (endZoom - startZoom) * eased;
    const coverage = 50 * (scale - 1);
    const amplitudeX = Math.min(driftX, coverage);
    const amplitudeY = Math.min(driftY, coverage);
    const panX = clamp(-(anchorX - 50) * scale, -coverage + amplitudeX, coverage - amplitudeX);
    const panY = clamp(-(anchorY - 50) * scale, -coverage + amplitudeY, coverage - amplitudeY);
    // Finite integer cycles, zero at both endpoints, independent of seek order.
    const envelope = p === 0 || p === 1 ? 0 : Math.sin(Math.PI * p) ** 2;
    const xPercent = panX + Math.sin(2 * Math.PI * cycles * p) * amplitudeX * envelope;
    const yPercent = panY + Math.sin(2 * Math.PI * (cycles + 1) * p) * amplitudeY * envelope;
    return { scale, xPercent, yPercent, progress: p };
  }
  function matchCutAt(frame, options) {
    const {
      cutFrame, halfDurationFrames = 12, axis = "x", distancePercent = 8,
      fromScale = 1, toScale = 1,
    } = options;
    integer(halfDurationFrames, "halfDurationFrames", 1);
    integer(cutFrame, "cutFrame", halfDurationFrames);
    if (!["x", "y", "scale"].includes(axis)) throw new RangeError("Unknown match-cut axis");
    number(distancePercent, "distancePercent", -50, 50);
    number(fromScale, "fromScale", 0.1, 4);
    number(toScale, "toScale", 0.1, 4);
    const p = progressAt(frame, cutFrame - halfDurationFrames, cutFrame + halfDurationFrames);
    const eased = easePeak(p);
    const distance = (2 * eased - 1) * distancePercent;
    return {
      progress: p, scale: fromScale + (toScale - fromScale) * eased,
      xPercent: axis === "x" ? distance : 0, yPercent: axis === "y" ? distance : 0,
      outgoingOpacity: frame < cutFrame ? 1 : 0,
      incomingOpacity: frame < cutFrame ? 0 : 1,
    };
  }
  function captionAtFrame(compiled, frame) {
    number(frame, "frame");
    const caption = compiled.captions.find((item) => item.start_frame <= frame && frame < item.end_frame);
    if (!caption) return null;
    const active = caption.words.findLast((word) => word.start_frame <= frame && frame < word.end_frame);
    return { id: caption.id, text: caption.text, activeWordIndex: active?.index ?? null };
  }
  function dissolveStateAt(frame, {startFrame, endFrame}) {
    const p = progressAt(frame, startFrame, endFrame);
    const q = p * p * (3 - 2 * p);
    // Incoming is composited OVER the fully opaque outgoing layer. Fading both
    // would expose the background and darken an otherwise constant-brightness cut.
    return {outgoingVisible: frame < endFrame, incomingVisible: frame >= startFrame,
      outgoingOpacity: frame < endFrame ? 1 : 0, incomingOpacity: q};
  }
  const api = Object.freeze({ easePeak, focusCameraAt, matchCutAt, captionAtFrame, dissolveStateAt });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.AtlasForgeCinematic = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
