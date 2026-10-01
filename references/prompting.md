# Prompting Seedance 2.5 (unit prompts)

`cine takes` writes the reference header for you ("@image1 is the look of ..., @image5 is Theo's face, @audio1
is ONLY the voice of Dana ..."). You write the BODY in `plan.json` `units[].prompt`, using this skeleton:

```
A <N> second cinematic <genre>, one continuous generation of <k> shots, <setting>. Vertical 9:16, ultra-real,
ARRI Alexa 35 look, Kodak 500T grain, <lighting>. Hard motivated cuts. Faces, wardrobe, vehicles and every
logo exactly as in the references.
BRANDS: the only logos anywhere are the fictional ones on the supplied boards (<names>) and <the product's own
brand>; every other sign or screen is blank. Screens face away from camera. No on-screen text, captions or subtitles.
FRAMING (only for units used in a split screen): every shot keeps its subject and action inside the middle half
of the frame height; nothing important in the top or bottom quarter.
SOUND: NO MUSIC AT ALL (music is added later). Only the spoken lines plus natural sound: <ambience>. There are
deliberate one-second beats of pure <ambience> between some lines, as marked.
VOICES: <name>, @audio1. <off-camera voices: accent, pitch, energy, how they're heard (radio, broadcast, phone)>.
PHYSICS: every object keeps one consistent physical state within a shot; phones never flip; no morphing,
flashes or glitch frames. <the hardest action's rules, e.g. cars: no spins, no reversing, always pointing forward>.
0 to 3.3 s: <shot>. <Speaker>, <delivery as adjectives>: "<line>"
3.3 to 6.2 s: ...
DELIVERY: every quoted line is spoken clearly, exactly as written, once, acted not read, the noted emotion in the
face (on camera) and voice, natural breaths, stressed words stressed. Radio lines are clear and lightly
compressed, never muffled. Nothing outside the quotes is ever spoken.
```

## Rules that came from real failures
- **Delivery notes are adjectives.** "(no panic)" got spoken aloud. Write "(calm, clipped)".
- **Brand and invented words:** spell phonetically in the line and add a note. Worked example: `Push-OWL` with
  "(the brand name, two syllables said as one word: PUSH then OWL like the bird, OWL stressed, the OW as in ouch
  and the final L clearly finished, no pause between them)". For a hard common word: `omni-channel` with
  "(said OM-nee CHAN-nel)". Captions use the real spelling.
- **Brand lines in short units.** Long 30 s takes got the brand word right about a quarter of the time; a 14 s
  ending unit with 3 to 6 takes got it clean.
- **Plan timings drift.** The model re-times shots to fit the lines; read the real cuts and line timings from the take.
- **Inserts:** `first_frame` = the last good frame; describe only the continuation and the physics. No other
  references are allowed with a first frame.
- **Voice refs:** 3 to 6 s of clean vocal stem per speaker, from an approved take. The prompt says the sample's
  words are never spoken (the header does this for you).
- **Off-camera voices** (commentator, spotter, narrator): describe accent, pitch and how they're heard; they never
  need lip sync, so they can be re-spaced in the edit.

# Keyframes and cast cards
`cine storyboard` builds these prompts from `plan.json`. Write rich `id_block`s (age, build, face shape, skin,
hair, eyes, one distinguishing detail) and keep wardrobe per scene. Identity cards are always face-on with no
headgear, or every close-up invents a new face. Fictional brand names must be short and spellable.
