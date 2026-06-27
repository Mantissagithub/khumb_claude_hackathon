import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Loader2, ArrowLeft, MapPin, Navigation, CheckCircle2, Search } from "lucide-react";
import { toast } from "sonner";
import { getMyReport, mediaUrl } from "@/public/publicApi";
import { useLang } from "@/public/i18n/LanguageContext";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";

function FoundMap({ lat, lng }) {
  if (lat == null || lng == null) return null;
  const d = 0.01;
  const bbox = `${lng - d},${lat - d},${lng + d},${lat + d}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <iframe title="Found location" src={src} className="h-52 w-full" loading="lazy" />
    </div>
  );
}

export default function ReportStatus() {
  const { id } = useParams();
  const { t } = useLang();
  const [r, setR] = useState(null);

  useEffect(() => {
    getMyReport(id).then(setR).catch((e) => { toast.error(e.message); setR(false); });
  }, [id]);

  if (r === null) {
    return <div className="grid min-h-svh place-items-center text-muted-foreground"><Loader2 className="size-5 animate-spin" /></div>;
  }
  if (r === false) {
    return <div className="grid min-h-svh place-items-center text-sm text-muted-foreground">{t("reportStatus.notFound")}</div>;
  }

  const isFound = r.status === "found" || r.status === "reunited";
  const hasGeo = r.found_lat != null && r.found_lng != null;

  return (
    <div className="min-h-svh bg-background px-4 py-8">
      <div className="mx-auto w-full max-w-xl">
        <Link to="/reports" className="mb-4 inline-flex items-center gap-1 text-base text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" /> {t("reportStatus.back")}
        </Link>

        {/* Status banner */}
        <Card className="mb-4 border-border bg-card">
          <CardContent className="flex items-center gap-3 py-5">
            {isFound ? <CheckCircle2 className="size-8 text-success" /> : <Search className="size-8 text-info" />}
            <div>
              <div className="flex items-center gap-2">
                <StatusBadge status={r.status} />
                <span className="font-mono text-xs text-muted-foreground">#{r.id}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {r.status === "searching" && t("reportStatus.searchingMsg")}
                {r.status === "found" && t("reportStatus.foundMsg")}
                {r.status === "reunited" && t("reportStatus.reunitedMsg")}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Found details */}
        {isFound && (
          <Card className="mb-4 border-success/30 bg-card">
            <CardHeader>
              <CardTitle className="text-base">{t("reportStatus.whereFound")}</CardTitle>
              <CardDescription>{t("reportStatus.whereFoundSub")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {r.found_photo_path && (
                <img src={mediaUrl(r.found_photo_path)} alt="Found person"
                  className="aspect-video w-full rounded-lg border border-border object-cover" />
              )}
              {r.found_center && (
                <p className="flex items-center gap-2 text-sm">
                  <MapPin className="size-4 text-primary" />
                  <span className="font-medium">{r.found_center}</span>
                </p>
              )}
              {hasGeo && (
                <>
                  <FoundMap lat={r.found_lat} lng={r.found_lng} />
                  <Button asChild className="w-full">
                    <a href={`https://www.google.com/maps/dir/?api=1&destination=${r.found_lat},${r.found_lng}`}
                       target="_blank" rel="noreferrer">
                      <Navigation className="size-4" /> {t("reportStatus.directions")}
                    </a>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        )}

        {/* Your report */}
        <Card className="border-border bg-card">
          <CardHeader><CardTitle className="text-base">{t("reportStatus.yourReport")}</CardTitle></CardHeader>
          <CardContent className="space-y-1.5 text-sm">
            <p><span className="text-muted-foreground">{t("reportStatus.fName")}</span> {r.person_name || "—"}</p>
            <p><span className="text-muted-foreground">{t("reportStatus.fGenderAge")}</span> {r.gender || "—"} · {r.age_band || "—"}</p>
            <p><span className="text-muted-foreground">{t("reportStatus.fLocation")}</span> {r.location_text || "—"}</p>
            <p><span className="text-muted-foreground">{t("reportStatus.fDescription")}</span> {r.description || "—"}</p>
            {r.photo_path && (
              <img src={mediaUrl(r.photo_path)} alt="" className="mt-2 aspect-square w-28 rounded-lg border border-border object-cover" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
