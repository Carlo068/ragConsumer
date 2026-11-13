export const TOKEN_PLACEHOLDER = "YOUR_ACCESS_KEY"

// The AI client authenticates with a personal access key sent as a bearer
// header. Until the person has just created one, the snippets carry an obvious
// placeholder rather than anything that looks real.
export function buildSnippets(serverName: string, mcpUrl: string, token?: string) {
  const key = token ?? TOKEN_PLACEHOLDER
  return {
    cli: `claude mcp add --transport http ${serverName} ${mcpUrl} --header "Authorization: Bearer ${key}"`,
    json: JSON.stringify(
      {
        mcpServers: {
          [serverName]: {
            type: "http",
            url: mcpUrl,
            headers: { Authorization: `Bearer ${key}` },
          },
        },
      },
      null,
      2
    ),
  }
}
