import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, MapPin, ImageOff, Radio } from "lucide-react";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Card, CardContent } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/shared/ui/select";
import { listReports, mediaUrl } from "@/shared/authApi";

const FILTERS = ["All", "Lost", "Found"];
const TYPE_LABEL = { lost_self: "Lost", seeking: "Seeking", found: "Found" };
const initials = (n) => (n || "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

function PersonCard({ r }) {
  const photo = mediaUrl(r.photo_path);
  const where = r.location_text || r.found_center || r.zone;
  return (
    <Link to={`/admin/reports/${r.id}`} className="group">
      <Card className="overflow-hidden border-border bg-card transition-shadow hover:shadow-md">
        <div className="relative aspect-[3/4] w-full overflow-hidden bg-muted">
          {photo ? (
            <img src={photo} alt={r.person_name || "person"} loading="lazy" className="size-full object-cover transition-transform duration-300 group-hover:scale-105" />
          ) : (
            <div className="flex size-full flex-col items-center justify-center gap-1 bg-gradient-to-br from-surface-2 to-surface-3 text-muted-foreground">
              <span className="grid size-16 place-items-center rounded-full bg-card text-xl font-medium text-foreground">{initials(r.person_name)}</span>
              <span className="flex items-center gap-1 text-[11px]"><ImageOff className="size-3" /> no photo</span>
            </div>
          )}
          <div className="absolute right-2 top-2"><StatusBadge status={r.status} /></div>
          <span className="absolute left-2 top-2 rounded-full bg-sig-coral px-2 py-0.5 text-[11px] font-medium text-white">
            {TYPE_LABEL[r.report_type] || "Report"}
          </span>
        </div>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="truncate font-medium">{r.person_name || "Unknown"}</p>
            <span className="shrink-0 text-xs text-muted-foreground">{r.age_band || "—"}</span>
          </div>
          <p className="mt-0.5 truncate text-xs capitalize text-muted-foreground">{r.gender || "—"}</p>
          {where && (
            <p className="mt-2 flex items-center gap-1 truncate text-xs text-muted-foreground">
              <MapPin className="size-3 shrink-0" /> {where}
            </p>
          )}
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">#{r.id} · {r.reporter_phone}</p>
        </CardContent>
      </Card>
    </Link>
  );
}

export default function Reports() {
  const [all, setAll] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("All");

  useEffect(() => {
    setLoading(true);
    listReports()
      .then(setAll)
      .catch(() => setAll([]))
      .finally(() => setLoading(false));
  }, []);

  const items = useMemo(() => {
    const term = q.trim().toLowerCase();
    return all.filter((r) => {
      if (filter === "Lost" && !(r.report_type === "lost_self" || r.report_type === "seeking")) return false;
      if (filter === "Found" && r.report_type !== "found") return false;
      if (!term) return true;
      return [r.person_name, r.location_text, r.description, r.reporter_phone, String(r.id)]
        .some((f) => (f || "").toLowerCase().includes(term));
    });
  }, [all, q, filter]);

  return (
    <>
      <PageHeader
        title="Reports"
        description="Live reports submitted by the public and operators. Open a card for the full record."
      >
        <span className="rounded-full bg-sig-coral/10 px-3 py-1 text-xs font-medium text-sig-coral">
          <Radio className="mr-1 inline size-3" /> {all.length} submissions
        </span>
      </PageHeader>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, location, phone…" className="pl-9" />
        </div>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
          <SelectContent>
            {FILTERS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">{items.length} shown</span>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-5 md:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="aspect-[3/4] rounded-lg" />)}
        </div>
      ) : items.length === 0 ? (
        <Card className="border-dashed border-border bg-card">
          <CardContent className="py-16 text-center text-sm text-muted-foreground">
            No reports submitted yet. Public/operator submissions will appear here.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-5 md:grid-cols-3 xl:grid-cols-5">
          {items.map((r) => <PersonCard key={r.id} r={r} />)}
        </div>
      )}
    </>
  );
}
