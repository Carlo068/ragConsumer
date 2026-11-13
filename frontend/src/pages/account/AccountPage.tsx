import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/hooks/useAuth"
import { useChangePassword } from "@/hooks/useChangePassword"
import { useI18n } from "@/i18n/useI18n"
import { ChangePasswordForm } from "./components/ChangePasswordForm"

export function AccountPage() {
  const { t } = useI18n()
  const { user } = useAuth()
  const { changePassword } = useChangePassword()

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">{t("account.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("account.intro", { email: user?.email ?? "" })}</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t("account.submit")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ChangePasswordForm onSubmit={changePassword} />
        </CardContent>
      </Card>
    </div>
  )
}
