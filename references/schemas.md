# File schemas (written by the agent, checked and used by `cine`)

All files live in the run folder (`runs/<slug>/`). Paths inside them are relative to the run folder.

## concepts.json (5 concepts)
```json
[{"title": "Box, Box, Brenda", "genre": "sports thriller", "runtime_s": 65, "est_usd": 55,
  "logline": "One line: who wants what, what's in the way, how the product wins it.",
  "hook": "The first 3 seconds: picture and first line.",
  "product_proof": "Exactly which product feature the story demonstrates, and how the audience sees it work.",
  "cast": ["Theo Vance, driver", "Dana Reyes, race engineer"], "locations": ["night street circuit", "pit wall"],
  "beats": {"hook": "...", "setup": "...", "turn": "...", "build": "...", "payoff": "...", "cta": "..."},
  "devices": ["split screen: two storylines that affect each other"], "risks": ["fast vehicle physics"],
  "evidence": "Which brief angle or approved claim it rests on, or 'user idea'"}]
```

## plan.json (the storyboard)
```json
{"title": "...", "logline": "...", "aspect": "9:16", "body_s": 64.8, "outro_s": 4, "runtime": {"min": 58, "max": 70},
 "look": {"camera": "ARRI Alexa 35 look", "lenses": "vintage spherical primes", "stock": "Kodak 500T", "grade": "rich night blacks", "style": "ultra-real, cinematic"},
 "world": {"fictional_brands": [{"id": "brand_ember", "name": "Ember Racing", "what": "the orange rival team", "applications": "car livery, team kit, pit board"}],
           "real_brands_to_avoid": ["any real team or sponsor"]},
 "cast": [{"id": "char_1", "name": "Theo Vance", "role": "driver", "importance": "lead",
           "id_block": "38 years old, lean, short dark hair, light stubble, olive skin, brown eyes",
           "wardrobe": {"S1": "green race suit"}, "voice": "light transatlantic accent, mid pitch, dry", "expressions": ["focused", "smirk"]},
          {"id": "char_8", "name": "TV commentator", "importance": "voice", "voice": "American male broadcast baritone"}],
 "locations": [{"id": "loc_track", "name": "street circuit", "description": "...", "time_of_day": "night", "key_light": "hard floodlights", "brands": ["brand_ember"]}],
 "vehicles": [{"id": "veh_1", "name": "the hero car", "description": "...", "livery": "...", "brands": ["brand_team"]}],
 "props": [],
 "scenes": [{"id": "S1", "slug": "INT. COCKPIT - NIGHT", "location": "loc_track", "characters": ["char_1"], "beat": "hook", "action": "...", "mood": "..."}],
 "keyframes": [{"id": "K1", "scene": "S1", "shot": "extreme close-up through the visor", "lens": "24mm", "angle": "eye level",
                "action": "Theo's eyes at 300 km/h, sparks streaking", "assets": ["char_1", "veh_1"], "expression": "focused"}],
 "units": [{"id": "R1", "world": "the race", "purpose": "hook to pit entry, 17 lines", "t0": 0, "gen_s": 30, "used_s": 30, "takes": 2,
            "keyframes": ["K1", "K2"], "cast": ["char_1", "char_2"], "boards": ["brand_ember"],
            "voice_refs": {"char_2": "vref/dana.mp3"},
            "prompt": "A 30 second cinematic race thriller, one continuous generation of ten shots... (see prompting.md)"},
           {"id": "SP", "world": "the race", "purpose": "insert: fix a spin", "t0": 23.0, "gen_s": 4, "first_frame": "R11@23.0", "prompt": "Continue this exact shot..."}],
 "lines": [{"t0": 3.3, "t1": 6.2, "who": "char_2", "on_camera": true, "unit": "R1",
            "line": "Theo. Your store. Brenda just abandoned her cart.", "delivery": "urgent but deadpan, stress on Brenda"}],
 "cta": {"spoken": "...", "onscreen": "Sign up free"},
 "sound": {"native": "...", "added": "only the notifications the audience must register: ...", "split": "..."},
 "music": {"sections": "build with a breakdown, slam into the drive on the pit-stop cut, warm close", "bpm": 128},
 "graphics": [{"id": "G1", "template": "toast", "t": 9.0, "purpose": "the web push arrives", "sound": "pop"}],
 "waivers": {"dialogue_cap": "only with the user's approval, and why"}}
```
- `importance`: lead (turnaround, expressions, identity card), support (turnaround, card), extra (card), voice (no images).
- `unit.keyframes`, `cast`, `boards` become the reference images, in that order (faces weigh most after keyframes). `refs` adds others: `[{"file": "capture/assets/x.png", "is": "the product box"}]`.
- `first_frame` turns a unit into an insert: `"TAKE@seconds"` or an image path. Inserts take no other references.
- Every quoted line in `lines` must appear in quotes in some unit's prompt, or it won't be spoken.

## graphics.json
```json
[{"id": "G1", "template": "toast", "duration": 2.4, "pos": {"x": 70, "y": 1000},
  "data": {"icon": "brief/brandkit/logo.png", "title": "Store name", "time": "now", "text": "Your candles are still in your cart", "stamp": "DISMISSED", "stamp_t": 1.6},
  "sfx": [{"rel_s": 0.42, "kind": "pop"}]}]
```
Template fields (`data`):
- **toast**: icon, title, time, text, stamp?, stamp_t?
- **message**: icon, sender, text, image?, chip?, chip_t?, pop?
- **product_card**: image, name, line, price?
- **claim_card**: figure (an approved claim), caption, source
- **callout**: image (a page capture), image_w (its pixel width), view_h, highlight {x,y,w,h}, label, zoom
- **tracker**: icon, title, steps [{name, state}], events [{t, step, state: ok|no|go, label}]
- **stamp**: words [..], gap
- **cta**: lines [..]
- **outro**: logo, headline, sub, button, card_image?

`sfx` kinds (assets/sfx): pop, alert, chime, swish, whoosh, stamp, tick, hit, thump, riser.

## music.json
```json
{"common": "Original instrumental for a cinematic <genre> commercial. No vocals. 128 bpm, D minor palette, <instruments>. Starts instantly with no fade in.",
 "sections": [{"name": "A", "ms": 31000, "prompt": "Section: suspense build... at 0:19 everything drops to one low drone..."},
              {"name": "B", "ms": 21000, "prompt": "Section: opens on a massive slam at 0:00..."}],
 "stitch": [{"name": "A", "at": 0.0, "trim": 29.3, "fade_out": [28.5, 0.8]}, {"name": "B", "at": 28.45, "fade_out": [19.6, 0.6]}],
 "total": 69.0, "out": "music.wav"}
```
Set B's `at` = (the picture cut where the slam should land) minus (`cine onset music/mus_B.mp3`).

## edit.json
```json
{"parts": [{"src": "R11", "in": 0, "out": 23.0}, {"src": "SP2", "in": 0, "out": 2.375, "audio_src": "R11", "audio_in": 23.0}, {"src": "R11", "in": 25.375, "out": 30}],
 "second": "BR1",
 "segments": [{"t0": 0, "t1": 8.46, "layout": "full"},
              {"t0": 8.46, "t1": 21.4, "layout": "split", "bottom": [{"t0": 8.46, "t1": 11.1, "src_in": 0.0, "y": 240}]},
              {"t0": 47.042, "t1": 49.2545, "layout": "full", "rt0": 47.042, "slow": 0.64}],
 "voc_moves": [[38.45, 39.22, 36.75]],
 "br_lines": [[1.70, 2.25, 10.16]],
 "captions": [[0.26, 3.30, "Lap forty-one, and Vance is hunting Castell!"]],
 "cap_y": [[50.0, 64.0, 1560]],
 "mg": [{"id": "G1", "t": 8.6, "speed": 1.0, "y": 731}],
 "sfx": [[9.02, "pop", 0.5]],
 "music": "music.wav", "music_gain": 0.5, "music_env": [[50.8, 63.1, 0.6]],
 "warp": {"t0": 47.042, "t1": 48.458, "k": 0.64},
 "divider": "0x73C4A7", "outro": "graphics/out/OUTRO.webm", "out": "final_v1", "work": "build"}
```
- `parts` lay takes end to end: that's the main timeline. `audio_src` keeps another take's sound under a replaced picture (inserts).
- `segments` are in FINAL time; `rt0` is where the segment starts on the main timeline (needed after a warp), `slow` plays it slowed.
- Split windows are `bottom` slices of the `second` take; their audio follows them, at room-tone level. Its spoken lines go in `br_lines` as `[src_t0, src_t1, final_t0]`.
- `voc_moves` re-space OFF-camera lines only: `[src_t0, src_t1, final_t0]` on the main timeline's vocal stem.
- `captions` come from the placed lines with the brand's spellings; `cap_y` keeps them off faces and graphics.
- `mg` places graphics (x, y, scale, speed 1.25 to 1.4 for snappy, cut); graphics are silent unless `"sounds": n`.
- `sfx` is the ONLY other added sound: events the audience must register.
- `outro`: the rendered outro template (`graphics/out/OUTRO.webm`, silent: the score carries it) or any brand mp4, or null.
