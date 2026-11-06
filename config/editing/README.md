# Cinematic edit contracts

`edit-plan.schema.json` is generated from `daily_video_factory.edit_plan.EditPlan`.
`second-question.example.json` demonstrates the current authored character-story
structure with 18 shots and literal speech anchors. It is an authoring example,
not a self-contained render project: media and measured timing live in the film's
own directory. Copy a plan into that directory and confirm every phrase/asset.

Non-voice audio cues support optional speech-anchored `gain_keyframes`. Their
`offset_db` values add to the base gain, fades and ducking; narration gain rides
are rejected. See the guide's copyable example before authoring a quiet-line mix.

```powershell
.venv/Scripts/python.exe scripts/compile_edit_plan.py videos/<project>/EDIT_PLAN.json
.venv/Scripts/python.exe scripts/compile_edit_plan.py videos/<project>/EDIT_PLAN.json --check
```

See [the edit-plan guide](../../docs/CINEMATIC_EDIT_PLANS.md) for timing semantics,
audio envelopes, failure behavior, the renderer primitives, tests and upstream
license decisions. A passing authored audit does not approve the rendered film
or predict audience reach.
