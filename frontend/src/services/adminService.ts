import { API_BASE_URL, apiClient } from "./apiClient"
import type { AuditFilters, AuditPage } from "@/models/audit"
import type { CreateInviteRequest, Invite, InviteCreated } from "@/models/invite"
import type { AdminUser } from "@/models/user"

function auditQuery(filters: AuditFilters, extra: Record<string, string> = {}) {
  const params = new URLSearchParams(extra)
  if (filters.action) params.set("action", filters.action)
  if (filters.actor) params.set("actor", filters.actor)
  const query = params.toString()
  return query ? `?${query}` : ""
}

export const adminService = {
  listUsers: () => apiClient.get<AdminUser[]>("/admin/users"),
  listInvites: () => apiClient.get<Invite[]>("/admin/invites"),
  createInvite: (payload: CreateInviteRequest) =>
    apiClient.post<InviteCreated>("/admin/invites", payload),
  revokeInvite: (id: string) => apiClient.delete(`/admin/invites/${id}`),
  listAudit: (filters: AuditFilters, limit: number, offset: number) =>
    apiClient.get<AuditPage>(
      `/admin/audit${auditQuery(filters, { limit: String(limit), offset: String(offset) })}`
    ),
  // A plain link: the browser downloads the file, sending the session cookie.
  auditCsvUrl: (filters: AuditFilters) => `${API_BASE_URL}/admin/audit.csv${auditQuery(filters)}`,
}
