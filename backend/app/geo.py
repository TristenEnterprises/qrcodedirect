"""QRCodeDirect — best-effort geo lookup for scan logs (8 Sep 2026).

Uses the free ip-api.com JSON endpoint (no key; ~45 req/min limit — fine for
v1 volumes) with a small in-memory cache. Failures are silent -> "unknown".
"""
import json
import threading
import time
import urllib.request

_cache: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()
_CACHE_TTL = 3600 * 24  # country for an IP rarely changes


def lookup_country(ip: str) -> str:
    if not ip or ip in ("127.0.0.1", "::1", "unknown"):
        return ""
    ip = ip.split(",")[0].strip()
    now = time.time()
    with _lock:
        hit = _cache.get(ip)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    try:
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip}?fields=status,countryCode",
            headers={"User-Agent": "qrcodedirect/0.1"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
        country = str(data.get("countryCode", "")) if data.get("status") == "success" else ""
    except Exception:
        country = ""
    with _lock:
        _cache[ip] = (now, country)
    return country


def guess_device(ua: str) -> str:
    ua = (ua or "").lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua or "ipad" in ua:
        return "mobile"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "bot"
    return "desktop"
