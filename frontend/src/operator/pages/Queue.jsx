import { useEffect, useState } from "react";
import { Loader2, Search, Sparkles, Check, X, FilePlus2, Phone, MapPin } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import {
  listSubmissions,
  getSubmission,
  runMatch,
  confirmMatch,
  promote,
  reject,
  reunite,
  mediaUrl,
} from "@/shared/authApi";

const STATUSES = ["pending", "reviewing", "matched", "promoted", "rejected"];

export default function Queue() {
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(null); // open submission
  const [candidates, setCandidates] = useState(null);
  const [matching, setMatching] = useState(false);
  const [acting, setActing] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const data = await listSubmissions(status, q);
      setItems(data.items);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function open(id) {
    setCandidates(null);
    try {
      const sub = await getSubmission(id);
      setActive(sub);
    } catch (err) {
      toast.error(err.message);
    }
  }

  async function doMatch() {
    setMatching(true);
    try {
      const res = await runMatch(active.id, 5);
      setCandidates(res.candidates);
      if (!res.candidates.length) toast.info("No candidate matches found");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setMatching(false);
    }
  }

  async function act(fn, successMsg) {
    setActing(true);
    try {
      await fn();
      toast.success(successMsg);
      setActive(null);
      refresh();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setActing(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Review Queue"
        description="Public missing-person reports awaiting staff review. Open a report, run a match against the registry, then confirm, create a new case, or reject."
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={setStatus}>
          <TabsList>
            {STATUSES.map((s) => (
              <TabsTrigger key={s} value={s} className="capitalize">{s}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <form
          onSubmit={(e) => { e.preventDefault(); refresh(); }}
          className="flex items-center gap-2"
        >
          <Input
            placeholder="Search name / description…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-64"
          />
          <Button type="submit" variant="secondary" size="icon"><Search className="size-4" /></Button>
        </form>
      </div>

      <Card className="border-border bg-card">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Last seen</TableHead>
                <TableHead>Reporter</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto size-4 animate-spin" />
                </TableCell></TableRow>
              )}
              {!loading && items.length === 0 && (
                <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                  No {status} submissions.
                </TableCell></TableRow>
              )}
              {!loading && items.map((s) => (
                <TableRow key={s.id} className="cursor-pointer" onClick={() => open(s.id)}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{s.id}</TableCell>
                  <TableCell className="font-medium">{s.missing_name || "—"}</TableCell>
                  <TableCell className="max-w-[260px] truncate text-muted-foreground">
                    {s.physical_description || "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{s.last_seen_location || "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{s.reporter_phone}</TableCell>
                  <TableCell><StatusBadge status={s.review_status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Detail + match dialog */}
      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-2xl">
          {active && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  Submission #{active.id}
                  <StatusBadge status={active.review_status} />
                </DialogTitle>
                <DialogDescription>Review the report and match against the registry.</DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 sm:grid-cols-[140px_1fr]">
                <div className="overflow-hidden rounded-lg border border-border bg-surface-1">
                  {active.photo_path ? (
                    <img src={mediaUrl(active.photo_path)} alt="" className="aspect-square w-full object-cover" />
                  ) : (
                    <div className="grid aspect-square place-items-center text-xs text-muted-foreground">
                      No photo
                    </div>
                  )}
                </div>
                <div className="space-y-1.5 text-sm">
                  <p><span className="text-muted-foreground">Name:</span> {active.missing_name || "—"}</p>
                  <p><span className="text-muted-foreground">Gender / Age:</span> {active.gender || "—"} · {active.age_band || "—"}</p>
                  <p className="flex items-center gap-1"><MapPin className="size-3.5 text-muted-foreground" /> {active.last_seen_location || "—"} {active.zone ? `(${active.zone})` : ""}</p>
                  <p><span className="text-muted-foreground">Description:</span> {active.physical_description || "—"}</p>
                  <p className="flex items-center gap-1"><Phone className="size-3.5 text-muted-foreground" /> {active.reporter_name ? `${active.reporter_name} · ` : ""}{active.reporter_phone}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                <Button onClick={doMatch} disabled={matching}>
                  {matching ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                  Run match
                </Button>
                <Button
                  variant="secondary"
                  disabled={acting}
                  onClick={() => act(() => promote(active.id, "Promoted from queue"), "New case created")}
                >
                  <FilePlus2 className="size-4" /> Create new case
                </Button>
                <Button
                  variant="ghost"
                  className="text-danger hover:text-danger"
                  disabled={acting}
                  onClick={() => act(() => reject(active.id, "Rejected from queue"), "Submission rejected")}
                >
                  <X className="size-4" /> Reject
                </Button>
              </div>

              {candidates && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">
                    {candidates.length} candidate match{candidates.length === 1 ? "" : "es"}
                  </p>
                  <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                    {candidates.map((c) => (
                      <div
                        key={c.case_id}
                        className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface-1 p-3"
                      >
                        <div className="min-w-0 text-sm">
                          <p className="font-medium">
                            {c.name || "Unknown"}{" "}
                            <span className="font-mono text-xs text-muted-foreground">{c.case_id}</span>
                          </p>
                          <p className="truncate text-muted-foreground">{c.physical_description}</p>
                          <p className="text-xs text-muted-foreground">{c.reason}</p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1.5">
                          <span className="text-sm font-semibold text-primary">
                            {(c.score * 100).toFixed(0)}%
                          </span>
                          <Button
                            size="sm"
                            disabled={acting}
                            onClick={() =>
                              act(
                                async () => { await confirmMatch(active.id, c.case_id, "Confirmed from queue"); await reunite(c.case_id, "Reunited via queue"); },
                                "Confirmed & marked reunited"
                              )
                            }
                          >
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
