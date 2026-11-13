import { useEffect, useMemo, useState, type ReactNode } from "react"
import { I18nContext, type I18nValue } from "./context"
import { DEFAULT_LOCALE, LOCALES, describeError, translate, type Locale, type Translate } from "./core"

const STORAGE_KEY = "locale"

function loadLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && (LOCALES as string[]).includes(saved)) return saved as Locale
  } catch {
    // Storage can be blocked (private windows); the default is fine.
  }
  return DEFAULT_LOCALE
}

// Server timestamps are naive UTC (no zone), so mark them as UTC before parsing.
const toDate = (value: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : value + "Z")

export function I18nProvider({ children, locale: initial }: { children: ReactNode; locale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(initial ?? loadLocale())

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const value = useMemo<I18nValue>(() => {
    const t: Translate = (key, params) => translate(locale, key, params)
    const tag = locale === "es" ? "es-MX" : "en-US"
    return {
      locale,
      setLocale: (next) => {
        setLocaleState(next)
        try {
          localStorage.setItem(STORAGE_KEY, next)
        } catch {
          // not persisted, still applies for this visit
        }
      },
      t,
      formatDate: (v) => toDate(v).toLocaleDateString(tag),
      formatDateTime: (v) => toDate(v).toLocaleString(tag),
      errorText: (err, fallbackKey) => describeError(err, t, fallbackKey),
    }
  }, [locale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
