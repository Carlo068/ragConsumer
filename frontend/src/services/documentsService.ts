import { apiClient } from "./apiClient"
import type { Document } from "@/models/document"

export const documentsService = {
  list: (collectionId: string) =>
    apiClient.get<Document[]>(`/collections/${collectionId}/documents`),

  upload: (collectionId: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return apiClient.postForm<Document>(`/collections/${collectionId}/documents`, form)
  },
}
