import { useEffect, useState } from "react";
import { Loader2, Sparkles, Check, X, Phone, MapPin, HandHeart } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/shared/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/shared/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import {
  listReports, matchReport, confirmReportMatch, rejectReport, reuniteReport, reportMedia,
} from "@/shared/authApi";

const TABS = ["searching", "found", "reunited"];
const TYPE_LABEL = { lost_self: "Lost (self)", seeking: "Seeking", found: "Found person" };

export default function Reports() {
  const [tab, setTab] = useState("searching");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(null);
  const [candidates, setCandidates] = useState(null);
  const [matching, setMatching] = useState(false);
  const [acting, setActing] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setItems(await listReports(tab));
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [tab]);

  async function doMatch() {
    setMatching(true);
    try {
      const c = await matchReport(active.id, 5);
      setCandidates(c);
      if (!c.length) toast.info("No candidate matches found");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setMatching(false);
    }
  }

  async function act(fn, msg) {
    setActing(true);
    try {
      await fn();
      toast.success(msg);
      setActive(null);
      setCandidates(null);
      refresh();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setActing(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Public Reports"
        description="Reports filed by the public (lost / seeking / found). Open one, match it against found reports and the registry, then confirm — the reporter sees the result instantly."
      />

      <Tabs value={tab} onValueChange={setTab} className="mb-4">
        <TabsList>
          {TABS.map((t) => <TabsTrigger key={t} value={t} className="capitalize">{t}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      <Card className="border-border bg-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Reporter</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow><TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto size-4 animate-spin" /></TableCell></TableRow>
              )}
              {!loading && items.length === 0 && (
                <TableRow><TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                  No {tab} reports.</TableCell></TableRow>
              )}
              {!loading && items.map((r) => (
                <TableRow key={r.id} className="cursor-pointer" onClick={() => { setActive(r); setCandidates(null); }}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{r.id}</TableCell>
                  <TableCell>{TYPE_LABEL[r.report_type]}</TableCell>
                  <TableCell className="font-medium">{r.person_name || "—"}</TableCell>
                  <TableCell className="max-w-[220px] truncate text-muted-foreground">{r.description || "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{r.location_text || "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{r.reporter_phone}</TableCell>
                  <TableCell><StatusBadge status={r.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-2xl">
          {active && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  Report #{active.id} <StatusBadge status={active.status} />
                  <span className="text-xs font-normal text-muted-foreground">{TYPE_LABEL[active.report_type]}</span>
                </DialogTitle>
                <DialogDescription>Match against found reports + the registry, then confirm.</DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 sm:grid-cols-[140px_1fr]">
                <div className="overflow-hidden rounded-lg border border-border bg-surface-1">
                  {active.photo_path ? (
                    <img src={reportMedia(active.photo_path)} alt="" className="aspect-square w-full object-cover" />
                  ) : (
                    <div className="grid aspect-square place-items-center text-xs text-muted-foreground">No photo</div>
                  )}
                </div>
                <div className="space-y-1.5 text-sm">
                  <p><span className="text-muted-foreground">Name:</span> {active.person_name || "—"}</p>
                  <p><span className="text-muted-foreground">Gender / Age:</span> {active.gender || "—"} · {active.age_band || "—"}</p>
                  <p className="flex items-center gap-1"><MapPin className="size-3.5 text-muted-foreground" /> {active.location_text || "—"}</p>
                  {active.center_name && <p className="flex items-center gap-1"><HandHeart className="size-3.5 text-muted-foreground" /> {active.center_name}</p>}
                  <p><span className="text-muted-foreground">Description:</span> {active.description || "—"}</p>
                  <p className="flex items-center gap-1"><Phone className="size-3.5 text-muted-foreground" /> {active.reporter_phone}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                {active.status === "searching" && (
                  <Button onClick={doMatch} disabled={matching}>
                    {matching ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Run match
                  </Button>
                )}
                {active.status === "found" && (
                  <Button disabled={acting} onClick={() => act(() => reuniteReport(active.id), "Marked reunited")}>
                    <Check className="size-4" /> Mark reunited
                  </Button>
                )}
                <Button variant="ghost" className="text-danger hover:text-danger" disabled={acting}
                  onClick={() => act(() => rejectReport(active.id, "Rejected"), "Report rejected")}>
                  <X className="size-4" /> Reject
                </Button>
              </div>

              {candidates && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">{candidates.length} candidate match{candidates.length === 1 ? "" : "es"}</p>
                  <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                    {candidates.map((c) => (
                      <div key={`${c.source}-${c.ref_id}`} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface-1 p-3">
                        <div className="min-w-0 text-sm">
                          <p className="font-medium">
                            {c.name || "Unknown"}{" "}
                            <span className="font-mono text-xs text-muted-foreground">
                              {c.source === "case" ? c.ref_id : `report #${c.ref_id}`}
                            </span>
                          </p>
                          <p className="truncate text-muted-foreground">{c.description}</p>
                          <p className="text-xs text-muted-foreground">{c.reason}</p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1.5">
                          <span className="text-sm font-semibold text-primary">{(c.score * 100).toFixed(0)}%</span>
                          <Button size="sm" disabled={acting}
                            onClick={() => act(() => confirmReportMatch(active.id, c.source, c.ref_id, "Confirmed"), "Match confirmed — reporter notified")}>
                            <Check className="size-3.5" /> Confirm
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
