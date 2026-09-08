"""QRCodeDirect — FastAPI backend v2 (customer accounts + storefront, 8 Sep 2026).

Public:
  GET  /r/{slug}            redirect (302) with scan logging; gated codes show capture
  POST /r/{slug}/capture    {email} -> store lead (MailWizz hook TBD), then redirect
  GET  /qr/{slug}.png|svg   styled QR render from the link's stored style

Customer API (session cookie `qrd_auth`; register → login → use):
  POST   /api/auth/register   {name,email,password}
  POST   /api/auth/login      {email,password} -> cookie
  POST   /api/auth/logout
  GET    /api/auth/me
  POST   /api/v1/links              create for the logged-in owner
  GET    /api/v1/links              list own (with scan counts)
  GET    /api/v1/links/{slug}       own detail
  PATCH  /api/v1/links/{slug}       update own
  DELETE /api/v1/links/{slug}
  GET    /api/v1/links/{slug}/stats?days=30
  POST   /api/v1/preview            style preview PNG (auth or admin key)

X-API-Key (server admin key) can impersonate admin: sees ALL links and may act on any slug.
The public /qr/{slug}.* endpoints stay open so codes work without login.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
from pathlib import Path

from fastapi import FastAPI, Request, Response, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from . import qr as qrlib
from . import geo as geolib

CONFIG_DIR = Path("/opt/qrcodedirect/config")
API_KEY_FILE = CONFIG_DIR / "api_key"

BASE_URL = os.environ.get("QR_BASE_URL", "https://qrcodedirect.com")
FRONTEND_DIST = Path(os.environ.get("QR_FRONTEND_DIST", "/opt/qrcodedirect/frontend/build"))

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}[a-z0-9]$|^[a-z0-9]{1,32}$")
SESSION_DAYS = 30


def load_api_key() -> str:
    CONFIG_DIR.mkdir(exist_ok=True)
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    key = "qrd_" + secrets.token_urlsafe(24)
    API_KEY_FILE.write_text(key)
    os.chmod(API_KEY_FILE, 0o600)
    return key


API_KEY = load_api_key()
db.init_db()
app = FastAPI(docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000)
    return digest.hex(), salt


def make_session(user_id: int) -> str:
    exp = int(__import__("time").time()) + SESSION_DAYS * 86400
    msg = f"qrd:{user_id}:{exp}".encode()
    return f"{hmac.new(_secret(), msg, hashlib.sha256).hexdigest()}.{user_id}.{exp}"


def _secret() -> bytes:
    f = CONFIG_DIR / "session_secret"
    if not f.exists():
        f.write_bytes(secrets.token_bytes(32))
        os.chmod(f, 0o600)
    return f.read_bytes()


def valid_session(token: str) -> int | None:
    try:
        digest, user_id, exp = token.split(".")
        if int(exp) < __import__("time").time():
            return None
        msg = f"qrd:{user_id}:{exp}".encode()
        if hmac.compare_digest(digest, hmac.new(_secret(), msg, hashlib.sha256).hexdigest()):
            return int(user_id)
    except Exception:
        pass
    return None


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def current_user(request: Request) -> int | None:
    return valid_session(request.cookies.get("qrd_auth", ""))


def require_user(request: Request) -> int:
    uid = current_user(request)
    if uid is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return uid


def _claim_scope(request: Request, link: dict) -> int | None:
    """Return the acting user id for admin checks. Admin key → None = all-links admin."""
    key = request.headers.get("x-api-key")
    if key and hmac.compare_digest(key, API_KEY):
        return None
    return require_user(request)


def _owns(link: dict, acting: int | None, request: Request) -> bool:
    if acting is None:
        return True  # admin key
    return link.get("owner_id") == acting


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


# ── lightweight brute-force limiter for auth endpoints ─────
_AUTH_LIMIT = {}
_AUTH_LOCK = threading.Lock()
AUTH_MAX_PER_MIN = 20


def _auth_allowed(ip: str) -> bool:
    import time
    now = time.time()
    with _AUTH_LOCK:
        q = [t for t in _AUTH_LIMIT.get(ip, []) if now - t < 60]
        if len(q) >= AUTH_MAX_PER_MIN:
            _AUTH_LIMIT[ip] = q
            return False
        q.append(now)
        _AUTH_LIMIT[ip] = q
        return True


def make_slug() -> str:
    alphabet = "abcdefghijkmnpqrstuvwxyz23456789"
    for _ in range(30):
        cand = "".join(secrets.choice(alphabet) for _ in range(7))
        if not db.slug_taken(cand):
            return cand
    raise HTTPException(status_code=500, detail="Could not allocate a slug")


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="dest_url is required")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="dest_url too long")
    return url


# ── auth ───────────────────────────────────────────────────
@app.post("/api/auth/register")
async def register(request: Request):
    if not _auth_allowed(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many attempts — try again in a minute")
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    name = str(body.get("name") or "").strip()[:80]
    password = str(body.get("password") or "")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    pw_hash, salt = hash_password(password)
    uid = db.create_user(email, name, pw_hash, salt)
    resp = JSONResponse({"ok": True, "user": db.get_user_by_id(uid)})
    _set_session(resp, uid)
    return resp


@app.post("/api/auth/login")
async def login(request: Request):
    if not _auth_allowed(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many attempts — try again in a minute")
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    user = db.get_user_by_email(email) if email else None
    if not user:
        raise HTTPException(status_code=401, detail="Email or password is wrong")
    digest, _ = hash_password(password, user["pw_salt"])
    if not hmac.compare_digest(digest, user["pw_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is wrong")
    resp = JSONResponse({"ok": True, "user": db.get_user_by_id(user["id"])})
    _set_session(resp, user["id"])
    return resp


def _cookie_kwargs():
    secure = os.environ.get("QR_COOKIE_SECURE", "1") != "0"
    return {"httponly": True, "samesite": "lax", "secure": secure, "path": "/"}


def _set_session(resp: Response, uid: int) -> None:
    resp.set_cookie("qrd_auth", make_session(uid), max_age=SESSION_DAYS * 86400,
                    **_cookie_kwargs())


@app.post("/api/auth/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("qrd_auth", path="/")
    return resp


@app.get("/api/auth/me")
def me(request: Request):
    uid = current_user(request)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return {"user": db.get_user_by_id(uid)}


# ── public redirect + capture ─────────────────────────────
@app.get("/r/{slug}")
async def redirect_slug(slug: str, request: Request, background: BackgroundTasks):
    link = db.get_link_by_slug(slug)
    if not link or not link["active"]:
        raise HTTPException(status_code=404, detail="Unknown code")
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")
    ref = request.headers.get("referer", "")
    country = geolib.lookup_country(ip)
    if link["gate_email"]:
        if request.cookies.get("qrd_" + slug) != "1":
            background.add_task(db.record_scan, link["id"], ip, country,
                                geolib.guess_device(ua), ua, ref)
            html = capture_page(slug, link["name"] or "this link")
            return HTMLResponse(html, status_code=200)
    background.add_task(db.record_scan, link["id"], ip, country,
                        geolib.guess_device(ua), ua, ref)
    resp = RedirectResponse(link["dest_url"], status_code=302)
    if link["gate_email"]:
        resp.set_cookie("qrd_" + slug, "1", max_age=60 * 60 * 24 * 90,
                        httponly=True, samesite="lax", secure=True, path="/")
    return resp


@app.post("/r/{slug}/capture")
async def capture_lead(slug: str, request: Request, background: BackgroundTasks):
    link = db.get_link_by_slug(slug)
    if not link or not link["active"]:
        raise HTTPException(status_code=404, detail="Unknown code")
    if not link["gate_email"]:
        raise HTTPException(status_code=400, detail="This code does not gate emails")
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    background.add_task(db.add_lead, link["id"], email)
    resp = RedirectResponse(link["dest_url"], status_code=302)
    resp.set_cookie("qrd_" + slug, "1", max_age=60 * 60 * 24 * 90,
                    httponly=True, samesite="lax", secure=True, path="/")
    return resp


def capture_page(slug: str, label: str) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>One step before you go</title>
<style>
:root{{--ink:#0B0B09;--paper:#FAF7F0;--accent:#E85D3F;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.card{{max-width:420px;width:100%;background:#fff;border:1px solid #eee4d6;border-radius:14px;padding:34px 28px;text-align:center;box-shadow:0 18px 50px rgba(11,11,9,.08)}}
h1{{font-size:1.35rem;font-weight:800;letter-spacing:-.01em;margin-bottom:10px}}
p{{color:#6a645a;font-size:.92rem;line-height:1.55;margin-bottom:20px}}
form{{display:flex;flex-direction:column;gap:10px}}
input{{padding:13px 14px;border:1.5px solid #ddd3c2;border-radius:10px;font-size:1rem;outline:none}}
input:focus{{border-color:var(--accent)}}
button{{background:var(--ink);color:#fff;border:0;border-radius:10px;padding:13px;font-size:.95rem;font-weight:700;cursor:pointer}}
button:hover{{background:var(--accent)}}
.err{{color:#c0392b;font-size:.8rem;display:none}}
.small{{margin-top:16px;font-size:.75rem;color:#aaa}}
</style></head><body>
<div class="card">
  <h1>Where shall we send you?</h1>
  <p>This code belongs to {label}. Leave your email to continue — we'll only
  use it for updates about this link.</p>
  <form onsubmit="submitEmail(event)">
    <input type="email" id="email" placeholder="you@example.com" required autocomplete="email"/>
    <button type="submit">Continue →</button>
    <span class="err" id="err">Please enter a valid email address.</span>
  </form>
  <p class="small">Powered by qrcodedirect.com</p>
</div>
<script>
async function submitEmail(e){{e.preventDefault();
  const el=document.getElementById('email');
  if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(el.value)){{document.getElementById('err').style.display='block';return}}
  const r=await fetch(window.location.pathname+'/capture',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:el.value}})}});
  if(r.redirected){{window.location.href=r.url}}
}}</script></body></html>"""


# ── QR artwork ──────────────────────────────────────────────
@app.get("/qr/{slug}.png")
async def qr_png(slug: str):
    link = db.get_link_by_slug(slug)
    if not link:
        raise HTTPException(status_code=404, detail="Unknown code")
    png = qrlib.render_png(f"{BASE_URL}/r/{slug}", link.get("style"))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/qr/{slug}.svg")
async def qr_svg(slug: str):
    link = db.get_link_by_slug(slug)
    if not link:
        raise HTTPException(status_code=404, detail="Unknown code")
    svg = qrlib.render_svg(f"{BASE_URL}/r/{slug}", link.get("style"))
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


# ── admin/customer API ─────────────────────────────────────
@app.post("/api/v1/links")
async def create_link(request: Request):
    uid = _claim_scope(request, {})
    body = await request.json()
    dest = validate_url(body.get("dest_url"))
    slug = str(body.get("slug") or "").strip().lower()
    if slug:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,31}[a-z0-9]|[a-z0-9]{1,32}", slug):
            raise HTTPException(status_code=400,
                                detail="Slug: 1-32 letters/numbers, may include hyphens")
        if db.slug_taken(slug):
            raise HTTPException(status_code=409, detail="Slug already taken")
    else:
        slug = make_slug()
    style = body.get("style") or {}
    if not isinstance(style, dict):
        raise HTTPException(status_code=400, detail="style must be an object")
    warnings = qrlib.validate_style(style)
    link_id = db.create_link(slug, dest, str(body.get("name") or ""), style,
                             bool(body.get("gate_email")), uid)
    link = db.get_link_by_slug(slug)
    link["id"] = link_id
    payload = _public_link(link)
    if warnings:
        payload["style_warnings"] = warnings
    return JSONResponse(payload, status_code=201)


@app.get("/api/v1/links")
async def list_links(request: Request):
    uid = _claim_scope(request, {})
    rows = db.list_links(owner_id=uid)
    return [_sum_link(r) for r in rows]


@app.get("/api/v1/links/{slug}")
async def link_detail(slug: str, request: Request):
    acting = _claim_scope(request, {})
    link = db.get_link_by_slug(slug)
    if not link or not _owns(link, acting, request):
        raise HTTPException(status_code=404, detail="Unknown code")
    return _public_link(link)


@app.patch("/api/v1/links/{slug}")
async def patch_link(slug: str, request: Request):
    acting = _claim_scope(request, {})
    link = db.get_link_by_slug(slug)
    if not link or not _owns(link, acting, request):
        raise HTTPException(status_code=404, detail="Unknown code")
    body = await request.json()
    fields: dict = {}
    warnings: list[str] = []
    if "dest_url" in body:
        fields["dest_url"] = validate_url(body["dest_url"])
    if "name" in body:
        fields["name"] = str(body["name"] or "")[:200]
    if "style" in body:
        if not isinstance(body["style"], dict):
            raise HTTPException(status_code=400, detail="style must be an object")
        fields["style"] = body["style"]
        warnings = qrlib.validate_style(body["style"])
    if "gate_email" in body:
        fields["gate_email"] = 1 if body["gate_email"] else 0
    if "active" in body:
        fields["active"] = 1 if body["active"] else 0
    if not db.update_link(slug, **fields):
        raise HTTPException(status_code=404, detail="Unknown code")
    payload = _public_link(db.get_link_by_slug(slug))
    if warnings:
        payload["style_warnings"] = warnings
    return payload


@app.delete("/api/v1/links/{slug}")
async def delete_link(slug: str, request: Request):
    acting = _claim_scope(request, {})
    link = db.get_link_by_slug(slug)
    if not link or not _owns(link, acting, request):
        raise HTTPException(status_code=404, detail="Unknown code")
    if not db.delete_link(slug):
        raise HTTPException(status_code=404, detail="Unknown code")
    return {"ok": True}


@app.get("/api/v1/links/{slug}/stats")
async def link_stats(slug: str, request: Request, days: int = 30):
    acting = _claim_scope(request, {})
    link = db.get_link_by_slug(slug)
    if not link or not _owns(link, acting, request):
        raise HTTPException(status_code=404, detail="Unknown code")
    return db.stats_for(link["id"], days=min(365, max(1, days)))


@app.post("/api/v1/preview")
async def style_preview(request: Request):
    _claim_scope(request, {})
    body = await request.json()
    dest = validate_url(body.get("dest_url"))
    style = body.get("style") or {}
    if not isinstance(style, dict):
        raise HTTPException(status_code=400, detail="style must be an object")
    png = qrlib.render_png(dest, style)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


def _sum_link(link: dict) -> dict:
    return {"slug": link["slug"], "dest_url": link["dest_url"], "name": link["name"],
            "gate_email": bool(link["gate_email"]), "active": bool(link["active"]),
            "created_at": link["created_at"], "scan_count": link.get("scans", 0),
            "qr_png": f"/qr/{link['slug']}.png", "qr_svg": f"/qr/{link['slug']}.svg"}


def _public_link(link: dict) -> dict:
    return {
        "slug": link["slug"],
        "dest_url": link["dest_url"],
        "name": link["name"],
        "style": link.get("style"),
        "gate_email": bool(link["gate_email"]),
        "active": bool(link["active"]),
        "created_at": link["created_at"],
        "redirect_url": f"{BASE_URL}/r/{link['slug']}",
        "qr_png": f"{BASE_URL}/qr/{link['slug']}.png",
        "qr_svg": f"{BASE_URL}/qr/{link['slug']}.svg",
        "stats_url": f"{BASE_URL}/api/v1/links/{link['slug']}/stats",
    }


@app.get("/healthz")
async def health():
    return {"ok": True, "service": "qrcodedirect", "version": "0.2.0-multi-user"}


# ── storefront SPA (served when the frontend build exists) ──
if FRONTEND_DIST.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIST / "static"), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith(("api/", "r/", "qr/")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text("utf-8"))
        raise HTTPException(status_code=404, detail="Not found")
