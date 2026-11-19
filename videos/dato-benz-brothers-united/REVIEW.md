# Review result

**Technical and sampled visual checks passed. Recipient confirmed.** The user confirmed this tribute is for Hock Siew / 拿督斯里谢惠福 and identified him in the seaside photograph. A separate song for Benz will be supplied later; that second film has not been started.

## Encoded film

The full song is present: 196.760 seconds of original audio and 5,903 video frames at 30fps, giving 196.766667 seconds of picture. Both the 1080p master and 720p viewing copy decode completely. Stereo correlation with the original song at zero offset is 0.999608 / 0.999600; measured gain difference is approximately −0.033dB per channel. The viewing copy retains byte-identical AAC audio from the master.

All forty supplied sung lines equal the forty rendered ASS lyric events. Events are ordered, do not overlap and stay inside the song clock. Encoded name crops and additional opening/place-name/long-line frames were inspected: **Hock Siew**, **拿督斯里谢惠福**, **浅顶** and **有你，兄弟同心** are correct and readable. No stale Dato Benz, Bosston or Pragon text appears in the rendered typography.

Every one of the forty shot midpoint samples was viewed in the encoded contact sheets. Six name appearances and the full-resolution closing dedication were checked separately. Root, renderer and independent direction/subtitle reviewers found no blocking missing glyph, clipping, overlay collision, photo aspect-ratio error or obvious anatomy problem in these samples. Nine sampled picture-binding comparisons corroborate the EDL with RGB mean error at most 0.916/255 and luma SSIM at least 0.99973.

## Motion and edit

Twenty-one distinct native generated source clips passed complete stream decoding and chronological sampled review. Selected source intervals exclude the initial door-closing setup, weak late waterfront movement and weaker helping-hand tail. The edited body shows actual steps, weight transfers, hand contact, tea pouring, rain and moving water. Forty shots follow phrases and instrumental breaths; returning to a take consumes a later, disjoint source interval. Playback rates are 0.903–1.0. The song itself is not retimed.

The source-photo animation was compared with the original for the four supplied people, clothing and venue. The final twelve seconds preserve the complete original seaside image, with locally typeset Mandarin dedication. Source consistency was reviewed visually; Hock Siew's name comes from the user's confirmation.

## Evidence and limits

[DELIVERY.json](DELIVERY.json) records hashes, sizes, encoded-audio and full-decode results. [FINAL-REVIEW.json](FINAL-REVIEW.json) preserves the independent encoded visual and subtitle findings; [NATIVE-REVIEW.json](NATIVE-REVIEW.json) preserves source motion checks. Review images are local under `renders/review/`; private media and acoustic intermediates are ignored by Git.

Review was based on chronological source frames and encoded samples, not independent complete real-time playback or human listening. The model-derived timing uses phrase captions rather than claimed exact per-syllable karaoke. Native generation is 720p and the master is upscaled to 1080p. No audience reaction is guaranteed.
