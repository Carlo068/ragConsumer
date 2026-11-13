import { useContext } from "react"
import { I18nContext, fallbackLocale, type I18nValue } from "./context"
import { describeError, translate, translatePlural, type Locale, type Translate } from "./core"

// Built once per language and reused, so hooks that depend on these functions
// don't see a "new" value on every render.
const fallbackCache = new Map<Locale, I18nValue>()

function fallbackValue(locale: Locale): I18nValue {
  let value = fallbackCache.get(locale)
  if (!value) {
    const t: Translate = (key, params) => translate(locale, key, params)
    const tag = locale === "es" ? "es-MX" : "en-US"
    value = {
      locale,
      setLocale: () => {},
      t,
      tp: (key, count, params) => translatePlural(locale, key, count, params),
      formatDate: (v) => new Date(v + "Z").toLocaleDateString(tag),
      formatDateTime: (v) => new Date(v + "Z").toLocaleString(tag),
      errorText: (err, fallbackKey) => describeError(err, t, fallbackKey),
    }
    fallbackCache.set(locale, value)
  }
  return value
}

export function useI18n(): I18nValue {
  // With no provider mounted (only tests render a component alone) the
  // fallback language is used; production always has the provider.
  return useContext(I18nContext) ?? fallbackValue(fallbackLocale)
}
