import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export default function Dashboard() {
  const [codes, setCodes] = useState(null);
  const [err, setErr] = useState("");

  async function load() {
    try { setCodes(await api.links()); } catch (e) { setErr(e.message); }
  }
  useEffect(() => { load(); }, []);

  async function toggleActive(c) {
    await api.update(c.slug, { active: !c.active });
    load();
  }
  async function toggleGate(c) {
    await api.update(c.slug, { gate_email: !c.gate_email });
    load();
  }
  async function remove(c) {
    if (!window.confirm(`Delete code "${c.slug}"? Scans are removed with it.`)) return;
    await api.del(c.slug);
    load();
  }
  function copy(c) {
    const url = `${window.location.origin}/r/${c.slug}`;
    navigator.clipboard?.writeText(url).then(() => alert("Code link copied: " + url));
  }

  return (
    <main className="wrap" style={{ paddingTop: 30, paddingBottom: 80 }}>
      <div className="label-inline" style={{ marginBottom: 22 }}>
        <div>
          <h1 className="h" style={{ fontSize: "1.7rem" }}>My codes</h1>
          <p style={{ color: "var(--muted)", fontSize: ".9rem" }}>Design, edit and watch every scan.</p>
        </div>
        <Link to="/app/new" className="btn btn-dark">＋ New code</Link>
      </div>

      {err && <div className="banner err">{err}</div>}
      {!codes && !err && <div className="spin" />}
      {codes && codes.length === 0 && (
        <div className="card" style={{ padding: 50, textAlign: "center" }}>
          <div style={{ fontSize: "2rem" }}>⬛</div>
          <h2 className="h" style={{ marginTop: 10, fontSize: "1.2rem" }}>No codes yet</h2>
          <p style={{ color: "var(--muted)", margin: "8px 0 20px" }}>Your first branded code takes about two minutes.</p>
          <Link to="/app/new" className="btn btn-accent">Design your first code</Link>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(320px,1fr))" }}>
        {codes && codes.map((c) => (
          <div className="card" key={c.slug} style={{ padding: 16, display: "flex", gap: 14 }}>
            <Link to={`/app/c/${c.slug}`} title="Open code page">
              <img src={`/qr/${c.slug}.png?ts=${encodeURIComponent(c.updated_at || "")}`} alt={c.slug} width={96} height={96} style={{ borderRadius: 10, background: "#fff", border: "1px solid var(--line)", display: "block" }} />
            </Link>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.name || "Untitled"}</div>
              <div style={{ fontSize: ".78rem", color: "var(--muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.dest_url}</div>
              <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                <span className="slug-mono">/{c.slug}</span>
                <span className={`pill ${c.active ? "" : "off"}`}>{c.active ? "live" : "paused"}</span>
                {c.gate_email && <span className="pill">leads</span>}
              </div>
              <div style={{ marginTop: 8, fontSize: ".86rem", fontWeight: 700 }}>
                {c.scan_count} scan{c.scan_count === 1 ? "" : "s"}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <Link className="btn btn-ghost btn-sm" to={`/app/c/${c.slug}`}>Design & stats</Link>
                <button className="btn btn-ghost btn-sm" onClick={() => copy(c)}>Copy link</button>
                <button className="btn btn-ghost btn-sm" onClick={() => toggleActive(c)}>{c.active ? "Pause" : "Resume"}</button>
                <button className="btn btn-ghost btn-sm" onClick={() => toggleGate(c)}>{c.gate_email ? "No lead gate" : "Lead gate"}</button>
                <button className="btn btn-ghost btn-sm" style={{ color: "var(--bad)" }} onClick={() => remove(c)}>Delete</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
