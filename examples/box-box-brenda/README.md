# Worked example: "Box, Box, Brenda" (PushOwl by Brevo, approved 27 Sep 2026)

A 68.8 s split-screen thriller: a race driver's candle store loses a cart; the product chases the buyer across
push, email and SMS while a rival chases him on track; a WhatsApp discount wins her as he takes the flag. Read
`case.md` for how each principle was applied and what went wrong. These are this story's choices, not defaults.

| File | What it is |
|---|---|
| `case.md` | principle by principle: what was decided here and why, including the failures and fixes |
| `unit_*.json` | the exact generation requests: R1 race 30 s, BR the second world 28 s, R2 race 20 s, E the 14 s ending with the brand lines, SP and MC 4 s first-frame inserts. Their reference URLs pointed at the original run's storage and won't resolve for you. |
| `edit.json` | the final edit (older key names `race`/`br`, which the assembler still accepts as `parts`/`second`) |
| `music.json` | the three score sections and how they were stitched to the cut |
| `plan_agent_format.json` | the storyboard as stored in the Brevo CPMA agent (a different, older schema from this package's `plan.json`; useful for the cast, scenes and lines) |
| `contact_sheet.png`, `concept_art.png` | the final cut's shots, and the 16:9 key art |

The final video lives in the CPMA agent's Library (creative race-brenda5), behind the Brevo login.
