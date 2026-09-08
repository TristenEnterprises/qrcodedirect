# QRCodeDirect — qrcodedirect.com

Dynamic QR platform (overnight v1 backend, 8 Sep 2026, Tris + Hermes).

## What it does (backend v1)
- **Create** dynamic links/codes: `POST /api/v1/links` (auto or custom slug, style params, optional email gate)
- **Redirect** `/r/{slug}` → destination, logging every scan (IP, device, referer, country best-effort)
- **Email capture**: gated codes serve a branded landing that collects an email before redirecting (MailWizz export hook TBD)
- **Styled QR artwork**: `/qr/{slug}.png` + `.svg` rendered from stored style (fg/bg colours, rounded dots, high-res, H error correction, optional centre logo patch)
- **Stats**: `/api/v1/links/{slug}/stats?days=30` — totals, unique visitors, daily series, top countries/devices/referers, leads captured
- Single-owner API key auth (`X-API-Key`, auto-generated at `/opt/qrcodedirect/config/api_key`)

## Stack
Python 3.12 · FastAPI · SQLite (WAL) at `/opt/qrcodedirect/data/qr.db` · python-qrcode + Pillow. Venv: `/opt/qrcodedirect/venv`. Service: PM2 `qrcodedirect-api` on 127.0.0.1:8400 (local-only until the storefront exists).

## Roadmap (next)
- React storefront/designer (colour/dots/logo, live preview) — our proven build loop
- Multi-tenant users + subscription tiers (Stripe; facilitator access available)
- White-label customer domains (CNAME + Caddy auto-HTTPS; Cloudflare infra exists)
- MailWizz hook for captured emails (VPS-3 MailWizz 3.0.4 + integration skill)
- GeoLite2 licence later (currently free ip-api.com lookup w/ cache)

## Tests
`cd backend && ../venv/bin/python -m pytest tests/ -q` → 8 passed.
