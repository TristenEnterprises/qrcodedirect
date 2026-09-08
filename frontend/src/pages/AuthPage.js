import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

export default function AuthPage({ mode, onDone }) {
  const isLogin = mode === "login";
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      const b = isLogin ? { email, password: pw } : { name, email, password: pw };
      await (isLogin ? api.login(b) : api.register(b));
      await onDone();
      nav("/app");
    } catch (ex) { setErr(ex.message || "Something went wrong"); }
    finally { setBusy(false); }
  }

  return (
    <main style={{ minHeight: "calc(100vh - 60px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 16px" }}>
      <div className="card" style={{ width: "100%", maxWidth: 420, padding: "30px 28px" }}>
        <h1 className="h" style={{ fontSize: "1.6rem" }}>{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p style={{ color: "var(--muted)", fontSize: ".9rem", marginTop: 6 }}>
          {isLogin ? "Sign in to manage your codes." : "Free to start — your codes are live the moment you save."}
        </p>
        <form onSubmit={submit}>
          {!isLogin && (
            <>
              <label className="field">Name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name or business" autoComplete="name" />
            </>
          )}
          <label className="field">Email</label>
          <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" />
          <label className="field">Password</label>
          <input className="input" type="password" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} placeholder={isLogin ? "Your password" : "At least 8 characters"} autoComplete={isLogin ? "current-password" : "new-password"} />
          {err && <div className="err">{err}</div>}
          <button className="btn btn-dark" disabled={busy} style={{ width: "100%", marginTop: 20 }}>
            {busy ? "One moment…" : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>
        <div style={{ marginTop: 18, fontSize: ".88rem", color: "var(--muted)", textAlign: "center" }}>
          {isLogin ? <>New here? <Link to="/register">Create a free account</Link></> : <>Already have an account? <Link to="/login">Sign in</Link></>}
        </div>
      </div>
    </main>
  );
}
