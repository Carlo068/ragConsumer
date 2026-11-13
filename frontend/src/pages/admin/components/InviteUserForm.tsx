import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { CopyBlock } from "@/components/common/CopyBlock"
import { useI18n } from "@/i18n/useI18n"
import type { InviteCreated } from "@/models/invite"

interface InviteUserFormProps {
  onInvite: (email: string) => Promise<InviteCreated>
}

export function InviteUserForm({ onInvite }: InviteUserFormProps) {
  const { t, errorText, formatDateTime } = useI18n()
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
      setError(errorText(err, "admin.inviteFailed"))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="invite-email">{t("admin.inviteEmail")}</Label>
          <Input
            id="invite-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <Button type="submit" disabled={submitting || !email.trim()}>
          {submitting ? t("admin.inviteSubmitting") : t("admin.inviteSubmit")}
        </Button>
      </form>
      {error && <p className="text-destructive text-sm">{error}</p>}

      {created && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <p className="text-sm">
            {t("admin.inviteCreated", {
              email: created.email,
              expires: formatDateTime(created.expires_at),
            })}
          </p>
          <CopyBlock label={t("admin.inviteLink")} code={created.invite_url} />
        </div>
      )}
    </div>
  )
}
