import { useCallback, useEffect, useState } from "react"
import { tokenService } from "@/services/tokenService"
import type { ApiToken, ApiTokenCreated } from "@/models/token"
import { useI18n } from "@/i18n/useI18n"

export function useTokens() {
  const { errorText } = useI18n()
  const [tokens, setTokens] = useState<ApiToken[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setTokens(await tokenService.list())
      setError(null)
    } catch (err) {
      setError(errorText(err, "tokens.loadFailed"))
    } finally {
      setLoading(false)
    }
  }, [errorText])

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
