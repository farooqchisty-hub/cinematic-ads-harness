"""Generation units through treg (Seedance 2.5 face), and the per-take QA tools.

A unit's prompt BODY is written by the agent in plan.json. This module builds the reference header
("@image1 is ... @audio1 is ONLY the voice of ..."), uploads every reference to public storage, submits
the takes, and downloads them to seq/<UNIT><n>.mp4. Task ids are written to seq/tasks.txt BEFORE polling,
so a crash never loses a paid take.
"""
import array, json, math, os, re, subprocess
from concurrent.futures import ThreadPoolExecutor
from .util import rj, wj, sh, dur, spend, download
from . import providers as P

SLUG = lambda s: re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def _ref_list(run, plan, u):
    """References in weight order: the unit's keyframes, each cast member's identity card, then boards."""
    A = lambda aid: next((a for coll in ("cast", "locations", "vehicles", "props") for a in plan.get(coll, []) if a["id"] == aid), None)
    out = []
    for k in u.get("keyframes", []):
        f = run.p("storyboard", f"kf_{k}.png")
        if os.path.exists(f):
            kf = next((x for x in plan.get("keyframes", []) if x["id"] == k), {})
            out.append((f, f"the look of {kf.get('action', k)}"))
    for cid in u.get("cast", []):
        f = run.p("storyboard", f"{cid}_card.png")
        if os.path.exists(f):
            out.append((f, f"{(A(cid) or {}).get('name', cid)}'s face"))
    for b in u.get("boards", []):
        f = run.p("storyboard", f"{b}.png")
        if os.path.exists(f):
            out.append((f, f"the {b.replace('_', ' ')} board (reproduce these logos exactly)"))
    for extra in u.get("refs", []):        # {"file": "...", "is": "..."} for anything else
        out.append((run.p(extra["file"]) if not os.path.isabs(extra["file"]) else extra["file"], extra["is"]))
    return out[:30]


def build_request(run, uid):
    plan = rj(run.p("plan.json"))
    u = next(x for x in plan["units"] if x["id"] == uid)
    cast = {c["id"]: c for c in plan.get("cast", [])}
    key = lambda f: f"{SLUG(run.state.get('brand', 'run'))}/{os.path.basename(run.dir)}/{os.path.basename(f)}"
    body = {"duration": int(round(float(u["gen_s"])))}
    header = []
    if u.get("first_frame"):
        # An insert: continue an existing take from its last good frame. reAPI cannot mix a first frame with
        # reference images (error 20003), and the size must be adaptive.
        ff = u["first_frame"]
        if "@" in ff:                       # "R11@23.0" = frame of take R11 at 23.0 s
            take, t = ff.split("@")
            ff = run.p("seq", f"{take}_at_{t}.jpg")
            sh(["ffmpeg", "-y", "-v", "error", "-ss", t, "-i", run.p("seq", f"{take}.mp4"), "-frames:v", "1", "-q:v", "2", ff])
        body["image_with_roles"] = [{"url": P.publish(ff if os.path.isabs(ff) else run.p(ff), key(ff)), "role": "first_frame"}]
        body["size"] = "adaptive"
        header.append("@image1 is the first frame of this shot; continue it exactly.")
    else:
        refs = _ref_list(run, plan, u)
        body["image_urls"] = [P.publish(f, key(f)) for f, _ in refs]
        body["size"] = plan.get("aspect", "9:16")
        if refs:
            header.append("References: " + "; ".join(f"@image{i + 1} is {d}" for i, (_, d) in enumerate(refs)) + ".")
    vrefs = list((u.get("voice_refs") or {}).items())
    if vrefs:
        body["audio_urls"] = [P.publish(run.p(f), key(f)) for _, f in vrefs]
        header.append(" ".join(f"@audio{i + 1} is ONLY the voice of {cast.get(cid, {}).get('name', cid)}: match timbre, pitch and accent exactly."
                               for i, (cid, _) in enumerate(vrefs)) + " The words in the voice samples are not part of this film and are never spoken.")
    body["prompt"] = "\n".join(header + [u["prompt"]])
    wj(run.p("units", f"request_{uid}.json"), body)
    return body


def takes(run, uid, n=2, start=1):
    body = build_request(run, uid)
    os.makedirs(run.p("seq"), exist_ok=True)
    def one(k):
        name = f"{uid}{k}"
        tid = P.seedance_submit(body)
        open(run.p("seq", "tasks.txt"), "a").write(f"{name} {tid}\n")
        st = P.seedance_poll(tid)
        download(st["output"]["video_urls"][0], run.p("seq", f"{name}.mp4"))
        spend(run, "produce", f"take {name}", body["duration"] * P.SEEDANCE_USD_S, provider="treg", ref=tid)
        return name
    with ThreadPoolExecutor(n) as ex:
        done = list(ex.map(one, range(start, start + n)))
    print("  takes:", ", ".join(done))
    return done


def resume(run, name):
    """Re-attach to a submitted take by its task id in seq/tasks.txt (after a crash or a closed terminal)."""
    tid = next(l.split()[1] for l in open(run.p("seq", "tasks.txt")) if l.split()[0] == name)
    st = P.seedance_poll(tid)
    download(st["output"]["video_urls"][0], run.p("seq", f"{name}.mp4"))
    return name


# ---- QA tools -------------------------------------------------------------------------------------
def stems(run, take):
    voc, amb = run.p("v", f"{take}_voc.wav"), run.p("v", f"{take}_amb.wav")
    if os.path.exists(voc):
        return voc, amb
    wav = run.p("v", f"{take}.wav")
    src = run.p("seq", f"{take}.mp4") if os.path.exists(run.p("seq", f"{take}.mp4")) else take
    sh(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "2", "-ar", "44100", wav])
    out = P.replicate(run, "qa", f"stems {take}", version=P.VERSIONS["demucs"], usd=P.RATES["demucs"],
                      inp={"audio": P.replicate_upload(wav), "stem": "vocals", "output_format": "wav"})
    P.fetch_replicate(out["vocals"], voc)
    P.fetch_replicate(out["no_vocals"], amb)
    return voc, amb


def loudness(path, a=None, b=None, step=0.1):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(a)] if a is not None else []) + (["-to", str(b)] if b is not None else []) + ["-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    x = array.array("h", subprocess.run(cmd, capture_output=True).stdout)
    w = int(16000 * step)
    return [((a or 0) + i / 16000, int(20 * math.log10(max(1, (sum(v * v for v in x[i:i + w]) / w) ** .5) / 32768) + 90)) for i in range(0, len(x) - w, w)]


def transcribe(run, path, words=True, label="qa"):
    mp3 = path.rsplit(".", 1)[0] + ".qa.mp3"
    sh(["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-b:a", "192k", mp3])
    u = P.replicate_upload(mp3)
    if words:
        return P.replicate(run, label, f"words {os.path.basename(path)}", version=P.VERSIONS["whisper_words"], usd=P.RATES["whisper_words"],
                           inp={"audio": u, "timestamp": "word", "language": "english", "batch_size": 24})
    return P.replicate(run, label, f"whisper {os.path.basename(path)}", version=P.VERSIONS["whisper"], usd=P.RATES["whisper"],
                       inp={"audio": u, "model": "large-v3", "language": "en"})


def qa(run, take):
    """Word transcript (both transcribers, on the full take and on its vocal stem) and a 1 fps contact sheet."""
    v = run.p("seq", f"{take}.mp4")
    voc, _ = stems(run, take)
    w = transcribe(run, v)
    wj(run.p("seq", f"{take}.words.json"), w)
    big = transcribe(run, voc, words=False)
    print(f"== {take} {dur(v):.2f}s  cuts: {' '.join(f'{c:.2f}' for c in cuts(v))}")
    print("  full mix: " + " ".join(c["text"].strip() for c in w.get("chunks", [])))
    print("  vocal stem (large-v3): " + str(big.get("transcription", "")).strip())
    n = int(dur(v))
    sh(["ffmpeg", "-y", "-v", "error", "-i", v, "-vf", f"fps=1,scale=240:-1,tile={min(n, 10)}x{(n + 9) // 10}", "-frames:v", "1", run.p("seq", f"{take}_sheet.jpg")])
    print(f"  sheet: {run.p('seq', take + '_sheet.jpg')}  (read it: faces, real-brand leaks, physics)")


def cuts(path, W=60, H=106):
    """Hard cuts by frame differencing (the ffmpeg scene filter misses some)."""
    N = W * H
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = [raw[i:i + N] for i in range(0, len(raw) - N + 1, N)]
    d = [sum(abs(a - b) for a, b in zip(fr[i], fr[i + 1])) / N for i in range(len(fr) - 1)]
    if not d:
        return []
    med = sorted(d)[len(d) // 2]
    fps = 24.0
    return [(i + 1) / fps for i in range(len(d)) if d[i] > max(14, 5 * med) and (i == 0 or d[i] > 2 * d[i - 1])]


def vref(run, take, a, b, name):
    """A clean voice-reference clip from a take's vocal stem (3 to 6 s works best)."""
    voc, _ = stems(run, take)
    out = run.p("vref", f"{name}.mp3")
    sh(["ffmpeg", "-y", "-v", "error", "-ss", str(a), "-to", str(b), "-i", voc, "-ac", "1", "-b:a", "192k", out])
    return out


def voices(run, clips, n=2):
    """Speaker check across takes. clips: [[label, take, t0, t1], ...]. Separates a woman from men reliably;
    two men are often merged, so report it as inconclusive in that case."""
    ins, fc, labs, marks, t = [], [], [], [], 0.0
    for k, (lab, take, a, b) in enumerate(clips):
        voc, _ = stems(run, take)
        ins += ["-i", voc]
        fc.append(f"[{k}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=mono,apad=pad_dur=0.8[c{k}]")
        labs.append(f"[c{k}]"); marks.append((lab, t, t + b - a)); t += b - a + 0.8
    test = run.p("v", "voicetest.wav")
    sh(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex", ";".join(fc) + ";" + "".join(labs) + f"concat=n={len(labs)}:v=0:a=1[o]", "-map", "[o]", test])
    o = P.replicate(run, "qa", "voice check", version=P.VERSIONS["diarize"], usd=P.RATES["diarize"], inp={"audio": P.replicate_upload(test), "num_speakers": n})
    sec = lambda x: sum(float(p) * 60 ** i for i, p in enumerate(reversed(str(x).split(":"))))
    res = {}
    for lab, a, b in marks:
        best = {}
        for s in o.get("segments", []):
            ov = max(0, min(b, sec(s["stop"])) - max(a, sec(s["start"])))
            if ov > 0:
                best[s["speaker"]] = round(best.get(s["speaker"], 0) + ov, 2)
        res[lab] = best
        print(f"  {lab:24s} {best}")
    return res
