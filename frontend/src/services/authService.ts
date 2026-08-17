import { apiClient } from "./apiClient"
import type { LoginRequest } from "@/models/auth"
import type { User } from "@/models/user"

export const authService = {
  login: (payload: LoginRequest) => apiClient.post<User>("/auth/login", payload),
  logout: () => apiClient.post<{ ok: boolean }>("/auth/logout"),
  me: () => apiClient.get<User>("/auth/me"),
}
