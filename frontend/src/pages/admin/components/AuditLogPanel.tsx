import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { AUDIT_ACTION_LABELS, auditActionLabel, type AuditEntry, type AuditFilters } from "@/models/audit"

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
  const [actor, setActor] = useState(filters.actor ?? "")

  function handleSearch(event: FormEvent) {
    event.preventDefault()
    onFilter({ ...filters, actor: actor.trim() || undefined })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Activity log</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-muted-foreground text-sm">
          Who did what, and when, including every search an AI assistant ran. Entries can't be
          edited or deleted.
        </p>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            What happened
            <select
              className="border-input bg-background h-9 rounded-md border px-2 text-sm"
              value={filters.action ?? ""}
              onChange={(e) => onFilter({ ...filters, action: e.target.value || undefined })}
            >
              <option value="">Everything</option>
              {Object.entries(AUDIT_ACTION_LABELS).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <form onSubmit={handleSearch} className="flex items-end gap-2">
            <label className="flex flex-col gap-1 text-sm">
              Person
              <Input
                value={actor}
                onChange={(e) => setActor(e.target.value)}
                placeholder="email"
              />
            </label>
            <Button type="submit" variant="outline">
              Filter
            </Button>
          </form>
          <Button
            variant="outline"
            nativeButton={false}
            render={<a href={csvUrl}>Download as spreadsheet (CSV)</a>}
          />
        </div>

        {error && <p className="text-destructive text-sm">{error}</p>}
        {loading && <p className="text-sm">Loading...</p>}
        {!loading && items.length === 0 && (
          <p className="text-muted-foreground text-sm">No activity matches.</p>
        )}

        <div className="flex flex-col divide-y">
          {items.map((entry) => (
            <div key={entry.id} className="flex flex-col gap-0.5 py-2 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">{auditActionLabel(entry.action)}</span>
                <span className="text-muted-foreground text-xs">
                  {new Date(entry.occurred_at + "Z").toLocaleString()}
                </span>
              </div>
              <p className="text-muted-foreground text-xs">
                {entry.actor_email ?? "Not signed in"}
                {entry.collection_name ? ` · ${entry.collection_name}` : ""}
              </p>
              {summarize(entry) && <p className="text-xs break-words">{summarize(entry)}</p>}
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{total} entries</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={!hasPrevious} onClick={onPrevious}>
              Newer
            </Button>
            <Button variant="outline" size="sm" disabled={!hasNext} onClick={onNext}>
              Older
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
