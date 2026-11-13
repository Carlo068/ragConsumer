import { useCallback, useEffect, useState } from "react"
import { membersService } from "@/services/membersService"
import type { CollectionRole } from "@/models/collection"
import type { Member } from "@/models/member"

export function useMembers(collectionId: string) {
  const [members, setMembers] = useState<Member[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setMembers(await membersService.list(collectionId))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load members")
    } finally {
      setLoading(false)
    }
  }, [collectionId])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function addMember(email: string, role: CollectionRole) {
    await membersService.add(collectionId, { email, role })
    await refresh()
  }

  async function changeRole(userId: string, role: CollectionRole) {
    await membersService.changeRole(collectionId, userId, { role })
    await refresh()
  }

  async function removeMember(userId: string) {
    await membersService.remove(collectionId, userId)
    await refresh()
  }

  return { members, loading, error, addMember, changeRole, removeMember }
}
