import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell, RequireAuth } from "./components/Layout";
import Landing from "./pages/Landing";
import { Login, Register } from "./pages/AuthPages";
import Overview from "./pages/Overview";
import { ReportFound, ReportLost } from "./pages/ReportForms";
import Matches from "./pages/Matches";
import Staff from "./pages/Staff";
import Profile from "./pages/Profile";

export default function App() {
  return (
    <Routes>
      <Route index element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="dashboard" element={<Overview />} />
          <Route path="report-lost" element={<ReportLost />} />
          <Route path="report-found" element={<ReportFound />} />
          <Route path="matches" element={<Matches />} />
          <Route path="profile" element={<Profile />} />
          <Route element={<RequireAuth staff />}>
            <Route path="staff" element={<Staff />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
