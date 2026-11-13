import { Link, useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useCollections } from "@/hooks/useCollections"
import { useAuth } from "@/hooks/useAuth"
import { useDocuments } from "@/hooks/useDocuments"
import { useMembers } from "@/hooks/useMembers"
import { canEditFiles, canManageCollection } from "@/models/collection"
import { DocumentList } from "./components/DocumentList"
import { MembersPanel } from "./components/MembersPanel"
import { UploadForm } from "./components/UploadForm"

export function UploadPage() {
  const { collectionId } = useParams<{ collectionId: string }>()
  const { collections } = useCollections()
  const { documents, loading, error, uploading, upload, remove, retry } = useDocuments(
    collectionId!
  )

  const collection = collections.find((c) => c.id === collectionId)
  const { user } = useAuth()
  const navigate = useNavigate()
  const { members, addMember, changeRole, removeMember } = useMembers(collectionId!)

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

      {canEditFiles(collection?.role) ? (
        <div className="mb-6">
          <UploadForm onUpload={upload} uploading={uploading} />
        </div>
      ) : (
        collection && (
          <p className="text-muted-foreground mb-6 text-sm">
            You can view this collection, but only editors and owners can add or remove files.
          </p>
        )
      )}

      {loading && <p>Loading documents...</p>}
      {error && <p className="text-destructive">{error}</p>}
      <DocumentList
        documents={documents}
        onDelete={remove}
        canDelete={canEditFiles(collection?.role)}
        canRetry={canEditFiles(collection?.role)}
        onRetry={retry}
      />

      {collection && user && (
        <div className="mt-8">
          <MembersPanel
            members={members}
            currentUserId={user.id}
            canManage={canManageCollection(collection.role)}
            onAdd={addMember}
            onChangeRole={changeRole}
            onRemove={async (userId) => {
              await removeMember(userId)
              // Leaving removes the collection from your list, so this page
              // would only show errors from here on.
              if (userId === user.id) navigate("/collections", { replace: true })
            }}
          />
        </div>
      )}
    </div>
  )
}
