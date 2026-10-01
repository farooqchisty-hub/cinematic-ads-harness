"""Paid providers and storage.

  treg       Seedance 2.5 face video (reAPI route), through the treg CLI the user signs in to.
  Replicate  ElevenLabs Music, demucs stems, two Whisper transcribers, pyannote speaker check.
  Images     through vendor/brief/run-render.mjs (OpenRouter, OpenAI or Replicate, whichever key is set).
  Storage    Seedance only reads reference images and voice clips from PUBLIC https links that return the
             raw bytes with a media content-type, so every reference is uploaded to the user's bucket first.
"""
import json, mimetypes, os, subprocess, time, urllib.error, urllib.request
from .util import env, sh, spend, PKG, UA

# ---- treg / Seedance ------------------------------------------------------------------------------
SEEDANCE_ROUTE = env("CINE_VIDEO_ROUTE", "reapi.video-gen.seedance-2-5")
SEEDANCE_MODEL = env("CINE_VIDEO_MODEL", "doubao-seedance-2.5-face")
SEEDANCE_USD_S = float(env("CINE_VIDEO_USD_PER_S", "0.2668"))   # 720p list rate; the ledger records it per take


def treg_call(args, tries=6):
    last = ""
    for _ in range(tries):
        r = subprocess.run(["treg", "call"] + args, capture_output=True, text=True)
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except Exception:
                last = r.stdout[-300:]
        else:
            last = (r.stderr or r.stdout)[-300:]
        time.sleep(8)
    raise RuntimeError(f"treg call failed: {last}")


def seedance_submit(body):
    body = {"model": SEEDANCE_MODEL, "resolution": "720p", "generate_audio": True, **body}
    j = treg_call([SEEDANCE_ROUTE, "--data", json.dumps(body)])
    if not j.get("id"):
        raise RuntimeError(f"no task id: {str(j)[:300]}")
    return j["id"]


def seedance_poll(task_id, timeout_s=3600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(15)
        try:
            st = treg_call(["reapi.tasks.get", "--query", f"id={task_id}"], tries=2)
        except RuntimeError:
            continue   # transient poll errors are normal; keep polling
        if st.get("status") in ("completed", "succeeded"):
            return st
        if st.get("status") in ("failed", "cancelled"):
            raise RuntimeError(f"task {task_id} {st.get('status')}: {str(st.get('error'))[:300]}")
    raise RuntimeError(f"task {task_id} timed out")


# ---- Replicate ------------------------------------------------------------------------------------
VERSIONS = {   # community models pinned to the versions the harness was built on
    "demucs": "5a7041cc9b82e5a558fea6b3d7b12dea89625e89da33f0447bd727c2d0ab9e77",          # ryan5453/demucs
    "whisper_words": "3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",   # vaibhavs10/incredibly-fast-whisper
    "whisper": "8099696689d249cf8b122d833c36ac3f75505c666a395ca40ef26f68e7d3d16e",         # openai/whisper (large-v3)
    "diarize": "6e29843b8c1b751ec384ad96d3566af2392046465152fef3cc22ad701090b64c",         # collectiveai-team/speaker-diarization-3
}
RATES = {"demucs": 0.02, "whisper_words": 0.01, "whisper": 0.03, "diarize": 0.02}


def _rep_key():
    k = env("REPLICATE_API_TOKEN") or env("REPLICATE_KEY")
    if not k:
        raise RuntimeError("REPLICATE_API_TOKEN is not set")
    return k


def _rep_req(url, data=None, method=None):
    h = {"Authorization": f"Bearer {_rep_key()}", "Content-Type": "application/json", "User-Agent": UA}
    for k in range(10):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=120))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and k < 9:
                time.sleep(int(e.headers.get("Retry-After") or 0) or 8 * (k + 1))
                continue
            raise RuntimeError(f"replicate {e.code}: {e.read().decode(errors='ignore')[:300]}")


def replicate(run, stage, what, *, version=None, model=None, inp=None, usd=0.0, final=False, timeout_s=900):
    """One prediction, waited for. version= for pinned community models, model= for official ones."""
    url = f"https://api.replicate.com/v1/models/{model}/predictions" if model else "https://api.replicate.com/v1/predictions"
    body = {"input": inp} if model else {"version": version, "input": inp}
    j = _rep_req(url, json.dumps(body).encode())
    t0 = time.time()
    while j.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > timeout_s:
            _rep_req(j["urls"]["cancel"], b"", "POST")
            raise RuntimeError(f"{what}: timed out and cancelled")
        time.sleep(5)
        try:
            j = _rep_req(j["urls"]["get"])
        except RuntimeError:
            continue
    if j["status"] != "succeeded":
        raise RuntimeError(f"{what}: {j['status']} {str(j.get('error'))[:300]}")
    spend(run, stage, what, usd, final=final, provider="replicate", ref=model or version[:12])
    return j["output"]


def replicate_upload(path):
    """Replicate's file store: a URL other Replicate predictions can read (not public)."""
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    out = sh(["curl", "-s", "-X", "POST", "-H", f"Authorization: Bearer {_rep_key()}", "-F", f"content=@{path};type={mime}",
              "https://api.replicate.com/v1/files"])
    return json.loads(out)["urls"]["get"]


def fetch_replicate(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Authorization": f"Bearer {_rep_key()}"})
    open(path, "wb").write(urllib.request.urlopen(req, timeout=600).read())
    return path


# ---- images ---------------------------------------------------------------------------------------
IMAGE_USD = {"low": 0.02, "medium": 0.05, "high": 0.19}


def render_image(run, stage, prompt, refs, out, aspect="9:16"):
    """Renders through the vendored static-ads provider chain; refs are local files or https links."""
    job = out + ".job.json"
    json.dump({"prompt": prompt, "aspect": aspect, "refs": refs, "out": out}, open(job, "w"))
    r = subprocess.run(["node", os.path.join(PKG, "vendor", "brief", "run-render.mjs"), job], capture_output=True, text=True,
                       env={**os.environ, "ADS_IMAGE_QUALITY": env("CINE_IMAGE_QUALITY", "high")}, cwd=os.getcwd())
    if r.returncode:
        raise RuntimeError(f"render failed for {os.path.basename(out)}: {(r.stderr or r.stdout)[-400:]}")
    usd = json.loads(r.stdout.strip().splitlines()[-1]).get("usd") or IMAGE_USD.get(env("CINE_IMAGE_QUALITY", "high"), 0.19)
    spend(run, stage, f"image {os.path.basename(out)}", usd, provider="image")
    os.remove(job)
    return out


# ---- public storage -------------------------------------------------------------------------------
def storage_ready():
    return bool(env("STORAGE_PUBLIC_BASE")) and bool(env("S3_BUCKET") or env("STORAGE_UPLOAD_CMD"))


def publish(path, key):
    """Upload one file to the user's public storage and return its public URL, verified to serve raw bytes.
    Either S3-compatible (AWS S3 or Cloudflare R2 via S3_* keys) or any shell command in STORAGE_UPLOAD_CMD
    with {file} and {key} placeholders (for example a wrangler, gsutil or rclone command)."""
    base = env("STORAGE_PUBLIC_BASE").rstrip("/")
    if not base:
        raise RuntimeError("STORAGE_PUBLIC_BASE is not set (the public URL prefix of your bucket)")
    prefix = env("STORAGE_PREFIX", "cine").strip("/")
    full = f"{prefix}/{key}" if prefix else key
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if env("S3_BUCKET"):
        import boto3
        s3 = boto3.client("s3", endpoint_url=env("S3_ENDPOINT") or None, aws_access_key_id=env("S3_ACCESS_KEY_ID"),
                          aws_secret_access_key=env("S3_SECRET_ACCESS_KEY"), region_name=env("S3_REGION", "auto"))
        extra = {"ContentType": mime}
        if env("S3_PUBLIC_ACL") == "1":
            extra["ACL"] = "public-read"
        s3.upload_file(path, env("S3_BUCKET"), full, ExtraArgs=extra)
    elif env("STORAGE_UPLOAD_CMD"):
        sh(env("STORAGE_UPLOAD_CMD").replace("{file}", f'"{path}"').replace("{key}", full).replace("{mime}", mime))
    else:
        raise RuntimeError("no storage configured: set S3_* keys or STORAGE_UPLOAD_CMD")
    url = f"{base}/{full}"
    for k in range(6):   # the video provider rejects HTML pages and slow-to-appear objects; check before using
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA}), timeout=30)
            ct = r.headers.get("content-type", "")
            if r.status == 200 and not ct.startswith("text/html"):
                return url
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(f"uploaded but not publicly readable as media: {url}")
