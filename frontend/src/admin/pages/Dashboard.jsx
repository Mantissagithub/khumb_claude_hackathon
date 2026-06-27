import { useEffect, useState } from "react";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatCard } from "@/shared/components/StatCard";
import { StatusBadge } from "@/shared/components/StatusBadge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/shared/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";
import { Badge } from "@/shared/ui/badge";
import { analytics, listCases } from "@/shared/authApi";

export default function Dashboard() {
  const [online, setOnline] = useState(null);
  const [stats, setStats] = useState(null);
  const [cases, setCases] = useState([]);

  useEffect(() => {
    Promise.all([analytics(), listCases({})])
      .then(([a, c]) => {
        setStats(a);
        setCases(c.items.slice(0, 6));
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }, []);

  const byStatus = stats?.cases_by_status ?? {};

  return (
    <>
      <PageHeader
        title="Operations Dashboard"
        description="Live overview of missing & found cases across all Kumbh Mela centers."
      >
        <Badge
          variant="outline"
          className={
            online
              ? "border-success/30 bg-success/15 text-success"
              : "border-warning/30 bg-warning/15 text-warning"
          }
        >
          <span
            className={`mr-1.5 inline-block size-1.5 rounded-full ${
              online ? "bg-success" : "bg-warning"
            }`}
          />
          {online === null ? "checking…" : online ? "Supabase online" : "offline"}
        </Badge>
      </PageHeader>

      <div className="mb-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard tone="navy" label="Total cases" value={(stats?.cases_total ?? 0).toLocaleString()} sublabel="across all centers" />
        <StatCard tone="coral" label="Active" value={(byStatus.Active ?? 0).toLocaleString()} sublabel="awaiting match" />
        <StatCard tone="mustard" label="Matched" value={(byStatus.Matched ?? 0).toLocaleString()} sublabel="pending confirmation" />
        <StatCard tone="forest" label="Reunited" value={(byStatus.Reunited ?? 0).toLocaleString()} sublabel="closed" />
      </div>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle>Recent cases</CardTitle>
          <CardDescription>Newest reports from across all reporting centers.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Case ID</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Age</TableHead>
                <TableHead>Zone</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cases.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    {online === false ? "Could not load cases." : "Loading…"}
                  </TableCell>
                </TableRow>
              )}
              {cases.map((c) => (
                <TableRow key={c.case_id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{c.case_id}</TableCell>
                  <TableCell className="font-medium">{c.name || "—"}</TableCell>
                  <TableCell><StatusBadge status={c.type} /></TableCell>
                  <TableCell className="text-muted-foreground">{c.age_band || "—"}</TableCell>
                  <TableCell className="text-muted-foreground">{c.zone || "—"}</TableCell>
                  <TableCell className="text-right"><StatusBadge status={c.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-lg bg-sig-cream px-7 py-6">
        <div>
          <h3 className="text-xl font-medium tracking-tight text-[#181d26]">
            313 separations predicted in the next 6 hours
          </h3>
          <p className="mt-1 text-sm text-[#5a4a33]">
            Pre-position 48 staff and 6 help desks at Sangam Ghat before the 4h peak.
          </p>
        </div>
        <button className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground">
          Plan operations
        </button>
      </div>
    </>
  );
}
