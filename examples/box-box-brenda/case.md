# Worked example: "Box, Box, Brenda" (approved 27 Sep 2026)

How the SKILL.md principles were applied to ONE concept. These values fit this story; they are not defaults for the next one.

**Concept:** a race driver's candle store loses Brenda's cart; PushOwl chases her across push, email and SMS (ignored) while a rival chases him on track; a WhatsApp 10% offer wins her as he takes the flag; the press-conference CTA. 68.8 s, 9:16. Finals: R2 `video/final/race-brenda7a_generated.mp4` and `race-brenda7b_fallback.mp4`; build dir `video/work/race-brenda6/`, edit_a.json.

| Principle | What we decided here and why |
|---|---|
| 2 Added sound | The story is about messages Brenda ignores, so each message arriving (cart alert, push, email, SMS, WhatsApp, order chime) had to register. The tracker, stamps, tower and wipes stayed silent after Farooq heard their swish as a "beep". |
| 3 Music | 4 generations spliced, so all were prompted with no music. One ElevenLabs score in 3 sections (chase build with a breakdown before the pit stop, a slam into the drive landed on the pit-stop cut, a warm close with its button just before the outro), dipped to 0.6 under the CTA. |
| 4 Device | Two worlds acting on each other (race and Brenda's sofa), and cutting between them flipped the audio, so split screens (race top, Brenda bottom) for the chase stretches: 720x640 middle-band crops, a mint divider, race ambience ducked to 0.35, Brenda's room at 0.35, and only her line clips (her breath stem made whisper invent words). |
| 5 Units | R1 race 30 s, BR Brenda 28 s continuous, R2 race 20 s, E ending 14 s holding both brand lines. Fixes were 4 s first-frame inserts (a spin fix, a new Marcus line). |
| 6 Brand words | `Push-OWL` + "(the brand name, two syllables said as one word: PUSH then OWL like the bird, OWL stressed, the OW as in ouch and the final L clearly finished, no pause between them)"; `omni-channel` + "(said OM-nee CHAN-nel)"; `e-commerce`. Passed 3 of 3 transcribers on the vocal stem (took 6 ending takes). |
| 7 Voices | Voice refs for Dana, Theo, Marcus; pyannote confirmed Dana across units and was inconclusive for the men. |
| 8 Pacing | Off-camera radio lines were re-spaced to fit Brenda's lines; that squeezed a native 1.4 s pause to 0.06 s (Farooq caught it); fixed with a 0.64x podium slow-mo plus Dana starting under the commentator's tail, which gives a 1.0 s pause. |
| 10 Physics | The car spun 180 degrees in R1; option A was a generated insert from the last good frame, option B cutaways; both delivered. |
| 11 Brands | A "DHL" banner appeared twice; kept only where it sat outside the split crop. |
| 12 Graphics | Played at 1.25 to 1.4x; the ORDER WON card was moved off Theo's face and corrected to $86.40 to match the toast. |
| Cost | $58.34 build + $5.34 fixes. |
