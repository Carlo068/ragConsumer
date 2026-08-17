import { Card, CardContent } from "@/components/ui/card"
import { StatusBadge } from "@/components/common/StatusBadge"
import type { Document } from "@/models/document"

interface DocumentListProps {
  documents: Document[]
}

export function DocumentList({ documents }: DocumentListProps) {
  if (documents.length === 0) {
    return <p className="text-muted-foreground text-sm">No documents uploaded yet.</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {documents.map((doc) => (
        <Card key={doc.id}>
          <CardContent className="flex items-center justify-between">
            <span className="text-sm">{doc.source_filename}</span>
            <StatusBadge status={doc.status} />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
