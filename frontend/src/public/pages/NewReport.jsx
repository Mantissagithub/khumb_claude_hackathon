import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Upload,
  Loader2,
  CheckCircle2,
  ArrowLeft,
  UserX,
  Search,
  HandHeart,
  MapPin,
} from "lucide-react";
import { toast } from "sonner";
import { submitReport, uploadPhoto } from "@/public/publicApi";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";

const AGE_BANDS = ["0-12", "13-25", "26-40", "41-60", "61-70", "71-80", "80+"];

const TYPES = [
  { id: "lost_self", label: "I am lost", icon: UserX, blurb: "Report yourself as separated from your group." },
  { id: "seeking", label: "I'm searching for someone", icon: Search, blurb: "A family member or friend is missing." },
  { id: "found", label: "I found a lost person", icon: HandHeart, blurb: "You found someone who seems lost." },
];

export default function NewReport() {
  const navigate = useNavigate();
  const [type, setType] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [gender, setGender] = useState("");
  const [ageBand, setAgeBand] = useState("");
  const [coords, setCoords] = useState(null); // {lat,lng}
  const [locating, setLocating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(null);

  const isFound = type === "found";
  const isSelf = type === "lost_self";

  function useMyLocation() {
    if (!navigator.geolocation) return toast.error("Location not available on this device");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
        toast.success("Location captured");
      },
      () => {
        setLocating(false);
        toast.error("Could not get location");
      }
    );
  }

  async function onSubmit(e) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const phone = fd.get("phone");
    if (!phone) return toast.error("Your contact number is required");
    setLoading(true);
    try {
      let photo_path = null;
      if (photo) photo_path = await uploadPhoto(photo);
      const id = await submitReport({
        phone,
        report_type: type,
        person_name: fd.get("person_name"),
        gender,
        age_band: ageBand,
        description: fd.get("description"),
        location_text: fd.get("location_text"),
        center_name: fd.get("center_name"),
        photo_path,
        lat: coords?.lat,
        lng: coords?.lng,
      });
      setDone({ id, phone });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      toast.error(err.message ?? "Submission failed");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="grid min-h-svh place-items-center bg-background px-4">
        <Card className="w-full max-w-md border-border bg-card text-center">
          <CardContent className="space-y-3 py-10">
            <CheckCircle2 className="mx-auto size-12 text-success" />
            <h2 className="text-xl font-semibold">Report received</h2>
            <p className="text-sm text-muted-foreground">
              Reference <span className="font-mono font-semibold">#{done.id}</span>. We're actively
              searching across all centers. Track the status anytime by logging in with your phone
              number.
            </p>
            <div className="flex flex-col gap-2 pt-2">
              <Button onClick={() => navigate("/track")}>Track my report</Button>
              <Button variant="secondary" onClick={() => { setDone(null); setType(null); }}>
                File another report
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-svh bg-background px-4 py-8">
      <div className="mx-auto w-full max-w-xl">
        <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Back
        </Link>

        {!type ? (
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle>What would you like to report?</CardTitle>
              <CardDescription>Choose the option that fits your situation.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {TYPES.map(({ id, label, icon: Icon, blurb }) => (
                <button
                  key={id}
                  onClick={() => setType(id)}
                  className="flex w-full items-center gap-3 rounded-lg border border-border bg-surface-1 p-4 text-left transition-colors hover:border-primary/50"
                >
                  <div className="grid size-10 shrink-0 place-items-center rounded-md bg-secondary text-primary">
                    <Icon className="size-5" />
                  </div>
                  <div>
                    <p className="font-medium">{label}</p>
                    <p className="text-sm text-muted-foreground">{blurb}</p>
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>
        ) : (
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle>{TYPES.find((t) => t.id === type).label}</CardTitle>
              <CardDescription>
                Add as much detail as you can — it helps us match faster.{" "}
                <button onClick={() => setType(null)} className="text-primary hover:underline">
                  Change
                </button>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="photo">{isFound ? "Photo of the person you found" : "Photo (if you have one)"}</Label>
                  <label
                    htmlFor="photo"
                    className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-surface-1 p-6 text-center text-sm text-muted-foreground hover:border-primary/50"
                  >
                    <Upload className="size-5" />
                    {photo ? photo.name : "Tap to add a photo"}
                  </label>
                  <Input id="photo" type="file" accept="image/*" capture="environment" className="hidden"
                    onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="person_name">
                    {isSelf ? "Your name" : isFound ? "Their name (if they can tell you)" : "Their name (if known)"}
                  </Label>
                  <Input id="person_name" name="person_name" placeholder="e.g. Ramesh Kumar" />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>Gender</Label>
                    <Select value={gender} onValueChange={setGender}>
                      <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Male">Male</SelectItem>
                        <SelectItem value="Female">Female</SelectItem>
                        <SelectItem value="Other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Approx. age</Label>
                    <Select value={ageBand} onValueChange={setAgeBand}>
                      <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                      <SelectContent>
                        {AGE_BANDS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="location_text">{isFound ? "Where did you find them?" : "Last seen location"}</Label>
                  <Input id="location_text" name="location_text" placeholder="e.g. Ramkund Ghat" />
                </div>

                {isFound && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="center_name">Help center they're at (if any)</Label>
                      <Input id="center_name" name="center_name" placeholder="e.g. Panchavati Help Center" />
                    </div>
                    <Button type="button" variant="secondary" className="w-full" onClick={useMyLocation} disabled={locating}>
                      {locating ? <Loader2 className="size-4 animate-spin" /> : <MapPin className="size-4" />}
                      {coords ? `Location captured (${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)})` : "Use my current location"}
                    </Button>
                  </>
                )}

                <div className="space-y-2">
                  <Label htmlFor="description">Description (clothes, marks, etc.)</Label>
                  <Textarea id="description" name="description" rows={3}
                    placeholder="e.g. saffron kurta, rudraksha mala, hard of hearing" />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phone">Your phone number *</Label>
                  <Input id="phone" name="phone" type="tel" required placeholder="+91…" />
                  <p className="text-xs text-muted-foreground">
                    Used to update you on a match and to view your report later.
                  </p>
                </div>

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading && <Loader2 className="size-4 animate-spin" />} Submit report
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
