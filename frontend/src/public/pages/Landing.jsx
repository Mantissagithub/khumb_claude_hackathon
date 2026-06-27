import { Link } from "react-router-dom";
import { HeartHandshake, FilePlus2, Search, Phone } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { useLang } from "@/public/i18n/LanguageContext";
import VoiceAssistant from "@/public/assistant/VoiceAssistant";

export default function Landing() {
  const { t } = useLang();
  return (
    <div className="bg-background px-4 pb-28 pt-10">
      <div className="mx-auto w-full max-w-md">
        <div className="space-y-2 text-center">
          <HeartHandshake className="mx-auto size-12 text-primary" />
          <h1 className="text-2xl font-semibold tracking-tight">{t("landing.heading")}</h1>
          <p className="text-sm text-muted-foreground">{t("landing.subtitle")}</p>
        </div>

        <div className="mt-8 space-y-3">
          <Button asChild className="h-16 w-full text-lg">
            <Link to="/new">
              <FilePlus2 className="size-6" /> {t("landing.fileReport")}
            </Link>
          </Button>
          <Button asChild variant="secondary" className="h-16 w-full text-lg">
            <Link to="/track">
              <Search className="size-6" /> {t("landing.viewReports")}
            </Link>
          </Button>
        </div>

        <div className="mt-10 rounded-lg border border-border bg-card p-4 text-center">
          <p className="flex items-center justify-center gap-2 text-sm font-medium">
            <Phone className="size-4 text-primary" /> {t("landing.helpline")}
          </p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">1920</p>
          <p className="text-xs text-muted-foreground">{t("landing.helplineSub")}</p>
        </div>

        <p className="mt-8 text-center text-[11px] text-muted-foreground">
          {t("landing.staff")}{" "}
          <Link to="/ops/login" className="font-medium text-primary hover:underline">
            {t("landing.staffLink")}
          </Link>
        </p>
      </div>

      <VoiceAssistant />
    </div>
  );
}
