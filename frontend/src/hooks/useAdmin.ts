import { useCallback, useEffect, useState } from "react"
import { adminService } from "@/services/adminService"
import type { Invite, InviteCreated } from "@/models/invite"
import type { AdminUser } from "@/models/user"
import { useI18n } from "@/i18n/useI18n"

export function useAdmin() {
  const { errorText } = useI18n()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [userList, inviteList] = await Promise.all([
        adminService.listUsers(),
        adminService.listInvites(),
      ])
      setUsers(userList)
      setInvites(inviteList)
      setError(null)
    } catch (err) {
      setError(errorText(err, "admin.loadFailed"))
    } finally {
      setLoading(false)
    }
  }, [errorText])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function createInvite(email: string): Promise<InviteCreated> {
    const created = await adminService.createInvite({ email })
    await refresh()
    return created
  }

  async function revokeInvite(id: string) {
    await adminService.revokeInvite(id)
    await refresh()
  }

  async function disableUser(id: string) {
    await adminService.disableUser(id)
    await refresh()
  }

  async function enableUser(id: string) {
    await adminService.enableUser(id)
    await refresh()
  }

  async function endSessions(id: string) {
    await adminService.endSessions(id)
  }

  async function createPasswordReset(id: string): Promise<InviteCreated> {
    const created = await adminService.createPasswordReset(id)
    await refresh()
    return created
  }

  return {
    users,
    invites,
    loading,
    error,
    createInvite,
    revokeInvite,
    disableUser,
    enableUser,
    endSessions,
    createPasswordReset,
  }
}
