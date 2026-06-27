import { Link } from "react-router-dom";
import { HeartHandshake, FilePlus2, Search, Phone } from "lucide-react";
import { Button } from "@/shared/ui/button";

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <div className="grid size-9 place-items-center rounded-md bg-sig-coral text-white font-semibold">
        स
      </div>
      <div className="leading-tight">
        <p className="text-lg font-semibold tracking-tight">SANGAM</p>
        <p className="text-xs text-muted-foreground">Kumbh Mela · Lost &amp; Found</p>
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-svh bg-background px-4 py-10">
      <div className="mx-auto w-full max-w-md">
        <Brand />

        <div className="mt-10 space-y-2 text-center">
          <HeartHandshake className="mx-auto size-12 text-primary" />
          <h1 className="text-2xl font-semibold tracking-tight">Reunite with your loved ones</h1>
          <p className="text-sm text-muted-foreground">
            File a report in seconds — no account needed. We search across every center to bring
            families back together.
          </p>
        </div>

        <div className="mt-8 space-y-3">
          <Button asChild className="h-14 w-full text-base">
            <Link to="/new">
              <FilePlus2 className="size-5" /> File a report
            </Link>
          </Button>
          <Button asChild variant="secondary" className="h-14 w-full text-base">
            <Link to="/track">
              <Search className="size-5" /> View my reports
            </Link>
          </Button>
        </div>

        <div className="mt-10 rounded-lg border border-border bg-card p-4 text-center">
          <p className="flex items-center justify-center gap-2 text-sm font-medium">
            <Phone className="size-4 text-primary" /> Emergency helpline
          </p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">1920</p>
          <p className="text-xs text-muted-foreground">Bhula-Bhatka / Lost &amp; Found Kendra</p>
        </div>

        <p className="mt-8 text-center text-[11px] text-muted-foreground">
          Staff member?{" "}
          <Link to="/ops/login" className="font-medium text-primary hover:underline">
            Control-room sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
