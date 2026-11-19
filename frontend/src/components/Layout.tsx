import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../theme";
import { Icon } from "./Icon";
import { Loading } from "./States";

export const Logo = ({ to = "/" }: { to?: string }) => (
  <Link className="logo" to={to}><span className="logo-mark"><Icon name="search" size={15} /></span>FindBack</Link>
);

export function ThemeButton() {
  const { theme, toggle } = useTheme();
  return (
    <button className="icon-btn" onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
      <Icon name={theme === "dark" ? "sun" : "moon"} />
    </button>
  );
}

const UnreadCtx = createContext<{ count: number; refresh: () => void }>({ count: 0, refresh: () => {} });
export const useUnread = () => useContext(UnreadCtx);

/** Signed-in layout: sidebar + content. */
export function AppShell() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [count, setCount] = useState(0);
  const refresh = useCallback(() => {
    api.notifications().then(n => setCount(n.filter(x => !x.is_read).length)).catch(() => {});
  }, []);
  useEffect(() => { refresh(); const t = setInterval(refresh, 60_000); return () => clearInterval(t); }, [refresh, loc.pathname]);
  const value = useMemo(() => ({ count, refresh }), [count, refresh]);
  if (!user) return null;
  return (
    <UnreadCtx.Provider value={value}>
      <div className="shell">
        <aside className="sidebar">
          <Logo to="/dashboard" />
          <nav aria-label="Main">
            <NavLink className="nav-link" to="/dashboard" end><Icon name="grid" />Overview</NavLink>
            <NavLink className="nav-link" to="/matches"><Icon name="inbox" />Matches</NavLink>
            <NavLink className="nav-link" to="/dashboard?tab=notifications">
              <Icon name="bell" />Notifications{count > 0 && <span className="badge">{count}</span>}</NavLink>
            <NavLink className="nav-link" to="/profile"><Icon name="user" />My profile</NavLink>
            <div className="nav-group">Report</div>
            <NavLink className="nav-link" to="/report-lost"><Icon name="box" />Lost item</NavLink>
            <NavLink className="nav-link" to="/report-found"><Icon name="box" />Found item</NavLink>
            {user.role === "staff" && (<>
              <div className="nav-group">Staff</div>
              <NavLink className="nav-link" to="/staff"><Icon name="shield" />Staff workspace</NavLink></>)}
          </nav>
          <div className="sidebar-foot">
            <Link to="/profile" className="avatar" aria-label="My profile" style={{ textDecoration: "none" }}>{user.name.slice(0, 1).toUpperCase()}</Link>
            <div className="who"><b>{user.name}</b><span className="muted tiny">{user.role === "staff" ? "Staff" : "User"}</span></div>
            <ThemeButton />
            <button className="icon-btn" aria-label="Log out" onClick={() => { logout(); nav("/"); }}><Icon name="logout" /></button>
          </div>
        </aside>
        <main className="main"><Outlet /></main>
      </div>
    </UnreadCtx.Provider>
  );
}

/** Redirects to /login when signed out; optional staff-only gate. */
export function RequireAuth({ staff = false }: { staff?: boolean }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <main className="main"><Loading /></main>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  if (staff && user.role !== "staff") {
    return <div className="empty"><h3>Staff only</h3><p>You do not have access to this page.</p></div>;
  }
  return <Outlet />;
}
