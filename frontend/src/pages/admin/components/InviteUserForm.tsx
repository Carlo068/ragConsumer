import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { CopyBlock } from "@/components/common/CopyBlock"
import type { InviteCreated } from "@/models/invite"

interface InviteUserFormProps {
  onInvite: (email: string) => Promise<InviteCreated>
}

export function InviteUserForm({ onInvite }: InviteUserFormProps) {
  const [email, setEmail] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<InviteCreated | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      setCreated(await onInvite(email.trim()))
      setEmail("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the invitation")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="invite-email">Email of the person to invite</Label>
          <Input
            id="invite-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <Button type="submit" disabled={submitting || !email.trim()}>
          {submitting ? "Creating..." : "Create invitation"}
        </Button>
      </form>
      {error && <p className="text-destructive text-sm">{error}</p>}

      {created && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <p className="text-sm">
            Send this link to <strong>{created.email}</strong>. It works once and expires on{" "}
            {new Date(created.expires_at + "Z").toLocaleString()}. This is the only time it's
            shown.
          </p>
          <CopyBlock label="Invitation link" code={created.invite_url} />
        </div>
      )}
    </div>
  )
}
