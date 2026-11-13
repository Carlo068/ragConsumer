import { createContext } from "react"
import { DEFAULT_LOCALE, type Locale, type Translate, type TranslatePlural } from "./core"

export interface I18nValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: Translate
  // A message that depends on a number: tp("collections.fileCount", 3) -> "3 archivos".
  tp: TranslatePlural
  // Dates from the server are naive UTC timestamps; these show them in the
  // reader's language and time zone.
  formatDate: (value: string) => string
  formatDateTime: (value: string) => string
  // A message in the current language for whatever went wrong.
  errorText: (err: unknown, fallbackKey?: Parameters<Translate>[0]) => string
}

export const I18nContext = createContext<I18nValue | null>(null)

// The language used when no provider is mounted (only ever tests). Production
// always renders the provider, so Spanish is what people get.
export let fallbackLocale: Locale = DEFAULT_LOCALE
export function setFallbackLocale(locale: Locale) {
  fallbackLocale = locale
}
