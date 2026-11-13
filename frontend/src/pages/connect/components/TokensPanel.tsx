import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { CopyBlock } from "@/components/common/CopyBlock"
import type { ApiToken, ApiTokenCreated } from "@/models/token"

interface TokensPanelProps {
  tokens: ApiToken[]
  onCreate: (name: string) => Promise<ApiTokenCreated>
  onRevoke: (id: string) => Promise<void>
  // Lets the page drop the new key into the connection snippets.
  onCreated?: (created: ApiTokenCreated) => void
}

function formatDate(value: string) {
  return new Date(value + "Z").toLocaleDateString()
}

export function TokensPanel({ tokens, onCreate, onRevoke, onCreated }: TokensPanelProps) {
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
      setError(err instanceof Error ? err.message : "Could not create the access key")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your access keys</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-muted-foreground text-sm">
          An access key lets your AI assistant search the matters you have access to, as you. Create
          one per device or app, and revoke it if you lose the device. Never share it: anyone who
          has it can search your matters.
        </p>

        <form onSubmit={handleSubmit} className="flex items-end gap-3">
          <div className="flex flex-1 flex-col gap-2">
            <Label htmlFor="token-name">Name (for example, Claude on my laptop)</Label>
            <Input
              id="token-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              required
            />
          </div>
          <Button type="submit" disabled={submitting || !name.trim()}>
            {submitting ? "Creating..." : "Create access key"}
          </Button>
        </form>
        {error && <p className="text-destructive text-sm">{error}</p>}

        {created && (
          <div className="flex flex-col gap-2 rounded-lg border p-4">
            <p className="text-sm">
              Your new key <strong>{created.name}</strong>. Copy it now: this is the only time it is
              shown. The connection commands below already include it.
            </p>
            <CopyBlock label="Access key" code={created.token} />
          </div>
        )}

        <div className="flex flex-col gap-2">
          {tokens.length === 0 && (
            <p className="text-muted-foreground text-sm">You have no access keys yet.</p>
          )}
          {tokens.map((token) => (
            <div key={token.id} className="flex items-center justify-between gap-3 text-sm">
              <div>
                <p>
                  {token.name} <span className="text-muted-foreground">({token.prefix}…)</span>
                </p>
                <p className="text-muted-foreground text-xs">
                  Created {formatDate(token.created_at)} · Expires {formatDate(token.expires_at)} ·{" "}
                  {token.last_used_at ? `Last used ${formatDate(token.last_used_at)}` : "Never used"}
                </p>
              </div>
              <ConfirmDialog
                trigger={
                  <Button variant="ghost" size="sm">
                    Revoke
                  </Button>
                }
                title={`Revoke "${token.name}"?`}
                description="Any AI assistant using this key loses access immediately. You can create a new key later."
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
