import { useLang } from "./LanguageContext";

// First-run gate: shown until the citizen picks a language. Big, language-neutral
// buttons so it's usable before any copy is localized.
export default function LanguageSelect() {
  const { setLang, langs, t } = useLang();
  return (
    <div className="min-h-svh bg-background px-4 py-10">
      <div className="mx-auto w-full max-w-md text-center">
        <div className="mx-auto mb-6 grid size-16 place-items-center rounded-2xl bg-sig-coral text-3xl font-semibold text-white">
          स
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">SANGAM</h1>
        <p className="mt-2 text-base text-muted-foreground">{t("langSelect.subtitle")}</p>

        <div className="mt-8 space-y-3">
          {langs.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              className="flex h-16 w-full items-center justify-center rounded-xl border border-border bg-card text-xl font-medium transition-colors hover:border-primary/60 active:translate-y-px"
            >
              {l.native}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
