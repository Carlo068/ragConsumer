import { useCallback, useEffect, useState } from "react"
import { collectionsService } from "@/services/collectionsService"
import type { Collection } from "@/models/collection"

export function useCollections() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await collectionsService.list()
      setCollections(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load collections")
    } finally {
      setLoading(false)
    }
  }, [])

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

  return { collections, loading, error, createCollection, renameCollection, deleteCollection }
}
