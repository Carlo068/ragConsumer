import { apiClient } from "./apiClient"
import type { ApiToken, ApiTokenCreated, CreateTokenRequest } from "@/models/token"

export const tokenService = {
  list: () => apiClient.get<ApiToken[]>("/tokens"),
  create: (payload: CreateTokenRequest) => apiClient.post<ApiTokenCreated>("/tokens", payload),
  revoke: (id: string) => apiClient.delete(`/tokens/${id}`),
}
