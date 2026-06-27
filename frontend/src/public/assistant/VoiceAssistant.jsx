import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, MicOff, X, Send, Loader2, Volume2 } from "lucide-react";
import { askAssistant } from "@/public/assistant/assistantApi";
import { useLang } from "@/public/i18n/LanguageContext";
import { SPEECH_LOCALE } from "@/public/i18n/translations";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";

const SR =
  typeof window !== "undefined" &&
  (window.SpeechRecognition || window.webkitSpeechRecognition);

export default function VoiceAssistant() {
  const navigate = useNavigate();
  const { t, lang } = useLang();
  const [open, setOpen] = useState(false);
  const [convo, setConvo] = useState([]); // {role, content}
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [text, setText] = useState("");
  const recognitionRef = useRef(null);
  const scrollRef = useRef(null);

  const locale = SPEECH_LOCALE[lang] || "en-IN";
  const voiceSupported = !!SR;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [convo, thinking]);

  // Stop everything when the panel closes.
  useEffect(() => {
    if (!open) {
      try { recognitionRef.current?.stop(); } catch { /* ignore */ }
      window.speechSynthesis?.cancel();
      setListening(false);
    }
  }, [open]);

  function speak(message) {
    if (!message || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(message);
    u.lang = locale;
    window.speechSynthesis.speak(u);
  }

  async function send(message) {
    const trimmed = (message || "").trim();
    if (!trimmed || thinking) return;
    const next = [...convo, { role: "user", content: trimmed }];
    setConvo(next);
    setText("");
    setThinking(true);
    try {
      const data = await askAssistant(next, lang);
      const reply = data.reply || "";
      if (reply) {
        setConvo([...next, { role: "assistant", content: reply }]);
        speak(reply);
      }
      if (data.navigate) {
        const route =
          data.navigate === "/new" && data.report_type
            ? `/new?type=${data.report_type}`
            : data.navigate;
        setTimeout(() => { setOpen(false); navigate(route); }, reply ? 900 : 0);
      }
    } catch {
      const msg = t("toast.assistantError");
      setConvo([...next, { role: "assistant", content: msg }]);
      speak(msg);
    } finally {
      setThinking(false);
    }
  }

  function toggleListen() {
    if (!voiceSupported) return;
    if (listening) {
      try { recognitionRef.current?.stop(); } catch { /* ignore */ }
      setListening(false);
      return;
    }
    window.speechSynthesis?.cancel();
    const rec = new SR();
    rec.lang = locale;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      const transcript = e.results?.[0]?.[0]?.transcript;
      setListening(false);
      if (transcript) send(transcript);
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }

  return (
    <>
      {/* Floating launcher */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label={t("assistant.open")}
          className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-primary px-5 py-4 text-primary-foreground shadow-lg transition-transform hover:scale-105 active:scale-95"
        >
          <Mic className="size-6" />
          <span className="text-base font-medium">{t("assistant.open")}</span>
        </button>
      )}

      {/* Panel */}
      {open && (
        <div className="fixed inset-x-0 bottom-0 z-50 mx-auto w-full max-w-md rounded-t-2xl border border-border bg-card shadow-2xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="flex items-center gap-2 text-base font-semibold">
              <Volume2 className="size-5 text-primary" /> {t("assistant.title")}
            </p>
            <Button variant="ghost" size="icon" aria-label="Close" onClick={() => setOpen(false)}>
              <X className="size-5" />
            </Button>
          </div>

          <div ref={scrollRef} className="max-h-[50svh] space-y-3 overflow-y-auto px-4 py-4">
            <Bubble role="assistant" text={t("assistant.greeting")} />
            {convo.map((m, i) => (
              <Bubble key={i} role={m.role} text={m.content} />
            ))}
            {(thinking || listening) && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                {listening ? t("assistant.listening") : t("assistant.thinking")}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 border-t border-border p-3">
            {voiceSupported && (
              <Button
                type="button"
                size="icon-lg"
                variant={listening ? "destructive" : "default"}
                aria-label={t("assistant.open")}
                className="size-14 shrink-0 rounded-full"
                onClick={toggleListen}
              >
                {listening ? <MicOff className="size-6" /> : <Mic className="size-6" />}
              </Button>
            )}
            <form
              className="flex flex-1 items-center gap-2"
              onSubmit={(e) => { e.preventDefault(); send(text); }}
            >
              <Input
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t("assistant.typePlaceholder")}
                className="h-12 text-base"
              />
              <Button type="submit" size="icon-lg" className="size-12 shrink-0" aria-label={t("assistant.send")} disabled={!text.trim() || thinking}>
                <Send className="size-5" />
              </Button>
            </form>
          </div>

          {!voiceSupported && (
            <p className="px-4 pb-3 text-xs text-muted-foreground">{t("assistant.unsupported")}</p>
          )}
        </div>
      )}
    </>
  );
}

function Bubble({ role, text }) {
  const mine = role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2 text-base ${
          mine ? "bg-primary text-primary-foreground" : "bg-surface-1 text-foreground"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
