import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Expanded } from "@/lib/bulk/collect"
import { formatBytes } from "@/lib/bulk/format"
import { summarizePlan, type PlanItem, type SkipReason } from "@/lib/bulk/plan"
import type { MessageKey } from "@/i18n/core"
import { useI18n } from "@/i18n/useI18n"

interface BulkReviewProps {
  plan: PlanItem[]
  zipProblems: Expanded["unreadableZips"]
  maxUploadBytes?: number
  onConfirm: () => void
  onCancel: () => void
}

const MB = 1024 * 1024
const REASON_ORDER: SkipReason[] = [
  "duplicate_existing",
  "duplicate_in_batch",
  "unsupported",
  "too_large",
  "empty",
  "system",
]
const MAX_LISTED = 100

function NameList({ items }: { items: PlanItem[] }) {
  return (
    <ul className="text-muted-foreground max-h-40 overflow-auto text-xs">
      {items.slice(0, MAX_LISTED).map((item) => (
        <li key={item.id} className="break-all">
          {item.path}
        </li>
      ))}
      {items.length > MAX_LISTED && <li>…</li>}
    </ul>
  )
}

// What will be uploaded and what was left out (and why), before anything is sent.
export function BulkReview({ plan, zipProblems, maxUploadBytes, onConfirm, onCancel }: BulkReviewProps) {
  const { t, tp } = useI18n()
  const { upload, skipped, bySkipReason, uploadBytes } = summarizePlan(plan)
  const limitMb = maxUploadBytes ? Math.round(maxUploadBytes / MB) : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("bulk.reviewTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {upload.length > 0 ? (
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              {tp("bulk.willUpload", upload.length, { size: formatBytes(uploadBytes) })}
            </summary>
            <NameList items={upload} />
          </details>
        ) : (
          <p className="text-sm">{t("bulk.nothing")}</p>
        )}

        {skipped.length > 0 && (
          <details>
            <summary className="text-muted-foreground cursor-pointer text-sm">
              {tp("bulk.skippedTitle", skipped.length)}
            </summary>
            <div className="mt-2 flex flex-col gap-2">
              {REASON_ORDER.filter((reason) => bySkipReason[reason]).map((reason) => (
                <div key={reason}>
                  <p className="text-sm">
                    {t(`bulk.skip.${reason}` as MessageKey, { mb: limitMb })} ({bySkipReason[reason]!.length})
                  </p>
                  <NameList items={bySkipReason[reason]!} />
                </div>
              ))}
            </div>
          </details>
        )}

        {zipProblems.map((problem) => (
          <p key={problem.path} className="text-destructive text-sm">
            {problem.reason === "too_large"
              ? t("bulk.zipTooBig", { name: problem.path, mb: 500 })
              : t("bulk.zipUnreadable", { name: problem.path })}
          </p>
        ))}

        <div className="flex gap-2">
          <Button type="button" disabled={upload.length === 0} onClick={onConfirm}>
            {tp("bulk.uploadButton", upload.length)}
          </Button>
          <Button type="button" variant="outline" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
