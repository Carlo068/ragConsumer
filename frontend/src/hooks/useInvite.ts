import { useEffect, useState } from "react"
import { inviteService } from "@/services/inviteService"
import type { InviteInfo } from "@/models/invite"

export function useInvite(token: string) {
  const [invite, setInvite] = useState<InviteInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [invalid, setInvalid] = useState(false)

  useEffect(() => {
    inviteService
      .get(token)
      .then(setInvite)
      .catch(() => setInvalid(true))
      .finally(() => setLoading(false))
  }, [token])

  async function accept(password: string) {
    await inviteService.accept(token, { password })
  }

  return { invite, loading, invalid, accept }
}
