import { Badge } from "@/shared/ui/badge";
import { cn } from "@/shared/lib/utils";

// Case statuses (PLAN.md schema): Active | Reunited | Matched
// + simulation risk levels: low | medium | high
const STYLES = {
  active: "bg-info/15 text-info border-info/30",
  reunited: "bg-success/15 text-success border-success/30",
  matched: "bg-warning/15 text-warning border-warning/30",
  low: "bg-success/15 text-success border-success/30",
  medium: "bg-warning/15 text-warning border-warning/30",
  high: "bg-danger/15 text-danger border-danger/30",
  missing: "bg-danger/15 text-danger border-danger/30",
  found: "bg-warning/15 text-warning border-warning/30",
  searching: "bg-info/15 text-info border-info/30",
  pending: "bg-info/15 text-info border-info/30",
  reviewing: "bg-warning/15 text-warning border-warning/30",
  confirmed: "bg-success/15 text-success border-success/30",
  rejected: "bg-danger/15 text-danger border-danger/30",
};

export function StatusBadge({ status, className }) {
  const key = String(status ?? "").toLowerCase();
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
        STYLES[key] ?? "bg-muted text-muted-foreground border-border",
        className
      )}
    >
      <span
        className={cn(
          "mr-1.5 inline-block size-1.5 rounded-full",
          key === "reunited" || key === "low"
            ? "bg-success"
            : key === "matched" || key === "medium" || key === "found"
            ? "bg-warning"
            : key === "high" || key === "missing"
            ? "bg-danger"
            : "bg-info"
        )}
      />
      {status}
    </Badge>
  );
}
