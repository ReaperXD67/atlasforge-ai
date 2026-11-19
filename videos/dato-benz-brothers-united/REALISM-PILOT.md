# Natural-person pilot before a new music video

**Current stage: both raw portrait tests are ready for user review, not accepted.** The user completed the Max upgrade, then requested Kling and Seedance 2.5 short tests before a full MV. Both jobs completed and returned 1920×1080 at 24fps, 5.041667 seconds (121 frames), without audio. Research itself spent zero credits; the current pair charged 425 credits and the final verified balance is 6,851. No further generation or full-song batch starts before user review.

## Reference set

Use approximately6–8 useful original, unfiltered camera files where available: front face, left/right three-quarter, natural expression, waist-up with hands, and full-body front/side. These are production recommendations, not provider minimums. Choose a consistent intended age, real outfit and hairstyle. Keep originals separate from any edited/compositional image and preserve hashes. Reserve a different real view as a comparison not supplied to the model.

Three new full-body frontal photographs have been received. The user explicitly marked Hock Siew as the left-hand man. Use the unmarked originals, not the red-annotated screenshot. These near-duplicate images strengthen frontal body/outfit evidence but do not fill side-view or motion gaps. A partially occluded arm must not be treated as fully observed anatomy.

If suitable clips exist, short genuine phone/event footage is the preferred main material. Optional captures of8–12seconds each—a relaxed head turn, normal full-body walk and simple seated hand/cup gesture—would give actual behaviour that still photographs cannot. Use steady eye-level framing, ordinary soft daylight, no beauty filters or forced performance. Assess existing footage before asking for new filming. See the [official reference guide](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References) and [Motion Control input guidance](https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control).

## Controlled model test

1. **Prepare the originals-only reference board.** Explicitly mark identity, body/wardrobe and environment roles. Do not select an AI-generated face as identity truth. Choose one ordinary lighting setup and actual outfit; avoid changing model, age, clothes, location and camera style at once.
2. **Portrait pair first:** one five-second neutral head/three-quarter turn with Kling O3 Pro and one with Seedance 2.5, selected in the user's latest instruction instead of the earlier proposed Seedance 2.0. Use best supported reference controls from the same real material, 1080p requested, native audio off. Record any parameter/feature differences; do not pretend the two APIs expose identical settings. Review raw output before ordering body shots.
3. **Later tests need separate authorization after user review.** If the portrait is convincing and further testing is authorized, compare a five-second waist-up hand/cup action and then a five-second normal full-body walk. If the references do not support a credible body/movement test, use real footage or obtain the missing evidence first. Do not fill the gap with a generic body description.
4. **Review every generated clip completely at 1× speed, full frame.** Compare with real photos and real motion when available. Inspect suspect moments frame by frame after playback. Check changing face shape, hairline/ears/jaw, normal skin and expressions, torso/head/shoulder proportions, posture and gait, foot contact, hand/object contact, cloth and shadows. Compare the accepted views together across cuts.
5. **A later 15–20-second edited pilot needs user/boss review** before the full song is generated. Build it only from accepted material after the next stage is authorized. Supply raw candidates as well as the restrained finished sample. No hard likeness/body/motion failure can be averaged away by attractive lighting or a high similarity score. If neither model passes, change the route toward genuine footage rather than scale the failure.

No new-model superiority is measured yet. Exact-person recognition and naturalness require the people who know him to judge the motion, not just an agent's selected still samples.

## Current pair and records

The first pair uses only original `assets/references-v3/originals/photo_2026-11-19_17-27-29.jpg` and `assets/photos/seaside.jpg`. Hock Siew is the left-hand man in the first, which supplies identity, frontal torso proportions and his actual white shirt. The seaside image supplies alternate facial evidence only. No generated anchor, invented cup action or full-body walk is part of this first test. Portrait framing cannot establish natural gait, feet or hidden-arm anatomy.

| Candidate | Task ID | Requested output | Realized submission charge |
| --- | --- | --- | --- |
| Kling O3 Pro | `491d93e2-2310-48e0-90ed-fcbca5e4b942` | 5s, 1080p, audio off | 85 credits |
| Seedance 2.5 | `566fd028-cd6b-4763-83d9-99f7f80b935e` | 5s, 1080p, audio off | 340 credits |

The post-upgrade balance was 7,276; observed submission balances were 7,191 and 6,851, a 425-credit total. No Max discount was observed on these calls. These costs supersede the earlier 285-credit planning estimate for a different Seedance 2.0 pair; that estimate is not a quote for this run. No retries, body tests or full-song batch are authorized by the remaining balance alone.

[pilot-v3.json](pilot-v3.json) retains original reference hashes/roles, model and exposed controls, exact prompt, task IDs, native metadata, realized costs, observations and user/boss verdict. Preserve complete untouched outputs; show both at 1× speed before any music, grading, retiming or selective edit. Technical decoding and visual still checks do not establish motion realism. Keep failed attempts and total costs in the comparison. Both complete raw clips are local:

- Kling: `assets/pilot-v3/kling-o3-pro-portrait-01.mp4`.
- Seedance 2.5: `assets/pilot-v3/seedance-2.5-portrait-01.mp4`.

Read [PILOT-REVIEW.md](PILOT-REVIEW.md) for sampled observations and [PILOT-TECHNICAL.json](PILOT-TECHNICAL.json) for measured output/hash/decode evidence. Both passed full decoding; no accepted model or new full MV exists. The new pilot outputs are 1080p as returned, separate from archived V2's 720p source footage. Recheck the local outputs from the repository root:

```powershell
.venv\Scripts\python.exe videos/dato-benz-brothers-united/inspect_pilot.py
```
