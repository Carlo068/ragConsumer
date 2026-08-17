import { useCallback, useEffect, useRef, useState } from "react"
import { documentsService } from "@/services/documentsService"
import type { Document } from "@/models/document"

const POLL_INTERVAL_MS = 2000

function hasPendingDocument(documents: Document[]): boolean {
  return documents.some((d) => d.status === "uploaded" || d.status === "processing")
}

export function useDocuments(collectionId: string) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const result = await documentsService.list(collectionId)
      setDocuments(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents")
    } finally {
      setLoading(false)
    }
  }, [collectionId])

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

  async function upload(file: File) {
    setUploading(true)
    try {
      await documentsService.upload(collectionId, file)
      await refresh()
    } finally {
      setUploading(false)
    }
  }

  return { documents, loading, error, uploading, upload }
}
