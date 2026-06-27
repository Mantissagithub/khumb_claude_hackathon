import { useState } from "react";
import { Route as RouteIcon, Loader2, Navigation } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { Button } from "@/shared/ui/button";
import { Label } from "@/shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Switch } from "@/shared/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/shared/ui/card";
import { bestRoute } from "@/shared/api";

// Member 4 owns this file. Endpoint: POST /api/routing/best
const NODES = [
  "Sangam Ghat",
  "Ram Ghat",
  "Zone Area 3",
  "Zone Area 7",
  "Zone Area 12",
  "Police Station Sector 12",
  "Central Help Desk",
];

export default function Routing() {
  const [from, setFrom] = useState(NODES[0]);
  const [to, setTo] = useState(NODES[5]);
  const [avoid, setAvoid] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await bestRoute({ from, to, avoid_chokepoints: avoid });
      setResult(data);
      toast.success("Route computed");
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
        title="Knowledge-Graph Routing"
        description="Query the knowledge graph for the best route between centers, zones, CCTV, and police — avoiding chokepoints."
      />

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RouteIcon className="size-4 text-primary" /> Plan route
            </CardTitle>
            <CardDescription>Pick origin and destination.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>From</Label>
                <Select value={from} onValueChange={setFrom}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {NODES.map((n) => (
                      <SelectItem key={n} value={n}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>To</Label>
                <Select value={to} onValueChange={setTo}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {NODES.map((n) => (
                      <SelectItem key={n} value={n}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border bg-surface-1 p-3">
                <Label htmlFor="avoid" className="cursor-pointer">Avoid chokepoints</Label>
                <Switch id="avoid" checked={avoid} onCheckedChange={setAvoid} />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : <Navigation className="size-4" />}
                Find best route
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>Best route</CardTitle>
            <CardDescription>
              {result ? `${result.distance_km} km · ${result.path?.length} stops` : "Plan a route to see directions."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {result ? (
              <ol className="relative space-y-4 border-l border-border pl-6">
                {result.steps.map((s, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[27px] grid size-5 place-items-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
                      {i + 1}
                    </span>
                    <p className="text-sm">{s}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="py-8 text-center text-muted-foreground">No route yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

const MOCK = {
  path: [
    { name: "Sangam Ghat", lat: 25.42, lng: 81.88 },
    { name: "Ram Ghat", lat: 25.44, lng: 81.85 },
    { name: "Police Station Sector 12", lat: 25.43, lng: 81.88 },
  ],
  distance_km: 2.4,
  steps: [
    "Start at Sangam Ghat",
    "Proceed north-west to Ram Ghat (avoids Chokepoint C-3)",
    "Turn east toward Police Station Sector 12",
    "Arrive at Police Station Sector 12",
  ],
};
