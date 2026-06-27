import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/operator/components/Layout";
import Login from "@/operator/pages/Login";
import Reports from "@/operator/pages/Reports";
import Queue from "@/operator/pages/Queue";
import FaceSearch from "@/operator/pages/FaceSearch";
import VoiceMatch from "@/operator/pages/VoiceMatch";
import { RequireAuth } from "@/shared/auth/AuthContext";

// Operator / Lost & Found center — mounted at "/ops". Any staff role.
export default function OperatorApp() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route
        element={
          <RequireAuth loginPath="/ops/login">
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Reports />} />
        <Route path="queue" element={<Queue />} />
        <Route path="face" element={<FaceSearch />} />
        <Route path="voice" element={<VoiceMatch />} />
      </Route>
      <Route path="*" element={<Navigate to="/ops" replace />} />
    </Routes>
  );
}
