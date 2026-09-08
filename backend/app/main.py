"""QRCodeDirect — FastAPI backend (overnight v1, 8 Sep 2026).

Public:
  GET  /r/{slug}            redirect (302) with scan logging; gated codes show capture
  POST /r/{slug}/capture    {email} -> store lead (MailWizz hook TBD), then redirect
  GET  /qr/{slug}.png|svg   styled QR render from the link's stored style

Admin API (X-API-Key header; single-owner v1, multi-tenant users later):
  POST   /api/v1/links              create {dest_url, slug?, name?, style?, gate_email?}
  GET    /api/v1/links              list with scan counts
  GET    /api/v1/links/{slug}       detail incl. stats
  PATCH  /api/v1/links/{slug}       update dest/name/style/gate_email/active
  DELETE /api/v1/links/{slug}
  GET    /api/v1/links/{slug}/stats?days=30
  POST   /api/v1/links/{slug}/regenerate-qr   (placeholder for style preview flow)
"""
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, Request, Response, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse

from . import db
from . import qr as qrlib
from . import geo as geolib

CONFIG_DIR = Path("/opt/qrcodedirect/config")
API_KEY_FILE = CONFIG_DIR / "api_key"

BASE_URL = os.environ.get("QR_BASE_URL", "https://qrcodedirect.com")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}[a-z0-9]$|^[a-z0-9]{1,32}$")


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


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def make_slug() -> str:
    alphabet = "abcdefghijkmnpqrstuvwxyz23456789"  # no 0/O/1/l
    for _ in range(20):
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
        # served cookie "qrd_<slug>" means we've captured this device already
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
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
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
    content = f"{BASE_URL}/r/{slug}"
    png = qrlib.render_png(content, link.get("style"))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/qr/{slug}.svg")
async def qr_svg(slug: str):
    link = db.get_link_by_slug(slug)
    if not link:
        raise HTTPException(status_code=404, detail="Unknown code")
    content = f"{BASE_URL}/r/{slug}"
    svg = qrlib.render_svg(content, link.get("style"))
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


# ── admin API ───────────────────────────────────────────────
@app.post("/api/v1/links")
async def create_link(request: Request, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
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
                             bool(body.get("gate_email")))
    link = db.get_link_by_slug(slug)
    link["id"] = link_id
    payload = _public_link(link)
    if warnings:
        payload["style_warnings"] = warnings
    return JSONResponse(payload, status_code=201)


@app.get("/api/v1/links")
async def list_links(x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    rows = db.list_links()
    return [{"slug": r["slug"], "dest_url": r["dest_url"], "name": r["name"],
             "gate_email": bool(r["gate_email"]), "active": bool(r["active"]),
             "created_at": r["created_at"], "scan_count": r["scans"],
             "qr_png": f"/qr/{r['slug']}.png", "qr_svg": f"/qr/{r['slug']}.svg"}
            for r in rows]


@app.get("/api/v1/links/{slug}")
async def link_detail(slug: str, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    link = db.get_link_by_slug(slug)
    if not link:
        raise HTTPException(status_code=404, detail="Unknown code")
    return _public_link(link)


@app.patch("/api/v1/links/{slug}")
async def patch_link(slug: str, request: Request,
                     x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
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


@app.post("/api/v1/preview")
async def style_preview(request: Request, x_api_key: str | None = Header(default=None)):
    """Render a QR PNG for an arbitrary destination + style — the designer's live preview."""
    require_key(x_api_key)
    body = await request.json()
    dest = validate_url(body.get("dest_url"))
    style = body.get("style") or {}
    if not isinstance(style, dict):
        raise HTTPException(status_code=400, detail="style must be an object")
    png = qrlib.render_png(dest, style)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@app.delete("/api/v1/links/{slug}")
async def delete_link(slug: str, x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    if not db.delete_link(slug):
        raise HTTPException(status_code=404, detail="Unknown code")
    return {"ok": True}


@app.get("/api/v1/links/{slug}/stats")
async def link_stats(slug: str, days: int = 30,
                     x_api_key: str | None = Header(default=None)):
    require_key(x_api_key)
    link = db.get_link_by_slug(slug)
    if not link:
        raise HTTPException(status_code=404, detail="Unknown code")
    return db.stats_for(link["id"], days=min(365, max(1, days)))


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
    return {"ok": True, "service": "qrcodedirect", "version": "0.1.0-overnight"}
