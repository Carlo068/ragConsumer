import { useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CopyBlock } from "@/components/common/CopyBlock"
import { useTokens } from "@/hooks/useTokens"
import { useI18n } from "@/i18n/useI18n"
import { TokensPanel } from "./components/TokensPanel"
import { buildSnippets } from "./snippets"

const MCP_BASE_URL = import.meta.env.VITE_MCP_BASE_URL ?? "http://localhost:8002"
const SERVER_NAME = "ragconsumer"

export function ConnectPage() {
  const { t } = useI18n()
  const mcpUrl = `${MCP_BASE_URL}/mcp`
  const { tokens, loading, error, createToken, revokeToken } = useTokens()
  const [freshToken, setFreshToken] = useState<string | undefined>()
  const { cli: cliSnippet, json: jsonSnippet } = buildSnippets(SERVER_NAME, mcpUrl, freshToken)

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t("connect.title")}</h1>
          <p className="text-muted-foreground text-sm">
            {t("connect.subtitle")}
          </p>
        </div>
        <Button
          variant="outline"
          nativeButton={false}
          render={<Link to="/collections">{t("common.backToCollections")}</Link>}
        />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>{t("connect.beforeTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground flex flex-col gap-2 text-sm">
          <p>{t("connect.before1")}</p>
          <p>{t("connect.before2")}</p>
        </CardContent>
      </Card>

      {loading && <p>{t("common.loading")}</p>}
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
          <CardTitle>{t("connect.clientTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <CopyBlock label={t("connect.cliLabel")} code={cliSnippet} />
          <CopyBlock label={t("connect.jsonLabel")} code={jsonSnippet} />
        </CardContent>
      </Card>
    </div>
  )
}
