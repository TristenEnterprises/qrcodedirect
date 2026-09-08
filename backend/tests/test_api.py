"""QRCodeDirect — API contract tests v2 (multi-user, 8 Sep 2026)."""
import json
import os
import tempfile

os.environ["QR_DATA_DIR"] = tempfile.mkdtemp(prefix="qrd-test-")
os.environ["QR_COOKIE_SECURE"] = "0"  # httpx testserver runs plain http

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app, API_KEY  # noqa: E402

client = TestClient(app)
H = {"X-API-Key": API_KEY}


def _reset():
    for f in os.listdir(os.environ["QR_DATA_DIR"]):
        os.unlink(os.path.join(os.environ["QR_DATA_DIR"], f))
    db.init_db()


def _register(email="a@b.com", pw="password123"):
    return client.post("/api/auth/register",
                       json={"name": "Anne", "email": email, "password": pw})


def test_health():
    assert client.get("/healthz").status_code == 200


def test_register_login_me_logout():
    _reset()
    r = _register()
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "a@b.com"
    # duplicate register
    assert _register().status_code == 409
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "a@b.com"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrongpass1"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": "a@b.com", "password": "password123"})
    assert ok.status_code == 200


def test_admin_key_still_works():
    _reset()
    r = client.post("/api/v1/links", headers=H,
                    json={"dest_url": "https://x.com", "slug": "adminkey"})
    assert r.status_code == 201


def test_owner_isolation():
    _reset()
    _register("anne@x.com", "password123")
    a = client.post("/api/v1/links", json={"dest_url": "https://anne.com", "slug": "anne-code"})
    assert a.status_code == 201
    # a second user cannot see or touch Anne's code
    _register("bob@x.com", "password123")
    lst = client.get("/api/v1/links")
    assert lst.status_code == 200 and lst.json() == []
    assert client.get("/api/v1/links/anne-code").status_code == 404
    assert client.patch("/api/v1/links/anne-code",
                        json={"dest_url": "https://evil.com"}).status_code == 404
    assert client.delete("/api/v1/links/anne-code").status_code == 404
    # admin key CAN see it
    admin_list = client.get("/api/v1/links", headers=H)
    assert any(x["slug"] == "anne-code" for x in admin_list.json())
    # sign back in as anne and confirm ownership
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "anne@x.com", "password": "password123"})
    assert client.get("/api/v1/links/anne-code").status_code == 200


def test_create_and_redirect_and_scan():
    _reset()
    _register()
    r = client.post("/api/v1/links", json={"dest_url": "https://printgiftz.com", "name": "pg"})
    assert r.status_code == 201
    slug = r.json()["slug"]
    assert len(slug) == 7
    redir = client.get(f"/r/{slug}", follow_redirects=False)
    assert redir.status_code == 302
    assert redir.headers["location"] == "https://printgiftz.com"
    stats = client.get(f"/api/v1/links/{slug}/stats").json()
    assert stats["total_scans"] == 1


def test_custom_slug_conflict():
    _reset()
    _register()
    a = client.post("/api/v1/links", json={"dest_url": "https://a.com", "slug": "take-me"})
    assert a.status_code == 201
    b = client.post("/api/v1/links", json={"dest_url": "https://b.com", "slug": "take-me"})
    assert b.status_code == 409


def test_gated_capture_flow():
    _reset()
    _register()
    r = client.post("/api/v1/links",
                    json={"dest_url": "https://oneoffcustom.com", "slug": "gated", "gate_email": True})
    assert r.status_code == 201
    land = client.get("/r/gated", follow_redirects=False)
    assert land.status_code == 200
    assert "email" in land.text.lower()
    cap = client.post("/r/gated/capture", json={"email": "buyer@b.com"}, follow_redirects=False)
    assert cap.status_code == 302
    assert cap.headers["location"] == "https://oneoffcustom.com"
    stats = client.get("/api/v1/links/gated/stats").json()
    assert stats["leads_captured"] == 1
    assert stats["total_scans"] == 1


def test_qr_renders():
    _reset()
    _register()
    client.post("/api/v1/links", json={"dest_url": "https://x.com", "slug": "art",
                                       "style": {"fg": "#0B0B09", "dots": "rounded"}})
    png = client.get("/qr/art.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
    svg = client.get("/qr/art.svg")
    assert svg.status_code == 200


def test_preview_and_warnings():
    _reset()
    _register()
    import base64 as b64
    logo = "data:image/png;base64," + b64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
    pv = client.post("/api/v1/preview", json={"dest_url": "https://y.com", "style": {}})
    assert pv.status_code == 200 and pv.headers["content-type"] == "image/png"
    # light gradient + logo → warning surfaced, still 201
    r = client.post("/api/v1/links", json={"dest_url": "https://z.com",
                                           "style": {"fg_mode": "gradient",
                                                     "fg_gradient": ["#123A5F", "#2EC4B6"],
                                                     "logo": {"data": logo, "scale": 20}}})
    assert r.status_code == 201
    assert r.json().get("style_warnings")


def test_patch_and_delete():
    _reset()
    _register()
    client.post("/api/v1/links", json={"dest_url": "https://x.com", "slug": "editable"})
    p = client.patch("/api/v1/links/editable", json={"dest_url": "https://y.com", "active": False})
    assert p.status_code == 200
    assert p.json()["dest_url"] == "https://y.com"
    assert client.get("/r/editable", follow_redirects=False).status_code == 404
    assert client.delete("/api/v1/links/editable").status_code == 200
    assert client.get("/r/editable").status_code == 404


def test_slug_validation():
    _reset()
    _register()
    bad = client.post("/api/v1/links", json={"dest_url": "https://x.com", "slug": "UPPER_case!"})
    assert bad.status_code == 400
    assert client.post("/api/v1/links", json={"dest_url": "notaurl"}).status_code == 201  # auto-https
