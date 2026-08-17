import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConnectionSnippet } from "./components/ConnectionSnippet"

const MCP_BASE_URL = import.meta.env.VITE_MCP_BASE_URL ?? "http://localhost:8002"
const SERVER_NAME = "ragconsumer"

export function ConnectPage() {
  const mcpUrl = `${MCP_BASE_URL}/mcp`

  const jsonSnippet = JSON.stringify(
    {
      mcpServers: {
        [SERVER_NAME]: {
          type: "http",
          url: mcpUrl,
        },
      },
    },
    null,
    2
  )

  const cliSnippet = `claude mcp add --transport http ${SERVER_NAME} ${mcpUrl}`

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Connect</h1>
          <p className="text-muted-foreground text-sm">
            One shared MCP server for every collection
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
            This project runs one shared MCP server, always at this same
            address. It only ever exposes whichever single collection is
            currently toggled on -- switch that from the collections list.
          </p>
          <p>
            Only one collection can be active at a time. Turn it off there
            when you're done to keep it private.
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
