import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { CopyBlock } from "@/components/common/CopyBlock"
import { useI18n } from "@/i18n/useI18n"
import type { InviteCreated } from "@/models/invite"
import type { AdminUser } from "@/models/user"

interface PeopleListProps {
  users: AdminUser[]
  currentUserId: string
  onDisable: (id: string) => Promise<void>
  onEnable: (id: string) => Promise<void>
  onEndSessions: (id: string) => Promise<void>
  onCreateReset: (id: string) => Promise<InviteCreated>
}

// Who has an account, with what an administrator can do when someone leaves the
// firm, loses a laptop or is locked out. Every action asks first, and the
// server records each one in the activity log.
export function PeopleList({
  users,
  currentUserId,
  onDisable,
  onEnable,
  onEndSessions,
  onCreateReset,
}: PeopleListProps) {
  const { t, errorText, formatDateTime } = useI18n()
  const [error, setError] = useState<string | null>(null)
  const [reset, setReset] = useState<InviteCreated | null>(null)

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(errorText(err, "admin.actionFailed"))
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <p className="text-destructive text-sm">{error}</p>}
      {users.map((user) => {
        const isSelf = user.id === currentUserId
        return (
          <div
            key={user.id}
            data-testid={`person-${user.email}`}
            className="flex flex-col gap-2 border-b pb-3 text-sm last:border-b-0"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className={user.is_active ? "" : "text-muted-foreground line-through"}>
                {user.email} {isSelf && t("common.you")}
              </span>
              <span className="flex gap-2">
                {user.is_admin && <Badge variant="secondary">{t("admin.administrator")}</Badge>}
                {!user.is_active && <Badge variant="destructive">{t("admin.disabled")}</Badge>}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {user.is_active ? (
                <>
                  <ConfirmDialog
                    trigger={
                      <Button variant="outline" size="sm">
                        {t("admin.endSessions")}
                      </Button>
                    }
                    title={t("admin.endSessionsTitle", { email: user.email })}
                    description={t("admin.endSessionsDescription")}
                    confirmLabel={t("admin.endSessions")}
                    onConfirm={() => run(() => onEndSessions(user.id))}
                  />
                  <ConfirmDialog
                    trigger={
                      <Button variant="outline" size="sm">
                        {t("admin.resetPassword")}
                      </Button>
                    }
                    title={t("admin.resetTitle", { email: user.email })}
                    description={t("admin.resetDescription")}
                    confirmLabel={t("admin.resetPassword")}
                    onConfirm={() => run(async () => setReset(await onCreateReset(user.id)))}
                  />
                  {!isSelf && (
                    <ConfirmDialog
                      trigger={
                        <Button variant="outline" size="sm">
                          {t("admin.disable")}
                        </Button>
                      }
                      title={t("admin.disableTitle", { email: user.email })}
                      description={t("admin.disableDescription")}
                      confirmLabel={t("admin.disable")}
                      onConfirm={() => run(() => onDisable(user.id))}
                    />
                  )}
                </>
              ) : (
                <ConfirmDialog
                  trigger={
                    <Button variant="outline" size="sm">
                      {t("admin.enable")}
                    </Button>
                  }
                  title={t("admin.enableTitle", { email: user.email })}
                  description={t("admin.enableDescription")}
                  confirmLabel={t("admin.enable")}
                  onConfirm={() => run(() => onEnable(user.id))}
                />
              )}
            </div>
            {reset?.email === user.email && (
              <div className="flex flex-col gap-2 rounded-lg border p-4">
                <p>
                  {t("admin.resetCreated", {
                    email: reset.email,
                    expires: formatDateTime(reset.expires_at),
                  })}
                </p>
                <CopyBlock label={t("admin.resetLink")} code={reset.invite_url} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
