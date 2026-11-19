# Realism and identity model routes — research only

Observed 19 November 2026. No generation, upload, credit spend, installation or account change was performed for this research. The parent confirmed account availability with read-only `whoami`. This memo distinguishes hosted capability, connector controls and untested quality claims.

## Recommendation

Use **real Hock Siew footage as the identity/motion baseline and preferred main footage** when the goal is a natural personal tribute. This is an editorial inference: original footage contains his actual face, proportions, gait and expressions, while a generative model must synthesize some of them. More expensive generation cannot establish authenticity by itself.

For AI-only inserts, the first comparison should be **Kling O3 Pro versus Seedance 2.0 in reference mode**, using the same new original photographs and simple actions. Gen-4.5 from an original photo is a useful optional first-frame-only control. Seedance 2.5 is a conditional extra arm if the reference or motion problem remains unresolved; its newer release and larger input capacity do not demonstrate superior Hock Siew likeness. No current candidate has been tested against his new photographs.

Do not repeat the V2 chain of generating an idealized solo portrait and treating that synthetic portrait as the identity truth for the remaining film. Each test should return to a frozen set of real photographs, with face and full-body references assigned explicit roles. A generated still can be a composition candidate, but must pass a real-photo comparison first and remain subordinate to original identity references.

## Controls actually available

| Route | Documented useful controls | Connected-tool consequence |
| --- | --- | --- |
| Kling O3 Pro | Runway API supports first/last-frame conditioning, up to seven I2V reference images including keyframes, and V2V with up to four reference images and a source at most ten seconds. | `generate_video` exposes `kling-o3-pro`, start/end frames, `referenceImages` and one `referenceVideo`. The connector narrows durations to 5/10/15s although API docs allow 3–15s. Promising **test candidate**, not a proven winner. |
| Kling 3.0 Pro | First/last keyframes; API supports shot segments and native sound. | `kling-3-pro` has no reference-image or V2V route in the current tool. It is therefore a weaker fit for this specific multi-angle identity comparison than O3. Do not confuse it with Kling Motion Control or newer Kling4. |
| Seedance 2.0 | Runway help lists reference mode with up to nine images, three video references (combined under15s) and three audio references. Subject, environment and motion roles can be specified. | Current tool exposes `seedance-2`, image refs, first/end frames, one reference video, optional native audio and resolution. It does **not** expose all multi-video/audio-reference UI controls. Use a small original-photo subset and verify actual accepted payload/output metadata. |
| Seedance 2.5 | Current help lists 4–30s, up to thirty image/ten video/ten audio references, plus reference/keyframe/edit/extend modes. | Tool enum includes `seedance-2.5` but its description caps output at1080p and has no draft/enhance control or multiple video/audio-reference fields. UI maximums are not a promise of MCP functionality. Account/task eligibility must be checked; no silent fallback during the comparison. |
| Gen-4.5 | Native image-to-video starts from one supplied image; 2–10s, 24/25fps. | Tool offers `gen-4.5`, start image and prompt, but no multiple image-reference or V2V route. A better first-frame-only control than assuming cheap Turbo is enough. It cannot use the new multi-view reference pack in the same way as O3/Seedance. |
| Aleph2 / Edit Studio | Edited-keyframe-driven alteration of real or generated footage; targeted changes preserve surrounding content according to vendor design. UI allows a reference image during keyframe preparation. | `edit_video` is a separate tool, with candidate-frame → edited-keyframe → submit workflow. Tool presence does not establish current account eligibility; parent reports `availableVideoToolModels.edit_video=[]`. Reserve for small environment/cleanup changes to real footage after eligibility is resolved, not as a magic repair of V2's synthetic face/body. |

The O3/3 controls above come from [Runway API input documentation](https://docs.dev.runwayml.com/assets/inputs/). Seedance2 controls come from its [Runway creation guide](https://help.runwayml.com/hc/en-us/articles/50488490233363-Creating-with-Seedance-2-0). Seedance2.5 UI controls come from its [current guide](https://help.runwayml.com/hc/en-us/articles/53542207042323-Creating-with-Seedance-2-5). Gen4.5 details come from its [creation specification](https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5). Aleph is described in [Edit Studio](https://help.runwayml.com/hc/en-us/articles/51683104370451-Creating-with-Edit-Studio) and its [prompting guide](https://help.runwayml.com/hc/en-us/articles/52150503729171-Aleph-2-0-Prompting-Guide).

### Documentation conflicts to retain

Gen4.5 help currently states720p while connector metadata advertises up to1080p; the earlier local generations actually returned1280×720. Seedance2.5's current help/API show4K, but connector guidance explicitly caps that route at1080p. Seedance2 UI help lists5–15s while the current tool accepts4–15s. These discrepancies should be resolved by an explicitly configured, authorized small pilot and returned metadata, not by claiming unsupported settings or spending on an unannounced fallback. A standard five-second1080p request avoids the Seedance duration discrepancy, but resolution must still be verified.

Kling4 and Kling3 Motion Control appeared in the parent's account inventory but are absent from the `generate_video` enum. Motion Control is a **different** route: its [official guide](https://help.runwayml.com/hc/en-us/articles/50280558448147-Creating-with-Kling-3-0-Motion-Control) requires a character image plus continuous single-person performance video, with full body/limbs visible and stable, moderate action. Do not imply the current plain Kling3Pro endpoint exposes those controls. These routes may be explored in the web UI or another documented connector only after the access path is established.

## Cost framework, not a workspace quote

Runway's [current Dev price table](https://docs.dev.runwayml.com/guides/pricing/) publishes the following baselines. Developer credits and the connected web/MCP workspace must not be assumed interchangeable. Confirm the applicable workspace quote before any future test.

| Route | Published Dev formula | Five-second output example |
| --- | --- | ---: |
| Gen4.5 | 12 credits/output second | 60 |
| Kling O3 Pro | 17 credits/output second | 85 |
| Seedance2,1080p | 40 credits/output second; minimum56 | 200 |
| Seedance2.5,720p | 30/output second +15/input-reference-video second; minimum80 | 150 without video |
| Seedance2.5,1080p | 68/output second +34/input-reference-video second; minimum80 | 340 without video |
| Aleph2 | 28 credits/source second; minimum56 | 140 |

A two-model O3/Seedance2 pilot with three five-second scenes each would be **855 Dev credits** by those formulas, before retries or differing workspace charges. An optional one-shot Gen4.5 control adds60. This is a planning comparison, not permission to spend or a full-film estimate. Do not buy enough credits for the whole MV before the chosen approach passes the short test.

## Pilot that can change the decision

1. Freeze original face/body references from the same approximate age and appearance. Include an unretouched front/three-quarter face and a full-body image; retain several photos as held-out comparison material.
2. Test the same three simple five-second shots in each candidate: neutral close-up with one blink/head turn; waist-up cup lift; full-body two-step walk with hands visible. One continuous shot, ordinary daylight and clothes, moderate camera motion. Disable model audio where supported; the music stays separate.
3. Compare with real footage and held-out photographs at100% size and normal playback. Inspect cheeks/eye spacing/jaw/ears/hairline, torso-to-head proportions, shoulder width, belly and posture, hand contact, gait/foot sliding, eye and mouth motion, skin texture and temporal drift. A still contact sheet is insufficient.
4. The user/boss must recognise the real person and accept naturalness on a small preview before bulk generation. No average score may conceal a wrong face or wrong body. If both models fail, prefer real-footage editing and smaller AI environmental inserts rather than scaling the failed recipe.

No vendor guide inspected supplies a guarantee of exact private-person identity or body consistency. Terms such as improved realism or preserved identity describe model intent and examples, not measured results on Hock Siew. These are proprietary hosted services; no model code/weights were downloaded or copied and no open-source licence is implied.
