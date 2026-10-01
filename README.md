# Cinematic Ads Harness

Give it a **product URL** and a **concept**. It builds a finished cinematic video ad (45 to 70 s, 9:16):
storyboard, cast, keyframes, motion graphics from the product's own page, generated scenes with native
dialogue, an original score, the edit, QA, and delivery files.

It's the system that made "Box, Box, Brenda" for PushOwl by Brevo, rebuilt to work for any product with a
link. An agent (Claude Code or Codex) drives it and makes the judgement calls; you approve at the gates.

```
URL ──> brief + verified claims ──> CONCEPT ──gate──> STORYBOARD ──gate──> graphics ──> takes ──> score
    ──> edit + QA ──gate──> final mp4, share copy, contact sheet, concept art, cost summary
```

## What it needs

1. **A product URL.**
2. **A concept.** Three ways to give one:
   - Let it write 5: *"Make 5 cinematic ad concepts for &lt;url&gt;"*, then *"Go with 3"*.
   - Say it: *"Cinematic ad for &lt;url&gt;. My concept: &lt;the story, who's in it, what the product proves, the tone&gt;"*.
   - Fill in `templates/concept.md` and point the agent at it.

Every path stops at a storyboard for your approval before any video is generated.

## Setup (once)

```bash
npm install                        # Node 20+ (the brief and image renders)
pip install -r requirements.txt    # Python 3 + Pillow (+ boto3 for S3/R2 storage)
cp .env.example .env               # add your keys (see below)
bin/cine doctor --storage          # checks every tool and key with free calls
```
| You provide | For |
|---|---|
| treg CLI, signed in (`treg login`) | Seedance 2.5 face video generation |
| `REPLICATE_API_TOKEN` | the score, vocal stems, transcription, the speaker check |
| `OPENROUTER_API_KEY` or `OPENAI_API_KEY` | the brief; cast cards, sheets, boards and keyframes |
| Public storage: `STORAGE_PUBLIC_BASE` + `S3_*` (S3 or Cloudflare R2) or `STORAGE_UPLOAD_CMD` | the video model reads references only from public links |
| ffmpeg with libvpx, Chrome | assembly and graphics |

**Why treg for video:** Seedance 2.x on Replicate and fal refuses any photoreal face (error E005), so
stories with recurring people can't be made there. treg's reAPI route (`doubao-seedance-2.5-face`) accepts
generated cast and keyframes, up to 30 reference images and 10 voice clips, makes 30 s takes with native
dialogue, refunds failed tasks, and reaches backup providers for the same model.

## Install as a skill

- **Claude Code:** copy this folder to `~/.claude/skills/cinematic-ads-harness/` (or a project's `.claude/skills/`), then ask: *"Make a cinematic video ad for &lt;url&gt;"*.
- **Codex:** put the folder in your workspace (or `~/.codex/skills/`); Codex reads `AGENTS.md`. Allow network access.

## Commands (the agent runs these; `bin/cine help` for all)

```bash
bin/cine new --url https://example.com/product          # -> runs/example-com
bin/cine brief    --run runs/example-com                 # brief, verified claims, brand kit
bin/cine capture  --run runs/example-com                 # real page screenshots for graphics
bin/cine claims   --run runs/example-com --approve all   # or approve/reject/add one by one
bin/cine concepts --run runs/example-com                 # after the agent writes concepts.json
bin/cine concept  --run runs/example-com --pick 2        # or --text "..." / --file concept.md
bin/cine validate --run runs/example-com                 # after the agent writes plan.json
bin/cine storyboard --run runs/example-com               # renders + contact sheet + storyboard.html
bin/cine graphics --run runs/example-com                 # after graphics.json
bin/cine takes    --run runs/example-com --unit R1 --n 2 # paid: video takes
bin/cine qa       --run runs/example-com --take R11 R12
bin/cine music    --run runs/example-com                 # after music.json
bin/cine assemble --run runs/example-com                 # after edit.json
bin/cine deliver  --run runs/example-com --final final_v1.mp4 --takes R11,E3 --music A,B --art 12,40 --title ".." --logline ".."
```

## What's in the run folder

`brief/` (brief.json, brandkit), `capture/`, `claims.json`, `concepts.json` + `concepts.html`, `concept.json`,
`plan.json`, `storyboard/` + `storyboard.html`, `graphics.json` + `graphics/out/`, `units/` (exact requests),
`seq/` (takes, transcripts, sheets, task ids), `v/` (stems), `vref/`, `music.json` + `music/`, `edit.json`,
`build/`, the final mp4, `out/` (share copy, contact sheet, concept art, costs.json), `ledger.json`.

## Costs

About $30 to $65 in video generation for a finished 60 to 70 s ad, plus $5 to $8 for the storyboard and
cents for QA. The ledger records every paid call; the video's cost is the final version only
(`references/costs.md`).

## Honest limits

- Agent-in-the-loop: the agent writes concepts, the plan, prompts and the edit, and picks takes; you approve. It isn't a one-click render.
- Video models still make mistakes (physics, a stray real-brand sign); the QA catches most, and a short insert fixes them.
- Confirm the music model's commercial-use terms before paid media.

## Read next

`SKILL.md` (the workflow), `references/principles.md`, `references/prompting.md`, `references/schemas.md`,
`references/qa.md`, `references/traps.md`, `examples/box-box-brenda/`.
