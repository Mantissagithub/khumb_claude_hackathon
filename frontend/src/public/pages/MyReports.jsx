import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, FilePlus2, LogOut, ChevronRight, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { listMyReports } from "@/public/publicApi";
import { usePublicAuth } from "@/public/auth/PublicAuthContext";
import { useLang } from "@/public/i18n/LanguageContext";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";

export default function MyReports() {
  const navigate = useNavigate();
  const { t } = useLang();
  const { phone, signOut } = usePublicAuth();
  const [reports, setReports] = useState(null);

  useEffect(() => {
    listMyReports().then(setReports).catch((e) => { toast.error(e.message); setReports([]); });
  }, []);

  return (
    <div className="bg-background px-4 py-8">
      <div className="mx-auto w-full max-w-xl">
        <Link to="/" className="mb-4 inline-flex items-center gap-1 text-base text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" /> {t("common.back")}
        </Link>

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{t("myReports.title")}</h1>
            <p className="text-sm text-muted-foreground">{phone}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={async () => { await signOut(); navigate("/"); }}>
            <LogOut className="size-4" /> {t("myReports.signOut")}
          </Button>
        </div>

        <Button asChild className="mb-4 h-14 w-full text-base">
          <Link to="/new"><FilePlus2 className="size-5" /> {t("myReports.fileNew")}</Link>
        </Button>

        {reports === null ? (
          <div className="grid place-items-center py-16 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : reports.length === 0 ? (
          <Card className="border-border bg-card">
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              {t("myReports.empty")}
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {reports.map((r) => (
              <Link key={r.id} to={`/reports/${r.id}`}>
                <Card className="border-border bg-card transition-colors hover:border-primary/50">
                  <CardContent className="flex items-center justify-between gap-3 p-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={r.status} />
                        <span className="text-xs text-muted-foreground">{t(`typeLabel.${r.report_type}`)}</span>
                      </div>
                      <p className="mt-1 truncate font-medium">{r.person_name || t("myReports.unnamed")}</p>
                      <p className="truncate text-sm text-muted-foreground">
                        {r.description || r.location_text || `#${r.id}`}
                      </p>
                    </div>
                    <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
