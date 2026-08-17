import { Link, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useCollections } from "@/hooks/useCollections"
import { useDocuments } from "@/hooks/useDocuments"
import { DocumentList } from "./components/DocumentList"
import { UploadForm } from "./components/UploadForm"

export function UploadPage() {
  const { collectionId } = useParams<{ collectionId: string }>()
  const { collections } = useCollections()
  const { documents, loading, error, uploading, upload, remove } = useDocuments(
    collectionId!
  )

  const collection = collections.find((c) => c.id === collectionId)

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Upload</h1>
          <p className="text-muted-foreground text-sm">
            {collection?.name ?? "Loading collection..."}
          </p>
        </div>
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link to="/collections">Back to collections</Link>}
        />
      </div>

      <div className="mb-6">
        <UploadForm onUpload={upload} uploading={uploading} />
      </div>

      {loading && <p>Loading documents...</p>}
      {error && <p className="text-destructive">{error}</p>}
      <DocumentList documents={documents} onDelete={remove} />
    </div>
  )
}
