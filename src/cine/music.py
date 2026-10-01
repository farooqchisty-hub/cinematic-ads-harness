"""An original score composed in sections and stitched to picture cuts.

Text-to-music models ignore timecodes inside one long prompt, so the agent writes one section per story
movement (music.json) and places each at a cut: measure the onset of a slam with `cine music --measure`
and set "at" so the hit lands on the picture.
"""
import array, math, os, subprocess
from .util import rj, sh, spend
from . import providers as P

USD_PER_S = 0.0083   # ElevenLabs Music on Replicate


def compose(run, spec_file="music.json"):
    S = rj(run.p(spec_file))
    for sec in S["sections"]:
        out = run.p("music", f"mus_{sec['name']}.mp3")
        if not os.path.exists(out):
            u = P.replicate(run, "score", f"music {sec['name']}", model="elevenlabs/music", usd=sec["ms"] / 1000 * USD_PER_S,
                            inp={"prompt": S["common"] + " " + sec["prompt"], "music_length_ms": sec["ms"], "force_instrumental": True,
                                 "output_format": "mp3_high_quality"})
            from .util import download
            download(u if isinstance(u, str) else u[0], out)
        print(f"  {os.path.basename(out)}  per-second loudness: {' '.join(str(v) for v in per_second(out))}")
    if S.get("stitch"):
        stitch(run, S)


def per_second(path):
    x = array.array("h", subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout)
    return [int(20 * math.log10(max(1, (sum(v * v for v in x[i * 8000:(i + 1) * 8000]) / 8000) ** .5) / 32768) + 60) for i in range(len(x) // 8000)]


def onset(path, window_s=3.0, jump_db=15):
    """The first point where loudness jumps by jump_db within 0.1 s: where a slam lands."""
    x = array.array("h", subprocess.run(["ffmpeg", "-v", "error", "-t", str(window_s), "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout)
    w = 400
    lv = [20 * math.log10(max(1, (sum(v * v for v in x[i:i + w]) / w) ** .5) / 32768) for i in range(0, len(x) - w, w)]
    for i in range(1, len(lv)):
        if lv[i] - lv[i - 1] >= jump_db or (lv[i] > -20 and lv[i - 1] < -35):
            return round(i * w / 8000, 3)
    return 0.0


def stitch(run, S):
    ins, fc, labs = [], [], []
    for k, st in enumerate(S["stitch"]):
        ins += ["-i", run.p("music", f"mus_{st['name']}.mp3")]
        ms = int(float(st["at"]) * 1000)
        f = f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo"
        if st.get("trim"):
            f += f",atrim=0:{st['trim']}"
        if st.get("fade_in"):
            f += f",afade=t=in:d={st['fade_in']}"
        if st.get("fade_out"):
            f += f",afade=t=out:st={st['fade_out'][0]}:d={st['fade_out'][1]}"
        fc.append(f + f",adelay={ms}|{ms}[s{k}]")
        labs.append(f"[s{k}]")
    fc.append("".join(labs) + f"amix=inputs={len(labs)}:normalize=0:duration=longest,atrim=0:{S['total']}[m]")
    out = run.p(S.get("out", "music.wav"))
    sh(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "[m]", out])
    print(f"  wrote {out}")
    return out
