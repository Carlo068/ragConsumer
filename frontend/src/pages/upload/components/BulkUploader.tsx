import { useBulkUpload } from "@/hooks/useBulkUpload"
import { BulkProgress } from "./BulkProgress"
import { BulkReview } from "./BulkReview"
import { DropZone } from "./DropZone"

interface BulkUploaderProps {
  collectionId: string
  existingNames: string[]
  maxUploadBytes?: number
  onFinished: () => void | Promise<void>
}

// Files, folders and .zip archives in one place: pick or drop, review what
// will be uploaded, then watch it upload a few at a time.
export function BulkUploader({ collectionId, existingNames, maxUploadBytes, onFinished }: BulkUploaderProps) {
  const bulk = useBulkUpload({ collectionId, existingNames, maxBytes: maxUploadBytes, onFinished })

  if (bulk.phase === "review") {
    return (
      <BulkReview
        plan={bulk.plan}
        zipProblems={bulk.zipProblems}
        maxUploadBytes={maxUploadBytes}
        onConfirm={bulk.confirm}
        onCancel={bulk.reset}
      />
    )
  }

  if (bulk.phase === "uploading" || bulk.phase === "finished") {
    return (
      <BulkProgress
        phase={bulk.phase}
        items={bulk.items}
        onStop={bulk.stop}
        onRetry={bulk.retryFailed}
        onReset={bulk.reset}
      />
    )
  }

  return (
    <DropZone onPicked={bulk.addPicked} maxUploadBytes={maxUploadBytes} busy={bulk.phase === "preparing"} />
  )
}
