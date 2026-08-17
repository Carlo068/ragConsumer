export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed"

export interface Document {
  id: string
  collection_id: string
  source_filename: string
  status: DocumentStatus
  created_at: string
}
