import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Routes, Route, Navigate, Link, useNavigate } from "react-router-dom";
import { api } from "./api";
import Landing from "./pages/Landing";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import EditorPage from "./pages/EditorPage";
import CodePage from "./pages/CodePage";

const Auth = createContext(null);
export const useAuth = () => useContext(Auth);

function Nav() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <nav className="topnav">
      <div className="wrap topnav-inner">
        <Link to="/" className="brand">QR<b>Direct</b></Link>
        <div className="nav-links" style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <a className="navlink" href="/#pricing">Pricing</a>
          <a className="navlink" href="/#how">How it works</a>
          {user ? (
            <>
              <Link className="navlink" to="/app">My codes</Link>
              <span style={{ fontSize: ".78rem", color: "var(--muted)" }}>{user.name || user.email}</span>
              <button className="btn btn-ghost btn-sm" onClick={async () => { await api.logout().catch(() => {}); logout(); nav("/"); }}>Log out</button>
            </>
          ) : (
            <>
              <Link className="navlink" to="/login">Log in</Link>
              <Link to="/register" className="btn btn-dark btn-sm" style={{ padding: "8px 16px" }}>Start free</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="spin" />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try { setUser((await api.me()).user); } catch (e) { setUser(null); } finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const logout = useCallback(() => { setUser(null); }, []);

  return (
    <Auth.Provider value={{ user, loading, logout, refresh }}>
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<AuthPage mode="login" onDone={refresh} />} />
        <Route path="/register" element={<AuthPage mode="register" onDone={refresh} />} />
        <Route path="/app" element={<Protected><Dashboard /></Protected>} />
        <Route path="/app/new" element={<Protected><EditorPage /></Protected>} />
        <Route path="/app/c/:slug" element={<Protected><CodePage /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Auth.Provider>
  );
}
