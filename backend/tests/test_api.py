"""QRCodeDirect — API contract tests (overnight v1, 8 Sep 2026)."""
import json
import os
import tempfile

os.environ["QR_DATA_DIR"] = tempfile.mkdtemp(prefix="qrd-test-")

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app, API_KEY  # noqa: E402

client = TestClient(app)
H = {"X-API-Key": API_KEY}


def _reset():
    for f in os.listdir(os.environ["QR_DATA_DIR"]):
        os.unlink(os.path.join(os.environ["QR_DATA_DIR"], f))
    db.init_db()


def test_health():
    assert client.get("/healthz").status_code == 200


def test_auth_required():
    r = client.post("/api/v1/links", json={"dest_url": "https://x.com"})
    assert r.status_code == 401
    r = client.get("/api/v1/links")
    assert r.status_code == 401


def test_create_and_redirect():
    _reset()
    r = client.post("/api/v1/links", headers=H,
                    json={"dest_url": "https://printgiftz.com", "name": "pg"})
    assert r.status_code == 201
    slug = r.json()["slug"]
    assert len(slug) == 7
    redir = client.get(f"/r/{slug}", follow_redirects=False)
    assert redir.status_code == 302
    assert redir.headers["location"] == "https://printgiftz.com"
    # scan recorded
    stats = client.get(f"/api/v1/links/{slug}/stats", headers=H).json()
    assert stats["total_scans"] == 1


def test_custom_slug_conflict():
    _reset()
    a = client.post("/api/v1/links", headers=H,
                    json={"dest_url": "https://a.com", "slug": "take-me"})
    assert a.status_code == 201
    b = client.post("/api/v1/links", headers=H,
                    json={"dest_url": "https://b.com", "slug": "take-me"})
    assert b.status_code == 409


def test_gated_capture_flow():
    _reset()
    r = client.post("/api/v1/links", headers=H,
                    json={"dest_url": "https://oneoffcustom.com",
                          "slug": "gated", "gate_email": True})
    assert r.status_code == 201
    land = client.get("/r/gated", follow_redirects=False)
    assert land.status_code == 200  # capture page served
    assert "email" in land.text.lower()
    cap = client.post("/r/gated/capture", json={"email": "a@b.com"},
                      follow_redirects=False)
    assert cap.status_code == 302
    assert cap.headers["location"] == "https://oneoffcustom.com"
    stats = client.get("/api/v1/links/gated/stats", headers=H).json()
    assert stats["leads_captured"] == 1
    assert stats["total_scans"] == 1
    # second visit redirects straight through
    again = client.get("/r/gated", headers={"cookie": "qrd_gated=1"},
                       follow_redirects=False)
    assert again.status_code == 302


def test_qr_renders():
    _reset()
    client.post("/api/v1/links", headers=H,
                json={"dest_url": "https://x.com", "slug": "art",
                      "style": {"fg": "#E85D3F", "bg": "#FFFFFF", "dots": "rounded"}})
    png = client.get("/qr/art.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert len(png.content) > 500
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
    svg = client.get("/qr/art.svg")
    assert svg.status_code == 200
    assert "svg" in svg.headers["content-type"]


def test_patch_and_delete():
    _reset()
    client.post("/api/v1/links", headers=H,
                json={"dest_url": "https://x.com", "slug": "editable"})
    p = client.patch("/api/v1/links/editable", headers=H,
                     json={"dest_url": "https://y.com", "active": False})
    assert p.status_code == 200
    assert p.json()["dest_url"] == "https://y.com"
    redir = client.get("/r/editable", follow_redirects=False)
    assert redir.status_code == 404  # inactive
    d = client.delete("/api/v1/links/editable", headers=H)
    assert d.status_code == 200
    assert client.get("/r/editable").status_code == 404


def test_slug_validation():
    bad = client.post("/api/v1/links", headers=H,
                      json={"dest_url": "https://x.com", "slug": "UPPER_case!"})
    assert bad.status_code == 400
