---
workflow: general-video
flow: automation
storyboard: no
message: "Revive turns recurring-payment failures into safe, explainable, duplicate-proof, and measurable recovery decisions"
destination: razorpay-buildathon-and-youtube
aspect: 1920x1080
language: en-IN
audience: "Razorpay judges, fintech product leaders, senior engineers, and recruiters"
length: 300s
angle: product-proof
narration: yes
---

## Intent

Create a technically credible five-minute product pitch for Revive — Autonomous Revenue Recovery.
The story must lead with customer and revenue value, then prove the claim through the live product,
hosted API evidence, guarded decision flows, causal measurement, and honest pilot boundaries. The
tone is confident Indian-English, commercially sharp, and precise without generic AI hype.

## Assets

- `assets/biznex/nexa-expressions/` — the reusable static Nexa presenter library; select expressions by scene intent and never animate her mouth.
- `captures/` — browser-only live product evidence captured at 1440x900 with browser chrome excluded.
- `https://revive-revenue.vercel.app` — primary live product source.
- `https://github.com/ReaperXD67/revive-ai` — engineering evidence and named fallback source.

## Customizations

- Use static Nexa expression changes as editorial punctuation: questioning, idea, warning, focused,
  analytical, reassuring, confident, and closing. Hold each expression long enough to read naturally.
- Drive browser capture from a reusable declarative recipe with safe-action allowlists, expected-text
  checks, one retry, fallback provenance, deterministic filenames, and an automatic capture manifest.
- Keep every dashboard portfolio metric labeled `Simulated portfolio`; label hosted API/storage proof
  as live evidence.

## Notes

- This video is about Revive, not Atomy. Do not show Atomy branding or make Atomy claims.
- The live simulation must never charge a customer or send a message.
- Do not expose secrets, environment variables, private records, PII, browser chrome, or personal tabs.
- Do not claim production merchant usage, real recovered revenue, real customers, official Razorpay
  endorsement, concurrency proof, or exactly-once execution.
- Delivery targets: H.264 MP4 at 1920x1080/30fps, exact sentence-case SRT, 1280x720 thumbnail,
  capture manifest, and public-upload checklist.
