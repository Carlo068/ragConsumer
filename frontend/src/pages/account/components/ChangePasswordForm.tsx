import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n/useI18n"

// Mirrors the backend's MIN_PASSWORD_LENGTH; the server enforces it anyway.
const MIN_PASSWORD_LENGTH = 12

interface ChangePasswordFormProps {
  onSubmit: (currentPassword: string, newPassword: string) => Promise<void>
}

export function ChangePasswordForm({ onSubmit }: ChangePasswordFormProps) {
  const { t, errorText } = useI18n()
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setDone(false)
    if (next.length < MIN_PASSWORD_LENGTH) {
      setError(t("account.tooShort", { min: MIN_PASSWORD_LENGTH }))
      return
    }
    if (next !== confirm) {
      setError(t("account.mismatch"))
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(current, next)
      setCurrent("")
      setNext("")
      setConfirm("")
      setDone(true)
    } catch (err) {
      setError(errorText(err, "account.failed"))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="current-password">{t("account.current")}</Label>
        <Input
          id="current-password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="new-password">{t("account.new")}</Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
        <p className="text-muted-foreground text-xs">
          {t("account.newHint", { min: MIN_PASSWORD_LENGTH })}
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="confirm-new-password">{t("account.repeat")}</Label>
        <Input
          id="confirm-new-password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      {error && <p className="text-destructive text-sm">{error}</p>}
      {done && <p className="text-sm">{t("account.done")}</p>}
      <Button type="submit" disabled={submitting || !current}>
        {submitting ? t("account.submitting") : t("account.submit")}
      </Button>
    </form>
  )
}
