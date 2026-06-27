import { useState } from "react";
import { ScanFace, MapPin, Upload, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
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
import { faceSearch } from "@/shared/api";

// Member 1 owns this file. Endpoint: POST /api/face/search
export default function FaceSearch() {
  const [image, setImage] = useState(null);
  const [aadhaar, setAadhaar] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    if (!image) return toast.error("Upload a photo first");
    setLoading(true);
    try {
      const form = new FormData();
      form.append("image", image);
      if (aadhaar) form.append("aadhaar", aadhaar);
      const data = await faceSearch(form);
      setResult(data);
      toast.success(`${data?.matches?.length ?? 0} match(es) found`);
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
        title="Face + Clothing CCTV Search"
        description="Upload an Aadhaar + supporting photos to match against the camera gallery, then route to the nearest camera or police station."
      />

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ScanFace className="size-4 text-primary" /> Search
            </CardTitle>
            <CardDescription>Match a missing person against CCTV.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="photo">Photo</Label>
                <label
                  htmlFor="photo"
                  className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-surface-1 p-6 text-center text-sm text-muted-foreground hover:border-primary/50"
                >
                  <Upload className="size-5" />
                  {image ? image.name : "Click to upload a face photo"}
                </label>
                <Input
                  id="photo"
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => setImage(e.target.files?.[0] ?? null)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="aadhaar">Aadhaar (optional)</Label>
                <Input
                  id="aadhaar"
                  placeholder="XXXX XXXX XXXX"
                  value={aadhaar}
                  onChange={(e) => setAadhaar(e.target.value)}
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading && <Loader2 className="size-4 animate-spin" />}
                Search gallery
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>Matches</CardTitle>
            <CardDescription>
              {result
                ? `${result.matches?.length ?? 0} candidate(s) found.`
                : "Run a search to see CCTV matches."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Case ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Camera</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(result?.matches ?? []).map((m) => (
                  <TableRow key={m.case_id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {m.case_id}
                    </TableCell>
                    <TableCell className="font-medium">{m.matched_name}</TableCell>
                    <TableCell className="text-muted-foreground">{m.camera_id}</TableCell>
                    <TableCell className="text-right font-medium text-primary">
                      {(m.score * 100).toFixed(0)}%
                    </TableCell>
                  </TableRow>
                ))}
                {!result && (
                  <TableRow>
                    <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                      No results yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>

            {result?.route && (
              <div className="rounded-lg border border-border bg-surface-1 p-4">
                <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                  <MapPin className="size-4 text-primary" /> Route to {result.route.to}
                </p>
                <ol className="list-inside list-decimal space-y-1 text-sm text-muted-foreground">
                  {result.route.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

const MOCK = {
  matches: [
    { case_id: "FOUND-0007", score: 0.93, camera_id: "CAM-12", matched_name: "Ramabai Pawar" },
    { case_id: "FOUND-0021", score: 0.71, camera_id: "CAM-04", matched_name: "Unknown" },
  ],
  route: {
    to: "Police Station — Sector 12",
    lat: 25.43,
    lng: 81.88,
    steps: ["Head north from CAM-12", "Cross Sangam Bridge", "Police Station 200m on right"],
  },
};
