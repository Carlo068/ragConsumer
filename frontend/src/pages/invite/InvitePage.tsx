import { useNavigate, useParams } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher"
import { useAuth } from "@/hooks/useAuth"
import { useI18n } from "@/i18n/useI18n"
import { useInvite } from "@/hooks/useInvite"
import { AcceptInviteForm } from "./components/AcceptInviteForm"

export function InvitePage() {
  const { token } = useParams<{ token: string }>()
  const { invite, loading, invalid, accept } = useInvite(token!)
  const { refresh } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()

  async function handleAccept(password: string) {
    await accept(password)
    await refresh()
    navigate("/collections", { replace: true })
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{t("invite.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm">{t("invite.checking")}</p>}
          {invalid && (
            <p className="text-sm">{t("invite.invalid")}</p>
          )}
          {invite && <AcceptInviteForm email={invite.email} onSubmit={handleAccept} />}
        </CardContent>
      </Card>
      <LanguageSwitcher />
    </div>
  )
}
