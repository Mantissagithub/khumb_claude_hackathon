import { useEffect, useState, useCallback } from "react";
import {
  Loader2, Check, X, HandHeart, ArrowLeftRight, ScanFace, MapPin, Sparkles, ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Badge } from "@/shared/ui/badge";
import { Avatar, AvatarImage, AvatarFallback } from "@/shared/ui/avatar";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  listReports, matchReport, confirmReportMatch, rejectReport, reuniteReport, reportMedia,
} from "@/shared/authApi";
import { verdictFromScore, faceEngineLive } from "@/shared/faceApi";

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
      <Avatar size="lg" className="size-40 rounded-2xl">
        {photo && <AvatarImage src={photo} alt={name} className="rounded-2xl" />}
        <AvatarFallback className="rounded-2xl text-4xl">{initials(name)}</AvatarFallback>
      </Avatar>
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

      // Pre-confirmed matches need no scoring; the rest get matched in parallel.
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

      const matched = await Promise.all(
        searching.map((r) => matchReport(r.id, 3).then((c) => ({ r, c })).catch(() => ({ r, c: [] })))
      );

      const seenPairs = new Set(); // dedupe report↔report matches found in both directions
      for (const { r: report, c: candidates } of matched) {
        const top = candidates[0];
        if (!top) {
          active.push({ report, match: { name: "—", caption: "No candidate yet", photo: null }, verdict: verdictFromScore(0), kind: "active" });
          continue;
        }
        if (top.source === "report") {
          const key = [String(report.id), String(top.ref_id)].sort().join("-");
          if (seenPairs.has(key)) continue;
          seenPairs.add(key);
        }
        const verdict = verdictFromScore(top.score, { second: candidates[1]?.score, reasonHint: top.reason });
        const match = resolveMatch(report, top, byId);
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
        description="Lost ↔ found matches surfaced by face recognition. Confirm the borderline ones; the system auto-approves the confident ones."
      >
        <Badge
          variant="outline"
          className={faceEngineLive ? "border-success/30 bg-success/15 text-success" : "border-info/30 bg-info/15 text-info"}
        >
          <ScanFace className="mr-1.5 size-3" />
          Face engine: {faceEngineLive ? "live" : "fallback matcher"}
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
