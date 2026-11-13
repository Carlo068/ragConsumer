import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { totals, type QueueItem } from "@/lib/bulk/queue"
import type { BulkPhase } from "@/hooks/useBulkUpload"
import type { MessageKey } from "@/i18n/core"
import { useI18n } from "@/i18n/useI18n"

interface BulkProgressProps {
  phase: BulkPhase
  items: QueueItem[]
  onStop: () => void
  onRetry: () => void
  onReset: () => void
}

function Bar({ fraction, label }: { fraction: number; label: string }) {
  const percent = Math.round(fraction * 100)
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className="bg-muted h-2 w-full overflow-hidden rounded-full"
    >
      <div className="bg-primary h-full transition-all" style={{ width: `${percent}%` }} />
    </div>
  )
}

// Overall and per-file progress while uploading, then a summary with the
// choice to retry what failed.
export function BulkProgress({ phase, items, onStop, onRetry, onReset }: BulkProgressProps) {
  const { t, tp, errorText } = useI18n()
  const sum = totals(items)
  const uploading = phase === "uploading"
  const unfinished = sum.failed + sum.cancelled

  return (
    <Card>
      <CardHeader>
        <CardTitle>{uploading ? t("bulk.uploading") : t("bulk.finishedTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Bar fraction={sum.fraction} label={t("bulk.progress", { done: sum.done, total: sum.total })} />
        <p className="text-sm">{t("bulk.progress", { done: sum.done, total: sum.total })}</p>

        {!uploading && sum.done > 0 && <p className="text-sm">{tp("bulk.finishedDone", sum.done)}</p>}
        {!uploading && unfinished > 0 && (
          <p className="text-destructive text-sm">{tp("bulk.finishedFailed", unfinished)}</p>
        )}

        <ul className="flex max-h-64 flex-col gap-2 overflow-auto text-sm">
          {items.map((item) => (
            <li key={item.id} className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-3">
                <span className="break-all">{item.path}</span>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {t(`bulk.state.${item.state}` as MessageKey)}
                </span>
              </div>
              {item.state === "uploading" && <Bar fraction={item.progress} label={item.path} />}
              {item.state === "failed" && (
                <p className="text-destructive text-xs">{errorText(item.error)}</p>
              )}
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2">
          {uploading ? (
            <Button type="button" variant="outline" onClick={onStop}>
              {t("bulk.stop")}
            </Button>
          ) : (
            <>
              {unfinished > 0 && (
                <Button type="button" onClick={onRetry}>
                  {t("bulk.retryFailed")}
                </Button>
              )}
              <Button type="button" variant="outline" onClick={onReset}>
                {t("bulk.uploadMore")}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
