import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { StatCard } from "@/shared/components/StatCard";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Progress } from "@/shared/ui/progress";
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
import { runSim } from "@/shared/api";

// Member 3 owns this file. Endpoint: POST /api/sim/run
function riskLevel(r) {
  return r >= 0.66 ? "high" : r >= 0.33 ? "medium" : "low";
}

export default function Simulation() {
  const [form, setForm] = useState({ pilgrims: 50000, hours: 6, seed: 42 });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: Number(e.target.value) }));

  async function onRun(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await runSim(form);
      setResult(data);
      toast.success("Simulation complete");
    } catch {
      toast.error("Backend not reachable — showing mock result");
      setResult(MOCK);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Operations Simulation"
        description="Simulate crowd & separation scenarios across zones and chokepoints to predict hotspots and resource needs."
      />

      <form
        onSubmit={onRun}
        className="mb-6 flex flex-wrap items-end gap-4 rounded-lg border border-border bg-card p-4"
      >
        <div className="space-y-1.5">
          <Label htmlFor="pilgrims">Pilgrims</Label>
          <Input id="pilgrims" type="number" className="w-36" value={form.pilgrims} onChange={set("pilgrims")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="hours">Hours</Label>
          <Input id="hours" type="number" className="w-24" value={form.hours} onChange={set("hours")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seed">Seed</Label>
          <Input id="seed" type="number" className="w-24" value={form.seed} onChange={set("seed")} />
        </div>
        <Button type="submit" disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
          Run simulation
        </Button>
      </form>

      {result && (
        <div className="mb-6 grid grid-cols-2 gap-5 lg:grid-cols-4">
          <StatCard tone="coral" label="Predicted separations" value={result.resources?.separations ?? "—"} />
          <StatCard tone="mustard" label="Staff needed" value={result.resources?.staff ?? "—"} />
          <StatCard tone="navy" label="Help desks" value={result.resources?.help_desks ?? "—"} />
          <StatCard tone="forest" label="Peak hour" value={result.resources?.peak_hour ?? "—"} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>Predicted hotspots</CardTitle>
            <CardDescription>Zones ranked by separation risk.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Zone</TableHead>
                  <TableHead className="w-[40%]">Risk</TableHead>
                  <TableHead className="text-right">Level</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(result?.hotspots ?? []).map((h) => (
                  <TableRow key={h.zone}>
                    <TableCell className="font-medium">{h.zone}</TableCell>
                    <TableCell>
                      <Progress value={h.risk * 100} className="h-2" />
                    </TableCell>
                    <TableCell className="text-right">
                      <StatusBadge status={riskLevel(h.risk)} />
                    </TableCell>
                  </TableRow>
                ))}
                {!result && (
                  <TableRow>
                    <TableCell colSpan={3} className="py-8 text-center text-muted-foreground">
                      Run a simulation to see hotspots.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>Separation timeline</CardTitle>
            <CardDescription>Expected separations per hour.</CardDescription>
          </CardHeader>
          <CardContent>
            {result?.timeline ? (
              <div className="flex h-48 items-end gap-2">
                {result.timeline.map((t, i) => {
                  const max = Math.max(...result.timeline.map((x) => x.value));
                  return (
                    <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-2">
                      <div
                        className="w-full rounded-t bg-primary/70"
                        style={{ height: `${Math.max((t.value / max) * 100, 4)}%` }}
                        title={`${t.value}`}
                      />
                      <span className="text-xs text-muted-foreground">{t.hour}h</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="py-8 text-center text-muted-foreground">No timeline yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

const MOCK = {
  hotspots: [
    { zone: "Sangam Ghat", lat: 25.42, lng: 81.88, risk: 0.91 },
    { zone: "Zone Area 12", lat: 25.43, lng: 81.86, risk: 0.74 },
    { zone: "Ram Ghat", lat: 25.44, lng: 81.85, risk: 0.55 },
    { zone: "Zone Area 3", lat: 25.41, lng: 81.89, risk: 0.28 },
  ],
  timeline: [
    { hour: 1, value: 12 },
    { hour: 2, value: 28 },
    { hour: 3, value: 64 },
    { hour: 4, value: 98 },
    { hour: 5, value: 71 },
    { hour: 6, value: 40 },
  ],
  resources: { separations: 313, staff: 48, help_desks: 6, peak_hour: "4h" },
};
