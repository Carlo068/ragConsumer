export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed"

export interface Document {
  id: string
  collection_id: string
  source_filename: string
  status: DocumentStatus
  // Why indexing failed, in plain words. Only set when status is "failed".
  error_message: string | null
  created_at: string
}
