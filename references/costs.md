# Costs

| Item | Rate |
|---|---|
| Seedance 2.5 face via treg, 720p | about $0.27 a second ($8 for a 30 s take) |
| Storyboard renders (gpt-image-2 high) | about $0.19 each; a storyboard is typically 25 to 40 renders |
| ElevenLabs Music via Replicate | about $0.0083 a second |
| Stems, transcripts, voice check | cents |

A 60 to 70 s ad built from 4 units plus 2 inserts with 2 to 3 takes each: about $30 to $65 in video, plus
$5 to $8 for the storyboard.

**The ledger rule.** Every paid call is written to `ledger.json`. The VIDEO's cost is the final version
only: the takes actually in the cut plus the music sections used (`cine deliver --takes .. --music ..`
marks them). Everything else (unused takes, re-rolls, inserts that weren't used, QA, unused music) is
test spend, kept in the ledger and in `out/costs.json` as `test_usd`. Anything shown to a wider audience
uses the final number and doesn't mention tests.

Always state the estimate before a paid step, and flag it when a fix costs more than planned.
