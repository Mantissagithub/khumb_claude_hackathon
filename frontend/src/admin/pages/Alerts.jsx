import { useEffect, useState, useCallback } from "react";
import {
  Loader2, Check, X, HandHeart, ArrowLeftRight, ScanFace, MapPin, Sparkles, ShieldCheck, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Badge } from "@/shared/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  listReports, listReportMatches, runFaceMatch, setMatchStatus,
  confirmReportMatch, reuniteReport, reportMedia,
} from "@/shared/authApi";

const TYPE_LABEL = { lost_self: "Lost (self)", seeking: "Seeking", found: "Found person" };
const initials = (n) => (n || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

const STRONG = 0.85;
function band(conf) {
  if (conf >= STRONG) return { key: "STRONG", label: "very likely", style: "bg-success/15 text-success border-success/30" };
  if (conf >= 0.6) return { key: "LIKELY", label: "likely", style: "bg-warning/15 text-warning border-warning/30" };
  if (conf >= 0.4) return { key: "POSSIBLE", label: "possible", style: "bg-info/15 text-info border-info/30" };
  return { key: "LOW", label: "weak", style: "bg-muted text-muted-foreground border-border" };
}

// which side is the searching person vs the found person
function sides(m) {
  const found = m.query?.report_type === "found" ? m.query : m.candidate;
  const seeking = m.query?.report_type === "found" ? m.candidate : m.query;
  return { found, seeking };
}

function PersonFace({ r, captionFallback }) {
  const photo = reportMedia(r?.photo_path);
  const name = r?.person_name;
  const caption = r ? (TYPE_LABEL[r.report_type] + (r.location_text ? ` · ${r.location_text}` : ` · #${r.id}`)) : captionFallback;
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

function MatchCard({ m, kind, onConfirm, onReject, onReunite, busy }) {
  const b = band(Number(m.confidence));
  const pct = Math.round(Number(m.confidence) * 100);
  return (
    <Card className="border-border bg-card">
      <CardContent className="p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <Badge variant="outline" className="rounded-full">{TYPE_LABEL[m.query?.report_type] || "Match"}</Badge>
          <Badge variant="outline" className={`gap-1 rounded-full ${b.style}`}>
            <ScanFace className="size-3" /> {pct}% · {b.label}
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <PersonFace r={m.query} />
          <ArrowLeftRight className="size-5 shrink-0 text-muted-foreground" />
          <PersonFace r={m.candidate} />
        </div>

        <p className="mt-3 text-sm font-medium text-foreground">
          {m.same_person ? "Likely the same person" : "Not a confident match"}
        </p>
        {m.reasoning && (
          <p className="mt-1.5 flex gap-1.5 text-xs text-muted-foreground">
            <Sparkles className="mt-0.5 size-3 shrink-0 text-mustard-foreground/70" /> {m.reasoning}
          </p>
        )}
        <p className="mt-1.5 text-[11px] text-muted-foreground">Claude Opus 4.8 · decision support only — confirm visually before reuniting.</p>

        <div className="mt-4 flex flex-wrap gap-2">
          {kind === "review" && (
            <>
              <Button size="sm" onClick={() => onConfirm(m)} disabled={busy}><Check className="size-4" /> Confirm match</Button>
              <Button size="sm" variant="outline" onClick={() => onReject(m)} disabled={busy}><X className="size-4" /> Reject</Button>
            </>
          )}
          {kind === "auto" && (
            <>
              <Badge variant="outline" className="gap-1 rounded-full border-success/30 bg-success/15 text-success">
                <ShieldCheck className="size-3" /> {m.status === "confirmed" ? "Confirmed" : "Auto-approved"}
              </Badge>
              <Button size="sm" variant="outline" onClick={() => onReunite(m)} disabled={busy}><HandHeart className="size-4" /> Mark reunited</Button>
              {m.status !== "confirmed" && (
                <Button size="sm" variant="outline" onClick={() => onReject(m)} disabled={busy}><X className="size-4" /> Reject</Button>
              )}
            </>
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
  const [running, setRunning] = useState(false);
  const [buckets, setBuckets] = useState({ review: [], auto: [], active: [] });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [matches, reports] = await Promise.all([listReportMatches(), listReports()]);

      // dedupe symmetric rows (A→B and B→A) by sorted pair, keep highest confidence
      const byPair = new Map();
      for (const m of matches) {
        if (m.status === "rejected") continue;
        const key = [m.query_report_id, m.candidate_report_id].sort((a, b) => a - b).join("-");
        const prev = byPair.get(key);
        if (!prev || Number(m.confidence) > Number(prev.confidence)) byPair.set(key, m);
      }
      const deduped = [...byPair.values()];

      const review = [], auto = [];
      const matchedIds = new Set();
      for (const m of deduped) {
        if (m.same_person) { matchedIds.add(m.query_report_id); matchedIds.add(m.candidate_report_id); }
        if (m.status === "confirmed" || (m.same_person && Number(m.confidence) >= STRONG)) auto.push(m);
        else if (m.same_person) review.push(m);
      }

      // actively matching: searching reports with a photo and no confident match yet
      const active = reports.filter(
        (r) => r.status === "searching" && r.photo_path && !matchedIds.has(r.id)
      );

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

  const onConfirm = (m) => act(async () => {
    const { found, seeking } = sides(m);
    await setMatchStatus(m.id, "confirmed");
    if (seeking && found) await confirmReportMatch(seeking.id, "report", String(found.id), "Confirmed from Alerts (Claude match)");
  }, "Match confirmed");
  const onReject = (m) => act(() => setMatchStatus(m.id, "rejected"), "Match dismissed");
  const onReunite = (m) => act(async () => {
    const { seeking } = sides(m);
    await reuniteReport((seeking || m.query).id);
  }, "Marked reunited");

  // backfill: run Claude matching for every searching report with a photo
  async function runAll() {
    setRunning(true);
    try {
      const reports = await listReports();
      const targets = reports.filter((r) => r.status === "searching" && r.photo_path);
      if (!targets.length) { toast.info("No reports with photos to match."); return; }
      toast.message(`Running Claude face match on ${targets.length} report(s)…`);
      await Promise.all(targets.map((r) => runFaceMatch(r.id).catch(() => null)));
      toast.success("Matching complete");
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRunning(false);
    }
  }

  const TABS = [
    { id: "review", label: "Review required", n: buckets.review.length },
    { id: "auto", label: "Auto-approved", n: buckets.auto.length },
    { id: "active", label: "Actively matching", n: buckets.active.length },
  ];

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Lost ↔ found matches judged by Claude vision. Confirm the borderline ones; high-confidence pairs are auto-approved."
      >
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-success/30 bg-success/15 text-success">
            <ScanFace className="mr-1.5 size-3" /> Face engine: Claude Opus 4.8
          </Badge>
          <Button size="sm" variant="outline" onClick={runAll} disabled={running}>
            {running ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} Run match
          </Button>
        </div>
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
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-lg" />)}
        </div>
      ) : tab === "active" ? (
        buckets.active.length === 0 ? (
          <Card className="border-dashed border-border bg-card">
            <CardContent className="py-16 text-center text-sm text-muted-foreground">No reports awaiting a match.</CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {buckets.active.map((r) => (
              <Card key={r.id} className="border-border bg-card">
                <CardContent className="p-5">
                  <div className="mb-4 flex items-center justify-between gap-2">
                    <Badge variant="outline" className="rounded-full">{TYPE_LABEL[r.report_type] || r.report_type}</Badge>
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Loader2 className="size-3.5 animate-spin" /> awaiting match
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <PersonFace r={r} />
                    <ArrowLeftRight className="size-5 shrink-0 text-muted-foreground" />
                    <PersonFace r={null} captionFallback="No candidate yet" />
                  </div>
                  {r.location_text && (
                    <p className="mt-3 flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="size-3" /> {r.location_text}</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : (
        buckets[tab].length === 0 ? (
          <Card className="border-dashed border-border bg-card">
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              No alerts in “{TABS.find((t) => t.id === tab)?.label}”. Try “Run match”.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {buckets[tab].map((m) => (
              <MatchCard key={m.id} m={m} kind={tab} busy={busy}
                onConfirm={onConfirm} onReject={onReject} onReunite={onReunite} />
            ))}
          </div>
        )
      )}
    </>
  );
}
