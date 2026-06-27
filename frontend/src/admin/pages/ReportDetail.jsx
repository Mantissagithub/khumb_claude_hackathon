import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Loader2, MapPin, Phone, ImageOff, CalendarClock } from "lucide-react";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Card, CardContent } from "@/shared/ui/card";
import { getCase, mediaUrl } from "@/shared/authApi";

const initials = (n) => (n || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

function Field({ label, value }) {
  if (value == null || value === "") return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm text-foreground">{value}</p>
    </div>
  );
}

export default function ReportDetail() {
  const { id } = useParams();
  const [c, setC] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setC(null);
    setError(null);
    getCase(id).then(setC).catch((e) => setError(e.message));
  }, [id]);

  const photo = c && mediaUrl(c.photo_path);

  return (
    <>
      <Link to="/admin/reports" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All reports
      </Link>

      {error ? (
        <Card className="border-border bg-card"><CardContent className="py-16 text-center text-sm text-danger">{error}</CardContent></Card>
      ) : !c ? (
        <div className="flex items-center justify-center py-24 text-muted-foreground"><Loader2 className="size-5 animate-spin" /></div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          {/* Photo */}
          <Card className="overflow-hidden border-border bg-card">
            <div className="aspect-square w-full overflow-hidden bg-muted">
              {photo ? (
                <img src={photo} alt={c.name || "person"} className="size-full object-cover" />
              ) : (
                <div className="flex size-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-surface-2 to-surface-3 text-muted-foreground">
                  <span className="grid size-20 place-items-center rounded-full bg-card text-2xl font-medium text-foreground">{initials(c.name)}</span>
                  <span className="flex items-center gap-1 text-xs"><ImageOff className="size-3.5" /> no photo on file</span>
                </div>
              )}
            </div>
            <CardContent className="space-y-1 p-4">
              <div className="flex items-center justify-between gap-2">
                <h1 className="truncate text-xl font-semibold tracking-tight">{c.name || "Unknown"}</h1>
                <StatusBadge status={c.status} />
              </div>
              <p className="font-mono text-xs text-muted-foreground">{c.case_id}</p>
            </CardContent>
          </Card>

          {/* Details */}
          <div className="space-y-6">
            <Card className="border-border bg-card">
              <CardContent className="grid grid-cols-2 gap-5 p-5 sm:grid-cols-3">
                <Field label="Type" value={<span className="capitalize">{c.type}</span>} />
                <Field label="Gender" value={<span className="capitalize">{c.gender}</span>} />
                <Field label="Age band" value={c.age_band} />
                <Field label="Language" value={c.language} />
                <Field label="Zone" value={c.zone} />
                <Field label="State / District" value={[c.district, c.state].filter(Boolean).join(", ")} />
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="space-y-4 p-5">
                <Field label="Physical description" value={c.physical_description} />
                {c.transcript_en && <Field label="Transcript (EN)" value={c.transcript_en} />}
                {c.transcript && !c.transcript_en && <Field label="Transcript" value={c.transcript} />}
                {c.remarks && <Field label="Remarks" value={c.remarks} />}
              </CardContent>
            </Card>

            <Card className="border-border bg-card">
              <CardContent className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2">
                {(c.last_seen_location || c.reporting_center) && (
                  <div className="flex items-start gap-2">
                    <MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Location</p>
                      <p className="text-sm">{c.last_seen_location || c.reporting_center}</p>
                      {c.lat != null && <p className="text-xs text-muted-foreground">{Number(c.lat).toFixed(4)}, {Number(c.lng).toFixed(4)}</p>}
                    </div>
                  </div>
                )}
                {c.reporter_mobile && (
                  <div className="flex items-start gap-2">
                    <Phone className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reporter</p>
                      <p className="text-sm">{c.reporter_mobile}</p>
                    </div>
                  </div>
                )}
                {c.reported_at && (
                  <div className="flex items-start gap-2">
                    <CalendarClock className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reported</p>
                      <p className="text-sm">{String(c.reported_at).slice(0, 19).replace("T", " ")}</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
