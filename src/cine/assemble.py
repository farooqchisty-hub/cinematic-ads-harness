#!/usr/bin/env python3
"""The assembler: takes + edit.json in, finished vertical ad out (24 fps, 1080x1920, about -14 LUFS).

  cine assemble runs/<slug>/edit.json        (or: python3 src/cine/assemble.py <edit.json> [--stems] [--rebuild])

edit.json (full schema and a worked example in references/schemas.md):
  parts:    [{src, in, out, audio_src?, audio_in?}]   takes laid end to end = the main timeline (full frame, top half of splits)
  second:   "BR1" or null                             the second world's continuous take (bottom half of split screens)
  segments: [{t0, t1, layout: full|split, rt0?, slow?, top_y?, bottom: [{t0, t1, src_in, y?}]}]
  voc_moves:[[src_t0, src_t1, dst_t0]]                re-space OFF-camera lines only (never move on-camera lines)
  br_lines: [[src_t0, src_t1, dst_t0]]                the second world's spoken lines, placed one by one
  captions: [[t0, t1, text]]                          from the placed script lines, brand spellings fixed
  cap_y:    [[t0, t1, y]]                             caption height overrides (keep captions off faces and graphics)
  mg:       [{id, t, x, y, scale, speed, cut?, sounds?}]   graphics from graphics/out/ (silent unless "sounds")
  sfx:      [[t, kind, vol?]]                         the ONLY added sounds: events the audience must register
  music, music_gain, music_env: [[t0, t1, gain]]      the composed score and its dips
  warp:     {t0, t1, k}                               slow one stretch of the main timeline (picture, ambience and voice together)
  outro:    path or null; out: output name; work: scratch dir name
"""
import json, os, re, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(sys.argv[1]))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cine import util as U, providers as PV
from cine.util import Run
RUN = Run(HERE)
SKIP_SFX = ("until", "typing", "bed", "shimmer", "glint", "roll")
SFX_MAP = [("chime", "chime"), ("cash", "chime"), ("stamp", "stamp"), ("alert", "alert"), ("riser", "riser"), ("thump", "thump"), ("thud", "thump"),
           ("hit", "hit"), ("click", "tick"), ("tick", "tick"), ("blip", "tick"), ("pop", "pop"), ("swipe", "swish"), ("swish", "swish"), ("whoosh", "whoosh")]

E = json.load(open(sys.argv[1])); FPS = 24
E.setdefault("race", E.get("parts")); E.setdefault("br", E.get("second"))
S, O = f"{HERE}/seq", f"{HERE}/{E.get('work', 'build')}"; os.makedirs(f"{O}/seg", exist_ok=True); os.makedirs(f"{O}/png", exist_ok=True)
KEY = U.env("REPLICATE_API_TOKEN") or U.env("REPLICATE_KEY")
BAND_H = 640   # a 720x640 band of the 720x1280 take becomes one 1080x960 half
DIV = E.get("divider", "0x73C4A7")   # the split-screen divider colour; set it from the brand kit

def run(cmd): return U.sh(cmd)

def demucs(wav, stem):
    v, nv = f"{O}/{stem}_voc.wav", f"{O}/{stem}_amb.wav"
    if os.path.exists(v) and os.path.exists(nv): return v, nv
    out = PV.replicate(RUN, "assemble", f"stems {stem}", version=PV.VERSIONS["demucs"], usd=PV.RATES["demucs"], final=True,
                       inp={"audio": PV.replicate_upload(wav), "stem": "vocals", "output_format": "wav"})
    PV.fetch_replicate(out["vocals"], v); PV.fetch_replicate(out["no_vocals"], nv); return v, nv

# ---- 1. race timeline and Brenda take ----------------------------------------------------------------
race = f"{O}/race.mov"
parts = E["race"]; RACE_S = round(sum(p["out"] - p["in"] for p in parts), 3)
if not os.path.exists(race) or "--rebuild" in sys.argv:
    ins, fc = [], []
    for k, p in enumerate(parts):
        ins += ["-i", f"{S}/{p['src']}.mp4", "-i", f"{S}/{p.get('audio_src', p['src'])}.mp4"]
        ai0 = p.get("audio_in", p["in"]); d = p["out"] - p["in"]
        fc.append(f"[{2*k}:v]trim={p['in']}:{p['out']},setpts=PTS-STARTPTS,fps={FPS},scale=720:1280,setsar=1,format=yuv420p[v{k}];"
                  f"[{2*k+1}:a]atrim={ai0}:{ai0 + d},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{k}]")
    fc.append("".join(f"[v{k}][a{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]")
    run(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "pcm_s16le", race])
brv = f"{S}/{E['br']}.mp4" if E.get("br") else None
for name, src in (("race", race), ("br", brv)):
    w = f"{O}/{name}.wav"
    if src and (not os.path.exists(w) or "--rebuild" in sys.argv): run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "2", "-ar", "44100", w])
race_voc, race_amb = demucs(f"{O}/race.wav", "race")
if brv:
    br_voc, br_amb = demucs(f"{O}/br.wav", "br")
else:   # one-world story: a silent stand-in keeps the mix graph the same
    br_voc = br_amb = f"{O}/silence.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", br_voc])
if "--stems" in sys.argv: sys.exit(0)
WP = E.get("warp"); DW = (WP["t1"] - WP["t0"]) * (1 / WP["k"] - 1) if WP else 0.0
def fmap(r):
    """Race time to final time: the warp region plays slowed, everything after it moves later by DW."""
    if not WP or r <= WP["t0"]: return r
    if r >= WP["t1"]: return r + DW
    return WP["t0"] + (r - WP["t0"]) / WP["k"]
race_voc_w, race_amb_w = race_voc, race_amb
if WP:
    a, b, k = WP["t0"], WP["t1"], WP["k"]
    race_voc_w, race_amb_w = f"{O}/race_voc_w.wav", f"{O}/race_amb_w.wav"
    # the slowed stretch keeps its crowd and spray (time-stretched, same pitch) but no voice: every line there is a placed clip
    for src, dst, mid in ((race_amb, race_amb_w, f"atempo={k}"), (race_voc, race_voc_w, f"atempo={k},volume=0")):
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex",
             f"[0:a]asplit=3[x][y][z];[x]atrim=0:{a},asetpts=PTS-STARTPTS[p0];[y]atrim={a}:{b},asetpts=PTS-STARTPTS,{mid}[p1];[z]atrim={b},asetpts=PTS-STARTPTS[p2];[p0][p1][p2]concat=n=3:v=0:a=1[o]",
             "-map", "[o]", dst])

# ---- 2. picture: full-frame and split segments ---------------------------------------------------------
segs = []
for n, g in enumerate(E["segments"]):
    d = round(g["t1"] - g["t0"], 4); out = f"{O}/seg/{n:02d}.mp4"
    NF = round(g["t1"] * FPS) - round(g["t0"] * FPS)   # exact frames on the 24 fps grid, so picture never drifts from sound
    HOLD = f",tpad=stop_mode=clone:stop_duration=0.5,trim=end_frame={NF}"
    if g["layout"] == "full":
        rt0, sl = g.get("rt0", g["t0"]), g.get("slow", 1.0)
        slow = f"setpts=PTS/{sl},minterpolate=fps={FPS}:mi_mode={g.get('mi', 'mci')}:mc_mode=aobmc:vsbmc=1," if sl < 1 else ""
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{rt0:.4f}", "-t", f"{d * sl + 0.1:.4f}", "-i", race, "-an",
             "-vf", f"{slow}scale=1080:1920:flags=lanczos,fps={FPS},setsar=1,format=yuv420p{HOLD}", "-frames:v", str(NF), "-c:v", "libx264", "-crf", "14", "-preset", "medium", out])
    else:
        ty = g.get("top_y", 320)
        ins = ["-ss", f"{g.get('rt0', g['t0']):.4f}", "-t", f"{d + 0.1:.4f}", "-i", race]
        fc = [f"[0:v]crop=720:{BAND_H}:0:{ty},scale=1080:960:flags=lanczos,setsar=1,fps={FPS}[top]"]
        for k, b in enumerate(g["bottom"]):
            ins += ["-ss", f"{b['src_in']:.4f}", "-t", f"{b['t1'] - b['t0']:.4f}", "-i", brv]
            fc.append(f"[{k+1}:v]crop=720:{BAND_H}:0:{b.get('y', 320)},scale=1080:960:flags=lanczos,setsar=1,fps={FPS},setpts=PTS-STARTPTS[b{k}]")
        nb = len(g["bottom"])
        fc.append("".join(f"[b{k}]" for k in range(nb)) + f"concat=n={nb}:v=1:a=0[bot]")
        wipe = 0.22 if g.get("open", True) else 0.001
        fc.append(f"[top]pad=1080:1920:0:0:black[t1];"
                  f"[t1][bot]overlay=0:'if(lt(t,{wipe}),1920-958*(t/{wipe}),962)':eval=frame:shortest=0[t2];"
                  f"color=c={DIV}:s=1080x6:r={FPS}:d={d:.4f}[dv];[t2][dv]overlay='if(lt(t,{wipe}),-1080+1080*(t/{wipe}),0)':957:eval=frame,format=yuv420p{HOLD}[v]")
        run(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "[v]", "-an", "-frames:v", str(NF), "-c:v", "libx264", "-crf", "14", "-preset", "medium", out])
    segs.append(out)
lst = f"{O}/seg/list.txt"; open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
BODY = round(E["segments"][-1]["t1"], 4)
base = f"{O}/base.mp4"
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-r", str(FPS), base])

# ---- 3. dialogue stem and captions --------------------------------------------------------------------
split_win = [(g["t0"], g["t1"]) for g in E["segments"] if g["layout"] == "split"]
br_win = [b for g in E["segments"] if g["layout"] == "split" for b in g["bottom"]]
def br_place(src, vol, tag):
    """The second world's sound follows its picture: each bottom window carries its own slice of that take."""
    fc, labs = [], []
    for k, b in enumerate(br_win):
        ms = int(b["t0"] * 1000); dd = b["t1"] - b["t0"]
        fc.append(f"[{src}]atrim={b['src_in']:.4f}:{b['src_in'] + dd:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.04,afade=t=out:st={max(0, dd - 0.06):.3f}:d=0.06,volume={vol},adelay={ms}|{ms}[{tag}{k}]")
        labs.append(f"[{tag}{k}]")
    if not labs: return [f"anullsrc=r=48000:cl=stereo,atrim=0:{BODY}[{tag}]"]
    fc.append("".join(labs) + f"amix=inputs={len(labs)}:normalize=0:duration=longest,apad=whole_dur={BODY}[{tag}]")
    return fc
def env(vals):
    """Piecewise gain for the race ambience: full level in full frame, ducked in the split screen, 0.15 s ramps."""
    e = "1"
    for a, b in split_win:
        r = 0.15; lo = vals
        e = f"if(between(t,{a-r:.3f},{b+r:.3f}),if(lt(t,{a:.3f}),1-(1-{lo})*(t-{a-r:.3f})/{r},if(gt(t,{b:.3f}),{lo}+(1-{lo})*(t-{b:.3f})/{r},{lo})),{e})"
    return e
dlg = f"{O}/dialogue.wav"
moves = E.get("voc_moves", []); lines = E.get("br_lines", [])
mute = "+".join(f"between(t,{fmap(a):.3f},{fmap(b):.3f})" for a, b, _ in moves) or "0"
fc = ([f"[2:a]asplit={len(moves)}" + "".join(f"[mv{k}]" for k in range(len(moves)))] if moves else []) + [f"[0:a]atrim=0:{BODY},volume='if({mute},0,1)':eval=frame[rv]"]
labs = ["[rv]"]
for k, (a, b, t) in enumerate(moves):
    ms = int(t * 1000)
    fc.append(f"[mv{k}]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={max(0, b - a - 0.05):.3f}:d=0.05,adelay={ms}|{ms}[m{k}]"); labs.append(f"[m{k}]")
if lines: fc.append(f"[1:a]asplit={len(lines)}" + "".join(f"[bl{k}]" for k in range(len(lines))))
for k, (a, b, t) in enumerate(lines):
    ms = int(t * 1000)
    fc.append(f"[bl{k}]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={max(0, b - a - 0.06):.3f}:d=0.06,volume={E.get('br_voice_gain', 1.2)},adelay={ms}|{ms}[b{k}]"); labs.append(f"[b{k}]")
fc.append("".join(labs) + f"amix=inputs={len(labs)}:normalize=0:duration=first,apad=whole_dur={BODY},atrim=0:{BODY}[d]")
run(["ffmpeg", "-y", "-v", "error", "-i", race_voc_w, "-i", br_voc, "-i", race_voc, "-filter_complex", ";".join(fc), "-map", "[d]", "-ar", "48000", "-ac", "2", dlg])

def in_split(t): return any(a <= t < b for a, b in split_win)
def cap_y(t):
    for a, b, y in E.get("cap_y", []):
        if a <= t < b: return y
    return 990 if in_split(t) else 1268
ov = []
for t0, t1, text in E["captions"]:
    words = text.split(); chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or re.search(r"[.?!,]$", w) and len(cur) >= 2: chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    n = sum(len(c) for c in chunks); t = t0
    for c in chunks:
        d = (t1 - t0) * len(c) / n
        k = len(ov); p = f"{O}/png/cap_{k}.png"; w, h = U.text_png(p, " ".join(c), 40 if in_split(t) else 46)
        ov.append((p, (1080 - w) // 2, cap_y(t), t, min(t + d + 0.12, BODY))); t += d
for i in range(len(ov) - 1):
    if ov[i][4] > ov[i + 1][3] - 0.02: ov[i] = ov[i][:4] + (ov[i + 1][3] - 0.02,)

# ---- 4. motion graphics ------------------------------------------------------------------------------
cues = {c["id"]: c for c in (U.rj(f"{HERE}/graphics/out/cues.json", {"cues": []}) or {"cues": []})["cues"]}
placed, events = [], []
for m in E["mg"]:
    sp = m.get("speed", 1.25); c = cues.get(m["id"], {})
    src_d = U.dur(f"{HERE}/graphics/out/{m['id']}.webm"); d = src_d / sp
    cut = min(m.get("cut", d), d)
    placed.append(dict(m, d=cut, speed=sp))
    cand = []
    for s in c.get("sfx", []):
        t = m["t"] + float(s["rel_s"]) / sp; name = s["cue"]
        if t > m["t"] + cut or any(x in name for x in SKIP_SFX): continue
        kind = next((v for k2, v in SFX_MAP if k2 in name.lower()), None)
        if kind: cand.append((t, kind))
    # a graphic's own cue sounds are opt-in ("sounds": n picks its n most meaningful); story sounds go in the explicit sfx list
    rank = {"alert": 0, "pop": 0, "stamp": 1, "chime": 1, "hit": 2, "whoosh": 3, "swish": 4, "thump": 4, "riser": 5, "tick": 6}
    keep = sorted(sorted(cand, key=lambda e: (rank.get(e[1], 9), e[0]))[:m.get("sounds", 0)])   # silent unless the storyboard gives this graphic a sound
    last = -9
    for t, kind in keep:
        if t - last >= 0.25: events.append((t, kind, None)); last = t
events += [(x[0], x[1], x[2] if len(x) > 2 else None) for x in E.get("sfx", [])]
events = [e for e in events if e[0] < BODY]
inputs = ["-i", base]
for c in placed: inputs += ["-c:v", "libvpx-vp9", "-i", f"{HERE}/graphics/out/{c['id']}.webm"]
for o in ov: inputs += ["-i", o[0]]
fc, vin = [], "[0:v]"
for k, c in enumerate(placed):
    sc = c.get("scale", 1.0)
    scale = f",scale={int(1080*sc)//2*2}:{int(1920*sc)//2*2}" if abs(sc - 1) > 1e-3 else ""
    fade = f",fade=t=out:st={max(0, c['d'] - 0.2):.3f}:d=0.2:alpha=1" if c.get("cut") else ""
    fc.append(f"[{k+1}:v]format=yuva420p,setpts=(PTS-STARTPTS)/{c['speed']},fps={FPS},trim=0:{c['d']:.3f}{fade},setpts=PTS-STARTPTS+{c['t']:.3f}/TB{scale}[m{k}]")
    o = f"[vm{k}]"; fc.append(f"{vin}[m{k}]overlay={c.get('x', 0)}:{c.get('y', 0)}:eof_action=pass:format=auto{o}"); vin = o
for k, (p, x, y, a, b) in enumerate(ov):
    i = 1 + len(placed) + k; o = f"[vc{k}]"; fc.append(f"{vin}[{i}:v]overlay={x}:{y}:enable='between(t,{a:.2f},{b:.2f})'{o}"); vin = o
body = f"{O}/body.mp4"
run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(fc), "-map", vin, "-an", "-t", f"{BODY:.4f}", "-r", str(FPS), "-c:v", "libx264", "-crf", "15", "-preset", "medium", body])

# ---- 5. sound: dialogue, ducked ambience, Brenda's room, MG sound design, music, outro -------------------
outro = E.get("outro"); OD = U.dur(outro) if outro else 0.0; TOT = BODY + OD
has_audio = bool(outro) and "audio" in run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", outro])
if not has_audio:   # no outro, or a silent one (the outro template): a silent stand-in keeps the mix graph the same
    outro = f"{O}/silent_outro.wav"; run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{max(OD, 0.1):.3f}", outro])
sfx_dir = U.SFX
VOL = {"hit": 0.5, "thump": 0.45, "whoosh": 0.4, "chime": 0.55, "stamp": 0.5, "alert": 0.5, "riser": 0.35, "pop": 0.5, "swish": 0.4, "tick": 0.3}
ai = ["-i", dlg, "-i", race_amb_w, "-i", br_amb, "-i", (E["music"] if os.path.isabs(E["music"]) else f"{HERE}/{E['music']}"), "-i", outro]
fc = [f"[0:a]asplit=2[dl][key0]",
      f"[1:a]atrim=0:{BODY},volume='{env(E.get('split_amb', 0.35))}':eval=frame,aresample=48000,aformat=channel_layouts=stereo[ra]"]
fc += br_place("2:a", E.get("br_room_gain", 0.35), "bra")
labs = ["[dl]", "[ra]", "[bra]"]
for k, (t, kind, v) in enumerate(events):
    ai += ["-i", f"{sfx_dir}/{kind}.mp3"]; ms = int(t * 1000)
    fc.append(f"[{5+k}:a]atrim=0:1.2,afade=t=out:st=0.9:d=0.3,volume={v or VOL.get(kind, 0.35)},adelay={ms}|{ms},aresample=48000,aformat=channel_layouts=stereo[s{k}]"); labs.append(f"[s{k}]")
fc.append("".join(labs) + f"amix=inputs={len(labs)}:normalize=0:duration=first,apad=whole_dur={TOT}[bodymix]")
om = int(BODY * 1000)
fc.append(f"[4:a]aresample=48000,aformat=channel_layouts=stereo,volume={E.get('outro_gain', 0.8)},adelay={om}|{om},apad=whole_dur={TOT}[oa]")
fc.append(f"[key0]apad=whole_dur={TOT},aformat=channel_layouts=stereo[key]")
mg = E.get("music_gain", 0.55)
menv = "1"
for a, b, g in E.get("music_env", []):
    menv = f"if(between(t,{a:.3f},{b:.3f}),{g},{menv})"
fc.append(f"[3:a]atrim=0:{TOT},aresample=48000,aformat=channel_layouts=stereo,volume={mg},volume='{menv}':eval=frame,afade=t=out:st={TOT-0.6:.3f}:d=0.6,apad=whole_dur={TOT}[mu]")
fc.append("[mu][key]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350:makeup=1[mud]")
fc.append(f"[bodymix][oa][mud]amix=inputs=3:normalize=0:duration=first,atrim=0:{TOT},loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
mix = f"{O}/mix.wav"
run(["ffmpeg", "-y", "-v", "error"] + ai + ["-filter_complex", ";".join(fc), "-map", "[a]", "-ar", "48000", mix])

final = f"{HERE}/{E.get('out', os.path.basename(HERE) + '_final')}.mp4"
vf = (f"[0:v]fps={FPS},setsar=1,format=yuv420p[v0];[1:v]scale=1080:1920,fps={FPS},setsar=1,format=yuv420p[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
      if OD else f"[0:v]fps={FPS},setsar=1,format=yuv420p[v]")
run(["ffmpeg", "-y", "-v", "error", "-i", body] + (["-c:v", "libvpx-vp9", "-i", E["outro"]] if OD and E["outro"].endswith(".webm") else ["-i", E["outro"]] if OD else ["-f", "lavfi", "-i", "color=black:s=16x16:d=0.1"]) + ["-i", mix, "-filter_complex", vf,
     "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", final])
json.dump({"placed": placed, "sfx": events, "captions": len(ov)}, open(f"{O}/placed.json", "w"), indent=1)
print(f"final {final} {U.dur(final):.2f}s; {len(placed)} graphics, {len(events)} sfx, {len(ov)} captions")
