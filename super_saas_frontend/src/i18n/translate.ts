import pt from "./pt.json";
import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";

const translations = { pt, en, es, fr } as const;

export type Language = keyof typeof translations;
export type TranslationKey = keyof typeof pt;

export const defaultLanguage: Language = "pt";

function getSelectedLanguage(): Language {
  if (typeof window === "undefined") {
    return defaultLanguage;
  }

  const selected = localStorage.getItem("language");
  if (!selected) {
    return defaultLanguage;
  }

  const normalized = selected.toLowerCase().split("-")[0] as Language;
  return normalized in translations ? normalized : defaultLanguage;
}

export function t(key: TranslationKey): string {
  const language = getSelectedLanguage();
  return translations[language][key] ?? translations[defaultLanguage][key] ?? key;
}

export function tStatus(status: string): string {
  const statusKey = `status_${status.toLowerCase()}` as TranslationKey;
  return t(statusKey);
}
