import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Users, Search, CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatCard } from "@/shared/components/StatCard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/ui/card";
import { Badge } from "@/shared/ui/badge";
import { Skeleton } from "@/shared/ui/skeleton";
import { analytics, listReports } from "@/shared/authApi";

// Brand-token bars — avoids pulling in a chart lib for a few breakdowns.
const CHART = ["bg-sig-coral", "bg-sig-forest", "bg-sig-mustard", "bg-[#254fad]", "bg-sig-peach"];

function BarRow({ label, value, pct, color }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="truncate text-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{value.toLocaleString()}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.max(pct, 2)}%` }} />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [online, setOnline] = useState(null);
  const [stats, setStats] = useState(null);
  const [reports, setReports] = useState([]);

  useEffect(() => {
    Promise.all([analytics(), listReports().catch(() => [])])
      .then(([a, r]) => {
        setStats(a);
        setReports(r);
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }, []);

  const byStatus = stats?.cases_by_status ?? {};
  const total = stats?.cases_total ?? 0;
  const found = byStatus.Reunited ?? 0;
  const lost = byStatus.Active ?? 0;
  const inProgress = byStatus.Matched ?? 0;
  const reunionRate = total ? Math.round((found / total) * 100) : 0;

  const topZones = stats?.top_zones ?? [];
  const zoneMax = Math.max(1, ...topZones.map((z) => z.n));

  const statusEntries = Object.entries(byStatus);
  const statusMax = Math.max(1, ...statusEntries.map(([, n]) => n));

  const rep = { searching: 0, found: 0, reunited: 0 };
  for (const r of reports) if (r.status in rep) rep[r.status] += 1;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Live overview of people reported lost and reunited across all Kumbh Mela centers."
      >
        <Badge
          variant="outline"
          className={
            online
              ? "border-success/30 bg-success/15 text-success"
              : "border-warning/30 bg-warning/15 text-warning"
          }
        >
          <span className={`mr-1.5 inline-block size-1.5 rounded-full ${online ? "bg-success" : "bg-warning"}`} />
          {online === null ? "checking…" : online ? "Live" : "offline"}
        </Badge>
      </PageHeader>

      {/* Hero: Found vs Lost */}
      <div className="mb-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {online === null ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[140px] rounded-lg" />)
        ) : (
          <>
            <StatCard tone="forest" label="People found" value={found.toLocaleString()} sublabel={`${reunionRate}% reunion rate`} />
            <StatCard tone="coral" label="Still lost" value={lost.toLocaleString()} sublabel="active — awaiting match" />
            <StatCard tone="mustard" label="In progress" value={inProgress.toLocaleString()} sublabel="matched, pending confirmation" />
            <StatCard tone="navy" label="Total cases" value={total.toLocaleString()} sublabel="across all centers" />
          </>
        )}
      </div>

      {/* Reunion progress */}
      <Card className="mb-6 border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Reunion progress</CardTitle>
          <CardDescription>{found.toLocaleString()} of {total.toLocaleString()} reunited</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-sig-forest" style={{ width: `${reunionRate}%` }} title={`Reunited ${found}`} />
            <div className="h-full bg-sig-mustard" style={{ width: `${total ? (inProgress / total) * 100 : 0}%` }} title={`In progress ${inProgress}`} />
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-sig-forest" /> Reunited</span>
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-sig-mustard" /> In progress</span>
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-muted-foreground/40" /> Still lost</span>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* By status */}
        <Card className="border-border bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Cases by status</CardTitle>
            <CardDescription>Distribution across the registry.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3.5">
            {statusEntries.length === 0 && <p className="text-sm text-muted-foreground">No data.</p>}
            {statusEntries.map(([status, n], i) => (
              <BarRow key={status} label={status} value={n} pct={(n / statusMax) * 100} color={CHART[i % CHART.length]} />
            ))}
          </CardContent>
        </Card>

        {/* Top zones */}
        <Card className="border-border bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Top zones by reports</CardTitle>
            <CardDescription>Where separations concentrate.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3.5">
            {topZones.length === 0 && <p className="text-sm text-muted-foreground">No zone data.</p>}
            {topZones.map((z, i) => (
              <BarRow key={z.zone} label={z.zone} value={z.n} pct={(z.n / zoneMax) * 100} color={CHART[i % CHART.length]} />
            ))}
            <Link to="/admin/map" className="inline-flex items-center gap-1 pt-1 text-xs font-medium text-foreground hover:underline">
              View density heatmap <ArrowUpRight className="size-3.5" />
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Public reports activity */}
      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-3">
        <Card className="border-border bg-card">
          <CardContent className="flex items-center gap-3 p-5">
            <div className="grid size-10 place-items-center rounded-lg bg-info/15 text-info"><Search className="size-5" /></div>
            <div><p className="text-2xl font-medium tabular-nums">{rep.searching}</p><p className="text-xs text-muted-foreground">Reports searching</p></div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card">
          <CardContent className="flex items-center gap-3 p-5">
            <div className="grid size-10 place-items-center rounded-lg bg-warning/15 text-warning"><Users className="size-5" /></div>
            <div><p className="text-2xl font-medium tabular-nums">{rep.found}</p><p className="text-xs text-muted-foreground">Matched / found</p></div>
          </CardContent>
        </Card>
        <Card className="border-border bg-card">
          <CardContent className="flex items-center gap-3 p-5">
            <div className="grid size-10 place-items-center rounded-lg bg-success/15 text-success"><CheckCircle2 className="size-5" /></div>
            <div><p className="text-2xl font-medium tabular-nums">{rep.reunited}</p><p className="text-xs text-muted-foreground">Reunited</p></div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
