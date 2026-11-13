import { API_BASE_URL, ApiError, apiClient } from "./apiClient"
import type { Document } from "@/models/document"

export const documentsService = {
  list: (collectionId: string) =>
    apiClient.get<Document[]>(`/collections/${collectionId}/documents`),

  upload: (collectionId: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return apiClient.postForm<Document>(`/collections/${collectionId}/documents`, form)
  },

  // One file, with progress and cancel (fetch can report neither for uploads).
  // `path` is the name it is stored under, including the folders it came from.
  uploadWithProgress: (
    collectionId: string,
    file: File,
    path: string,
    onProgress: (fraction: number) => void,
    signal: AbortSignal
  ) =>
    new Promise<Document>((resolve, reject) => {
      const request = new XMLHttpRequest()
      request.open("POST", `${API_BASE_URL}/collections/${collectionId}/documents`)
      request.withCredentials = true
      request.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total)
      }
      request.onload = () => {
        let body: { detail?: unknown; code?: string; params?: Record<string, string | number> } | null = null
        try {
          body = JSON.parse(request.responseText)
        } catch {
          body = null
        }
        if (request.status >= 200 && request.status < 300) return resolve(body as unknown as Document)
        reject(
          new ApiError(
            request.status,
            typeof body?.detail === "string" ? body.detail : request.statusText,
            typeof body?.code === "string" ? body.code : undefined,
            body?.params
          )
        )
      }
      request.onerror = () => reject(new TypeError("Network error"))
      const abort = () => {
        request.abort()
        reject(new DOMException("Upload cancelled", "AbortError"))
      }
      if (signal.aborted) return abort()
      signal.addEventListener("abort", abort, { once: true })
      const form = new FormData()
      form.append("file", file, path)
      request.send(form)
    }),

  remove: (collectionId: string, documentId: string) =>
    apiClient.delete(`/collections/${collectionId}/documents/${documentId}`),

  retry: (collectionId: string, documentId: string) =>
    apiClient.post<Document>(`/collections/${collectionId}/documents/${documentId}/reingest`),
}
