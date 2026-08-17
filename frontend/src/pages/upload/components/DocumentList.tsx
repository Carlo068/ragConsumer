import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { StatusBadge } from "@/components/common/StatusBadge"
import type { Document } from "@/models/document"

interface DocumentListProps {
  documents: Document[]
  onDelete: (documentId: string) => void
}

export function DocumentList({ documents, onDelete }: DocumentListProps) {
  if (documents.length === 0) {
    return <p className="text-muted-foreground text-sm">No documents uploaded yet.</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {documents.map((doc) => (
        <Card key={doc.id}>
          <CardContent className="flex items-center justify-between gap-3">
            <span className="text-sm">{doc.source_filename}</span>
            <div className="flex items-center gap-2">
              <StatusBadge status={doc.status} />
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
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
