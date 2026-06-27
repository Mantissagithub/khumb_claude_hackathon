import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.jsx";
import { Toaster } from "@/shared/ui/sonner";
import { AuthProvider } from "@/shared/auth/AuthContext";
import { PublicAuthProvider } from "@/public/auth/PublicAuthContext";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <PublicAuthProvider>
          <App />
        </PublicAuthProvider>
      </AuthProvider>
      <Toaster theme="light" position="bottom-right" />
    </BrowserRouter>
  </StrictMode>
);
