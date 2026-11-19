import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout, RequireAuth } from "./components/Layout";
import Home from "./pages/Home";
import { Login, Register } from "./pages/AuthPages";
import Dashboard from "./pages/Dashboard";
import { ReportFound, ReportLost } from "./pages/ReportForms";
import { MatchDetail, Matches } from "./pages/Matches";
import Staff from "./pages/Staff";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<AppLayout />}>
        <Route index element={<Home />} />
        <Route element={<RequireAuth />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="report-lost" element={<ReportLost />} />
          <Route path="report-found" element={<ReportFound />} />
          <Route path="matches" element={<Matches />} />
          <Route path="matches/:id" element={<MatchDetail />} />
        </Route>
        <Route element={<RequireAuth staff />}>
          <Route path="staff" element={<Staff />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
