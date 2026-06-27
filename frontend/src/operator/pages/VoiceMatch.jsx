import { useState } from "react";
import { AudioLines, Upload, Loader2, Languages } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Badge } from "@/shared/ui/badge";
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
import { voiceMatch } from "@/shared/api";

// Member 2 owns this file. Endpoint: POST /api/voice/match
export default function VoiceMatch() {
  const [audio, setAudio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    if (!audio) return toast.error("Upload an audio clip first");
    setLoading(true);
    try {
      const form = new FormData();
      form.append("audio", audio);
      const data = await voiceMatch(form);
      setResult(data);
      toast.success("Transcribed & matched");
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
        title="Cross-Language Voice Matching"
        description="A pilgrim who can't speak the local language records audio — we transcribe, translate, and match it against existing records."
      />

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AudioLines className="size-4 text-primary" /> Record / Upload
            </CardTitle>
            <CardDescription>Accepts .wav / .mp3 / .m4a clips.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="audio">Audio clip</Label>
                <label
                  htmlFor="audio"
                  className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-surface-1 p-6 text-center text-sm text-muted-foreground hover:border-primary/50"
                >
                  <Upload className="size-5" />
                  {audio ? audio.name : "Click to upload an audio clip"}
                </label>
                <Input
                  id="audio"
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={(e) => setAudio(e.target.files?.[0] ?? null)}
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading && <Loader2 className="size-4 animate-spin" />}
                Transcribe & match
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Languages className="size-4 text-primary" /> Transcript
              </CardTitle>
              <CardDescription>
                {result ? (
                  <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">
                    Detected: {result.language}
                  </Badge>
                ) : (
                  "Upload a clip to see the transcript."
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">Original</p>
                <p className="rounded-md bg-surface-1 p-3">{result?.transcript ?? "—"}</p>
              </div>
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">English</p>
                <p className="rounded-md bg-surface-1 p-3">{result?.transcript_en ?? "—"}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle>Candidate matches</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(result?.candidates ?? []).map((c) => (
                    <TableRow key={c.case_id}>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {c.case_id}
                      </TableCell>
                      <TableCell className="font-medium">{c.name}</TableCell>
                      <TableCell className="text-right font-medium text-primary">
                        {(c.score * 100).toFixed(0)}%
                      </TableCell>
                    </TableRow>
                  ))}
                  {!result && (
                    <TableRow>
                      <TableCell colSpan={3} className="py-8 text-center text-muted-foreground">
                        No results yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

const MOCK = {
  language: "Tamil",
  transcript: "எனக்கு என் மகனை காணவில்லை, அவர் பெயர் முருகன்",
  transcript_en: "I cannot find my son, his name is Murugan",
  candidates: [
    { case_id: "KMP-2027-00088", score: 0.88, name: "Murugan S." },
    { case_id: "KMP-2027-00102", score: 0.64, name: "Muruga Vel" },
  ],
};
