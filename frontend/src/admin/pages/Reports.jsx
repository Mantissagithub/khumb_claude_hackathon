import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, MapPin, ImageOff } from "lucide-react";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Card, CardContent } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/shared/ui/select";
import { listCases, mediaUrl } from "@/shared/authApi";

const STATUSES = ["All", "Active", "Matched", "Reunited"];
const initials = (n) => (n || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

function PersonCard({ c }) {
  const photo = mediaUrl(c.photo_path);
  const where = c.last_seen_location || c.reporting_center || c.zone;
  return (
    <Link to={`/admin/reports/${encodeURIComponent(c.case_id)}`} className="group">
      <Card className="overflow-hidden border-border bg-card transition-shadow hover:shadow-md">
        <div className="relative aspect-[4/3] w-full overflow-hidden bg-muted">
          {photo ? (
            <img src={photo} alt={c.name || "person"} className="size-full object-cover transition-transform duration-300 group-hover:scale-105" />
          ) : (
            <div className="flex size-full flex-col items-center justify-center gap-1 bg-gradient-to-br from-surface-2 to-surface-3 text-muted-foreground">
              <span className="grid size-14 place-items-center rounded-full bg-card text-lg font-medium text-foreground">{initials(c.name)}</span>
              <span className="flex items-center gap-1 text-[11px]"><ImageOff className="size-3" /> no photo</span>
            </div>
          )}
          <div className="absolute right-2 top-2"><StatusBadge status={c.status} /></div>
        </div>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="truncate font-medium">{c.name || "Unknown"}</p>
            <span className="shrink-0 text-xs text-muted-foreground">{c.age_band || "—"}</span>
          </div>
          <p className="mt-0.5 truncate text-xs capitalize text-muted-foreground">{c.gender || "—"} · {c.type}</p>
          {where && (
            <p className="mt-2 flex items-center gap-1 truncate text-xs text-muted-foreground">
              <MapPin className="size-3 shrink-0" /> {where}
            </p>
          )}
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">{c.case_id}</p>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function Reports() {
  const [all, setAll] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("All");

  useEffect(() => {
    setLoading(true);
    listCases({ limit: 200 })
      .then((r) => setAll(r.items))
      .catch(() => setAll([]))
      .finally(() => setLoading(false));
  }, []);

  const items = useMemo(() => {
    const term = q.trim().toLowerCase();
    return all.filter((c) => {
      if (status !== "All" && c.status !== status) return false;
      if (!term) return true;
      return [c.name, c.physical_description, c.last_seen_location, c.case_id, c.zone]
        .some((f) => (f || "").toLowerCase().includes(term));
    });
  }, [all, q, status]);

  // Photographed people first — so the grid leads with prominent images.
  const sorted = useMemo(
    () => [...items].sort((a, b) => (b.photo_path ? 1 : 0) - (a.photo_path ? 1 : 0)),
    [items]
  );

  return (
    <>
      <PageHeader
        title="Reports"
        description="Everyone reported missing or found across the Kumbh. Open a card for the full record."
      />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, description, ID…" className="pl-9" />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">{sorted.length} people</span>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-5 md:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-lg" />)}
        </div>
      ) : sorted.length === 0 ? (
        <Card className="border-dashed border-border bg-card">
          <CardContent className="py-16 text-center text-sm text-muted-foreground">No people match your filters.</CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-5 md:grid-cols-3 xl:grid-cols-4">
          {sorted.map((c) => <PersonCard key={c.case_id} c={c} />)}
        </div>
      )}
    </>
  );
}
