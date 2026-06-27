import { createRoot } from "react-dom/client";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import "../index.css";
import AdminApp from "@/admin/AdminApp";
import { Toaster } from "@/shared/ui/sonner";
import { AuthProvider } from "@/shared/auth/AuthContext";
createRoot(document.getElementById("root")).render(
  <HashRouter>
    <AuthProvider>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="*" element={<Navigate to="/admin/login" replace />} />
      </Routes>
    </AuthProvider>
    <Toaster theme="light" position="bottom-right" />
  </HashRouter>
);
