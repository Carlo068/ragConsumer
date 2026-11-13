import { Link, useNavigate, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useCollections } from "@/hooks/useCollections"
import { useAuth } from "@/hooks/useAuth"
import { useDocuments } from "@/hooks/useDocuments"
import { useLimits } from "@/hooks/useLimits"
import { useI18n } from "@/i18n/useI18n"
import { useMembers } from "@/hooks/useMembers"
import { canEditFiles, canManageCollection } from "@/models/collection"
import { DocumentList } from "./components/DocumentList"
import { MembersPanel } from "./components/MembersPanel"
import { UploadForm } from "./components/UploadForm"

export function UploadPage() {
  const { t } = useI18n()
  const { collectionId } = useParams<{ collectionId: string }>()
  const { collections } = useCollections()
  const limits = useLimits()
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
          <h1 className="text-2xl font-semibold">{t("upload.title")}</h1>
          <p className="text-muted-foreground text-sm">
            {collection?.name ?? t("upload.loadingCollection")}
          </p>
        </div>
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link to="/collections">{t("common.backToCollections")}</Link>}
        />
      </div>

      {canEditFiles(collection?.role) ? (
        <div className="mb-6">
          <UploadForm onUpload={upload} uploading={uploading} maxUploadBytes={limits?.max_upload_bytes} />
        </div>
      ) : (
        collection && (
          <p className="text-muted-foreground mb-6 text-sm">
            {t("upload.viewOnly")}
          </p>
        )
      )}

      {loading && <p>{t("upload.loadingDocuments")}</p>}
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
