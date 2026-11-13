import { useState } from "react"
import { CopyBlock } from "@/components/common/CopyBlock"
import { useCollections } from "@/hooks/useCollections"
import { useTokens } from "@/hooks/useTokens"
import { useI18n } from "@/i18n/useI18n"
import { ConnectStep } from "./components/ConnectStep"
import { MatterAccessList } from "./components/MatterAccessList"
import { SampleQuestions } from "./components/SampleQuestions"
import { TokensPanel } from "./components/TokensPanel"
import { buildSnippets } from "./snippets"

const MCP_BASE_URL = import.meta.env.VITE_MCP_BASE_URL ?? "http://localhost:8002"
const SERVER_NAME = "ragconsumer"

// A guide in four steps: choose the matters, create a key, paste it into the
// AI assistant, try a question. The raw configuration is tucked away under
// "Advanced" for the few people who want it.
export function ConnectPage() {
  const { t } = useI18n()
  const mcpUrl = `${MCP_BASE_URL}/mcp`
  const { collections, loading: loadingCollections, error: collectionsError, setAiAccess } = useCollections()
  const { tokens, loading, error, createToken, revokeToken } = useTokens()
  const [freshToken, setFreshToken] = useState<string | undefined>()
  const { cli: cliSnippet, json: jsonSnippet } = buildSnippets(SERVER_NAME, mcpUrl, freshToken)

  const anyMatterOn = collections.some((c) => c.ai_enabled)

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">{t("connect.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("connect.subtitle")}</p>
      </div>

      {(loading || loadingCollections) && <p>{t("common.loading")}</p>}
      {(error || collectionsError) && <p className="text-destructive">{error ?? collectionsError}</p>}

      <ConnectStep number={1} title={t("connect.step1Title")} done={anyMatterOn}>
        <p className="text-muted-foreground text-sm">{t("connect.step1Intro")}</p>
        <MatterAccessList collections={collections} onToggle={setAiAccess} />
      </ConnectStep>

      <ConnectStep number={2} title={t("connect.step2Title")} done={tokens.length > 0}>
        <TokensPanel
          tokens={tokens}
          onCreate={createToken}
          onRevoke={revokeToken}
          onCreated={(created) => setFreshToken(created.token)}
        />
      </ConnectStep>

      <ConnectStep number={3} title={t("connect.step3Title")}>
        <p className="text-muted-foreground text-sm">{t("connect.step3Intro")}</p>
        <CopyBlock label={t("connect.addressLabel")} code={mcpUrl} />
        {freshToken ? (
          <CopyBlock label={t("tokens.keyLabel")} code={freshToken} />
        ) : (
          <p className="text-muted-foreground rounded-lg border border-dashed p-3 text-sm">
            {t("connect.keyPlaceholder")}
          </p>
        )}
        <p className="text-muted-foreground text-xs">{t("connect.step3Note")}</p>
      </ConnectStep>

      <ConnectStep number={4} title={t("connect.step4Title")}>
        <p className="text-muted-foreground text-sm">{t("connect.step4Intro")}</p>
        <SampleQuestions />
      </ConnectStep>

      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">{t("connect.advancedTitle")}</summary>
        <div className="mt-3 flex flex-col gap-4">
          <p className="text-muted-foreground text-sm">{t("connect.advancedIntro")}</p>
          <CopyBlock label={t("connect.cliLabel")} code={cliSnippet} />
          <CopyBlock label={t("connect.jsonLabel")} code={jsonSnippet} />
        </div>
      </details>
    </div>
  )
}
