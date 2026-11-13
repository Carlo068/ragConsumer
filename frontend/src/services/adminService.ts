import { apiClient } from "./apiClient"
import type { CreateInviteRequest, Invite, InviteCreated } from "@/models/invite"
import type { AdminUser } from "@/models/user"

export const adminService = {
  listUsers: () => apiClient.get<AdminUser[]>("/admin/users"),
  listInvites: () => apiClient.get<Invite[]>("/admin/invites"),
  createInvite: (payload: CreateInviteRequest) =>
    apiClient.post<InviteCreated>("/admin/invites", payload),
  revokeInvite: (id: string) => apiClient.delete(`/admin/invites/${id}`),
}
