import { useCallback, useEffect, useState } from "react"
import { collectionsService } from "@/services/collectionsService"
import type { Collection } from "@/models/collection"
import { useI18n } from "@/i18n/useI18n"

export function useCollections() {
  const { errorText } = useI18n()
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await collectionsService.list()
      setCollections(result)
      setError(null)
    } catch (err) {
      setError(errorText(err, "collections.loadFailed"))
    } finally {
      setLoading(false)
    }
  }, [errorText])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function createCollection(name: string) {
    await collectionsService.create({ name })
    await refresh()
  }

  async function renameCollection(id: string, name: string) {
    await collectionsService.rename(id, { name })
    await refresh()
  }

  async function deleteCollection(id: string) {
    await collectionsService.remove(id)
    await refresh()
  }

  async function setAiAccess(id: string, enabled: boolean) {
    await collectionsService.setAiAccess(id, enabled)
    await refresh()
  }

  return {
    collections,
    loading,
    error,
    createCollection,
    renameCollection,
    deleteCollection,
    setAiAccess,
  }
}
