# V3 — a grounded personal tribute

The user preferred the Seedance 2.5 short test and authorized this new cinematic full-song MV with natural backgrounds. V3 is now rendered and ready for client review: technical checks passed, and [VISUAL-REVIEW-V3.md](VISUAL-REVIEW-V3.md) found no blocking defect in the inspected encoded stills. The 45-shot film is a warm personal celebration of friendship, health and happiness. User/boss likeness and creative acceptance remain pending. The original 196.760-second recording and all forty canonical Mandarin lyric cues are unchanged. [DELIVERY-V3.json](DELIVERY-V3.json) summarizes the export and evidence.

## The person and his surroundings

Hock Siew is the user-confirmed left-hand man in the new white-shirt originals, and the man identified by the user in the original seaside photograph. His age, broad face, neck, shoulder width and full build are the reference. Do not slim his torso, borrow the companion's chest logo, invent a more glamorous face, or substitute an anonymous performer. The dark-coat Benz photograph stays out of this film.

Use original photographs as identity evidence throughout. A generated scene or the preferred pilot may be a comparison output, but it does not become the identity source for later generations. The near-duplicate standing photographs do not provide independent side views, gait or hidden-arm evidence.

Keep the film in two familiar, coherent settings: the actual wood-panelled room with his plain white shirt and cream trousers, and a boat/waterfront setting grounded in the original seaside photograph with the burgundy outfit. Use ordinary ambient/window light and realistic surface detail. Water, fabric and gentle camera movement should obey the same lighting and physical space as him. Avoid invented palaces, luxury halls, theatrical fog, oversized lens flares or an orange cinematic cast.

The scenes are newly generated tribute imagery, not evidence that a photographed historical event happened. Naturalness and emotional recognition take priority over spectacle.

## Admitted protagonist sources

Eight Seedance 2.5 sources are admitted for the edit, with 75 seconds of requested generation: seven ten-second takes and a five-second replacement for the clipped-head room-medium take. The source files are 1920×1080 at 24fps, with generated audio off. Source admission uses complete decoding and ten chronological samples per attempt, plus additional crop proofs. It does not establish full-speed naturalness, exact-person recognition or user approval.

| Source alias | Admitted content and constraint |
| --- | --- |
| `hock-room-close` | Solo room portrait, plain white shirt, broad visible build and modest facial movement. |
| `hock-room-medium` | Maps to the five-second repair, with complete headroom and hands/wrists below frame; only 0.2–4.8 seconds admitted. The original clipped-head take is excluded. |
| `hock-window` | Seated room/window moment; mandatory 1600×900 crop excludes an unsupported watch. |
| `hock-tea` | Solo cup lift/settle; sampled contact is plausible, without a continuous-motion guarantee. |
| `hock-doorway` | Tight 704×396 head/shoulder crop excludes an added companion-like badge and watch. It is softer and is not full-body evidence. |
| `hock-boat-wide` | Upper-left 1280×720 crop retains seated head/shoulders and natural boat setting while excluding unsupported accessories. |
| `hock-boat-close` | Face, sea and rail in the full source aspect; tight scalp headroom requires zero letterbox and no extra punch-in. |
| `hock-waterfront` | Upper-left 1280×720 crop retains face, shoulders and ordinary coastal setting while excluding an unsupported watch. |

The [generation ledger](generation-jobs-v3.json), [source review](SOURCE-REVIEW-V3.json), [admitted manifest](native-clips-v3.json) and [edit plan](edit-plan-v3.json) preserve exact file hashes, intervals, source-pixel crops and selection reasons. Required crops are renderer-enforced, and missing-crop/protagonist-retime negative preflight cases were tested. Cropping excludes an unwanted detail; it does not repaint or restore a face, prove body anatomy, or recover the discarded pixels.

## Natural context and the edit

Six new ten-second Gen-4.5 face-free contextual sources are admitted at native 1280×720: water, rain/window, tea, waterfront, trees and a modest table. The first tea-pour attempt was excluded for a near-overflowing rim while pouring continued; the first table attempt was excluded for excessive steam. Their replacements are admitted. The tea repair is admitted only with its enforced 720×405 cup/liquid crop to exclude a malformed teapot and stray object. Its effective detail is therefore below the full 720p source frame.

The rain take contains a physical push/close-focus change rather than the requested static camera. A denser transition sheet was inspected; retain it as a moving-camera shot rather than claiming static-camera compliance. The empty waterfront path and other generated environments are ordinary tribute settings, not verified locations from Hock Siew's biography.

Only the legacy full-frame `sea-dawn` and `wet-footsteps` environmental sources are reused. Old generated protagonist scenes and soft legacy face-free crops are excluded. New sources were selected for a visually grounded world; mandatory crops and their softness are stated rather than presented as native 1080p detail.

The finished edit contains 184.75 seconds of native movement and 12.042 seconds of the original closing photograph over 45 shots. Native source time comprises 146.633 distinct seconds and 38.117 seconds of declared non-adjacent protagonist reprisals across fourteen motifs. Contextual source intervals are not replayed. Repeated portrait motifs return at name refrains; they are not claimed as unique footage, adjacent gesture loops or slow-motion padding.

The original song and vocal phrases set cut placement, and all name-containing cues stay on recipient-labelled sources. Short context changes alternate with longer personal expressions. The opening uses the moving `hock-boat-close` take at source 2 seconds; only the final 12.042 seconds use the authentic seaside photograph and Mandarin dedication. The soundtrack remains complete and unretimed, and text is authored in the edit rather than generated inside video scenes.

The closing copy remains: “献给拿督斯里谢惠福”, “Hock Siew”, “有你，兄弟同心。”, “愿你平安，幸福永久。” and “兄弟情义 · 一路同行”. Keep titles and captions restrained and readable, with clear space around his face.

## Picture finishing and validation

The [V3 renderer](prepare_film_v3.py) completed the native 24fps edit using lossless FFV1 segment staging and one final 1080p H.264/AAC picture encode. The master is 275,380,943 bytes (275.38MB), and the 720p copy is 91,604,950 bytes (91.60MB). The 4,723 picture frames span 196.791667 seconds, covering the original 196.760-second soundtrack. Natural colour and skin/fabric texture are preserved without default sharpening, beauty restoration, synthetic grain or motion interpolation. Protagonist files are native 1920×1080 Seedance 2.5 and stay at normal speed; effective detail depends on any mandatory crop. Native 720p context and smaller crop regions are upscaled for delivery. A 1920×1080 master does not make every input/crop native 1080p. Letterbox is zero so it cannot crop hair or headroom.

[verify_film_v3.py](verify_film_v3.py) passed full master/share decoding, all forty canonical/ASS lyric lines, recipient-labelled name cues and nine sampled encoded-picture bindings. Original audio correspondence measured zero offset, left/right correlations 0.999608/0.999600 and approximately −0.033dB gain; the viewing copy preserves an identical encoded AAC payload. The full local receipt is `renders/v3/Hock-Siew-Personal-Tribute-V3.verification.json`, summarized in [DELIVERY-V3.json](DELIVERY-V3.json).

[VISUAL-REVIEW-V3.md](VISUAL-REVIEW-V3.md) records inspection of all 45 shot samples, name anchors, the moving opening and final dedication, with no blocking defect found in those stills. This is sampled encoded-image review, not complete normal-speed playback or a guarantee about intervening motion. Cropped detail, generated identity and personal recognition remain practical limits; user/boss creative acceptance is pending.

## Actual charges and exclusions

The verified pre-V3 balance was 6,851 credits. Fourteen base submissions used 6,160, and three repairs added 580: **6,740 credits across seventeen attempts**, leaving **111 verified**. The repairs were a five-second Seedance room replacement (340) and two ten-second Gen-4.5 context replacements (240). Excluded original attempts remain charged and recorded. Fourteen new sources are admitted for editing; the other three attempts are excluded.

All seventeen attempts decoded completely and each received ten chronological samples; crop/transition checks are additional scoped evidence. The [ledger](generation-jobs-v3.json) records live workspace deltas, and [SOURCE-REVIEW-V3.json](SOURCE-REVIEW-V3.json) states admission/exclusion limits. Source generation is complete. No extra credit purchase or subscription change occurred, and the small remaining balance is not an automatic new generation batch.

The earlier raw comparison used 425 credits; prior V1/V2 work used 2,224. The research stage itself used zero credits and performed no provider uploads. These historical stages remain separate from V3 production.

Private originals, soundtrack, provider URLs and large media remain local. The project keeps editable source, admission and verification records in Git, preserving V1/V2 and the raw pilot for comparison.
