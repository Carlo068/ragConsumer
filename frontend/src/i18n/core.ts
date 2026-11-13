import { en, type Messages } from "./messages/en"
import { es } from "./messages/es"

export type Locale = "es" | "en"
export const LOCALES: Locale[] = ["es", "en"]
export const DEFAULT_LOCALE: Locale = "es"

export const catalogs: Record<Locale, Messages> = { es, en }

// "a.b.c" for every string leaf of the catalog, so a misspelled key is a
// compile error rather than a blank label.
type Leaves<T, Prefix extends string = ""> = {
  [K in keyof T & string]: T[K] extends string
    ? `${Prefix}${K}`
    : Leaves<T[K], `${Prefix}${K}.`>
}[keyof T & string]

export type MessageKey = Leaves<Messages>
export type Params = Record<string, string | number>

export function lookup(messages: Messages, key: string): string | undefined {
  let node: unknown = messages
  for (const part of key.split(".")) {
    if (node === null || typeof node !== "object") return undefined
    node = (node as Record<string, unknown>)[part]
  }
  return typeof node === "string" ? node : undefined
}

export function interpolate(template: string, params?: Params): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole
  )
}

export function translate(locale: Locale, key: string, params?: Params): string {
  // Fall back to the other language, then to the key itself, so a gap shows up
  // as visible text during development instead of an empty button.
  const text = lookup(catalogs[locale], key) ?? lookup(catalogs.en, key) ?? key
  return interpolate(text, params)
}

export type Translate = (key: MessageKey, params?: Params) => string

// Turns whatever went wrong into a message in the person's language. Backend
// errors carry a stable code, so the English text the server also sends is
// never shown; anything without a code falls back by HTTP status.
export function describeError(
  err: unknown,
  t: Translate,
  fallbackKey: MessageKey = "errors.unknown"
): string {
  const error = err as { status?: number; code?: string; params?: Params } | null
  if (error?.code && lookup(en, `errors.${error.code}`) !== undefined) {
    return t(`errors.${error.code}` as MessageKey, error.params)
  }
  const status = error?.status
  if (status === 401) return t("errors.not_authenticated")
  if (status === 403) return t("errors.status403")
  if (status === 404) return t("errors.status404")
  if (status === 409) return t("errors.status409")
  if (status === 413) return t("errors.status413")
  if (status === 422) return t("errors.status422")
  if (status !== undefined && status >= 500) return t("errors.status5xx")
  if (error instanceof TypeError) return t("errors.network") // fetch could not connect
  return t(fallbackKey)
}
