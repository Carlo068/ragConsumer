import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { CopyBlock } from "@/components/common/CopyBlock"
import { useI18n } from "@/i18n/useI18n"
import type { ApiToken, ApiTokenCreated } from "@/models/token"

interface TokensPanelProps {
  tokens: ApiToken[]
  onCreate: (name: string) => Promise<ApiTokenCreated>
  onRevoke: (id: string) => Promise<void>
  // Lets the page drop the new key into the connection snippets.
  onCreated?: (created: ApiTokenCreated) => void
}

export function TokensPanel({ tokens, onCreate, onRevoke, onCreated }: TokensPanelProps) {
  const { t, errorText, formatDate } = useI18n()
  const [name, setName] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<ApiTokenCreated | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await onCreate(name.trim())
      setCreated(result)
      onCreated?.(result)
      setName("")
    } catch (err) {
      setError(errorText(err, "tokens.createFailed"))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("tokens.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-muted-foreground text-sm">
          {t("tokens.intro")}
        </p>

        <form onSubmit={handleSubmit} className="flex items-end gap-3">
          <div className="flex flex-1 flex-col gap-2">
            <Label htmlFor="token-name">{t("tokens.nameLabel")}</Label>
            <Input
              id="token-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              required
            />
          </div>
          <Button type="submit" disabled={submitting || !name.trim()}>
            {submitting ? t("tokens.creating") : t("tokens.create")}
          </Button>
        </form>
        {error && <p className="text-destructive text-sm">{error}</p>}

        {created && (
          <div className="flex flex-col gap-2 rounded-lg border p-4">
            <p className="text-sm">
              {t("tokens.newKey", { name: created.name })}
            </p>
            <CopyBlock label={t("tokens.keyLabel")} code={created.token} />
          </div>
        )}

        <div className="flex flex-col gap-2">
          {tokens.length === 0 && (
            <p className="text-muted-foreground text-sm">{t("tokens.none")}</p>
          )}
          {tokens.map((token) => (
            <div key={token.id} className="flex items-center justify-between gap-3 text-sm">
              <div>
                <p>
                  {token.name} <span className="text-muted-foreground">({token.prefix}…)</span>
                </p>
                <p className="text-muted-foreground text-xs">
                  {t("tokens.detail", {
                    created: formatDate(token.created_at),
                    expires: formatDate(token.expires_at),
                    used: token.last_used_at
                      ? t("tokens.lastUsed", { date: formatDate(token.last_used_at) })
                      : t("tokens.neverUsed"),
                  })}
                </p>
              </div>
              <ConfirmDialog
                trigger={
                  <Button variant="ghost" size="sm">
                    {t("tokens.revoke")}
                  </Button>
                }
                title={t("tokens.revokeTitle", { name: token.name })}
                description={t("tokens.revokeDescription")}
                confirmLabel="Revoke"
                onConfirm={() => onRevoke(token.id)}
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
