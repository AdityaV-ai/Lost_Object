import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Loading } from "./States";

const Brand = () => (
  <Link className="brand" to="/"><span className="brand-mark">F</span><span>FindBack<small>Campus Lost &amp; Found</small></span></Link>
);

export function Header() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <header className="site-header">
      <Brand />
      <nav>
        {user ? (<>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/report-lost">Report lost</NavLink>
          <NavLink to="/report-found">Report found</NavLink>
          <NavLink to="/matches">Matches</NavLink>
          {user.role === "staff" && <NavLink to="/staff">Staff</NavLink>}
        </>) : (<>
          <a href="/#how">How it works</a>
          <NavLink to="/report-lost">Report lost</NavLink>
          <NavLink to="/report-found">Report found</NavLink>
        </>)}
      </nav>
      <div className="nav-actions">
        {user ? (<>
          <span className="user-chip">{user.name}</span>
          <button className="btn btn-ghost" onClick={() => { logout(); nav("/"); }}>Log out</button>
        </>) : (<>
          <Link className="btn btn-ghost" to="/login">Log in</Link>
          <Link className="btn btn-primary" to="/register">Create account</Link>
        </>)}
      </div>
    </header>
  );
}

export const Footer = () => (
  <footer className="footer"><div className="wrap footer-inner"><Brand />
    <p>Helping campus communities reunite with what matters.</p>
    <span>© FindBack · Institutional recovery platform</span></div></footer>
);

export function AppLayout() {
  return (<><Header /><Outlet /><Footer /></>);
}

/** Redirects to /login when signed out; optional staff-only gate. */
export function RequireAuth({ staff = false }: { staff?: boolean }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <main className="page-wrap"><Loading /></main>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (staff && user.role !== "staff") {
    return <main className="page-wrap"><div className="empty-state"><h3>Staff only</h3><p>You do not have access to this page.</p></div></main>;
  }
  return <Outlet />;
}
