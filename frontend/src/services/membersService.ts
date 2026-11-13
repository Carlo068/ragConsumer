import { apiClient } from "./apiClient"
import type { AddMemberRequest, Member, UpdateMemberRoleRequest } from "@/models/member"

const base = (collectionId: string) => `/collections/${collectionId}/members`

export const membersService = {
  list: (collectionId: string) => apiClient.get<Member[]>(base(collectionId)),
  add: (collectionId: string, payload: AddMemberRequest) =>
    apiClient.post<Member>(base(collectionId), payload),
  changeRole: (collectionId: string, userId: string, payload: UpdateMemberRoleRequest) =>
    apiClient.patch<Member>(`${base(collectionId)}/${userId}`, payload),
  remove: (collectionId: string, userId: string) =>
    apiClient.delete(`${base(collectionId)}/${userId}`),
}
