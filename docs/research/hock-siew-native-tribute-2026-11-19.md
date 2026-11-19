# Native motion for a personal full-song tribute

Observed 19 November 2026. The user requested actual moving AI scenes, precise supplied lyrics, a personal photo ending, and an editable GitHub delivery. Existing Runway credits were explicitly authorised up to 2,250 for this film. The implementation decision was how to turn short native takes into a complete 196.760-second music film without replacing subject motion with still-image camera effects.

## Focused comparison

| Primary upstream inspected | License / maintenance evidence | Decision and practical cost |
| --- | --- | --- |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper), inspected head `6cb639e70786aea42b9233006ae60eaf07190bdb` | MIT; head dated 2026-11-12. Production uses already installed 1.2.1 with CTranslate2 4.8.1. | **Adapt** existing recognition and native cross-attention alignment APIs. Independent cropped recognition corrected a false opening timestamp; final forty-line phrase decisions remain frozen. Medium-model CPU/int8 avoids new GPU inference dependencies. No upstream code was vendored. |
| [imageio/imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg), head `26277bb102b64c42d939c3a550301edbe2c81921` | BSD-2-Clause wrapper; head dated 2026-11-03. Bundled binary has its own FFmpeg licenses. | **Adopt existing 0.6.0 binary locator**, which selects FFmpeg 7.1 on this machine. Actual NVENC 1080p smoke render passed; system 9.0 failed driver compatibility. The selected static binary enables GPL/version3; no binary is redistributed in this project. |
| [kkroening/ffmpeg-python](https://github.com/kkroening/ffmpeg-python), head `df129c7ba30aaa9ffffb81a48f53aa7253b0b4e6` | Apache-2.0; inspected head dated 2022-07-11. | **Defer** another wrapper. The existing subprocess path expresses the required trim/filter/concat operations, keeps exact command arguments reviewable and adds no dependency. |
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion), head `3fcd5ae3eb8b30f40037983410217183ce3ddb81` | Custom Remotion License; head dated 2026-11-18. Free-use eligibility and company licensing depend on the entity, per [license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md). | **Defer** a browser/React render layer for this footage-led film. It would add another media clock and require evaluating licence applicability without improving native subject motion. Existing HTML motion skills remain available for other project types. |

Commit dates were read from canonical GitHub repository APIs, not inferred from popularity. These observations describe the inspection date; reproducible local versions are recorded separately from upstream head commits.

## Motion prompting and edit adaptation

Runway's primary [Gen-4 guide](https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide) recommends a clear physical action, simple prompts and motion-focused image-to-video direction. Its [image-to-video guide](https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide) assigns composition and lighting to the first frame. We applied one principal action per take: carry a shared weight, offer a grip, pour tea or continue a journey. This is a prompting principle, not copied code or a new skill pack.

Twelve action-led hero takes and eight plate-led motion takes provide independent people, hands, cloth, rain and water movement. One supplied-photo animation provides a personal bridge. Original edit code admits only hashed local clips with provenance and reviewed ranges. Forty frame-based shots follow phrase entrances, including tea at the lyric about the cup, rain at 风雨同路 and the waterfront at the final blessing. Return shots use disjoint source intervals. Song speed and gain remain unchanged.

Existing FFmpeg/native-footage patterns in this repository were sufficient. No additional editor, framework or unreviewed skill collection was installed. The meaningful upgrade is an end-to-end native-video path with source admission, exact timing, transactional render replacements and encoded-audio verification.

## Verification boundary

Each complete native stream was decoded and eight chronological frames reviewed; selected contact points and the waterfront tail received denser inspection. The final source intervals exclude the weaker waterfront tail and opening door-closing setup. The photo animation was compared against the original for the four supplied people. It remains an AI interpretation of movement; the final seaside photograph is original and unretouched.

Final checks compare all forty lyric lines, exact 5,903-frame coverage, source bindings, full export decoding, zero-offset stereo audio correlation and gain, and actual encoded title/name/dedication crops. See the project's DELIVERY.json and REVIEW.md for the measured delivery, rather than treating the planned checks as passed.
