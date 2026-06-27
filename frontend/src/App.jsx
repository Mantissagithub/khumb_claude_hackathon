import { Routes, Route } from "react-router-dom";
import PublicApp from "@/public/PublicApp";
import OperatorApp from "@/operator/OperatorApp";
import AdminApp from "@/admin/AdminApp";

// Three role surfaces, three link bases, one deployment:
//   Public          → /          (apps owner: public agent)
//   Operator center → /ops       (apps owner: operator agent)
//   Control center  → /admin     (apps owner: admin agent)
// This file is the only routing coordination point — each agent owns its folder.
export default function App() {
  return (
    <Routes>
      <Route path="/ops/*" element={<OperatorApp />} />
      <Route path="/admin/*" element={<AdminApp />} />
      <Route path="/*" element={<PublicApp />} />
    </Routes>
  );
}
