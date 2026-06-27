import { cn } from "@/shared/lib/utils";

// Airtable "signature voltage" stat cards — full-bleed brand color surfaces.
const TONES = {
  navy: "bg-sig-navy text-white",
  coral: "bg-sig-coral text-white",
  forest: "bg-sig-forest text-white",
  mustard: "bg-sig-mustard text-[#1d1208]",
  plain: "bg-card text-card-foreground border border-border",
};

export function StatCard({ label, value, sublabel, tone = "plain" }) {
  const isPlain = tone === "plain";
  return (
    <div
      className={cn(
        "flex min-h-[140px] flex-col justify-between rounded-lg p-6",
        TONES[tone] ?? TONES.plain
      )}
    >
      <p
        className={cn(
          "text-xs font-semibold uppercase tracking-wide",
          isPlain ? "text-muted-foreground" : "opacity-85"
        )}
      >
        {label}
      </p>
      <p className="text-4xl font-medium leading-none tracking-tight">{value}</p>
      {sublabel && (
        <p className={cn("text-xs", isPlain ? "text-muted-foreground" : "opacity-80")}>
          {sublabel}
        </p>
      )}
    </div>
  );
}
