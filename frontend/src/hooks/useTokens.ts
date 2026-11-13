import { useCallback, useEffect, useState } from "react"
import { tokenService } from "@/services/tokenService"
import type { ApiToken, ApiTokenCreated } from "@/models/token"

export function useTokens() {
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setTokens(await tokenService.list())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your access keys")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function createToken(name: string): Promise<ApiTokenCreated> {
    const created = await tokenService.create({ name })
    await refresh()
    return created
  }

  async function revokeToken(id: string) {
    await tokenService.revoke(id)
    await refresh()
  }

  return { tokens, loading, error, createToken, revokeToken }
}
