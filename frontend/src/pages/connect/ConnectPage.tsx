import { useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CopyBlock } from "@/components/common/CopyBlock"
import { useTokens } from "@/hooks/useTokens"
import { TokensPanel } from "./components/TokensPanel"
import { buildSnippets } from "./snippets"

const MCP_BASE_URL = import.meta.env.VITE_MCP_BASE_URL ?? "http://localhost:8002"
const SERVER_NAME = "ragconsumer"

export function ConnectPage() {
  const mcpUrl = `${MCP_BASE_URL}/mcp`
  const { tokens, loading, error, createToken, revokeToken } = useTokens()
  const [freshToken, setFreshToken] = useState<string | undefined>()
  const { cli: cliSnippet, json: jsonSnippet } = buildSnippets(SERVER_NAME, mcpUrl, freshToken)

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Connect</h1>
          <p className="text-muted-foreground text-sm">
            Let your own AI assistant search your matters
          </p>
        </div>
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link to="/collections">Back to collections</Link>}
        />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Before you connect</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground flex flex-col gap-2 text-sm">
          <p>
            Your AI assistant connects to one address and signs in with your
            own access key. It can only search the matters you have turned on
            for it on the collections list, and only while you still have
            access to them.
          </p>
          <p>
            What you turn on here affects only your own AI, never a
            colleague's. Turn a matter off there whenever you want to keep it
            private.
          </p>
        </CardContent>
      </Card>

      {loading && <p>Loading...</p>}
      {error && <p className="text-destructive mb-4">{error}</p>}

      <div className="mb-6">
        <TokensPanel
          tokens={tokens}
          onCreate={createToken}
          onRevoke={revokeToken}
          onCreated={(created) => setFreshToken(created.token)}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connect your MCP client</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <CopyBlock label="claude mcp add (CLI)" code={cliSnippet} />
          <CopyBlock label=".mcp.json" code={jsonSnippet} />
        </CardContent>
      </Card>
    </div>
  )
}
