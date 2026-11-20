# Benz image-film research

Observed 20 November 2026. This is a focused study for an image-based music film, not a claim to have searched every source or watched complete films. Public creator descriptions and original upload metadata were inspected. No creator footage, music, image or code asset was downloaded into the film.

## Creative precedents

### A person and their world become one composition

[Patrick Clair’s first-person True Detective interview](https://www.artofthetitle.com/title/true-detective/) explains how location expressed character, with landscape photos projected over simple geometry, then combined with portraits, spatial motion and focus. [Antibody’s own Season 3 page](https://antibody.tv/works/true-detective-3/) supplies original studio images and film credits. The useful principle is that the portrait belongs to the space and story; it is not a bordered photograph placed over a background.

**Adaptation for Benz:** one clear face inside an inhabited warm/cool environment; restrained near/far camera separation; glass, doorway or rain as motivated foreground. Keep the eyes and glasses readable. Do not import the crime, fragmentation, death or fire imagery, or make a memorial portrait.

### Material changes can carry the song

[The Peach Kings’ own Be Around production post](https://www.thepeachkings.com/blog/bearound) credits Paul Trillo and describes a still-photography double-exposure idea developed with landscapes, fabrics and filmed textures. The [band’s music page](https://www.thepeachkings.com/music) identifies the work as an official video. This is mixed footage/compositing, not evidence that the original was made from stills alone.

**Adaptation for Benz:** repeat one light-bearing material across rain glass, a sheltered doorway, a wet canal and a bright gathering space. Cut between the environment and the person on lyrical meaning. Avoid multiple copies of Benz or a constant generic crossfade.

### Portrait restraint, with one lesson deliberately rejected

[Adele’s own clips page](https://www.adele.com/clips/) links the [original Send My Love video](https://www.youtube.com/watch?v=fk4BbF7B29w). [Director Patrick Daughters’ interview](https://shots.net/news/view/90370-adele-s-new-music-video-is-just-gorgeous) describes layered performance takes; the interview’s search text was available, but direct fetching timed out. Its production claim is therefore recorded as a director interview, not as a completed frame-by-frame review.

**Adaptation for Benz:** keep a strong, legible central identity and allow the surrounding image to carry variation. **Do not copy the multiple-exposure bodies:** the user previously objected to seeing several apparent honorees, and the new source does not provide multiple natural poses.

The user’s supplied golden-light reference is a mood/composition reference only. Its full-body anatomy, face, pose, bubbles and black void are not instructions to reproduce another person or build an entire film out of one pose.

## Three concrete methods

1. **Full-bleed environmental integration.** Generate a coherent room, street or waterside image around the known Benz pose, or composite an identity-preserving subject matte into that environment. Match light direction, contact and scale. Do not draw a print frame, border, photo mount or card. If an uncertain shoulder edge needs concealment, use an actual architectural foreground edge rather than rebuilding an arm.
2. **Subject keepout masks.** An image/alpha mask reserves the person from relative-depth displacement and atmospheric UV motion. Environment, reflection and fog can change around a rigid identity region. This is the proposed pipeline improvement; correctness must be demonstrated with source/render tests, not inferred from the presence of a mask.
3. **Meaningful composition changes.** Alternate a person-bearing view with an environmental detail and a wider consequence: warm window → sheltered doorway → many warm homes. Use a new final-chorus image and clear close/wide regions. No every-line title card, uniform zoom or blank portrait placeholder.

## Upstream comparison

These repositories were checked through canonical GitHub repository/commit metadata and raw pinned source/license files. A current head is maintenance evidence, not a reason to replace a tested local pin.

| Candidate | Inspected evidence | Decision |
| --- | --- | --- |
| [Three.js](https://github.com/mrdoob/three.js) | Current head `c67bf518965dc4262116f1492e91f3f382278138`, 20 November 2026; repository active, MIT. Existing tested local r187 commit `7e89746a687bb88271253698fa108b1dd59825d0`. The pinned `examples/jsm/objects/Reflector.js` is about11KB and `Water.js` about13KB, both using Three imports rather than a separate framework. [Official material documentation](https://archive.threejs.org/docs/api/en/materials/MeshStandardMaterial.html) documents grayscale alpha masks; RGB alpha maps sample the green channel. | **Adapt within the existing renderer.** Use local masks and explicit time-driven shader uniforms. Preserve the MIT notice if copying example code. Do not add a full reflection/water implementation unless the film needs it and the render benchmark passes. A small original mask shader may be the better fit. |
| [pmndrs/postprocessing](https://github.com/pmndrs/postprocessing/tree/a1f103559d15cf56cbcbb15d4373711b09418f3f) | Active head `a1f103559d15cf56cbcbb15d4373711b09418f3f`, 1 November2026; package6.39.6. **Zlib license**, not MIT. No direct dependencies in the inspected package manifest; peer Three is `>=0.168.0 <0.188.0`, compatible with r187. Adds a separate effect/composer abstraction and render-target passes. | **Defer.** Bloom or synthetic depth-of-field does not repair likeness, contact or story composition. Existing Three is sufficient for the narrow keepout/atmosphere upgrade. |
| [rembg](https://github.com/danielgatis/rembg/tree/991927b77667946dab59c50df31f7d4640e80457) | Active head `991927b77667946dab59c50df31f7d4640e80457`, 6 November2026. Code MIT; model weights have their own provenance/licensing considerations. Would add segmentation/ONNX packages and model data. | **Defer installation.** Built-in image editing can produce the required raster cutout/mask. Do not silently install a second ML stack or treat the code license as blanket weight permission. |

No additional framework, model download, provider upload or financial/account action was performed by this research. Earlier Hock runtime/provenance is a reusable implementation baseline, not a source of Benz artwork or identity.

## Evidence needed before delivery

Check the actual trimmed audio before text placement. Test a short integrated portrait scene at1080p: no rectangular card edge, accurate glasses/head/build, natural contact and unobstructed eyes. Test a nonhuman environment with atmosphere, and verify the keepout region remains rigid. Seek out of order and compare repeated frames. Review all real encoded shot samples and named-cue appearances. Full decoding, audio correspondence and exact render-to-encode bindings remain separate from creative approval.
