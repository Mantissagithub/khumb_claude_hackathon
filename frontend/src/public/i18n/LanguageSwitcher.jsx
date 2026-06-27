import { useState } from "react";
import { createPortal } from "react-dom";
import { Globe, Check, X } from "lucide-react";
import { useLang } from "./LanguageContext";

// "Language" button → bottom sheet listing every supported language.
export default function LanguageSwitcher() {
  const { lang, setLang, langs } = useLang();
  const [open, setOpen] = useState(false);
  const current = langs.find((l) => l.code === lang);

  function choose(code) {
    setLang(code);
    setOpen(false);
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-2 text-sm font-medium text-foreground"
        aria-haspopup="dialog"
      >
        <Globe className="size-4 text-primary" />
        <span>{current?.native || "Language"}</span>
      </button>

      {open && createPortal(
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />

          {/* Sheet */}
          <div className="absolute inset-x-0 bottom-0 mx-auto flex max-h-[80svh] w-full max-w-md flex-col rounded-t-2xl border border-border bg-card shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <p className="flex items-center gap-2 text-base font-semibold">
                <Globe className="size-5 text-primary" /> Language · भाषा
              </p>
              <button onClick={() => setOpen(false)} aria-label="Close" className="rounded-full p-1 hover:bg-muted">
                <X className="size-5" />
              </button>
            </div>

            <div className="overflow-y-auto p-2">
              {langs.map((l) => {
                const active = l.code === lang;
                return (
                  <button
                    key={l.code}
                    onClick={() => choose(l.code)}
                    dir="auto"
                    className={`flex w-full items-center justify-between gap-3 rounded-xl px-4 py-4 text-left transition-colors ${
                      active ? "bg-secondary" : "hover:bg-muted"
                    }`}
                  >
                    <span className="flex items-baseline gap-2">
                      <span className="text-lg font-medium">{l.native}</span>
                      <span className="text-sm text-muted-foreground">{l.label}</span>
                    </span>
                    {active && <Check className="size-5 shrink-0 text-primary" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
