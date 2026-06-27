import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, ArrowLeft, Phone, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { requestOtp, verifyOtp } from "@/public/publicApi";
import { usePublicAuth } from "@/public/auth/PublicAuthContext";
import { useLang } from "@/public/i18n/LanguageContext";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";

export default function Track() {
  const navigate = useNavigate();
  const { t } = useLang();
  const { phone: sessionPhone, setPhone } = usePublicAuth();
  const [step, setStep] = useState("phone"); // phone | code
  const [phone, setPhoneInput] = useState("");
  const [code, setCode] = useState("");
  const [demoCode, setDemoCode] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (sessionPhone) navigate("/reports", { replace: true });
  }, [sessionPhone, navigate]);

  async function sendCode(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const { demo_code } = await requestOtp(phone);
      setDemoCode(demo_code || "");
      if (demo_code) setCode(demo_code); // demo convenience
      setStep("code");
      toast.success(t("toast.codeSent"));
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function verify(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const p = await verifyOtp(phone, code);
      setPhone(p);
      toast.success(t("toast.signedIn"));
      navigate("/reports", { replace: true });
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-background px-4 py-10">
      <div className="mx-auto w-full max-w-sm">
        <Link to="/" className="mb-4 inline-flex items-center gap-1 text-base text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" /> {t("common.back")}
        </Link>
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-primary" /> {t("track.title")}
            </CardTitle>
            <CardDescription>
              {step === "phone" ? t("track.descPhone") : t("track.descCode", { phone })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {step === "phone" ? (
              <form onSubmit={sendCode} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="phone" className="text-base">{t("track.phoneLabel")}</Label>
                  <Input id="phone" type="tel" required placeholder="+91…" value={phone}
                    className="h-14 text-lg" onChange={(e) => setPhoneInput(e.target.value)} />
                </div>
                <Button type="submit" className="h-14 w-full text-base" disabled={loading}>
                  {loading && <Loader2 className="size-5 animate-spin" />}
                  <Phone className="size-5" /> {t("track.sendCode")}
                </Button>
              </form>
            ) : (
              <form onSubmit={verify} className="space-y-4">
                {demoCode && (
                  <div className="rounded-md border border-info/30 bg-info/10 px-3 py-2 text-center text-sm">
                    {t("track.demoCode")} <span className="font-mono font-semibold">{demoCode}</span>
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="code" className="text-base">{t("track.codeLabel")}</Label>
                  <Input id="code" inputMode="numeric" required placeholder="------" value={code}
                    onChange={(e) => setCode(e.target.value)} className="h-14 text-center text-2xl tracking-[0.4em]" />
                </div>
                <Button type="submit" className="h-14 w-full text-base" disabled={loading}>
                  {loading && <Loader2 className="size-5 animate-spin" />} {t("track.verify")}
                </Button>
                <button type="button" onClick={() => setStep("phone")}
                  className="w-full text-center text-sm text-muted-foreground hover:text-foreground">
                  {t("track.diffNumber")}
                </button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
