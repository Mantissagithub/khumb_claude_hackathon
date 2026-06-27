import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/admin/components/Layout";
import Login from "@/admin/pages/Login";
import Dashboard from "@/admin/pages/Dashboard";
import Alerts from "@/admin/pages/Alerts";
import Reports from "@/admin/pages/Reports";
import ReportDetail from "@/admin/pages/ReportDetail";
import MapView from "@/admin/pages/MapView";
import Staff from "@/admin/pages/Staff";
import { RequireAuth } from "@/shared/auth/AuthContext";

// Control Center (Admin) — mounted at "/admin". Admin role only.
// Nav surfaces: Dashboard · Alerts · Reports · Map. (Staff stays reachable
// at /admin/staff but is off-nav; Simulation/Routing are parked.)
export default function AdminApp() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route
        element={
          <RequireAuth loginPath="/admin/login" role="admin">
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="reports" element={<Reports />} />
        <Route path="reports/:id" element={<ReportDetail />} />
        <Route path="map" element={<MapView />} />
        <Route path="staff" element={<Staff />} />
      </Route>
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}
