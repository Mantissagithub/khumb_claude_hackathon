import { useEffect, useState, useCallback } from "react";
import {
  Loader2, Check, X, HandHeart, ArrowLeftRight, ScanFace, MapPin, Sparkles, ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Badge } from "@/shared/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  listReports, confirmReportMatch, rejectReport, reuniteReport, reportMedia,
} from "@/shared/authApi";
import { verdictFromScore } from "@/shared/faceApi";
import { descriptorFor, distance, faceVerdict } from "@/admin/lib/faceMatch";

const TYPE_LABEL = { lost_self: "Lost (self)", seeking: "Seeking", found: "Found person" };
const initials = (n) => (n || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

const BAND_STYLE = {
  STRONG: "bg-success/15 text-success border-success/30",
  LIKELY: "bg-warning/15 text-warning border-warning/30",
  POSSIBLE: "bg-info/15 text-info border-info/30",
  NO_MATCH: "bg-muted text-muted-foreground border-border",
};

function BandChip({ verdict }) {
  return (
    <Badge variant="outline" className={`gap-1 rounded-full ${BAND_STYLE[verdict.band]}`}>
      <ScanFace className="size-3" />
      {verdict.confidence_pct}% · {verdict.band.replace("_", " ").toLowerCase()}
    </Badge>
  );
}

function PersonFace({ name, photo, caption }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center gap-2 text-center">
      <div className="aspect-[3/4] w-40 overflow-hidden rounded-xl border border-border bg-muted sm:w-44">
        {photo ? (
          <img src={photo} alt={name} loading="lazy" className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center bg-gradient-to-br from-surface-2 to-surface-3 text-3xl font-medium text-muted-foreground">
            {initials(name)}
          </div>
        )}
      </div>
      <div className="min-w-0">
        <p className="truncate text-base font-semibold">{name || "Unknown"}</p>
        <p className="truncate text-xs text-muted-foreground">{caption}</p>
      </div>
    </div>
  );
}

// Resolve the "other side" of a match to a name + photo for the card.
function resolveMatch(report, candidate, byId) {
  if (candidate) {
    const other = candidate.source === "report" ? byId[candidate.ref_id] : null;
    return {
      source: candidate.source,
      ref_id: candidate.ref_id,
      name: candidate.name,
      caption: candidate.source === "case" ? `Registry · ${candidate.ref_id}` : `Report #${candidate.ref_id}`,
      photo: other ? reportMedia(other.photo_path) : null,
      reason: candidate.reason,
      score: candidate.score,
      where: candidate.zone,
    };
  }
  // already-confirmed report: build from its own matched fields
  const other = report.matched_report_id ? byId[report.matched_report_id] : null;
  return {
    source: report.matched_report_id ? "report" : "case",
    ref_id: report.matched_report_id || report.matched_case_id,
    name: other?.person_name || report.matched_case_id || "Matched record",
    caption: report.found_center ? `Found · ${report.found_center}` : "Confirmed match",
    photo: reportMedia(report.found_photo_path || other?.photo_path),
    where: report.found_center,
  };
}

function AlertCard({ alert, onConfirm, onReject, onReunite, busy }) {
  const { report, match, verdict, kind } = alert;
  return (
    <Card className="border-border bg-card">
      <CardContent className="p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <Badge variant="outline" className="rounded-full">{TYPE_LABEL[report.report_type] || report.report_type}</Badge>
          <BandChip verdict={verdict} />
        </div>

        <div className="flex items-center gap-3">
          <PersonFace
            name={report.person_name}
            photo={reportMedia(report.photo_path)}
            caption={report.location_text || `Report #${report.id}`}
          />
          <ArrowLeftRight className="size-5 shrink-0 text-muted-foreground" />
          <PersonFace name={match.name} photo={match.photo} caption={match.caption} />
        </div>

        <p className="mt-3 text-sm font-medium text-foreground">{verdict.label}</p>
        <ul className="mt-1.5 space-y-1">
          {verdict.reasons.slice(0, 3).map((r, i) => (
            <li key={i} className="flex gap-1.5 text-xs text-muted-foreground">
              <Sparkles className="mt-0.5 size-3 shrink-0 text-mustard-foreground/70" /> {r}
            </li>
          ))}
        </ul>
        {match.where && (
          <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="size-3" /> {match.where}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {kind === "review" && (
            <>
              <Button size="sm" onClick={() => onConfirm(alert)} disabled={busy}>
                <Check className="size-4" /> Confirm match
              </Button>
              <Button size="sm" variant="outline" onClick={() => onReject(alert)} disabled={busy}>
                <X className="size-4" /> Reject
              </Button>
            </>
          )}
          {kind === "auto" && (
            <>
              <Badge variant="outline" className="gap-1 rounded-full border-success/30 bg-success/15 text-success">
                <ShieldCheck className="size-3" /> Auto-approved
              </Badge>
              {report.status !== "reunited" && (
                <Button size="sm" variant="outline" onClick={() => onReunite(alert)} disabled={busy}>
                  <HandHeart className="size-4" /> Mark reunited
                </Button>
              )}
            </>
          )}
          {kind === "active" && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Comparing against registry & found reports…
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function Alerts() {
  const [tab, setTab] = useState("review");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [buckets, setBuckets] = useState({ review: [], auto: [], active: [] });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const reports = await listReports();
      const byId = Object.fromEntries(reports.map((r) => [String(r.id), r]));
      // the "found" side of a confirmed/linked pair — show only the anchor.
      const linked = new Set(reports.filter((r) => r.matched_report_id).map((r) => String(r.matched_report_id)));
      const review = [], auto = [], active = [];

      // Embed every report photo once with on-device face recognition.
      const descById = Object.fromEntries(
        await Promise.all(reports.map(async (r) => [String(r.id), await descriptorFor(reportMedia(r.photo_path))]))
      );

      const isOpposite = (a, b) =>
        (a.report_type === "found" && (b.report_type === "seeking" || b.report_type === "lost_self")) ||
        ((a.report_type === "seeking" || a.report_type === "lost_self") && b.report_type === "found");

      // Pre-confirmed matches need no scoring; the rest get matched by face.
      const searching = [];
      for (const report of reports) {
        if (linked.has(String(report.id))) continue;
        const resolved = report.review_status === "confirmed" || report.status !== "searching";
        if (resolved && (report.matched_report_id || report.matched_case_id)) {
          auto.push({ report, match: resolveMatch(report, null, byId), verdict: verdictFromScore(0.7), kind: "auto" });
        } else if (report.status === "searching") {
          searching.push(report);
        }
      }

      const seenPairs = new Set(); // dedupe report↔report matches found in both directions
      for (const report of searching) {
        const qd = descById[String(report.id)];
        // best opposite-direction report by face distance
        let best = null;
        if (qd) {
          for (const cand of searching) {
            if (cand.id === report.id || !isOpposite(report, cand)) continue;
            const d = distance(qd, descById[String(cand.id)]);
            if (d == null) continue;
            if (!best || d < best.d) best = { cand, d };
          }
        }
        if (!best) {
          active.push({
            report,
            match: { name: "—", caption: qd ? "No candidate yet" : "No face in photo", photo: null },
            verdict: {
              band: "NO_MATCH", confidence_pct: 0,
              label: qd ? "No match found" : "No usable face",
              reasons: [
                qd ? "No opposite-direction report matches this face yet." : "No clear face detected in this photo — can't compare faces.",
                "On-device face recognition · decision support only.",
              ],
            },
            kind: "active",
          });
          continue;
        }
        const key = [String(report.id), String(best.cand.id)].sort().join("-");
        if (seenPairs.has(key)) continue;
        seenPairs.add(key);
        const verdict = faceVerdict(best.d);
        const match = {
          source: "report", ref_id: String(best.cand.id), name: best.cand.person_name,
          caption: `Report #${best.cand.id}`, photo: reportMedia(best.cand.photo_path),
          where: best.cand.location_text || best.cand.found_center,
        };
        if (verdict.band === "STRONG") auto.push({ report, match, verdict, kind: "auto" });
        else if (verdict.band === "NO_MATCH") active.push({ report, match, verdict, kind: "active" });
        else review.push({ report, match, verdict, kind: "review" });
      }
      setBuckets({ review, auto, active });
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function act(fn, msg) {
    setBusy(true);
    try { await fn(); toast.success(msg); await load(); }
    catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  const onConfirm = (a) => act(() => confirmReportMatch(a.report.id, a.match.source, a.match.ref_id, "Confirmed from Alerts"), "Match confirmed");
  const onReject = (a) => act(() => rejectReport(a.report.id, "Rejected from Alerts"), "Match rejected");
  const onReunite = (a) => act(() => reuniteReport(a.report.id), "Marked reunited");

  const TABS = [
    { id: "review", label: "Review required", n: buckets.review.length },
    { id: "auto", label: "Auto-approved", n: buckets.auto.length },
    { id: "active", label: "Actively matching", n: buckets.active.length },
  ];
  const items = buckets[tab];

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Lost ↔ found matches ranked by on-device face recognition. Confirm the borderline ones; the system auto-approves the confident ones."
      >
        <Badge variant="outline" className="border-success/30 bg-success/15 text-success">
          <ScanFace className="mr-1.5 size-3" />
          Face engine: on-device
        </Badge>
      </PageHeader>

      <Tabs value={tab} onValueChange={setTab} className="mb-5">
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
              <Badge variant="outline" className="ml-1.5 rounded-full px-1.5 py-0 text-[10px]">{t.n}</Badge>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {loading ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-lg" />)}
        </div>
      ) : items.length === 0 ? (
        <Card className="border-dashed border-border bg-card">
          <CardContent className="py-16 text-center text-sm text-muted-foreground">
            No alerts in “{TABS.find((t) => t.id === tab)?.label}”.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {items.map((a) => (
            <AlertCard key={`${a.kind}-${a.report.id}`} alert={a} busy={busy}
              onConfirm={onConfirm} onReject={onReject} onReunite={onReunite} />
          ))}
        </div>
      )}
    </>
  );
}
