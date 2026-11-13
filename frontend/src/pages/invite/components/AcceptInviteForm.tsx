import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n/useI18n"

// Mirrors the backend's MIN_PASSWORD_LENGTH; the server enforces it anyway.
const MIN_PASSWORD_LENGTH = 12

interface AcceptInviteFormProps {
  email: string
  onSubmit: (password: string) => Promise<void>
}

export function AcceptInviteForm({ email, onSubmit }: AcceptInviteFormProps) {
  const { t, errorText } = useI18n()
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(t("invite.tooShort", { min: MIN_PASSWORD_LENGTH }))
      return
    }
    if (password !== confirm) {
      setError(t("invite.mismatch"))
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(password)
    } catch (err) {
      setError(errorText(err, "invite.failed"))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <p className="text-sm">
        {t("invite.invitedAsBefore")}
        <strong>{email}</strong>
        {t("invite.invitedAsAfter")}
      </p>
      <div className="flex flex-col gap-2">
        <Label htmlFor="new-password">{t("invite.password")}</Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <p className="text-muted-foreground text-xs">
          {t("invite.passwordHint", { min: MIN_PASSWORD_LENGTH })}
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="confirm-password">{t("invite.repeat")}</Label>
        <Input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      {error && <p className="text-destructive text-sm">{error}</p>}
      <Button type="submit" disabled={submitting}>
        {submitting ? t("invite.submitting") : t("invite.submit")}
      </Button>
    </form>
  )
}
