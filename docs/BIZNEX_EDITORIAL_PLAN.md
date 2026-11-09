# BizNex daily editorial plan

**Recurring production paused by the owner on 9 November 2026.** These dates are
archived planning slots, not an active schedule. Work only when explicitly requested.
The 8 November slot was missed; no catch-up was posted. The Borrowed Countdown was
prepared for the explicitly requested 9 November release.

Originally prepared **7 November 2026** for the daily operator. Target: **one new
original episode per Asia/Kolkata calendar day**, distributed once to YouTube
Shorts, Instagram Reels and the Facebook Page. Three destinations are one
episode, not three separate daily productions. Target release window is **09:00
IST (03:30 UTC)**; this is an operating choice, not a proven best posting time.

The dates below are **planned production slots**. No future script, render,
publication or activated schedule is established by this document. Preserve
*The Second Question*, *The Yes Machine*, and existing publication receipts.
Keep the five rejected pilot follow-ups held; never use them to fill a missed day.

## Next seven original episodes

All are clearly labeled fictional illustrations, not customer experiences or
Atomy testimonials. Aim for 50–75 spoken words, 25–40 measured seconds, one
conflict, a visible consequence, and a useful ending. The script may change before
production; the concept and visual cause must remain distinct from earlier films.

| IST date / new project ID | Hook and story | Code-authored scene direction | Voice performance and ending |
| --- | --- | --- | --- |
| **Nov 8** · `biznex-the-empty-chair` | **“Everyone had an answer. Nobody had asked me.”** An imaginary roundtable crowds one decision; the quiet narrator finally makes room for her own question. | New miniature room: chairs slide toward a central object as abstract speech shapes crowd it. Camera drops to one empty chair. Moving that chair back opens a clear view of the object; end in a balanced wide shot. No stock people, quoted endorsements or copied interface. | Wry observation → overwhelmed, slightly quicker thought → quiet self-question → warm agency. End: “What do *I* need to understand?” |
| **Nov 9** · `biznex-the-borrowed-countdown` | **“The timer was loud. My reason was missing.”** A fictional countdown becomes the reason to act, until the character separates someone else's deadline from her own decision. | New kinetic desk: mechanical digits occupy almost the whole frame, casting moving shadows over a tiny undecided token. Camera slips behind the digits to reveal their shallow construction. Token takes an unhurried side path while the timer continues. Do not depict an actual Atomy offer or deadline. | Urgent opening → embarrassed recognition → deliberate quiet → composed resolve. End: “A countdown isn't my reason.” No implication that real deadlines can always be ignored. |
| **Nov 10** · `biznex-the-perfect-frame` | **“I was buying for someone who didn't exist yet.”** A character imagines an impossibly perfect future routine, then chooses around the day she actually has. | A polished empty picture frame expands into an elaborate miniature ideal day. Reverse camera reveals a much smaller real desk and a single useful object. Frame folds into a modest stand that fits the desk. Transform geometry directly; no generated images or before/after health imagery. | Hopeful, lightly amused fantasy → vulnerable admission → curious practicality → relieved smile. End: “Start with the life you actually have.” |
| **Nov 11** · `biznex-the-question-that-stayed` | **“I kept making my question sound nicer.”** Three decorative versions of a question conceal its meaning; the simplest version finally lets a conversation move forward. | Original messenger-like set, without platform logos: word ribbons coil around an unreadable center. Each rewrite adds a loop. A straight ribbon gently unfolds them and creates a clear bridge between two abstract figures. Camera crosses the bridge for the payoff. | Self-conscious hesitation → affectionate self-awareness → clear, unforced question → relief. End with the plain question: “What am I agreeing to?” |
| **Nov 12** · `biznex-two-different-mornings` | **“It fit her morning. It didn't fit mine.”** Two fictional friends discover that sharing a preference does not require identical routines. | Split miniature rooms with different clocks, shelf spacing and daily paths. One neutral object traverses each room; it fits one layout and obstructs the other. The second room rearranges around a different choice. Final camera joins both rooms without declaring a winner. No identifiable product, efficacy comparison or price. | Friendly certainty → puzzled mismatch → curious understanding → generous acceptance. End: “Different lives can make different choices.” |
| **Nov 13** · `biznex-the-rehearsal` | **“I wanted confidence before I started.”** A character rehearses one small question, stumbles, tries again, and learns that preparation can be modest. | New tabletop stage: spotlight initially dwarfs a tiny paper-like figure. A rehearsal route redraws after each stumble; the light narrows to one reachable step. Final reveal shows a practice room, not a cheering audience or success podium. Procedural line paths and simple articulated shapes only. | Candid anxiety → a restrained awkward pause → gentle determination → grounded satisfaction. End: “Today, I can practise one question.” No earnings, recruitment or outcome promise. |
| **Nov 14** · `biznex-the-message-i-rewrote` | **“My invitation sounded like a deadline.”** The narrator replaces a pushy fictional message with a clear invitation that leaves the other person room to choose. | A compressed message ribbon squeezes through a narrow funnel. Backspace physically releases its tension; the ribbon opens into two equal, unobstructed routes labeled “ASK” and “NOT NOW.” End on generous negative space, not a closing sales button. This is a new invitation set, not a reuse of the Yes Machine's gate sequence. | Sheepish confession → thoughtful rewrite → warm, conversational invitation → relaxed acceptance. End: “You're welcome to ask. You're free to wait.” Caption can invite questions about researching Atomy without requesting a purchase or signup. |

Use **BizNex Stories** and a short end-context line, “Atomy · independent
educational community.” Each caption states “Fictional illustrative story;
synthetic narration. Independent education, not an official Atomy account.”
State any actual commercial relationship accurately. Do not invent one. Keep
hashtags compact and unique; use a distinct question in the caption rather than
repeating the narration opener and upload description.

## Keep the liked narrator; direct complete thoughts

Reuse the installed, pinned CosyVoice3 runtime and the original authorized
Kokoro `af_heart` reference. Its SHA-256 is
`45b687b4567ca160de01382212e4bd0860c75b163175650b1ee5b65add438da6`.
Copy that reference and its provenance into each **new** project's portable
assets; never regenerate it silently or modify the completed films.

Use three to five complete thought groups at speed 1.0, with an intentional
performance arc from the table and sparing authored silence at the turn. Keep
the clean transcript separate from synthesis controls. Preserve seed,
instructions, selected/failed takes, measured words, reference hash and ASR
evidence. Repair only failed takes, retaining their rejected versions. Do not
automatically insert laughs or breaths: the [real audition](NEXT_VOICE_PASS.md)
supported fewer phrasing resets and exact words, not a proven human-quality
score. The documented-template variant that changed “asked” to “ask” remains
failed, not an acceptable shortcut.

## What the implementation can actually automate

The [story runner](NEXT_STORY_PIPELINE.md) already joins voice preparation,
measured edit compilation, original sound, a builder, rendering, encoded-speech
QA, decoded review sheets and portable packaging. Verified reuse binds exact
inputs and outputs. It does **not** create a new story or infer its physical
scene actions. [The generic voice stage](../scripts/prepare_story_voice.py)
accepts a fresh performance plan; old canonical media are never overwritten.

`prepare_yes_machine.py` hardcodes that film's project ID, thirteen shot modes,
spoken anchors and headings. `build_procedural_short.mjs` requires its mechanical
world and exactly three gates. Changing the narration or title is not enough to
produce these seven stories. The older `script.py` produces longer structured
explainer copy; its schema requires 5–10 substantial body paragraphs and does
not produce the procedural scene contract. Neither path currently provides
unattended original daily story authoring at this quality.

**Practical next implementation:** have the daily agent author a new project
from a selected row, then reuse the proven production stages. Add a small
validated, data-driven story recipe for explicit word anchors, scene family,
props, camera, action, headings and audio cues. Build two or three reusable
local scene families (miniature rooms, kinetic desk, ribbon paths), with distinct
actions and compositions per story. Reject unknown actions, missing anchors,
unchanged prior scripts and unsupported scene families. This is proposed work,
not a delivered generator. Keep the existing pinned Three.js/GSAP/HyperFrames
stack and reviewed licenses; no new orchestration framework, image/video model,
paid API, or voice model is needed for this plan. Existing upstream decisions
and measured costs are in [the runner guide](NEXT_STORY_PIPELINE.md) and
[voice research](NEXT_VOICE_PASS.md).

Prepare the next project ahead of its release day. The measured Yes Machine run
is evidence that a **prepared** production recipe can complete locally; it is
not a benchmark for authoring, new-scene implementation or unattended quality.
Until the recipe authoring gap is filled, a wake-up can execute an agent's
authored work, but a queue watcher alone cannot create the next film.

## Daily release and duplicate prevention

Routine release is within the user's ongoing authorization; a new permission
question is not a daily workflow stage. The operator must still establish:

1. **One date slot:** bind the IST date to exactly one new `episode_id` before
   authoring. Inspect the active queue and dated operator reports first. Never
   send a second episode to compensate for a missed day. A missed slot is
   reported as missed; it does not unlock the held pilots or replay a completed
   film. Complete delayed destinations of the same episode using their original
   receipts; if this would create two episodes on one platform on one date,
   defer the newer slot instead of posting a burst.
2. **Editorial inputs:** original script and physical action, no unsupported
   claims, correct disclosures and local asset provenance. These fiction-only
   briefs intentionally assert no product, membership, health, price or earnings
   facts. If a factual line is added, check the current official source for the
   exact market and record URL, date and supporting statement in the project.
   The old [U.S. source pack](EDITORIAL_SOURCES.md) is not worldwide evidence or
   a substitute for a fresh check. No invented facts from model memory.
3. **Actual exported-film checks:** exact script/SRT/word timing, selected voice
   provenance, full MP4 decode, loudness/alignment/clipping checks, every encoded
   speech window's independent ASR, decoded scene/cut/action samples, and a
   current `DELIVERY_REVIEW.json` with no blocking visual findings. Inspect the
   real film's reading spans, causal motion and ending; frame extraction alone
   is not creative review. Keep technical evidence separate from subjective
   voice quality and any audience claim.
4. **One campaign, three posts:** use the same verified MP4 hash and episode ID
   for all three destinations. Stable post IDs are `<date>-<platform>` in the
   day's campaign; account, timezone, public visibility and transport are
   explicit. Enqueue only after review. Use one designated active queue, with
   its path recorded in the operator status; separate SQLite files do not share
   deduplication. Preserve the rejected-pilot queue and its holds.
5. **Confirm each destination:** revalidate sources and the actual owned
   account before publishing. API jobs use existing receipts; browser jobs
   must be claimed and reconciled with observed account/title/remote URL and
   matching file-hash evidence. An ambiguous result stays uncertain. Never
   clear receipts or upload a second copy to fix a caption, thumbnail or
   interrupted confirmation. A successful destination is not retried because
   another destination failed. Do not describe browser observation as API
   verification or imply missing Meta authorization has been solved.

The queue already deduplicates **platform + account + video hash**, including
across campaigns in the same database. It does not currently enforce the
one-episode-per-IST-date limit for different videos. The date-slot rule above
is therefore an operator obligation until a tested persistent date guard is
implemented. The story-publication bridge accepts reviewed story projects;
it does not implement daily story generation. See [Social Operator](SOCIAL_OPERATOR.md)
and [campaign contracts](SOCIAL_CAMPAIGNS.md) for the current execution paths.

At 24 and 72 hours, record only real available observations, separately by
platform and comparable age. Use missing values when metrics are unavailable.
The first week tests whether a concrete physical consequence and a restrained
voice turn hold attention; it does not establish causation or guarantee reach.
Use observed questions to author the next week's new stories, not to repost
the best-performing file or manufacture engagement.
