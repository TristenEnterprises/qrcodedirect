import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, DEFAULT_STYLE, styleWarnings } from "../api";

const MAX_LOGO_B64 = 1_400_000;

/* Collapsible settings section (printgiftz-style: hide/reveal when needed) */
function Section({ n, title, open, children }) {
  const [on, setOn] = useState(open !== false);
  return (
    <div className={`sec ${on ? "" : "closed"}`}>
      <button type="button" className="sec-head" onClick={() => setOn(!on)} aria-expanded={on}>
        <span><span className="sec-num">{n}</span>{title}</span>
        <svg className="chev" width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 6l5 5 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      <div className="sec-body">{children}</div>
    </div>
  );
}

export default function Designer({ initial, onSaved }) {
  const editing = !!initial;
  const nav = useNavigate();
  const [dest, setDest] = useState(initial?.dest_url || "");
  const [slug, setSlug] = useState(initial?.slug || "");
  const [name, setName] = useState(initial?.name || "");
  const [gate, setGate] = useState(!!initial?.gate_email);
  const [style, setStyle] = useState(
    initial?.style
      ? { ...DEFAULT_STYLE, ...initial.style,
          fg_gradient: Array.isArray(initial.style.fg_gradient) ? initial.style.fg_gradient : DEFAULT_STYLE.fg_gradient }
      : { ...DEFAULT_STYLE }
  );
  const [pv, setPv] = useState(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const [logoName, setLogoName] = useState(initial?.style?.logo?.data ? "Saved logo" : "");
  const [showPreview, setShowPreview] = useState(true);
  const timer = useRef(null);

  const renderPreview = useCallback(async (destUrl, st) => {
    try {
      const url = await api.preview({ dest_url: destUrl || "https://example.com", style: st });
      setPv((old) => { if (old) URL.revokeObjectURL(old); return url; });
    } catch (e) { /* keep last frame while typing */ }
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => renderPreview(dest, style), 420);
    return () => clearTimeout(timer.current);
  }, [dest, style, renderPreview]);

  const set = (patch) => setStyle((s) => ({ ...s, ...patch }));
  const warnings = styleWarnings(style);
  const logoScale = style.logo?.scale || 18;
  const hasLogo = !!(style.logo && style.logo.data);

  function onLogoFile(f) {
    if (!f) return;
    if (!/^image\//.test(f.type)) { setErr("Logo must be an image (PNG, JPG or WebP)."); return; }
    const rd = new FileReader();
    rd.onload = () => {
      const data = String(rd.result);
      if (data.length > MAX_LOGO_B64) { setErr("Logo image is too big — use one under ~1 MB."); return; }
      setErr(""); setLogoName(f.name);
      set({ logo: { data, scale: logoScale } });
    };
    rd.readAsDataURL(f);
  }

  function removeLogo() { set({ logo: null }); setLogoName(""); setErr(""); }

  async function save(e) {
    e?.preventDefault();
    if (!dest.trim()) { setErr("Enter the destination link your code should open."); return; }
    setErr(""); setOk(""); setBusy(true);
    const body = { dest_url: dest, name: name || "My code", style, gate_email: gate };
    if (!editing && slug.trim()) body.slug = slug.trim().toLowerCase();
    try {
      const res = editing ? await api.update(initial.slug, body) : await api.create(body);
      if (res.style_warnings && res.style_warnings.length) setOk("Saved — " + res.style_warnings[0]);
      else setOk("Saved — your code is live.");
      if (!editing) nav(`/app/c/${res.slug}`);
      else onSaved?.(res);
    } catch (ex) { setErr(ex.message || "Save failed"); }
    finally { setBusy(false); }
  }

  function download() {
    if (!initial) { setErr("Save the code first, then download the PNG."); return; }
    const a = document.createElement("a");
    a.href = `/qr/${initial.slug}.png?dl=1`;
    a.download = `qrcodedirect-${initial.slug}.png`;
    document.body.appendChild(a); a.click(); a.remove();
  }

  const seg = (current, onClick, options) => (
    <div style={{ display: "inline-flex", border: "1px solid var(--line)", borderRadius: 10, overflow: "hidden" }}>
      {options.map(([val, label]) => (
        <button type="button" key={val} onClick={() => onClick(val)}
          style={{ border: 0, background: current === val ? "var(--ink)" : "transparent", color: current === val ? "#fff" : "var(--ink)", padding: "9px 15px", fontSize: ".85rem", fontWeight: 600, lineHeight: 1.4, cursor: "pointer" }}>
          {label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="des-grid">
      {/* LEFT: collapsible settings */}
      <div>
        <form onSubmit={save}>
          <Section n="1" title="Destination">
            <label className="field">Destination link</label>
            <input className="input" value={dest} onChange={(e) => setDest(e.target.value)} placeholder="https://yourbusiness.com/offer" autoComplete="url" />
            <div className="helptext">Where the code takes people. You can change it any time — no reprint needed.</div>
            <div className="row2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div>
                <label className="field">Name (optional)</label>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Summer menu" />
              </div>
              {!editing && (
                <div>
                  <label className="field">Your short link (optional)</label>
                  <input className="input" value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "").slice(0, 32))} placeholder="summer-menu" style={{ fontFamily: "var(--mono)" }} />
                  <div className="helptext">Blank = we pick one.</div>
                </div>
              )}
            </div>
          </Section>

          <Section n="2" title="Colour and dots">
            <label className="field">Code colour</label>
            {seg(style.fg_mode, (m) => set({ fg_mode: m }), [["solid", "Single colour"], ["gradient", "Gradient"]])}

            {style.fg_mode === "gradient" ? (
              <div className="grid" style={{ gridTemplateColumns: "1fr 1fr auto", gap: 10, alignItems: "end", marginTop: 10 }}>
                <div><span className="helptext" style={{ display: "block", marginBottom: 4 }}>From</span>
                  <input type="color" value={style.fg_gradient[0]} onChange={(e) => set({ fg_gradient: [e.target.value, style.fg_gradient[1]] })} style={{ width: "100%", height: 44, border: "1px solid var(--line)", borderRadius: 8, background: "#fff", cursor: "pointer" }} />
                </div>
                <div><span className="helptext" style={{ display: "block", marginBottom: 4 }}>To</span>
                  <input type="color" value={style.fg_gradient[1]} onChange={(e) => set({ fg_gradient: [style.fg_gradient[0], e.target.value] })} style={{ width: "100%", height: 44, border: "1px solid var(--line)", borderRadius: 8, background: "#fff", cursor: "pointer" }} />
                </div>
                <div style={{ width: 130 }}>
                  <span className="helptext" style={{ display: "block", marginBottom: 4 }}>Angle {style.fg_angle}°</span>
                  <input type="range" min={0} max={360} value={style.fg_angle} onChange={(e) => set({ fg_angle: Number(e.target.value) })} style={{ width: "100%" }} />
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 10 }}>
                <input type="color" value={style.fg} onChange={(e) => set({ fg: e.target.value })} style={{ width: 64, height: 44, border: "1px solid var(--line)", borderRadius: 8, background: "#fff", cursor: "pointer" }} />
                <span style={{ fontSize: ".86rem", color: "var(--muted)", fontFamily: "var(--mono)" }}>{style.fg}</span>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 6 }}>
              <div>
                <label className="field">Background</label>
                <input type="color" value={style.bg} onChange={(e) => set({ bg: e.target.value })} style={{ width: "100%", height: 40, border: "1px solid var(--line)", borderRadius: 8, background: "#fff", cursor: "pointer" }} />
              </div>
              <div>
                <label className="field">Dots</label>
                {seg(style.dots, (d) => set({ dots: d }), [["rounded", "Rounded"], ["square", "Square"]])}
              </div>
            </div>
          </Section>

          <Section n="3" title="Centre logo" open={hasLogo}>
            <div className="helptext" style={{ marginBottom: 10 }}>Optional — your logo sits in the middle of the code (it stays scannable; that part is decode-tested).</div>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <label className="btn btn-ghost btn-sm" style={{ cursor: "pointer" }}>
                {hasLogo ? "Replace logo" : "Upload logo"}
                <input type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => onLogoFile(e.target.files?.[0])} />
              </label>
              {hasLogo && (
                <>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={removeLogo}>Remove logo</button>
                  <span style={{ fontSize: ".78rem", color: "var(--muted)", maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{logoName}</span>
                </>
              )}
            </div>
            {hasLogo && (
              <div style={{ marginTop: 12 }}>
                <span className="helptext" style={{ display: "block", marginBottom: 4 }}>Logo size {logoScale}% — max 26% for reliable scanning</span>
                <input type="range" min={8} max={28} value={logoScale}
                  onChange={(e) => set({ logo: { ...style.logo, scale: Number(e.target.value) } })} style={{ width: "100%" }} />
              </div>
            )}
          </Section>

          <div className="sec">
            <div className="sec-body" style={{ paddingTop: 14 }}>
              <label style={{ fontWeight: 600, fontSize: ".9rem", display: "flex", gap: 8, alignItems: "center", cursor: "pointer" }}>
                <input type="checkbox" checked={gate} onChange={(e) => setGate(e.target.checked)} style={{ width: 16, height: 16 }} />
                Collect emails before redirecting
              </label>
              {gate && <div className="helptext" style={{ marginTop: 6 }}>Visitors see a short "leave your email" page first — good for offers and menus.</div>}
            </div>
          </div>

          {warnings.map((w) => <div key={w} className="banner err" style={{ fontSize: ".8rem" }}>{w}</div>)}
          {err && <div className="banner err">{err}</div>}
          {ok && <div className="banner ok">{ok}</div>}

          <div className="des-actions">
            <button className="btn btn-accent" disabled={busy}>{busy ? "Saving…" : editing ? "Save changes" : "Create code"}</button>
            {editing && <button type="button" className="btn btn-ghost" onClick={download}>Download PNG</button>}
            {!editing && <Link to="/app" className="btn btn-ghost">Cancel</Link>}
          </div>
        </form>
      </div>

      {/* RIGHT: preview (sticky only on wide screens, hideable everywhere) */}
      <div className="card des-preview" style={{ padding: 16 }}>
        <div className="label-inline">
          <span className="field" style={{ margin: 0 }}>Live preview</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowPreview(!showPreview)}>
            {showPreview ? "Hide preview" : "Show preview"}
          </button>
        </div>
        {showPreview && (
          <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 280, background: "repeating-conic-gradient(#eee 0% 25%, #fff 0% 50%) 0 0 / 22px 22px", borderRadius: 12, padding: 14, marginTop: 10 }}>
              {pv ? <img src={pv} alt="Your QR code preview" style={{ width: "100%", maxWidth: 280, borderRadius: 10, boxShadow: "0 10px 30px rgba(0,0,0,.14)" }} /> : <div className="spin" />}
            </div>
            <div className="helptext" style={{ marginTop: 8, textAlign: "center" }}>Scannable by design — every style is decode-tested.</div>
          </>
        )}
      </div>
    </div>
  );
}
