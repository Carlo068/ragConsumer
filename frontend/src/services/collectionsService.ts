import { apiClient } from "./apiClient"
import type { Collection, CreateCollectionRequest, UpdateCollectionRequest } from "@/models/collection"

export const collectionsService = {
  list: () => apiClient.get<Collection[]>("/collections"),
  create: (payload: CreateCollectionRequest) =>
    apiClient.post<Collection>("/collections", payload),
  rename: (id: string, payload: UpdateCollectionRequest) =>
    apiClient.patch<Collection>(`/collections/${id}`, payload),
  remove: (id: string) => apiClient.delete(`/collections/${id}`),
}
