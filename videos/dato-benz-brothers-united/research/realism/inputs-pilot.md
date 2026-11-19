# Inputs and controlled pilot for a natural Hock Siew film

Research only, observed 19 November 2026. No generation, uploads, paid calls, purchases, installations or project/Git edits were performed by this researcher. The recommendations below are a proposed production protocol, not a claim that any new model has passed a Hock Siew test.

## The most reliable route to an authentic face and body

Prefer real camera footage of Hock Siew for his prominent face, gait, gestures and body. Editing real pixels preserves the photographed person instead of asking a generator to reconstruct his anatomy in each scene. This is an engineering/editorial recommendation, not a benchmark claim that all AI must fail. AI can supply restrained environment/detail inserts or a small number of explicitly approved shots. A cinematic result can come from framing, shot selection, matching light, pacing and colour rather than repeatedly synthesizing the subject.

Do not request dozens of photographs. Start with approximately **6–8 original, unfiltered files**, selecting the most useful existing ones. Practical desired coverage:

1. A clear frontal head-and-shoulders view, relaxed neutral expression.
2. Left three-quarter view.
3. Right three-quarter view.
4. A natural gentle smile/candid expression with visible eyes and mouth.
5. Waist-up view with both hands visible in the intended outfit.
6. Full-body front view with head, torso, feet and hands in frame.
7. Optional side/full-body view and a second natural candid if available.

Use current photographs that represent the same intended age, hair, body proportions and wardrobe. Prefer original camera files rather than screenshots or messaging-app recompressions. Avoid beauty filters, strong wide-angle selfies, sunglasses, people crossing the face and very hard coloured light. Keep the real skin and normal facial asymmetry. A stocky build must be established by actual waist/full-body photographs, not inferred from a cropped face or an AI-created portrait. These quantities are our production recommendations, not published model minimums.

Runway's image-reference guide recommends natural even light and a neutral expression, and its long-film guide warns that a lone angle leaves unseen views underdetermined. The latter recommends neutral multi-angle character plates; for this real-person job, use **actual photographs for those views where possible** instead of treating generated new angles as ground truth. [Reference guide](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References), [long-film guide](https://help.runwayml.com/hc/en-us/articles/26871350018835-How-to-create-longer-videos-and-films).

Each shot should select the relevant original references and assign their roles: identity, body/wardrobe and optional environment. A provider's maximum reference count is not a reason to feed every photograph into every shot. Maintain an originals-only reference board and label any AI-edited image as synthetic. Do not promote a generated face/body into the sole identity authority for subsequent shots.

## Optional phone video is more valuable than many extra photos

If Hock Siew is available, three simple **8–12-second continuous phone clips** would be useful:

- Relaxed waist-up portrait: neutral expression, gentle smile, small head turn; face remains visible.
- A short normal walk: full body in frame, a few ordinary steps, no exaggerated performance.
- Seated cup or hand gesture: hands visible from the start, one modest action.

Record in ordinary soft daylight, steady eye-level framing, the same outfit, without beauty mode, portrait-video blur, cuts or fast camera moves. Native1080p or better originals are sufficient for a useful test; fake4K is not needed. These are capture suggestions, not mandatory specs. If clips already exist, assess them first rather than making him reshoot unnecessarily.

Real clips can be used directly. If performance transfer is tested, match the image's framing, pose and proportions to the driving video. Runway's Kling3 Motion Control guide recommends one fully visible subject, real-person actions, steady continuous shots and matching body coverage. It supports720p/1080p in its web flow, but that does **not** establish that the current connected generation tool exposes its dedicated motion-control settings. [Official motion-control guide](https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control).

Act-Two is another performance route, not a universal full-body realism fix. Its documented best practices favour one well-lit, continuously visible subject framed no wider than waist-up, with hands visible for gesture transfer and modest motion. Its image and video modes preserve/control different things. The published web cost is5credits/second with a3-second minimum; connector availability and current account pricing still need verification before testing. [Official Act-Two guide](https://help.runwayml.com/hc/en-us/articles/42311337895827-Performance-Capture-with-Act-Two).

## Two-stage pilot before a new full film

**Before paid tests:** inspect originals and make a reference board, record missing angles/body coverage, select one real outfit and ordinary lighting, and show the user what will anchor identity. Confirm a small explicit test cap when new references/credits arrive. The current user instruction authorizes research only.

**Stage1 — matched portrait pair:** once future testing is authorized, compare the two candidate routes on the same5-second simple face/head-turn shot first. Review the raw pair before commissioning body shots. Use the same original references, framing, wardrobe, ordinary light and nominal output resolution. Avoid heavy grading, sharpening, interpolation, face restoration or music that might hide errors. Record actual model/version, prompts, references, input-video charges, duration, native resolution and cost.

Root's proposed comparison is Kling O3Pro versus Seedance2 at1080p without audio. At the inspected published Dev rates, one5-second portrait pair is285credits. If it passes, all three cases across both routes total855output-only credits. These are published Dev estimates, **not a connected-workspace quote or authority to spend**; actual image preparation and input/reference-video charges must be added where applicable. The workspace's displayed quote/realized cost controls. [Runway pricing](https://docs.dev.runwayml.com/guides/pricing/).

**Stage2 — body, hands and continuity:** only after the portrait check, compare the same two remaining5-second cases on both routes: waist-up hand/cup action and normal full-body walk. This completes six takes/30seconds of generated output across the two models, not30seconds of guaranteed usable film. Compare all three cases together for the same real face, body and outfit. Keep environments simple; additional outfits and dramatic location changes wait until naturalness passes. A proposed future1,100-credit cap would leave room at these inspected rates for two O3Pro5-second retakes or one Seedance2 retake; that cap needs a live quote and user authorization, and it is not being spent now. Retry only a named defect, not an unbounded search. Assemble a short15–20-second approval pilot from accepted material and an optional genuine-photo anchor, with intended subtitles and restrained finish. Have the user/boss approve it at normal speed before scaling to the entire song. A model wins by the supplied person's acceptance, not a promotional ranking.

View raw candidates at1× speed and full frame, alongside clearly labelled real reference material, before reviewing frame crops. Reject changing face/jaw/ear/hairline, invented weight/height/torso shape, plastic skin, unnatural permanent smiles, eye or mouth drift, hand-object slipping, foot sliding, cloth changes or inconsistent wardrobe/accessories. Test the face and body both during motion and across edits. If the short pilot still looks fake, change the route or use actual footage; do not buy a full-film batch or cover the failure with effects.

Encoding, cadence, SSIM-to-source and successful decoding remain useful delivery checks, but none establishes that the generated subject is naturally Hock Siew. Face-embedding similarity likewise cannot substitute for family/boss recognition or whole-body temporal review.

## Tools/repositories: narrow reuse rather than a pack install

| Source inspected | Licence / maintenance evidence | Fit and decision |
| --- | --- | --- |
| [FFmpeg legal/source](https://ffmpeg.org/legal.html), existing project FFmpeg7.1 pipeline | Core LGPL2.1+ with optional GPL components; the installed static binary enables GPL/version3. Existing runtime, no new dependency. | **Adopt existing editing path** for real-footage trims, native cadence, restrained colour, captions and exact soundtrack. It does not resynthesize the subject. No binary redistribution proposed. |
| [OpenCV](https://github.com/opencv/opencv), inspected head `851cc5baa57391ea5a9571f95eec234dca9ff558`, dated2026-11-19 | Current4.x licence Apache2.0, [licence file](https://github.com/opencv/opencv/blob/4.x/LICENSE); current head activity verified from canonical GitHub API. | **Optional adaptation**, only if basic input focus/exposure or motion diagnostics are missing. These can triage obvious technical defects; they cannot certify identity/naturalness. No install needed for the current research. |
| [Meta SAM2](https://github.com/facebookresearch/sam2), inspected head `2b90b9f5ceec907a1c18123530e92e794ad901a4`, dated2024-12-16 | Code/checkpoints Apache2.0; optional connected-component extension has separate BSD3 notice. The repo's latest listed release activity is2024, so do not describe it as recently updated. | **Defer** until there is a named real-footage masking/compositing need. It can segment video, not repair someone's face. PyTorch/CUDA/checkpoints add cost; Windows documentation recommends WSL/Ubuntu. Ordinary real-footage editing needs none of it. |

No open-source framework, skill pack or face-restoration model was installed. A new tool is justified only after a specific pilot failure and a measurable expected benefit.
