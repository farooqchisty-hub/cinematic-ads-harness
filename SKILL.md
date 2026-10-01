---
name: cinematic-ads-harness
description: Build a finished cinematic AI video ad (45 to 70 s, 9:16) for any product from two inputs, a product URL and a concept (the user's own, or one of 5 this skill writes). Covers setup, brief and verified claims, concepts, storyboard with cast cards and keyframes, motion graphics from the product's own page, Seedance 2.5 generation via treg, a composed score, frame-exact assembly, QA and delivery, with user approval gates. Use when asked for a cinematic video ad, a video commercial, a story-driven ad, or "make a video ad for <url>".
---

# Cinematic Ads Harness

You (the agent) drive this harness. The scripts in `bin/cine` do the mechanical work (rendering,
generation, stems, transcripts, assembly); you do the judgement work (concepts, the plan, prompts,
picking takes, timing the edit, spotting glitches), and the user approves at the gates. Never skip a
gate, and never start paid video generation before the storyboard is approved.

Read `references/principles.md` before writing a concept or a plan, `references/prompting.md` before
writing a unit prompt, and `references/traps.md` before your first production run.
`examples/box-box-brenda/` is one worked example; read it as an example, never as a template.

## 0. When the user starts: tell them this (in your own words, briefly)

> This harness needs two things: **a product URL** and **a concept**.
> For the concept you can (a) let me write 5 cinematic concepts from the page and pick one, (b) describe
> your own in a few lines (the story, who's in it, what the product proves, the tone), or (c) fill in
> `templates/concept.md`. Every path stops at a storyboard for your approval before any video is made.
> A finished 60 to 70 s ad costs about $30 to $65 in generation, plus retakes.

## 1. Setup (first run on a machine)

Run `cine doctor`. For every MISSING row, ask the user for it, explain what it's for, and store keys
only in a local `.env` (copy `.env.example`; never commit it, never print keys back):

| Needed | Ask for | Why |
|---|---|---|
| treg | install the treg CLI and sign in (`treg login`) | Seedance 2.5 face video (see below) |
| Replicate | `REPLICATE_API_TOKEN` | the score (ElevenLabs Music), vocal stems, two transcribers, the speaker check |
| Text + image model | `OPENROUTER_API_KEY` (recommended) or `OPENAI_API_KEY` | the brief, and cast cards, sheets, boards, keyframes (gpt-image-2) |
| Public storage | `STORAGE_PUBLIC_BASE` plus `S3_*` keys (AWS S3 or Cloudflare R2) or a `STORAGE_UPLOAD_CMD` | the video model only reads references from public https links |
| Tools | ffmpeg with libvpx, Python 3 + Pillow, Node 20, Chrome | rendering and assembly |

Then `cine doctor --storage` (uploads one tiny test file and confirms it's publicly readable).

**Why treg, not Replicate, for video** (tell the user if they ask): Seedance 2.x on Replicate and fal
refuses any photorealistic face input (error E005, a privacy classifier; downscaling, blurring and
stylising all fail), so a story with recurring people can't be made there. treg routes to reAPI's
`doubao-seedance-2.5-face`, which accepts generated cast and keyframes, up to 30 reference images and 10
voice-reference clips, and 30 s continuous takes with native dialogue. Failed or moderated tasks are
refunded, and one token reaches backup providers for the same model.

## 2. Brief and claims (gate: claims approved)

```
cine new --url <product url>                 # prints the run folder, e.g. runs/example-com
cine brief --run runs/example-com            # brief.json, verified claims, brand kit (cents)
cine capture --run runs/example-com          # real screenshots + assets for graphics (free)
```
Show the user the candidate claims (`cine claims --run ..`). Each was quoted verbatim from the page.
Ask them to approve, reject, or add claims with a source (`--approve c1,c3`, `--add "4.8 stars: rated 4.8 on X" --source <url>`).
Also ask: target market and language (casting and accents follow it), runtime (45 to 70 s), any names
or topics to avoid (add them to `never_say` in claims.json). Only approved claims may appear as
numbers or promises anywhere in the script or graphics; `cine validate` enforces it.

## 3. Concept (gate: user picks or gives one)

- **User gave a concept:** `cine concept --run .. --text "<their words>"` (or `--file concept.md`). Their idea is the spine; fill gaps only, and say what you added.
- **No concept:** write `concepts.json` with 5 concepts (schema in `references/schemas.md`) from the brief, the approved claims, and the page captures, then `cine concepts --run ..` and show the page. Each concept: logline, genre, runtime, the first 3 s, cast, worlds, the product mechanic and how the story PROVES it, beat order (hook, setup, turn, build, payoff, in-world CTA), devices it needs and why, risks, estimated cost. Make the 5 genuinely different (genre, world, device), all fictional worlds with invented brands. Then `cine concept --pick N`.

## 4. Storyboard (gate: user approves the storyboard page)

Write `plan.json` (schema in `references/schemas.md`) from the concept, applying `references/principles.md`:
cast with identity blocks and voices, locations, vehicles and props, fictional brand boards, scenes,
keyframes, generation units with prompts (`references/prompting.md`), every line with speaker, timing,
on/off camera and delivery, the CTA (approved claims only), the sound plan (native first; added sounds
only for events the audience must register), the music plan (sections), and the graphics plan.

```
cine validate --run ..        # fix every issue; warnings are judgement calls
cine storyboard --run ..      # cast cards, sheets, boards, keyframes (about $0.19 each), contact sheet, storyboard.html
```
Read the contact sheet and every render yourself (faces, spelling on boards, real-brand leaks); re-render
bad ones with `--only key --force`. Show the user `storyboard.html` with the cost estimate, and WAIT.

## 5. Graphics

Write `graphics.json` from the plan's graphics list using the templates (toast, message, product_card,
claim_card, callout, tracker, stamp, cta, outro), real images from `capture/` and `brief/brandkit/`, and
approved claims only. `cine graphics --run ..`. Check each WebM's bounding box against the faces in the
shots it sits over; graphics never cover a face. A graphic gets a sound only per principle 2.

## 6. Production (paid; state the estimate before each unit)

1. Generate the unit with the most dialogue first: `cine takes --run .. --unit R1 --n 2`.
2. `cine qa --run .. --take R11 R12`: read both transcripts and the contact sheet. Reject takes with wrong words, mispronounced brand words (judge on the vocal stem), drifting faces, physics errors or real-brand leaks.
3. Cut voice references from the best take for every recurring speaker (`cine vref`), add them to the remaining units' `voice_refs`, then generate those units. Short units holding brand lines or the CTA get 3 or more takes.
4. Fix a bad moment with a short insert unit (`first_frame: "R11@23.0"`, 4 s), not by re-rolling a good long take.
5. Pin real line timings from the vocal stem (`cine stems --at a b`), not from word stamps.

## 7. Score

Write `music.json` (sections matching the story's energy; `references/schemas.md`), `cine music`, read
the per-second loudness, measure each slam with `cine onset`, set the stitch offsets so hits land on
cuts, and run `cine music` again to stitch.

## 8. Assemble and QA (gate: user approves the cut)

Write `edit.json` (`references/schemas.md`), `cine assemble --run ..`, then run every check in
`references/qa.md` on the final: every line present and in order, brand words on the vocal stem, frame
scan (faces, brands, physics, graphics over faces, dark or flash frames), voices, loudness, runtime.
Send the user the cut with exactly what was checked and what wasn't. For feedback: assess first and
explain the cause, propose options with costs, and when they're unsure build both.

## 9. Deliver

`cine deliver --run .. --final <name>.mp4 --takes <takes in the cut> --music <sections used> --art <t1,t2> --title ".." --logline ".."`
gives a share copy under 30 MB, the final contact sheet, 16:9 concept art from real frames, and
`out/costs.json`. The video's cost is the final version only (takes in the cut plus music used);
everything else is test spend (`references/costs.md`).

## House rules
- Nothing is published, posted or sent anywhere by this harness; it writes files. Uploads go only to the user's own storage, for the video model to read.
- No em or en dashes in anything written for people.
- Say what was checked and what wasn't; never claim a check passed that didn't run.
