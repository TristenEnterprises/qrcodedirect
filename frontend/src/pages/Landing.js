import { Link } from "react-router-dom";

/* qrcodedirect.com storefront landing (8 Sep 2026) */
const DEMOS = [
  { slug: "demo-wedding", label: "Gradient · rounded", note: "Wedding invites" },
  { slug: "demo-menu", label: "Square · classic", note: "Restaurant menu" },
  { slug: "demo-art", label: "Angle gradient", note: "Art portfolio" },
];

const FEATURES = [
  ["🎨", "Make it yours", "Solid or gradient colours, square or rounded dots — match your brand in seconds, not with a developer."],
  ["⭐", "Your logo, centre stage", "Drop in your logo. The engine keeps every code scannable — with real decode tests behind it."],
  ["📈", "Know every scan", "See scans per day, country and device. Know exactly when your menu, flyer or van gets looked at."],
  ["🔗", "Your link, your code", "Dynamic codes — point them anywhere, change the destination any time, no reprint."],
  ["✉️", "Grow your list", "Optional email capture: a code that collects leads before it sends them to your page."],
  ["🖨️", "Print-ready", "High-resolution PNG and SVG exports for anything from a business card to a billboard."],
];

const PLANS = [
  { name: "Free", price: "£0", per: "forever", features: ["3 live codes", "Solid + gradient styling", "Scan counts", "QRDirect watermark-free PNG"], cta: "Start free", to: "/register" },
  { name: "Pro", price: "£9", per: "/month", features: ["100 live codes", "Logo on your code", "Full stats (country · device)", "Custom slug"], cta: "Start free", to: "/register" },
  { name: "Business", price: "£29", per: "/month", features: ["Unlimited codes", "Email capture pages", "Your own domain (white-label)", "Priority support"], cta: "Start free", to: "/register" },
];

export default function Landing() {
  return (
    <main>
      {/* HERO */}
      <section style={{ padding: "90px 0 70px", textAlign: "center", overflow: "hidden" }}>
        <div className="wrap">
          <p style={{ fontSize: ".72rem", letterSpacing: ".25em", textTransform: "uppercase", color: "var(--accent)", fontWeight: 700, marginBottom: 18 }}>Dynamic QR codes · designed by you</p>
          <h1 className="h" style={{ fontSize: "clamp(2.3rem,6vw,4.1rem)", lineHeight: 1.05, maxWidth: "15ch", margin: "0 auto" }}>
            QR codes that look like <span style={{ color: "var(--accent)" }}>you.</span>
          </h1>
          <p style={{ margin: "22px auto 0", maxWidth: 560, color: "var(--muted)", fontSize: "1.08rem" }}>
            Your colours. Your logo. Your link, always editable — and every scan tracked.
            Stop handing customers a black-and-white afterthought.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 32, flexWrap: "wrap" }}>
            <Link to="/register" className="btn btn-dark">Design your first code — free</Link>
            <a href="#how" className="btn btn-ghost">See how it works</a>
          </div>
          <div style={{ marginTop: 26, fontSize: ".82rem", color: "var(--muted)" }}>
            No account needed to look around · set-up takes 2 minutes
          </div>
        </div>
      </section>

      {/* DEMO GALLERY */}
      <section id="how" style={{ padding: "40px 0 70px", background: "var(--card)", borderBlock: "1px solid var(--line)" }}>
        <div className="wrap">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 26 }}>
            {DEMOS.map((d) => (
              <div key={d.slug} className="card" style={{ padding: 18, textAlign: "center" }}>
                <img src={`/qr/${d.slug}.png`} alt={d.label} style={{ width: "100%", maxWidth: 240, borderRadius: 12, background: "#fff", display: "block", margin: "0 auto" }} loading="lazy" />
                <div style={{ marginTop: 12, fontWeight: 700 }}>{d.label}</div>
                <div style={{ fontSize: ".82rem", color: "var(--muted)" }}>{d.note}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section style={{ padding: "76px 0" }}>
        <div className="wrap">
          <h2 className="h" style={{ fontSize: "clamp(1.7rem,4vw,2.6rem)", textAlign: "center" }}>Everything a code needs to <span style={{ color: "var(--accent)" }}>work harder</span></h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(290px,1fr))", gap: 26, marginTop: 42 }}>
            {FEATURES.map(([icon, t, body]) => (
              <div className="card" key={t} style={{ padding: 22 }}>
                <div style={{ fontSize: "1.7rem" }}>{icon}</div>
                <h3 style={{ marginTop: 10, fontWeight: 700 }}>{t}</h3>
                <p style={{ marginTop: 6, fontSize: ".92rem", color: "var(--muted)" }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing" style={{ padding: "70px 0", background: "var(--card)", borderBlock: "1px solid var(--line)" }}>
        <div className="wrap">
          <h2 className="h" style={{ fontSize: "clamp(1.7rem,4vw,2.6rem)", textAlign: "center" }}>Simple pricing</h2>
          <p style={{ textAlign: "center", color: "var(--muted)", marginTop: 8 }}>Start free. Upgrade when your codes are working.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(250px,1fr))", gap: 20, marginTop: 40, alignItems: "stretch" }}>
            {PLANS.map((p) => (
              <div className="card" key={p.name} style={{ padding: 26, display: "flex", flexDirection: "column" }}>
                <div style={{ fontWeight: 800, fontSize: "1.05rem" }}>{p.name}</div>
                <div style={{ margin: "12px 0 4px" }}><span className="h" style={{ fontSize: "2rem" }}>{p.price}</span> <span style={{ color: "var(--muted)", fontSize: ".86rem" }}>{p.per}</span></div>
                <ul style={{ listStyle: "none", margin: "14px 0 22px", display: "grid", gap: 8, flex: 1 }}>
                  {p.features.map((f) => <li key={f} style={{ fontSize: ".88rem", color: "var(--muted)", display: "flex", gap: 8 }}><span style={{ color: "var(--ok)" }}>✓</span>{f}</li>)}
                </ul>
                <Link to={p.to} className="btn btn-dark" style={{ width: "100%" }}>{p.cta}</Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding: "80px 0", textAlign: "center" }}>
        <div className="wrap">
          <h2 className="h" style={{ fontSize: "clamp(1.8rem,4vw,2.8rem)" }}>Two minutes from now,<br />your code could be <span style={{ color: "var(--accent)" }}>unmistakably yours.</span></h2>
          <Link to="/register" className="btn btn-dark" style={{ marginTop: 28, padding: "15px 30px", fontSize: "1.02rem" }}>Create my first code</Link>
        </div>
      </section>

      <footer style={{ borderTop: "1px solid var(--line)", padding: "26px 0", textAlign: "center", fontSize: ".8rem", color: "var(--muted)" }}>
        © {new Date().getFullYear()} QRCodeDirect · qrcodedirect.com
      </footer>
    </main>
  );
}
