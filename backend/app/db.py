"""QRCodeDirect — database layer v2 (users + ownership, 8 Sep 2026).

Tables:
  users  — customer accounts (email+password, pbkdf2)
  links  — one row per QR code (owner_id nullable = admin/system/demo)
  scans  — one row per hit on /r/{slug}
  leads  — captured emails on gated codes
"""
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

DATA_DIR = os.environ.get("QR_DATA_DIR", "/opt/qrcodedirect/data")
DB_PATH = os.path.join(DATA_DIR, "qr.db")

_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT DEFAULT '',
  pw_hash TEXT NOT NULL,
  pw_salt TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  dest_url TEXT NOT NULL,
  name TEXT DEFAULT '',
  style TEXT NOT NULL DEFAULT '{}',
  gate_email INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  link_id INTEGER NOT NULL REFERENCES links(id) ON DELETE CASCADE,
  ts TEXT NOT NULL,
  ip TEXT DEFAULT '',
  country TEXT DEFAULT '',
  device TEXT DEFAULT '',
  ua TEXT DEFAULT '',
  ref TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  link_id INTEGER NOT NULL REFERENCES links(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  ts TEXT NOT NULL,
  status TEXT DEFAULT 'new',
  meta TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_scans_link_ts ON scans(link_id, ts);
CREATE INDEX IF NOT EXISTS idx_leads_link ON leads(link_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat(timespec="seconds")


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        c.executescript(SCHEMA)
        cols = [row["name"] for row in c.execute("PRAGMA table_info(links)").fetchall()]
        if "owner_id" not in cols:  # migration from pre-multi-user v1 db
            c.execute("ALTER TABLE links ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        c.execute("CREATE INDEX IF NOT EXISTS idx_links_owner ON links(owner_id)")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


# ---------- users ----------
def create_user(email: str, name: str, pw_hash: str, salt: str) -> int:
    ts = now_iso()
    with _write_lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO users (email,name,pw_hash,pw_salt,created_at) VALUES (?,?,?,?,?)",
            (email.lower().strip(), (name or "").strip()[:80], pw_hash, salt, ts),
        )
        return cur.lastrowid


def get_user_by_email(email: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    with _conn() as c:
        row = c.execute("SELECT id,email,name,created_at FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def count_users() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]


# ---------- links ----------
def create_link(slug: str, dest_url: str, name: str, style: dict,
                gate_email: bool, owner_id: int | None) -> int:
    ts = now_iso()
    with _write_lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO links (slug,dest_url,name,style,gate_email,owner_id,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (slug, dest_url, name, json.dumps(style), 1 if gate_email else 0,
             owner_id, ts, ts),
        )
        return cur.lastrowid


def slug_taken(slug: str) -> bool:
    with _conn() as c:
        return c.execute("SELECT 1 FROM links WHERE slug=?", (slug,)).fetchone() is not None


def get_link_by_slug(slug: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM links WHERE slug=?", (slug,)).fetchone()
    return dict(row) if row else None


def update_link(slug: str, **fields) -> bool:
    allowed = {"dest_url", "name", "style", "gate_email", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return False
    cols.append("updated_at")
    values = [fields[k] for k in cols[:-1]]
    values.append(now_iso())
    values.append(slug)
    sql = f"UPDATE links SET {', '.join(k + '=?' for k in cols)} WHERE slug=?"
    with _write_lock, _conn() as c:
        cur = c.execute(sql, values)
        return cur.rowcount > 0


def list_links(owner_id: int | None = None) -> list[dict]:
    with _conn() as c:
        if owner_id is None:
            rows = c.execute(
                "SELECT l.*, (SELECT COUNT(*) FROM scans s WHERE s.link_id=l.id) AS scans"
                " FROM links l ORDER BY l.id DESC LIMIT 500").fetchall()
        else:
            rows = c.execute(
                "SELECT l.*, (SELECT COUNT(*) FROM scans s WHERE s.link_id=l.id) AS scans"
                " FROM links l WHERE l.owner_id=? ORDER BY l.id DESC LIMIT 500",
                (owner_id,)).fetchall()
    return [dict(r) for r in rows]


def count_links(owner_id: int) -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) n FROM links WHERE owner_id=?", (owner_id,)).fetchone()["n"]


def delete_link(slug: str) -> bool:
    with _write_lock, _conn() as c:
        cur = c.execute("DELETE FROM links WHERE slug=?", (slug,))
        return cur.rowcount > 0


# ---------- scans ----------
def record_scan(link_id: int, ip: str, country: str, device: str, ua: str, ref: str) -> None:
    with _write_lock, _conn() as c:
        c.execute(
            "INSERT INTO scans (link_id,ts,ip,country,device,ua,ref) VALUES (?,?,?,?,?,?,?)",
            (link_id, now_iso(), ip, country, device, ua[:300], ref[:500]),
        )


def stats_for(link_id: int, days: int = 30) -> dict:
    days = max(1, days)
    since = days_ago_iso(days)
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM scans WHERE link_id=?",
                          (link_id,)).fetchone()["n"]
        window = c.execute("SELECT COUNT(*) n FROM scans WHERE link_id=? AND ts>=?",
                           (link_id, since)).fetchone()["n"]
        uniq = c.execute("SELECT COUNT(DISTINCT ip) n FROM scans WHERE link_id=? AND ts>=?",
                         (link_id, since)).fetchone()["n"]
        daily = [
            dict(r)
            for r in c.execute(
                "SELECT substr(ts,1,10) day, COUNT(*) n FROM scans"
                " WHERE link_id=? AND ts>=? GROUP BY day ORDER BY day",
                (link_id, since),
            ).fetchall()
        ]
        countries = [dict(r) for r in c.execute(
            "SELECT country, COUNT(*) n FROM scans WHERE link_id=? AND ts>=? AND country!=''"
            " GROUP BY country ORDER BY n DESC LIMIT 8", (link_id, since)).fetchall()]
        devices = [dict(r) for r in c.execute(
            "SELECT device, COUNT(*) n FROM scans WHERE link_id=? AND ts>=? AND device!=''"
            " GROUP BY device ORDER BY n DESC", (link_id, since)).fetchall()]
        referers = [dict(r) for r in c.execute(
            "SELECT ref, COUNT(*) n FROM scans WHERE link_id=? AND ts>=? AND ref!=''"
            " GROUP BY ref ORDER BY n DESC LIMIT 6", (link_id, since)).fetchall()]
        leads = c.execute("SELECT COUNT(*) n FROM leads WHERE link_id=?",
                          (link_id,)).fetchone()["n"]
    return {
        "total_scans": total,
        "scans_in_window": window,
        "unique_visitors": uniq,
        "days": days,
        "daily": daily,
        "top_countries": countries,
        "devices": devices,
        "top_referers": referers,
        "leads_captured": leads,
    }


# ---------- leads ----------
def add_lead(link_id: int, email: str) -> None:
    with _write_lock, _conn() as c:
        c.execute(
            "INSERT INTO leads (link_id,email,ts,status) VALUES (?,?,?, 'new')",
            (link_id, email.lower().strip(), now_iso()),
        )
