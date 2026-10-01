# Handoff: Cinematic Ads Harness

**What it is.** A package that turns a product URL and a concept into a finished cinematic video ad (45 to 70 s,
9:16): storyboard, cast, keyframes, motion graphics from the product's own page, generated scenes with native
dialogue, an original score, the edit, QA and delivery files. It's the system behind PushOwl's "Box, Box, Brenda"
ad, generalised to work for any product.

**Who runs it.** An AI coding agent (Claude Code or Codex) drives it and makes the creative calls; you approve at
three gates. It isn't a one-click render.

## The two inputs
1. **A product URL.**
2. **A concept**, given one of three ways:
   - *"Make 5 cinematic ad concepts for &lt;url&gt;"*, then pick one.
   - *"My concept: &lt;story, who's in it, what the product proves, tone&gt;"*.
   - Fill in `templates/concept.md`.

## Get started (about 15 minutes)
1. Clone the repo, then run `npm install` and `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and add the keys below.
3. Run `bin/cine doctor --storage`. Everything should show "ok".
4. In Claude Code (with the folder in `~/.claude/skills/`) or Codex, say: *"Make a cinematic video ad for &lt;url&gt;"*.

| You need | For |
|---|---|
| treg CLI, signed in (`treg login`) | video generation (Seedance 2.5 face) |
| Replicate token | music, vocal stems, transcription, the voice check |
| OpenRouter or OpenAI key | the brief; cast cards, keyframes |
| A public bucket (S3 or Cloudflare R2) | the video model only reads reference images and voices from public links |
| ffmpeg (with libvpx), Node 20, Python 3, Chrome | rendering and assembly |

## The flow
```
URL ──> brief + claims (you approve the claims) ──> CONCEPT (gate 1) ──> STORYBOARD (gate 2)
    ──> graphics ──> video takes ──> score ──> edit + QA ──> CUT (gate 3) ──> delivery files
```
- **Claims:** pulled from the page with the exact quote. You approve or add claims, and nothing else can appear as a number or promise.
- **Storyboard:** a review page with the cast, keyframes, every line with its delivery, graphics, sound and music plan, and the cost. No video is generated before you approve it.
- **Delivery:** the final mp4, a share copy under 30 MB, a contact sheet, 16:9 concept art, and the cost (final version only).

## Cost
About $30 to $65 of video generation per finished 60 to 70 s ad, plus $5 to $8 for the storyboard.

## Status (be aware)
- **Verified:** the setup check, the plan rule checker, all 9 graphics templates rendering, and the assembler, which rebuilt the approved PushOwl ad identically (picture and sound).
- **Never run yet:** the paid stages (brief against a live page, storyboard renders, video takes, music, transcription). They're ported from the steps that made the PushOwl ad, so the first real run may need small fixes.

## Where to look
`README.md` for the commands, `SKILL.md` for the agent's workflow, `references/` for the principles,
prompting, schemas, QA, costs and traps, and `examples/box-box-brenda/` for the worked example.
