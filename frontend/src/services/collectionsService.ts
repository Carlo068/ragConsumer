import { apiClient } from "./apiClient"
import type { Collection } from "@/models/collection"

export const collectionsService = {
  list: () => apiClient.get<Collection[]>("/collections"),
}
