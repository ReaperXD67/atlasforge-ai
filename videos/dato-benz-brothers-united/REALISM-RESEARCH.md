# Natural likeness: research decision

Research completed 19 November 2026. **No new footage was generated, no reference was uploaded to a generation provider, and no credits were spent during this research.** V2 passed technical delivery checks but the user reports that the boss rejected its face/body appearance as fake. It is not an accepted creative result.

## What needs to change

The previous pipeline used two limited real photographs, created a polished solo portrait, and then supplied that synthetic portrait as another reference for five more scenes. That can reinforce a consistent reinterpretation of a person. The starting images also invented body views, posture and walking behaviour that the supplied photographs did not establish. Sharper encoding and correct subtitles cannot resolve those problems. These are findings and failure hypotheses from the [local audit](research/realism/audit.md), not an experiment proving one model alone caused the failure.

The preferred natural-person route is **real Hock Siew footage, edited cinematically**, with AI used for restrained environments/details or individually accepted inserts. This recommendation follows from preserving his photographed face, proportions, expressions and gait. If only photographs are available, natural full-body motion remains a synthesis problem; more credits cannot guarantee the missing behaviour.

For generated inserts, keep an immutable **original-photo identity/body reference set**, separate from scene/style references. A generated composition may be tested, but does not become the ground truth for his appearance. Hold out a genuinely different real view for comparison. Runway itself explains that an unseen angle can produce character variations, and recommends neutral multi-angle reference material. [Long-film guidance](https://help.runwayml.com/hc/en-us/articles/26871350018835-How-to-create-longer-videos-and-films), [reference guidance](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References).

## Candidate comparison

These are candidates for an experiment, not a ranking of proven Hock Siew results. The connected account lists the first four models below; the current generation tool exposes their named routes. Web/API features and tool controls differ.

| Route | Useful control and limitation | Decision |
| --- | --- | --- |
| Kling O3 Pro | Multiple image references; official API permits up to seven I2V references including keyframes. V2V source at most ten seconds with up to four image references. Current tool narrows durations to 5/10/15s. | First pilot candidate for explicit identity/body references. Not interchangeable with Kling3Pro. |
| Seedance2 | Reference mode combines subject/body/scene evidence; web guide lists up to nine images. The current tool exposes image references and one reference video, not every multi-video/audio UI control. | Second pilot candidate using the same real references and action. |
| Gen4.5 | Original-photo start-frame conditioning; no multi-image identity-reference or V2V route in this tool. Official help and earlier local outputs are720p despite broader connector metadata. | Optional inexpensive first-frame control, not the main multi-view consistency experiment. Verify returned metadata. |
| Seedance2.5 | Broader current web/API inputs and edit/extend modes. Connector guidance caps output at1080p and does not expose all current50-reference/draft/4K controls. More expensive at1080p. | Conditional follow-up only if a specific pilot defect warrants it; newer is not evidence of superior likeness. |
| Kling Motion Control / Act-Two | Drive appearance from actual performance; require suitable continuous performance footage and matching body framing. Dedicated controls are not exposed by the current ordinary Kling3Pro route. | Research option if useful real motion exists and an authorized access path is established; direct editing of the real footage is the simpler baseline. |
| Aleph video editing | Targeted environment/cleanup alterations of real footage. A listed tool is not proof of workspace eligibility; current tool-model inventory for editing is empty. | Conditional minor cleanup, not a repair for an invented face/body. |

Controls are documented in [API inputs](https://docs.dev.runwayml.com/assets/inputs/), [Seedance2](https://help.runwayml.com/hc/en-us/articles/50488490233363-Creating-with-Seedance-2-0), [Seedance2.5](https://help.runwayml.com/hc/en-us/articles/53542207042323-Creating-with-Seedance-2-5), [Gen4.5](https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5) and [Motion Control](https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control). Detailed limits, source URLs and conflicts are retained in [the model comparison](research/realism/models.md).

Kling4 and dedicated Motion Control appear in account availability but are absent from this generation tool's model enum. Do not silently substitute another route or claim that web controls were used. No candidate has yet been tested on the new references.

## New reference assessment

The user supplied three960×1280 photos, `photo_2026-11-19_17-27-{24,29,32}.jpg`, and explicitly identified the **left-hand man** with a red outline in a separate screenshot. Only the unmarked originals are reference material. Their local hashes and roles are recorded in [reference-intake-v3.json](reference-intake-v3.json); private files remain ignored under `assets/references-v3/originals/`.

The new set adds standing body proportions, hands, footwear and a real white-shirt/cream-trouser outfit. All three are near-duplicates of one frontal two-person pose under the same indoor lighting. They do not supply three independent angles, natural gait or a clean side profile. One arm overlaps the companion. Use relevant real evidence and preserve those limitations instead of inventing the hidden side. A near-duplicate held-out photo is not an independent-view identity test.

## Pilot and spending decision

The [pilot protocol](REALISM-PILOT.md) starts with one matched5-second portrait per shortlisted model, then tests hands and a short full-body walk only if the face test passes. Judge the complete raw clips at normal speed, alongside the real references. A short client-approved pilot must precede another full-song batch. No model is declared a winner in this research.

Published Dev rates imply285credits for the first portrait pair and855for all six five-second tests at the stated settings. A future1,100-credit ceiling leaves a limited retry reserve. These figures are **planning baselines, not a connected-workspace quote or permission to spend**. Actual model, duration, resolution, reference-video charges and workspace pricing must be checked before a future submission. [Current Dev pricing](https://docs.dev.runwayml.com/guides/pricing/).

## Reuse and tooling

No skill pack, face-restoration model or new runtime was installed. Existing FFmpeg editing already handles real footage, soundtrack and captions. Adapt separate appearance/motion/body/continuity checks from evaluation research; do not reduce naturalness to one score. Public video preference benchmarks compare general tasks, not proof of this private individual's fidelity. [VBench](https://github.com/Vchitect/VBench), [benchmark methodology](https://artificialanalysis.ai/methodology/video).

| Upstream inspected | License / maintenance observed | Decision |
| --- | --- | --- |
| [Runway Python SDK](https://github.com/runwayml/sdk-python), head `628001561b0784c4c65360813d9bb08a2058b3d3`, 2026-11-16 | Apache2.0; current API schema source. | Inspect types if connector gaps become material; no API migration or separate account created. |
| [VBench](https://github.com/Vchitect/VBench), head `fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490`, 2026-08-21 | Apache2.0 code; model/data dependencies have separate terms. | Adapt dimension separation, defer heavy automated suite. Consistency can score a stable synthetic surrogate. |
| [PhotoMaker](https://github.com/TencentARC/PhotoMaker), head `060b4fcb10b76a4554edf565d6106b7e36c968f0`, 2024-10-31 | Apache2.0 except third-party components; V2 introduces InsightFace dependencies with separate model terms. | Defer; still-image personalization is not a demonstrated whole-body video solution here. |
| [InsightFace](https://github.com/deepinsight/insightface), head `c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52`, 2026-10-19 | MIT code; public pretrained models restricted to non-commercial research absent separate licensing. | No weights/downloads/recognition. A face similarity score would not establish natural gait or client acceptance. |

Canonical commit dates were read from repository APIs. Licenses were inspected from upstream sources; no upstream code or weights were copied. Additional capture and tooling notes are in [inputs-pilot.md](research/realism/inputs-pilot.md).

**Readiness:** research and the test protocol are complete. Production generation is held while the reference set is assessed and the user supplies credits/start instructions. No new full-length video is claimed.
