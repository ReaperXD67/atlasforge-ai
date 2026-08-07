# AtlasForge AI publishing and claims policy

This is an engineering guardrail, not legal advice.

## Non-negotiable content rules

- No earnings guarantees, income promises, fabricated screenshots, or typical-results implications.
- No claim that passive income, financial freedom, a side hustle, or an Atomy opportunity is easy, automatic, or risk-free.
- No cure, treatment, prevention, diagnosis, or guaranteed skincare/supplement result.
- No invented ingredient, certification, compensation-plan, price, or clinical-study detail.
- No simulated testimonial presented as real.
- Atomy appears only after meaningful independent education and is compared with alternatives.
- The CTA asks for engagement or further learning, not pressure to buy or join.
- Disclose AI-generated narration and meaningfully realistic synthetic footage.
- Mark paid promotion when an applicable relationship or benefit exists.

## YouTube-specific considerations

YouTube requires disclosure when realistic altered or synthetic content could be mistaken for real. It also states that disclosure itself does not remove monetization eligibility: [altered/synthetic content help](https://support.google.com/youtube/answer/14328491). This repository sets `status.containsSyntheticMedia` when uploading and includes a plain-language description disclosure.

Monetization requires original, authentic value. YouTube specifically scrutinizes repetitive, mass-produced, template-like material and low-value slideshows: [channel monetization policies](https://support.google.com/youtube/answer/1311392?hl=en-GB). A technically unique render is not necessarily editorially original.

For each video, the pipeline therefore varies the topic, script, scene plan, queries, visual palette, music progression, and thumbnail copy. The durable educational framework can remain consistent, but most of each episode must add distinct analysis.

## Operational review cadence

Automation can run unattended after setup. Still schedule a non-editing governance review:

- weekly: inspect policy/quality reports and viewer feedback;
- monthly: audit a sample of product/financial claims and source licenses;
- after provider/model changes: run a private test video before unattended publishing;
- after YouTube policy changes: update prompts, gates, disclosures, and documentation.

If a quality gate blocks a video, resolve the underlying content or configuration issue. Do not disable `fail_on_quality_gate` merely to maintain the one-video-per-day cadence.
