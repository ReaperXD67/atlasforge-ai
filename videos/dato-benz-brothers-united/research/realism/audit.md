# Hock Siew V2 realism audit

Observed 19 November 2026. Research only: no new generations, paid calls, model installations, private-media uploads or production-file changes.

The client's rejection is the controlling result: V2 passed encoding, timing and sampled defect checks, but failed the intended natural-person appearance. Those are different acceptance questions. The earlier "recognizable" metadata records an internal sampled judgement, not confirmation that the boss accepted the likeness.

## Evidence inspected

- Original user-confirmed `assets/photos/seaside.jpg` (960×1280) and `brothers.jpg` (1280×853).
- New `hock-seaside.png` and `hock-walk.png` plates at full image size, and the six plate/motion prompts in `generation-jobs-v2.json`.
- Chronological `hock-tea-contact.jpg`, `hock-doorway-contact.jpg`, and the encoded walking first/middle/last proof sheet.
- `edit-plan-v2.json`, `REVIEW-V2.md`, and the recorded source/caption verification approach.

This audit inspects supplied images, source metadata and chronological frames. It does not pretend to be a complete real-time playback, human audio audition or a quantitative identity test. New clips should not be admitted on this limited review alone.

## What is observed, and what is inferred

| Evidence | Observation | Likely consequence / inference |
| --- | --- | --- |
| Real references | The seaside photo gives an oblique seated view with a non-neutral expression, strong sunset lighting and another person partly occluding the pose. The group image has a much smaller face, approximately120×140 source pixels by visual estimate; it is not an isolated studio portrait. Neither provides a clean full-height view of his legs and shoes, nor motion. | The model must invent missing geometry, texture and gait. More image pixels in a generated portrait do not establish that the extra detail belongs to the real man. |
| First generated seaside plate | It changes a candid interaction into a solitary posed hero portrait, reconstructing the unseen arm/seat relationship and adding a clearer sun/reflection composition. Facial skin/stubble and garment texture are more pronounced than the real source can substantiate. | A plausible polished likeness can still feel like a digital surrogate to somebody who knows him. The issue can exist in the starting still before video generation. |
| Identity reference chain | All five subsequent plate prompts explicitly use the accepted AI seaside portrait as reference3 and ask to match it exactly. | The pipeline can consistently reproduce the first model's reinterpretation rather than the real person. Temporal consistency with that image is not sufficient evidence of real-person fidelity. This is an inference from the documented inputs, not a claim that generated references are always unsuitable. |
| Full-body walking plate | A new full-body pose, dark trousers, shoes and stride are created from references that do not show a clear matching whole-body pose or his walking manner. | "Stocky build" is a broad description, not a reconstruction of his actual stature, shoulder/waist distribution or gait. A different model still needs the missing evidence. |
| Six creative briefs | Most takes repeat the same three-quarter gaze, burgundy top, warm light, shallow focus and small smile. Scenes are deliberately photogenic and very clean. | The unified look risks reading as advertising imagery or an idealized portrait set, rather than candid life. Naturalness needs less stylization and more observed behaviour, not additional glamour keywords. |
| Tea and doorway chronological frames | Movement exists, but much of it is small head/gaze/smile change while hands or the cup remain in similar positions. The tea take does not complete its prompted cup set-down. | Coherence and absence of a gross morph do not prove an action feels spontaneous or physically convincing. Repeated restrained expressions can feel animated even when eight still samples look clean. |
| Final source edit |179.125 seconds of native motion includes126.658 seconds of distinct source time and52.467 seconds of revisited motion. Twelve reprise shots are explicitly listed, with several returns to the same walk, window, tea and seaside actions. | Repeating the same smile/gaze/stride can make limited motion more noticeable. This is a perceived editorial risk, not proof that all portrait reprises are bad. |
| Technical verification | Decode, frame count, audio correlation, lyric completeness and EDL/encoded-frame comparison passed. Native24 removed avoidable24→30 cadence repeats in a short sample. | These prove the edit was rendered as specified. They do not establish faithful face/body reconstruction, natural acting or the client's aesthetic acceptance. |

The dominant failure hypothesis is **an inadequately verified synthetic person already present in the still plates, then animated and repeated**, rather than a failure that sharpening, bitrate or more transitions can solve. It remains a hypothesis until the user/boss identifies the most objectionable face/body examples and the new reference set is examined.

## Change the production hierarchy

1. **Prioritize real footage of Hock Siew.** If any phone clips, event video or candid footage exist, use his actual face, body and mannerisms as the visual backbone. Cinematic editing, sound-led pacing and respectful colour work can come from real material. AI can supply environments or non-personal detail where necessary.
2. **Use original photos as identity evidence, not the accepted AI image.** Keep an original-only reference bundle and a separate scene/style bundle. A generated frame can be an explicitly tested compositional aid, but must not silently become the authority for his face/body. Every proposed hero still must be judged against real references before paying to animate it.
3. **Hold out references.** Reserve at least one clear real facial angle and one body view from generation inputs. Inspect output against those separately. If there is no convincing match from another real view, reject or reduce the shot rather than declare that a prompt's "identity lock" worked.
4. **Test appearance and motion separately.** First admit a neutral, minimally altered still; then a short motion test. Start with ordinary diffuse daylight and one natural gesture. Change one factor at a time. Do not mix a new model, altered outfit, new body pose, dramatic relighting and new location in the first test.
5. **Select the model from this person's pilot, not a generic leaderboard.** Use the same reference bundle and comparable scene/action with the shortlisted models. Keep failures and retry counts. A model that creates a pretty face but changes his body fails this task.
6. **Approve a short ungraded pilot before bulk generation.** A small comparison containing a neutral head turn, a medium walking shot and one hand/object contact is more diagnostic than another full song. Ask the user/boss to judge actual normal-speed clips with no title masking the face. Their familiarity is essential; an agent's broad resemblance judgement must not substitute for it.

The current request authorizes research first. The above is a future test protocol, not authority to spend new credits now.

## Reference evidence that would reduce guessing

Prefer original camera files over forwarded screenshots or beauty-filtered edits. Useful views are neutral front, left/right three-quarter and profile, in even light, plus a relaxed whole-body standing view in clothing he actually wears. Include hands and ordinary shoes where those will appear on screen. A small set of distinct, clear views is preferable to many near-duplicates.

A brief natural phone video is especially useful: a normal head turn/smile and several ordinary steps show behaviour that static photos cannot supply. Do not demand a performance, a forced grin or unusual action. Exact requirements should follow the selected model's official input controls. If new references conflict in age, hairstyle or body appearance, agree a period/look rather than blend them indiscriminately.

## Replacement acceptance gates

Treat these as separate pass/fail questions. Do not average a failed likeness into a high overall "cinematic" score.

- **Appearance before motion:** the user recognizes the person without the name label; face shape, hairline, age presentation, neck, shoulder/torso proportions and familiar clothing look right. The generated surface detail must not become a substitute for missing real information.
- **Full-speed temporal review:** watch each entire source clip repeatedly at normal speed. Check changing expressions, gaze and blinks, teeth/jaw/ear boundaries, skin texture crawl, and changes through the turn. Inspect problem moments frame by frame after normal-speed review, rather than selecting only pleasant stills.
- **Whole-body plausibility:** check posture, arm swing, step timing, heel/toe contact, sliding feet, weight transfer, clothing tension and shadows. Compare actual body references with similar camera perspective; there is no universal head-to-body ratio threshold that proves the individual is correct.
- **Contact and physical action:** cups, hands, rails and chairs retain contact and believable weight; fingers release and grasp coherently. A requested action that never completes should not be called a successful performance.
- **Cross-shot continuity:** evaluate several accepted shots side by side, including different real view angles. Keep face/body/wardrobe and period consistent without forcing identical expressions or poses everywhere.
- **Client realism checkpoint:** no long edit or large generation batch until the user/boss accepts the short motion pilot as natural. If no candidate clears the gate, use real footage/photos and AI-free human shots; do not conceal the failure under fast cuts, heavy grading or face restoration.

No automatic face score should be presented as "95% Hock Siew" or proof that a viewer will believe the video. This audit did not compute or propose deploying biometric recognition.

## Primary research and tooling decisions

- Runway recommends clear subject images with even light and neutral expression, and notes that more changed variables can introduce variation. That supports improving input evidence and simplifying the first experiment; it is not a guarantee of exact fidelity. [Official Gen-4 References guide](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References).
- VBench separates consistency, motion, image quality and other dimensions. Its subject-consistency implementation compares visual features across frames; a stable synthetic surrogate can therefore be internally consistent. VBench-2.0 explicitly distinguishes convincing appearance from physical/anatomical faithfulness. **Adapt its separate-dimension evaluation principle**, not a single leaderboard score or an untested automated gate. No package was installed or code copied. [VBench repository](https://github.com/Vchitect/VBench), [subject-consistency source](https://github.com/Vchitect/VBench/blob/master/vbench/subject_consistency.py), [VBench-2.0 paper](https://arxiv.org/abs/2503.21755).
- The inspected VBench head was `fd18b3d055cb0fc6f066ca90fe2c3c8cbb698490`, dated2026-08-21; repository licence Apache2.0. Model/data dependencies would still need separate review before installation. [Licence](https://github.com/Vchitect/VBench/blob/master/LICENSE).
- **Defer default InsightFace/ArcFace-based automation.** Besides not measuring natural body motion or acting, InsightFace's code licence and supplied model terms differ: MIT code does not grant unrestricted commercial rights to its default pretrained models. The inspected head was `c6c3af7bd2d0a0bf4b78c78437357f3521aa5d52`, dated2026-10-19. No weights were downloaded and no recognition was run. [Official licence statement](https://github.com/deepinsight/insightface/blob/master/README.md#license).

There is no measured new-model win yet. The research is sufficient to redesign a controlled pilot; it is not evidence that buying more credits or switching a model name alone will make the full video natural.
