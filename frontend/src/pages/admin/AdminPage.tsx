import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { useAdmin } from "@/hooks/useAdmin"
import { useAuditLog } from "@/hooks/useAuditLog"
import { useI18n } from "@/i18n/useI18n"
import { AuditLogPanel } from "./components/AuditLogPanel"
import { InviteUserForm } from "./components/InviteUserForm"

export function AdminPage() {
  const { t, formatDateTime } = useI18n()
  const { users, invites, loading, error, createInvite, revokeInvite } = useAdmin()
  const audit = useAuditLog()

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">{t("admin.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {t("admin.intro")}
        </p>
      </div>

      {loading && <p>{t("common.loading")}</p>}
      {error && <p className="text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>{t("admin.inviteTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <InviteUserForm onInvite={createInvite} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("admin.pendingTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {invites.length === 0 && (
            <p className="text-muted-foreground text-sm">{t("admin.noPending")}</p>
          )}
          {invites.map((invite) => (
            <div key={invite.id} className="flex items-center justify-between gap-3 text-sm">
              <div>
                <p>{invite.email}</p>
                <p className="text-muted-foreground text-xs">
                  {t("admin.expires", { date: formatDateTime(invite.expires_at) })}
                </p>
              </div>
              <ConfirmDialog
                trigger={
                  <Button variant="ghost" size="sm">
                    {t("tokens.revoke")}
                  </Button>
                }
                title={t("admin.revokeTitle", { email: invite.email })}
                description={t("admin.revokeDescription")}
                confirmLabel={t("tokens.revoke")}
                onConfirm={() => revokeInvite(invite.id)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("admin.peopleTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {users.map((user) => (
            <div key={user.id} className="flex items-center justify-between text-sm">
              <span>{user.email}</span>
              {user.is_admin && <Badge variant="secondary">{t("admin.administrator")}</Badge>}
            </div>
          ))}
        </CardContent>
      </Card>

      <AuditLogPanel
        items={audit.items}
        total={audit.total}
        filters={audit.filters}
        loading={audit.loading}
        error={audit.error}
        hasNext={audit.hasNext}
        hasPrevious={audit.hasPrevious}
        csvUrl={audit.csvUrl}
        onFilter={audit.applyFilters}
        onNext={audit.nextPage}
        onPrevious={audit.previousPage}
      />
    </div>
  )
}
