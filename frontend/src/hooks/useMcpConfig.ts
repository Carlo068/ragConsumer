import { useCallback, useEffect, useState } from "react"
import { mcpConfigService } from "@/services/mcpConfigService"
import type { McpActiveCollection } from "@/models/mcpConfig"

export function useMcpConfig() {
  const [active, setActive] = useState<McpActiveCollection | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setActive(await mcpConfigService.get())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load MCP status")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function activate(collectionId: string) {
    setActive(await mcpConfigService.setActive(collectionId))
  }

  async function deactivate() {
    setActive(await mcpConfigService.setActive(null))
  }

  return { active, loading, error, activate, deactivate, refresh }
}
