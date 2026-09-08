import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Routes, Route, Navigate, Link, useNavigate, useLocation } from "react-router-dom";
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
  const loc = useLocation();
  const onHome = loc.pathname === "/";
  return (
    <nav className="topnav">
      <div className="wrap topnav-inner">
        <Link to="/" className="brand">QR<b>Direct</b></Link>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {onHome && (
            <>
              <a className="btn btn-ghost btn-sm" href="/#how">How it works</a>
              <a className="btn btn-ghost btn-sm" href="/#pricing">Pricing</a>
            </>
          )}
          {user ? (
            <>
              <Link to="/app" className="btn btn-ghost btn-sm">My codes</Link>
              <Link to="/app/new" className="btn btn-dark btn-sm">New code</Link>
              <span className="nav-name" style={{ fontSize: ".78rem", color: "var(--muted)", maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.name || user.email}</span>
              <button className="btn btn-ghost btn-sm" onClick={async () => { await api.logout().catch(() => {}); logout(); nav("/"); }}>Log out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost btn-sm">Log in</Link>
              <Link to="/register" className="btn btn-dark btn-sm">Start free</Link>
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
