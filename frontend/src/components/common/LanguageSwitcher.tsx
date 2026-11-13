import { LOCALES, type Locale } from "@/i18n/core"
import { useI18n } from "@/i18n/useI18n"

const LABELS: Record<Locale, string> = { es: "ES", en: "EN" }
const NAMES: Record<Locale, string> = { es: "Español", en: "English" }

// Spanish is the default; English stays available as a second language.
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n()
  return (
    <div role="group" aria-label={t("common.language")} className="flex gap-1 text-xs">
      {LOCALES.map((code) => (
        <button
          key={code}
          type="button"
          lang={code}
          title={NAMES[code]}
          aria-label={NAMES[code]}
          aria-pressed={locale === code}
          onClick={() => setLocale(code)}
          className={
            "rounded px-1.5 py-0.5 " +
            (locale === code ? "bg-muted font-semibold" : "text-muted-foreground hover:underline")
          }
        >
          {LABELS[code]}
        </button>
      ))}
    </div>
  )
}
