import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import Designer from "./Designer";

/* One code: tabs for Design and Stats. */
function StatsTab({ slug }) {
  const [days, setDays] = useState(30);
  const [s, setS] = useState(null);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try { setS(await api.stats(slug, days)); setErr(""); } catch (e) { setErr(e.message); }
  }, [slug, days]);
  useEffect(() => { load(); }, [load]);

  if (err) return <div className="banner err">{err}</div>;
  if (!s) return <div className="spin" />;

  const maxDay = Math.max(1, ...s.daily.map((d) => d.n));
  const list = (rows) => rows && rows.length
    ? rows.map((r) => (
        <div key={r.day || r.country || r.device || r.ref || Math.random()} className="label-inline" style={{ padding: "7px 0", borderBottom: "1px solid var(--line)", fontSize: ".9rem" }}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--muted)" }}>{(r.day || r.country || r.device || r.ref || "unknown").toString()}</span>
          <b>{r.n}</b>
        </div>
      ))
    : <p className="helptext">No data yet in this window.</p>;

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <div style={{ display: "flex", gap: 8 }}>
        {[7, 30, 90].map((d) => (
          <button key={d} className="btn btn-sm" onClick={() => setDays(d)}
            style={days === d ? { background: "var(--ink)", color: "var(--paper)" } : { background: "transparent", border: "1px solid var(--line)" }}>
            {d} days
          </button>
        ))}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))" }}>
        {[
          ["Total scans", s.total_scans],
          [`In last ${s.days}d`, s.scans_in_window],
          ["Unique visitors", s.unique_visitors],
          ["Emails captured", s.leads_captured],
        ].map(([l, v]) => (
          <div className="card" key={l} style={{ padding: 16, textAlign: "center" }}>
            <div className="h" style={{ fontSize: "1.7rem" }}>{v}</div>
            <div className="helptext" style={{ marginTop: 2 }}>{l}</div>
          </div>
        ))}
      </div>

      {/* daily bar chart */}
      <div className="card" style={{ padding: 18 }}>
        <div className="field" style={{ margin: 0 }}>Scans per day</div>
        {s.daily.length === 0 ? (
          <p className="helptext" style={{ padding: "18px 0" }}>No scans yet — share your code and check back.</p>
        ) : (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 130, marginTop: 12 }}>
            {s.daily.map((d) => (
              <div key={d.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
                <span style={{ fontSize: ".62rem", color: "var(--muted)", marginBottom: 3 }}>{d.n || ""}</span>
                <div title={`${d.day}: ${d.n}`} style={{ width: "100%", background: d.n ? "var(--accent)" : "rgba(11,11,9,.06)", borderRadius: "3px 3px 0 0", height: `${Math.max(3, (d.n / maxDay) * 100)}%` }} />
              </div>
            ))}
          </div>
        )}
        <div className="helptext" style={{ marginTop: 8, textAlign: "right" }}>{s.daily.length ? `${s.daily[0]?.day} → ${s.daily[s.daily.length - 1]?.day}` : ""}</div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
        <div className="card" style={{ padding: 18 }}><div className="field" style={{ margin: 0 }}>Top countries</div>{list(s.top_countries)}</div>
        <div className="card" style={{ padding: 18 }}><div className="field" style={{ margin: 0 }}>Devices</div>{list(s.devices)}</div>
        <div className="card" style={{ padding: 18 }}><div className="field" style={{ margin: 0 }}>Top referrers</div>{list(s.top_referers)}</div>
      </div>
    </div>
  );
}

export default function CodePage() {
  const { slug } = useParams();
  const [link, setLink] = useState(null);
  const [tab, setTab] = useState("design");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.link(slug).then(setLink).catch((e) => setErr(e.message));
  }, [slug]);

  if (err) return <main className="wrap" style={{ paddingTop: 30 }}><div className="banner err">{err} · <Link to="/app">back to codes</Link></div></main>;
  if (!link) return <div className="spin" />;

  const short = `${window.location.origin}/r/${link.slug}`;

  return (
    <main className="wrap" style={{ paddingTop: 26, paddingBottom: 90 }}>
      <div className="label-inline" style={{ marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Link to="/app" className="navlink">← My codes</Link>
          <h1 className="h" style={{ fontSize: "1.35rem" }}>{link.name || link.slug}</h1>
          <span className="slug-mono">/{link.slug}</span>
        </div>
        <a className="btn btn-ghost btn-sm" href={link.qr_png} download={`qrcodedirect-${link.slug}.png`}>Download PNG</a>
        <a className="btn btn-ghost btn-sm" href={link.qr_svg} download={`qrcodedirect-${link.slug}.svg`}>Download SVG</a>
      </div>
      <p className="helptext" style={{ marginBottom: 16 }}>
        Code URL: <span className="slug-mono">{short}</span> · opens <span style={{ color: "var(--muted)" }}>{link.dest_url}</span>
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
        {[["design", "Design"], ["stats", "Statistics"]].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} className="btn btn-sm"
            style={tab === id ? { background: "var(--ink)", color: "var(--paper)" } : { background: "transparent", border: "1px solid var(--line)" }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "design" ? (
        <Designer initial={link} onSaved={(u) => setLink(u)} />
      ) : (
        <StatsTab slug={link.slug} />
      )}
    </main>
  );
}
