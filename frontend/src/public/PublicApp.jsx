import { Routes, Route, Navigate, Link } from "react-router-dom";
import Landing from "@/public/pages/Landing";
import NewReport from "@/public/pages/NewReport";
import Track from "@/public/pages/Track";
import MyReports from "@/public/pages/MyReports";
import ReportStatus from "@/public/pages/ReportStatus";
import { RequirePhone } from "@/public/auth/PublicAuthContext";
import { LanguageProvider, useLang } from "@/public/i18n/LanguageContext";
import LanguageSelect from "@/public/i18n/LanguageSelect";
import LanguageSwitcher from "@/public/i18n/LanguageSwitcher";

function TopBar() {
  const { t } = useLang();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-xl items-center justify-between gap-2 px-4 py-2">
        <Link to="/" className="flex items-center gap-2" aria-label={t("common.home")}>
          <div className="grid size-8 place-items-center rounded-md bg-sig-coral text-sm font-semibold text-white">
            स
          </div>
          <span className="text-base font-semibold tracking-tight">{t("brand.name")}</span>
        </Link>
        <LanguageSwitcher />
      </div>
    </header>
  );
}

// Public (citizen) surface — mounted at "/". Open submit; phone-OTP to view.
const RTL_LANGS = ["ur", "ks"];

function PublicShell() {
  const { chosen, lang } = useLang();
  if (!chosen) return <LanguageSelect />;

  return (
    <div className="min-h-svh bg-background" dir={RTL_LANGS.includes(lang) ? "rtl" : "ltr"}>
      <TopBar />
      <Routes>
        <Route index element={<Landing />} />
        <Route path="new" element={<NewReport />} />
        <Route path="track" element={<Track />} />
        <Route path="reports" element={<RequirePhone><MyReports /></RequirePhone>} />
        <Route path="reports/:id" element={<RequirePhone><ReportStatus /></RequirePhone>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function PublicApp() {
  return (
    <LanguageProvider>
      <PublicShell />
    </LanguageProvider>
  );
}
