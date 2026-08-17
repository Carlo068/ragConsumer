import { Link, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useCollections } from "@/hooks/useCollections"
import { ConnectionSnippet } from "./components/ConnectionSnippet"

const MCP_BASE_URL = import.meta.env.VITE_MCP_BASE_URL ?? "http://localhost:8002"

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "collection"
}

export function ConnectPage() {
  const { collectionId } = useParams<{ collectionId: string }>()
  const { collections } = useCollections()
  const collection = collections.find((c) => c.id === collectionId)

  const serverName = collection ? slugify(collection.name) : "collection"
  const mcpUrl = `${MCP_BASE_URL}/mcp`

  const jsonSnippet = JSON.stringify(
    {
      mcpServers: {
        [serverName]: {
          type: "http",
          url: mcpUrl,
        },
      },
    },
    null,
    2
  )

  const cliSnippet = `claude mcp add --transport http ${serverName} ${mcpUrl}`

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Connect</h1>
          <p className="text-muted-foreground text-sm">
            {collection?.name ?? "Loading collection..."}
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
            Each MCP server instance is bound to exactly one collection at
            startup -- an agent connected here can only ever see this
            collection, by design. Make sure an <code>mcp_server</code>{" "}
            instance is actually running with{" "}
            <code>MCP_COLLECTION_ID={collectionId}</code> before using the
            snippets below.
          </p>
          <p>
            The address below assumes the default Docker Compose port
            mapping. If you're running multiple collections simultaneously,
            each needs its own <code>mcp_server</code> service block on a
            different port.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connect your MCP client</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <ConnectionSnippet label="claude mcp add (CLI)" code={cliSnippet} />
          <ConnectionSnippet label=".mcp.json" code={jsonSnippet} />
        </CardContent>
      </Card>
    </div>
  )
}
