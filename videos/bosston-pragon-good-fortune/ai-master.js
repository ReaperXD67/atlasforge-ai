/* A single absolute song clock drives AI worlds, lyrics and the final fade. */
(() => {
  const D = window.FILM_DATA, clamp = x => Math.max(0, Math.min(1, x));
  const fade = document.getElementById('render-fade');
  window.__hf = window.__hf || {};
  window.__hf.buildReady = window.__hf.buildReady || {};
  window.__timelines = window.__timelines || {};
  window.__hf.buildReady.bosston = Promise.all([
    window.__hf.buildReady.bosstonAi, document.fonts.ready,
    ...Array.from(document.images, img => img.decode()),
  ]).then(() => {
    window.renderBosstonMasterAt = t => {
      const time = Math.max(0, Math.min(D.duration - .000001, t));
      window.renderAiCinemaAt(time);
      window.renderLyricsAt(time);
      fade.style.opacity = 1 - Math.min(clamp(time / .55), clamp((D.duration - time) / .8));
      window.__bosstonCurrentShot = window.__bosstonAiShot;
    };
    window.renderBosstonMasterAt(0);
  });
})();
