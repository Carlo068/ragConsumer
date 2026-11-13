import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { StatusBadge } from "@/components/common/StatusBadge"
import type { MessageKey, Translate } from "@/i18n/core"
import { useI18n } from "@/i18n/useI18n"
import type { Document } from "@/models/document"

interface DocumentListProps {
  documents: Document[]
  onDelete: (documentId: string) => void
  canDelete: boolean
  onRetry?: (documentId: string) => void
  canRetry?: boolean
}

const FAILURE_CODES = ["no_text", "unreadable", "timed_out", "index_outdated", "unexpected"]

// The worker stores a short code for why a file failed; show it in the reader's
// language. (Older entries stored English text, which is shown as it is.)
function failureText(message: string, t: Translate) {
  return FAILURE_CODES.includes(message) ? t(`upload.failure.${message}` as MessageKey) : message
}

export function DocumentList({
  documents,
  onDelete,
  canDelete,
  onRetry,
  canRetry = false,
}: DocumentListProps) {
  const { t } = useI18n()
  if (documents.length === 0) {
    return <p className="text-muted-foreground text-sm">{t("upload.empty")}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {documents.map((doc) => (
        <Card key={doc.id}>
          <CardContent className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm">{doc.source_filename}</span>
              <div className="flex items-center gap-2">
                <StatusBadge status={doc.status} />
                {canRetry && onRetry && doc.status === "failed" && (
                  <Button variant="outline" size="sm" onClick={() => onRetry(doc.id)}>
                    {t("upload.retry")}
                  </Button>
                )}
                {canDelete && (
                  <ConfirmDialog
                    trigger={
                      <Button variant="ghost" size="sm">
                        {t("common.delete")}
                      </Button>
                    }
                    title={t("upload.deleteTitle", { name: doc.source_filename })}
                    description={t("upload.deleteDescription")}
                    onConfirm={() => onDelete(doc.id)}
                  />
                )}
              </div>
            </div>
            {doc.status === "failed" && doc.error_message && (
              <p className="text-destructive text-xs">{failureText(doc.error_message, t)}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
