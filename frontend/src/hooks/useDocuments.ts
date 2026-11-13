import { useCallback, useEffect, useRef, useState } from "react"
import { documentsService } from "@/services/documentsService"
import type { Document } from "@/models/document"
import { useI18n } from "@/i18n/useI18n"

const POLL_INTERVAL_MS = 2000

function hasPendingDocument(documents: Document[]): boolean {
  return documents.some((d) => d.status === "uploaded" || d.status === "processing")
}

export function useDocuments(collectionId: string) {
  const { errorText } = useI18n()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await documentsService.list(collectionId)
      setDocuments(result)
      setError(null)
    } catch (err) {
      setError(errorText(err, "upload.loadFailed"))
    } finally {
      setLoading(false)
    }
  }, [collectionId, errorText])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Poll only while something is still uploaded/processing -- once every
  // document has settled to ready/failed, this effect's cleanup stops the
  // interval and nothing keeps refetching in the background.
  const documentsRef = useRef(documents)
  documentsRef.current = documents

  useEffect(() => {
    if (!hasPendingDocument(documentsRef.current)) return

    const interval = setInterval(refresh, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [documents, refresh])

  async function remove(documentId: string) {
    await documentsService.remove(collectionId, documentId)
    await refresh()
  }

  async function retry(documentId: string) {
    await documentsService.retry(collectionId, documentId)
    await refresh()
  }

  return { documents, loading, error, refresh, remove, retry }
}
