import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, ArrowLeft, Phone, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { requestOtp, verifyOtp } from "@/public/publicApi";
import { usePublicAuth } from "@/public/auth/PublicAuthContext";
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
      toast.success("Verification code sent");
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
      toast.success("Signed in");
      navigate("/reports", { replace: true });
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-svh bg-background px-4 py-10">
      <div className="mx-auto w-full max-w-sm">
        <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Back
        </Link>
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-primary" /> View my reports
            </CardTitle>
            <CardDescription>
              {step === "phone"
                ? "Enter the phone number you used when filing your report."
                : `Enter the 6-digit code sent to ${phone}.`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {step === "phone" ? (
              <form onSubmit={sendCode} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone number</Label>
                  <Input id="phone" type="tel" required placeholder="+91…" value={phone}
                    onChange={(e) => setPhoneInput(e.target.value)} />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  <Phone className="size-4" /> Send code
                </Button>
              </form>
            ) : (
              <form onSubmit={verify} className="space-y-4">
                {demoCode && (
                  <div className="rounded-md border border-info/30 bg-info/10 px-3 py-2 text-center text-sm">
                    Demo code: <span className="font-mono font-semibold">{demoCode}</span>
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="code">Verification code</Label>
                  <Input id="code" inputMode="numeric" required placeholder="------" value={code}
                    onChange={(e) => setCode(e.target.value)} className="text-center tracking-[0.4em]" />
                </div>
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading && <Loader2 className="size-4 animate-spin" />} Verify &amp; view
                </Button>
                <button type="button" onClick={() => setStep("phone")}
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground">
                  Use a different number
                </button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
