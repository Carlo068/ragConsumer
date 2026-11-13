import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useI18n } from "@/i18n/useI18n"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { RoleSelect } from "@/components/common/RoleSelect"
import type { CollectionRole } from "@/models/collection"
import type { Member } from "@/models/member"

interface MembersPanelProps {
  members: Member[]
  currentUserId: string
  canManage: boolean
  onAdd: (email: string, role: CollectionRole) => Promise<void>
  onChangeRole: (userId: string, role: CollectionRole) => Promise<void>
  onRemove: (userId: string) => Promise<void>
}

export function MembersPanel({
  members,
  currentUserId,
  canManage,
  onAdd,
  onChangeRole,
  onRemove,
}: MembersPanelProps) {
  const { t, errorText } = useI18n()
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<CollectionRole>("viewer")
  const [error, setError] = useState<string | null>(null)

  // Server rules (e.g. "must keep at least one owner") surface as messages
  // here rather than being second-guessed in the UI.
  async function attempt(action: () => Promise<void>) {
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(errorText(err, "common.didntWork"))
    }
  }

  async function handleAdd(event: FormEvent) {
    event.preventDefault()
    await attempt(async () => {
      await onAdd(email.trim(), role)
      setEmail("")
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("members.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {members.map((member) => {
          const isMe = member.user_id === currentUserId
          return (
            <div key={member.user_id} className="flex items-center justify-between gap-3 text-sm">
              <span>
                {member.email}
                {isMe && <span className="text-muted-foreground"> {t("common.you")}</span>}
              </span>
              <div className="flex items-center gap-2">
                {canManage ? (
                  <RoleSelect
                    aria-label={t("members.roleFor", { email: member.email })}
                    value={member.role}
                    onChange={(next) => attempt(() => onChangeRole(member.user_id, next))}
                  />
                ) : (
                  <span className="text-muted-foreground">{t(`roles.${member.role}`)}</span>
                )}
                {(canManage || isMe) && (
                  <ConfirmDialog
                    trigger={
                      <Button variant="ghost" size="sm">
                        {isMe ? t("common.leave") : t("common.remove")}
                      </Button>
                    }
                    title={isMe ? t("members.leaveTitle") : t("members.removeTitle", { email: member.email })}
                    description={isMe ? t("members.leaveDescription") : t("members.removeDescription")}
                    confirmLabel={isMe ? t("common.leave") : t("common.remove")}
                    onConfirm={() => attempt(() => onRemove(member.user_id))}
                  />
                )}
              </div>
            </div>
          )
        })}

        {error && <p className="text-destructive text-sm">{error}</p>}

        {canManage && (
          <form onSubmit={handleAdd} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-4">
            <div className="flex min-w-48 flex-1 flex-col gap-1">
              <label htmlFor="member-email" className="text-sm font-medium">
                {t("members.addLabel")}
              </label>
              <Input
                id="member-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("members.placeholder")}
                required
              />
            </div>
            <RoleSelect aria-label={t("members.roleForNew")} value={role} onChange={setRole} />
            <Button type="submit" disabled={!email.trim()}>
              {t("common.add")}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
