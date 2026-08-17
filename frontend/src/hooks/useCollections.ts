import { useEffect, useState } from "react"
import { collectionsService } from "@/services/collectionsService"
import type { Collection } from "@/models/collection"

export function useCollections() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    collectionsService
      .list()
      .then(setCollections)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load collections")
      )
      .finally(() => setLoading(false))
  }, [])

  return { collections, loading, error }
}
