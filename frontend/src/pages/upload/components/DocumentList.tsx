import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { StatusBadge } from "@/components/common/StatusBadge"
import type { Document } from "@/models/document"

interface DocumentListProps {
  documents: Document[]
  onDelete: (documentId: string) => void
  canDelete: boolean
  onRetry?: (documentId: string) => void
  canRetry?: boolean
}

export function DocumentList({
  documents,
  onDelete,
  canDelete,
  onRetry,
  canRetry = false,
}: DocumentListProps) {
  if (documents.length === 0) {
    return <p className="text-muted-foreground text-sm">No documents uploaded yet.</p>
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
                    Try again
                  </Button>
                )}
                {canDelete && (
                  <ConfirmDialog
                    trigger={
                      <Button variant="ghost" size="sm">
                        Delete
                      </Button>
                    }
                    title={`Delete "${doc.source_filename}"?`}
                    description="This permanently removes the file and everything indexed from it. This can't be undone."
                    onConfirm={() => onDelete(doc.id)}
                  />
                )}
              </div>
            </div>
            {doc.status === "failed" && doc.error_message && (
              <p className="text-destructive text-xs">{doc.error_message}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
