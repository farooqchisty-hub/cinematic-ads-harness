"""Setup check, brief, page capture and the claims ledger."""
import json, os, re, shutil, subprocess, sys, urllib.request
from .util import PKG, env, rj, wj, sh, UA
from . import providers as P

HF = "hyperframes@0.8.78"


def doctor(run=None, storage_test=False):
    """Checks every tool and key with free calls. Prints a table and returns True when ready."""
    rows = []
    ok = lambda name, good, note="": rows.append((name, "ok" if good else "MISSING", note))
    ff = shutil.which("ffmpeg")
    ok("ffmpeg", bool(ff), ff or "install ffmpeg (brew install ffmpeg)")
    if ff:
        dec = sh(["ffmpeg", "-hide_banner", "-decoders"], check=False)
        ok("ffmpeg libvpx-vp9 decoder", "libvpx-vp9" in dec, "needed to read transparent WebM graphics")
    ok("ffprobe", bool(shutil.which("ffprobe")))
    try:
        import PIL  # noqa
        ok("python Pillow", True)
    except ImportError:
        ok("python Pillow", False, "pip install -r requirements.txt")
    node = shutil.which("node")
    nv = sh(["node", "--version"], check=False).strip() if node else ""
    ok("node 20+", bool(node) and int((nv.lstrip("v").split(".") or ["0"])[0] or 0) >= 20, nv or "install Node 20+")
    ok("npm packages", os.path.exists(os.path.join(PKG, "node_modules", "@resvg")), "run: npm install (in the package folder)")
    ok("npx (HyperFrames)", bool(shutil.which("npx")), f"graphics render with npx {HF}; it needs Chrome or downloads one")
    tr = shutil.which("treg")
    ok("treg CLI", bool(tr), "install treg and sign in (treg login); see README")
    if tr:
        bal = subprocess.run(["treg", "balance"], capture_output=True, text=True)
        m = re.search(r"Balance\s+\$([\d.,]+)", bal.stdout)
        ok("treg signed in", bal.returncode == 0 and bool(m), f"balance ${m.group(1)}" if m else (bal.stderr or bal.stdout)[-160:].strip())
    rk = env("REPLICATE_API_TOKEN") or env("REPLICATE_KEY")
    good = False
    if rk:
        try:
            urllib.request.urlopen(urllib.request.Request("https://api.replicate.com/v1/account", headers={"Authorization": f"Bearer {rk}"}), timeout=30)
            good = True
        except Exception:
            pass
    ok("Replicate token", good, "REPLICATE_API_TOKEN (music, stems, transcription, voice check)")
    ok("text key for the brief", bool(env("OPENROUTER_API_KEY") or env("OPENAI_API_KEY")), "OPENROUTER_API_KEY or OPENAI_API_KEY")
    ok("image key", bool(env("OPENROUTER_API_KEY") or env("OPENAI_API_KEY") or rk), "OpenRouter, OpenAI or Replicate (gpt-image-2)")
    ok("public storage", P.storage_ready(), "STORAGE_PUBLIC_BASE plus S3_* keys or STORAGE_UPLOAD_CMD")
    if env("S3_BUCKET"):
        try:
            import boto3  # noqa
            ok("python boto3", True)
        except ImportError:
            ok("python boto3", False, "pip install boto3 (S3 or R2 storage)")
    if storage_test and P.storage_ready():
        from PIL import Image
        t = os.path.join(run.dir if run else os.getcwd(), "_doctor.png")
        Image.new("RGB", (8, 8), (0, 128, 96)).save(t)
        try:
            u = P.publish(t, "_doctor/check.png")
            ok("storage upload + public read", True, u)
        except Exception as e:
            ok("storage upload + public read", False, str(e)[:160])
        os.remove(t)
    w = max(len(r[0]) for r in rows)
    for n, s, note in rows:
        print(f"  {n.ljust(w)}  {s.ljust(7)}  {note}")
    ready = all(s == "ok" for _, s, _ in rows)
    print("\nready" if ready else "\nnot ready: fix the MISSING rows (nothing has been spent)")
    return ready


def brief(run, url, extra=()):
    """Reads the landing page and builds brief.json + brandkit/ (cents of LLM spend)."""
    cmd = ["node", os.path.join(PKG, "vendor", "brief", "run-brief.mjs"), "--url", url, "--out", run.p("brief")] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    sys.stdout.write(r.stdout)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    out = json.loads(r.stdout.strip().splitlines()[-1])
    from .util import spend
    spend(run, "brief", "brief + brand kit", out.get("usd", 0), provider="llm")
    run.set(url=url, brand=out.get("brand"), stage="brief")
    return out


def capture(run, url, n=16):
    """Real screenshots and assets from the product page, for motion graphics and references (free)."""
    out = run.p("capture")
    if os.path.exists(out):
        shutil.rmtree(out)
    r = subprocess.run(["npx", "--yes", HF, "capture", url, "-o", out, "--skip-vision", "--max-screenshots", str(n), "--json"],
                       capture_output=True, text=True, cwd=run.dir)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-1200:])
    shots = sorted(os.listdir(os.path.join(out, "screenshots"))) if os.path.exists(os.path.join(out, "screenshots")) else []
    assets = sorted(f for f in os.listdir(os.path.join(out, "assets")) if not f.startswith(".")) if os.path.exists(os.path.join(out, "assets")) else []
    wj(run.p("capture_index.json"), {"url": url, "screenshots": shots, "assets": assets})
    print(f"  {len(shots)} screenshots, {len(assets)} assets in {out}")
    return out


# ---- claims ---------------------------------------------------------------------------------------
def claims_init(run):
    """Candidate claims from the brief (each quoted verbatim from the page) become claims.json, all pending.
    The user confirms, edits or adds; only approved claims may appear in the script or graphics."""
    b = rj(run.p("brief", "brief.json"))
    if not b:
        raise RuntimeError("run `cine brief` first")
    cur = {c["id"]: c for c in (rj(run.p("claims.json"), {}) or {}).get("claims", [])}
    rows = []
    for c in b.get("claims", []):
        if c.get("status") != "verified":
            continue
        rows.append(cur.get(c["id"]) or {"id": c["id"], "figure": c.get("figure"), "claim": c.get("claim"), "quote": c.get("quote"),
                                         "source": b.get("source_url"), "status": "pending"})
    data = rj(run.p("claims.json"), {}) or {}
    data.update({"brand": b.get("brand"), "claims": rows + [c for c in cur.values() if c["id"].startswith("u")],
                 "never_say": data.get("never_say", b.get("never_say", [])), "competitors": b.get("competitors", [])})
    wj(run.p("claims.json"), data)
    return data


def claims_show(run):
    d = rj(run.p("claims.json"))
    for c in d["claims"]:
        print(f"  [{c['status']:8}] {c['id']:4} {c['figure']}: {c['claim']}  (\"{(c.get('quote') or '')[:70]}\")")
    print(f"  never say: {', '.join(d.get('never_say', [])) or 'none'}   competitors kept out: {', '.join(d.get('competitors', [])) or 'none'}")


def claims_set(run, approve=(), reject=(), add=None, source=None):
    d = rj(run.p("claims.json"))
    for c in d["claims"]:
        if c["id"] in approve or "all" in approve:
            c["status"] = "approved"
        if c["id"] in reject:
            c["status"] = "rejected"
    if add:
        n = 1 + sum(1 for c in d["claims"] if c["id"].startswith("u"))
        fig, _, txt = add.partition(":")
        d["claims"].append({"id": f"u{n}", "figure": fig.strip(), "claim": txt.strip() or fig.strip(), "quote": None,
                            "source": source or "provided by the user", "status": "approved"})
    wj(run.p("claims.json"), d)
    return d


def approved_claims(run):
    return [c for c in (rj(run.p("claims.json"), {}) or {}).get("claims", []) if c.get("status") == "approved"]
