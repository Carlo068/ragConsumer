import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { MessageKey } from "@/i18n/core"
import { useI18n } from "@/i18n/useI18n"
import { AUDIT_ACTIONS, type AuditEntry, type AuditFilters } from "@/models/audit"

interface AuditLogPanelProps {
  items: AuditEntry[]
  total: number
  filters: AuditFilters
  loading: boolean
  error: string | null
  hasNext: boolean
  hasPrevious: boolean
  csvUrl: string
  onFilter: (filters: AuditFilters) => void
  onNext: () => void
  onPrevious: () => void
}

// What the entry is about, in a short readable line. For AI searches this is
// the question asked; the full record (with the passages returned) is in the CSV.
function summarize(entry: AuditEntry): string {
  const query = entry.detail?.query
  if (typeof query === "string") return `"${query}"`
  return entry.target ?? ""
}

export function AuditLogPanel({
  items,
  total,
  filters,
  loading,
  error,
  hasNext,
  hasPrevious,
  csvUrl,
  onFilter,
  onNext,
  onPrevious,
}: AuditLogPanelProps) {
  const { t, formatDateTime } = useI18n()
  const [actor, setActor] = useState(filters.actor ?? "")
  const actionLabel = (code: string) =>
    (AUDIT_ACTIONS as readonly string[]).includes(code) ? t(`audit.actions.${code}` as MessageKey) : code

  function handleSearch(event: FormEvent) {
    event.preventDefault()
    onFilter({ ...filters, actor: actor.trim() || undefined })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("audit.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-muted-foreground text-sm">
          {t("audit.intro")}
        </p>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            {t("audit.whatHappened")}
            <select
              className="border-input bg-background h-9 rounded-md border px-2 text-sm"
              value={filters.action ?? ""}
              onChange={(e) => onFilter({ ...filters, action: e.target.value || undefined })}
            >
              <option value="">{t("audit.everything")}</option>
              {AUDIT_ACTIONS.map((code) => (
                <option key={code} value={code}>
                  {t(`audit.actions.${code}` as MessageKey)}
                </option>
              ))}
            </select>
          </label>
          <form onSubmit={handleSearch} className="flex items-end gap-2">
            <label className="flex flex-col gap-1 text-sm">
              {t("audit.person")}
              <Input
                value={actor}
                onChange={(e) => setActor(e.target.value)}
                placeholder={t("audit.personPlaceholder")}
              />
            </label>
            <Button type="submit" variant="outline">
              {t("audit.filter")}
            </Button>
          </form>
          <Button
            variant="outline"
            nativeButton={false}
            render={<a href={csvUrl}>{t("audit.download")}</a>}
          />
        </div>

        {error && <p className="text-destructive text-sm">{error}</p>}
        {loading && <p className="text-sm">{t("common.loading")}</p>}
        {!loading && items.length === 0 && (
          <p className="text-muted-foreground text-sm">{t("audit.none")}</p>
        )}

        <div className="flex flex-col divide-y">
          {items.map((entry) => (
            <div key={entry.id} className="flex flex-col gap-0.5 py-2 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">{actionLabel(entry.action)}</span>
                <span className="text-muted-foreground text-xs">
                  {formatDateTime(entry.occurred_at)}
                </span>
              </div>
              <p className="text-muted-foreground text-xs">
                {entry.actor_email ?? t("audit.notSignedIn")}
                {entry.collection_name ? ` · ${entry.collection_name}` : ""}
              </p>
              {summarize(entry) && <p className="text-xs break-words">{summarize(entry)}</p>}
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{t("audit.total", { total })}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={!hasPrevious} onClick={onPrevious}>
              {t("audit.newer")}
            </Button>
            <Button variant="outline" size="sm" disabled={!hasNext} onClick={onNext}>
              {t("audit.older")}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
