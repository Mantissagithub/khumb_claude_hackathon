import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
import { useLang } from "@/public/i18n/LanguageContext";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { Card, CardContent } from "@/shared/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";

const AGE_BANDS = ["0-12", "13-25", "26-40", "41-60", "61-70", "71-80", "80+"];

const TYPES = [
  { id: "lost_self", icon: UserX },
  { id: "seeking", icon: Search },
  { id: "found", icon: HandHeart },
];

// Shared sizing for big, easy-to-tap form controls.
const FIELD = "h-14 text-base";
const LABEL = "text-base font-semibold";

export default function NewReport() {
  const navigate = useNavigate();
  const { t } = useLang();
  const [searchParams] = useSearchParams();
  const presetType = searchParams.get("type");
  const [type, setType] = useState(
    TYPES.some((ty) => ty.id === presetType) ? presetType : null
  );
  const [photo, setPhoto] = useState(null);
  const [gender, setGender] = useState("");
  const [ageBand, setAgeBand] = useState("");
  const [coords, setCoords] = useState(null); // {lat,lng}
  const [locating, setLocating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(null);

  const isFound = type === "found";
  const isSelf = type === "lost_self";

  // Inside the form, Back returns to the type chooser; on the chooser it goes home.
  function goBack() {
    if (type) setType(null);
    else navigate("/");
  }

  function useMyLocation() {
    if (!navigator.geolocation) return toast.error(t("toast.locationUnavailable"));
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
        toast.success(t("toast.locationCaptured"));
      },
      () => {
        setLocating(false);
        toast.error(t("toast.locationFailed"));
      }
    );
  }

  async function onSubmit(e) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const phone = fd.get("phone");
    if (!phone) return toast.error(t("toast.phoneRequired"));
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
      toast.error(err.message ?? t("toast.submitFailed"));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="grid place-items-center bg-background px-4 py-16">
        <Card className="w-full max-w-md border-border bg-card text-center">
          <CardContent className="space-y-3 py-10">
            <CheckCircle2 className="mx-auto size-12 text-success" />
            <h2 className="text-xl font-semibold">{t("newReport.received")}</h2>
            <p className="text-sm text-muted-foreground">{t("newReport.receivedMsg", { id: done.id })}</p>
            <div className="flex flex-col gap-2 pt-2">
              <Button className="h-14 text-base font-semibold" onClick={() => navigate("/track")}>
                {t("newReport.trackBtn")}
              </Button>
              <Button
                variant="secondary"
                className="h-14 text-base font-semibold"
                onClick={() => { setDone(null); setType(null); }}
              >
                {t("newReport.fileAnother")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="bg-background px-4 py-6">
      <div className="mx-auto w-full max-w-xl">
        <button
          onClick={goBack}
          className="mb-5 inline-flex items-center gap-1.5 text-base font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-5" /> {t("common.back")}
        </button>

        {!type ? (
          <>
            <h1 className="text-2xl font-bold tracking-tight">{t("newReport.q")}</h1>
            <p className="mt-1 text-base text-muted-foreground">{t("newReport.qSub")}</p>

            <div className="mt-6 space-y-3">
              {TYPES.map(({ id, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setType(id)}
                  className="flex w-full items-center gap-4 rounded-2xl border-2 border-border bg-card p-5 text-left transition-colors hover:border-primary active:translate-y-px"
                >
                  <div className="grid size-14 shrink-0 place-items-center rounded-xl bg-secondary text-primary">
                    <Icon className="size-7" />
                  </div>
                  <div>
                    <p className="text-lg font-semibold">{t(`types.${id}.label`)}</p>
                    <p className="text-sm text-muted-foreground">{t(`types.${id}.blurb`)}</p>
                  </div>
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-bold tracking-tight">{t(`types.${type}.label`)}</h1>
            <p className="mt-1 text-base text-muted-foreground">{t("newReport.detailSub")}</p>

            <form onSubmit={onSubmit} className="mt-6 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="photo" className={LABEL}>
                  {isFound ? t("newReport.photoFound") : t("newReport.photoOpt")}
                </Label>
                <label
                  htmlFor="photo"
                  className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-border p-8 text-center text-base text-muted-foreground hover:border-primary"
                >
                  <Upload className="size-7" />
                  {photo ? photo.name : t("newReport.photoTap")}
                </label>
                <Input id="photo" type="file" accept="image/*" capture="environment" className="hidden"
                  onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="person_name" className={LABEL}>
                  {isSelf ? t("newReport.nameSelf") : isFound ? t("newReport.nameFound") : t("newReport.nameKnown")}
                </Label>
                <Input id="person_name" name="person_name" className={FIELD} placeholder={t("newReport.namePlaceholder")} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className={LABEL}>{t("newReport.gender")}</Label>
                  <Select value={gender} onValueChange={setGender}>
                    <SelectTrigger className={FIELD}><SelectValue placeholder={t("common.select")} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Male">{t("gender.male")}</SelectItem>
                      <SelectItem value="Female">{t("gender.female")}</SelectItem>
                      <SelectItem value="Other">{t("gender.other")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className={LABEL}>{t("newReport.age")}</Label>
                  <Select value={ageBand} onValueChange={setAgeBand}>
                    <SelectTrigger className={FIELD}><SelectValue placeholder={t("common.select")} /></SelectTrigger>
                    <SelectContent>
                      {AGE_BANDS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="location_text" className={LABEL}>
                  {isFound ? t("newReport.locFound") : t("newReport.locLast")}
                </Label>
                <Input id="location_text" name="location_text" className={FIELD} placeholder={t("newReport.locPlaceholder")} />
              </div>

              {isFound && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="center_name" className={LABEL}>{t("newReport.center")}</Label>
                    <Input id="center_name" name="center_name" className={FIELD} placeholder={t("newReport.centerPlaceholder")} />
                  </div>
                  <Button type="button" variant="secondary" className="h-14 w-full text-base font-semibold" onClick={useMyLocation} disabled={locating}>
                    {locating ? <Loader2 className="size-5 animate-spin" /> : <MapPin className="size-5" />}
                    {coords
                      ? t("newReport.locationCaptured", { lat: coords.lat.toFixed(4), lng: coords.lng.toFixed(4) })
                      : t("newReport.useLocation")}
                  </Button>
                </>
              )}

              <div className="space-y-2">
                <Label htmlFor="description" className={LABEL}>{t("newReport.description")}</Label>
                <Textarea id="description" name="description" rows={3} className="text-base"
                  placeholder={t("newReport.descPlaceholder")} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone" className={LABEL}>{t("newReport.phone")}</Label>
                <Input id="phone" name="phone" type="tel" required className={FIELD} placeholder="+91…" />
                <p className="text-sm text-muted-foreground">{t("newReport.phoneHelp")}</p>
              </div>

              <Button type="submit" className="h-14 w-full text-base font-semibold" disabled={loading}>
                {loading && <Loader2 className="size-5 animate-spin" />} {t("newReport.submit")}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
