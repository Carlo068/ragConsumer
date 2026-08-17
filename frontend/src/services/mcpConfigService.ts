import { apiClient } from "./apiClient"
import type { McpActiveCollection } from "@/models/mcpConfig"

export const mcpConfigService = {
  get: () => apiClient.get<McpActiveCollection>("/mcp/active-collection"),
  setActive: (collectionId: string | null) =>
    apiClient.put<McpActiveCollection>("/mcp/active-collection", {
      collection_id: collectionId,
    }),
}
