import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "@/public/pages/Landing";
import NewReport from "@/public/pages/NewReport";
import Track from "@/public/pages/Track";
import MyReports from "@/public/pages/MyReports";
import ReportStatus from "@/public/pages/ReportStatus";
import { RequirePhone } from "@/public/auth/PublicAuthContext";

// Public (citizen) surface — mounted at "/". Open submit; phone-OTP to view.
export default function PublicApp() {
  return (
    <Routes>
      <Route index element={<Landing />} />
      <Route path="new" element={<NewReport />} />
      <Route path="track" element={<Track />} />
      <Route path="reports" element={<RequirePhone><MyReports /></RequirePhone>} />
      <Route path="reports/:id" element={<RequirePhone><ReportStatus /></RequirePhone>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
