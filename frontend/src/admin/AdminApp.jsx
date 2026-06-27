import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/admin/components/Layout";
import Login from "@/admin/pages/Login";
import Dashboard from "@/admin/pages/Dashboard";
import Staff from "@/admin/pages/Staff";
import Simulation from "@/admin/pages/Simulation";
import Routing from "@/admin/pages/Routing";
import { RequireAuth } from "@/shared/auth/AuthContext";

// Control Center (Admin) — mounted at "/admin". Admin role only.
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
        <Route path="staff" element={<Staff />} />
        <Route path="simulation" element={<Simulation />} />
        <Route path="routing" element={<Routing />} />
      </Route>
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}
