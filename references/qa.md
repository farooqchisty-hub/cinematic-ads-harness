# QA gates

Run all of these before showing anything to the user, and report exactly what ran.

**Per take (`cine qa`)**
- Two transcripts: word-level on the full take, and Whisper large-v3 on the demucs vocal stem. Every planned line present, in order, exact words.
- Brand and invented words are judged on the vocal stem. On a full mix, music and SFX make transcribers mishear even correct audio.
- The contact sheet: read it. Faces match the identity cards; boards spelled right; no real brands (crop or reject); no physics errors (a vehicle turning around, a phone flipping, morphing hands).
- Cuts from `cine cuts` (frame differencing); the ffmpeg scene filter misses some.

**Timing**
- Line starts come from the vocal stem's loudness per 0.1 s (`cine stems --at a b`). Whisper stamps the first word after a silence early and long.
- Whisper hallucinates words in silence and in breaths. Use only clips of real lines from a second world's stem.

**Voices**
- `cine voices` with clips of each recurring speaker across takes. Diarization separates a woman from men reliably but often merges two men; report that case as inconclusive and suggest a listen.

**Final cut**
- A full transcript of the final: every line, in order.
- Brand words again on the final vocal stem if any graphic or sound sits near them.
- Dark or flash frames: none (scan mean brightness per frame).
- Graphics never over a face, numbers agree across graphics and with approved claims.
- No natural pause between speakers squeezed under about a second.
- Loudness about -14 LUFS integrated; runtime as planned; picture and sound frame-aligned (segments use exact frame counts).
- A share copy under 30 MB.
