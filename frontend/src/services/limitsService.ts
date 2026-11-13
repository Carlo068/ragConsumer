import { apiClient } from "./apiClient"

export interface Limits {
  max_upload_bytes: number
}

export const limitsService = {
  get: () => apiClient.get<Limits>("/limits"),
}
