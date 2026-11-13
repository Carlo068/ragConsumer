import { apiClient } from "./apiClient"
import type { AcceptInviteRequest, InviteInfo } from "@/models/invite"
import type { User } from "@/models/user"

export const inviteService = {
  get: (token: string) => apiClient.get<InviteInfo>(`/invites/${encodeURIComponent(token)}`),
  accept: (token: string, payload: AcceptInviteRequest) =>
    apiClient.post<User>(`/invites/${encodeURIComponent(token)}/accept`, payload),
}
