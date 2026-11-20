# V4 visual review

Reviewed at 2026-11-20T05:10:52+00:00. Reviewer: independent storyboard/art worker. This is a pre-encode review of the full 54-shot image film, not a claim that the boss has approved it.

## Evidence and scope

- Reviewed all 54 interior shot views in `v4-renderer/renders/smoke/contact-01.png` through `contact-04.png`, labelled with shot IDs and source times. Their mapping is in `contact-sheets.json`.
- Inspected original 1920×1080 smoke samples for the opening portrait, main song title, Mandarin name anchor, event-photo name anchor, seaside photograph and closing dedication. Relevant examples are `frame-001.png`, `frame-012.png`, `frame-017.png`, `frame-053.png`, `frame-075.png` and `frame-108.png`.
- The fresh `smoke-result.json` records 110 samples covering every shot, zero browser errors and byte-identical repeat seeking. These establish render determinism at sampled times, not artistic approval or final sound sync.
- Plan SHA256 at review: `a9e7b98fa89b395334fa498d66a162386daf898ae90bde2af546edf7a4ea0dcd`.
- The contact sheets precede the final twelve chapter luma-mask changes. No full encoded film or continuous sound playback has been reviewed here. Exact seam timing, lyrical performance sync, compression artifacts and motion comfort still need continuous-picture review.

## Targeted correction recheck

Rechecked at 2026-11-20T05:14:49+00:00 against `v4-renderer/targeted-result.json`, plan SHA256 `8e6b6ee6581e0d3c9e0098a2366d919951f6ddf7d6e3ee9027e49c50926f33b3`. Inspected all three targeted contact sheets (36 samples /18 affected shots), plus full-resolution `targeted/frame-001.png` and `targeted/frame-035.png`.

- **Closed at sampled-frame level — title contrast.** The first correction removed the panel but left dark type on a dark upper-left patch. The final correction moved both lines to the warm upper-right sky. Inspected `v4-renderer/renders/title-final/frame-001.png` at21.193s, full1920×1080, at 2026-11-20T05:15:49+00:00: dark title and dedication are clearly readable, separated from bridge geometry, without a presentation panel or clipping. Final plan SHA256: `7f05e91871dc1958ac75fa473719b5ff57b069bc933d42ca68ca9cab8af1e929`.

- **Closed at sampled-frame level — chorus variety.** Revised non-name shots now show distinct near bronze/bridge, river/home and horizon regions. The tail no longer repeats an indistinguishable wide reveal in the contact-sheet read. Continuous motion comfort and cut rhythm still need encoded review.
- **Closed at sampled-frame level — cup payoff.** s39/s40 use cropped reflection/material views; the complete cup becomes readable at141.61s during the toast phrase. The visual hierarchy now supports the intended lyric.
- **Closed at sampled-frame level — garden template void.** Art-only shots exclude the empty medallion and give the living garden/pond the frame. The seaside-photo anchor remains identifiable.
- **Closed at sampled-frame level — final photo mount.** At193.612s the translated original portrait fits the right-page mount more convincingly. Dedication text is directly on ivory paper, legible and separated from the face. The photo remains a rigid original crop.

## Original priority findings

No P0 identity or content failure was observed in the samples. The original P1 findings below are retained with their evidence; the targeted recheck above is the current status. All five original P1 findings are closed at sampled-frame level after the targeted corrections; no unresolved P0/P1 still-framing finding remains. Continuous encoded review remains outstanding.

### P1 — Main song title has inadequate contrast

**18.20–22.30s, s06; explicit evidence at 21.193s / `smoke/frame-012.png`.** Ivory-white song title and dedication are placed on a pale ivory rectangular panel. The stable interior sample is faint, not merely an entrance fade. The panel also makes the composition look like a presentation callout.

**Change:** use deep ink `#21464a` title and subtitle, remove the panel/background/padding/border, and place the authored type directly over the quiet landscape region. Recheck a settled sample around 20.5–21.2s. Resolved and visually verified in the final title sample described above.

### P1 — Chorus shots need more distinct visual subjects

**81.04–94.34s, s23–s28; 149.32–175.20s, s43–s51.** Contact sheets 02–04 show the same bridge-wide view recurring with photo/pillar toggles. The first-chorus s24/s25/s28 share the same camera path in the inspected plan. In the finale, s50 and s51 repeat the same reveal camera while using the same image; a new cut restarts that view immediately after the last lyric. These are related shots, but the contact-sheet reads remain nearly identical. Increasing the shot count alone does not resolve the user's prior slide-show complaint.

**Change:** keep the authentic-photo name anchors legible, then give the intervening lines different purposeful subjects from the current image: a near bronze/silk detail, the actual crossing, the connected river/homes, then a horizon reveal. Avoid cutting between two almost identical wides or restarting the same reveal at 170.10s. Use a continuous tail move or a meaningfully new region there. No additional generated artwork is required. Recheck one representative frame from each changed composition plus the affected cut in motion.

### P1 — The toast visual is revealed before its lyrical payoff

**133.96–149.32s, s39–s42; evidence at 140.326s / `frame-080.png` and 143.800s / `frame-082.png`.** The complete cup and bridge reflection are already visible before “这一杯敬相识的缘”. At the toast phrase, the edit goes back to a close crop that cuts off much of the cup. The most meaningful visual lands before the line it was designed to support.

**Change:** reserve the readable complete cup/reflection composition for the 141.26s cue. Use tactile paper, silk or reflection details for the two preceding lines, then arrive at the full cup on the toast. Keep the bridge reflection contained in the cup; do not introduce pouring, hands or generated people. Recheck 140.8s versus 141.6s to confirm the intended reveal actually occurs.

### P1 — The garden's empty medallion looks like an unfilled template

**119.42–133.96s, s35–s38; `contact-03.png`, especially 129.458s / `frame-074.png` and 133.026s / `frame-076.png`.** A large blank cream circular panel occupies roughly the left quarter to third of the image. The real photograph floats separately on the right or far left instead of using that architectural area. The empty panel attracts attention without contributing to the lyric.

**Change:** frame the garden so the empty medallion is outside the composition, or make that architecture the intentional carrier for a genuine photographic print. Preserve the original photo pixels and keep the actual face unobstructed. Avoid filling it with another title block. Recheck both a photo-bearing and an art-only garden shot.

### P1 — Closing photograph is offset from its physical mount

**185.10–196.76s, s54; 193.612s / `frame-108.png`.** The actual portrait sits at the left side of the large right-page mount, leaving a broad blank area on the right. This weakens the illusion that the photograph belongs to the book and makes the composite read as a floating card.

**Change:** translate the original rigid photo plane to align with the right-page mount; keep the crop and aspect ratio unchanged. Root applied x=5.3 rather than x=3.8, plus removing the rectangular title panel. The translated image and dedication were verified in the targeted final sample described above. Do not regenerate or retouch Hock.

## Identity and content observations

The sampled portraits consistently show the user-confirmed Hock Siew. The event crop excludes the surrounding men's faces. The seaside crop excludes the companion's face; a hand/body fragment remains within the original photograph, but it does not present a second honoree. No face obstruction, body reconstruction, generated human likeness, unintended readable generated text or clipped lyric was observed in the inspected views. The closing copy celebrates health, happiness and ongoing friendship; it does not read as a funeral dedication.

The art maintains the ivory/bronze/blue-green/cinnabar material system. The storm, confluence, braid, coastal and cup plates have readable symbolic differences. The final world is brighter and more saturated than the earlier scenes; whether that transition feels earned remains a motion-and-music question, not established by a still contact sheet.

## Recheck boundary

Only changed shots need fresh full-resolution framing samples. Changed seams need short motion inspection. This document does not request a redundant complete smoke pass after isolated typography or photo-plane translations. A continuous encoded review is still needed after these pre-encode corrections to establish that the film feels paced to the song rather than a sequence of polished still cards.
