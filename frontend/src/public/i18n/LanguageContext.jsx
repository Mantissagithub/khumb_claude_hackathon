import { createContext, useContext, useState, useCallback } from "react";
import { translations } from "./translations";
import { LANGS } from "./languages";

export { LANGS };

const STORAGE_KEY = "sangam-lang";
const LanguageContext = createContext(null);

function resolve(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return LANGS.some((l) => l.code === stored) ? stored : null;
  });

  const setLang = useCallback((code) => {
    localStorage.setItem(STORAGE_KEY, code);
    setLangState(code);
  }, []);

  // t("a.b.c", { id: 5 }) — falls back to English, then to the key itself.
  const t = useCallback(
    (key, vars) => {
      const active = lang || "en";
      let str = resolve(translations[active], key);
      if (str == null) str = resolve(translations.en, key);
      if (str == null) return key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          str = str.replaceAll(`{${k}}`, String(v));
        }
      }
      return str;
    },
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, t, langs: LANGS, chosen: !!lang }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLang() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLang must be used within a LanguageProvider");
  return ctx;
}
