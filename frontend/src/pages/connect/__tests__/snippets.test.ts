import { describe, expect, it } from "vitest"
import { TOKEN_PLACEHOLDER, buildSnippets } from "@/pages/connect/snippets"

describe("buildSnippets", () => {
  it("uses an obvious placeholder when there is no fresh key", () => {
    const { cli, json } = buildSnippets("ragconsumer", "https://x/mcp")
    expect(cli).toContain(`Bearer ${TOKEN_PLACEHOLDER}`)
    expect(JSON.parse(json).mcpServers.ragconsumer.headers.Authorization).toBe(
      `Bearer ${TOKEN_PLACEHOLDER}`
    )
  })

  it("embeds a fresh key in both snippets", () => {
    const { cli, json } = buildSnippets("ragconsumer", "https://x/mcp", "rag_abc")
    expect(cli).toContain('--header "Authorization: Bearer rag_abc"')
    expect(JSON.parse(json).mcpServers.ragconsumer.headers.Authorization).toBe("Bearer rag_abc")
  })
})
