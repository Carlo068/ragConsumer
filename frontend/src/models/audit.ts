export interface AuditEntry {
  id: string
  occurred_at: string
  actor_email: string | null
  action: string
  collection_id: string | null
  collection_name: string | null
  target: string | null
  detail: Record<string, unknown> | null
  ip: string | null
}

export interface AuditPage {
  items: AuditEntry[]
  total: number
}

export interface AuditFilters {
  action?: string
  actor?: string
}

// The action codes the server records. Their names in each language are in the
// message catalogs under audit.actions.
export const AUDIT_ACTIONS = [
  "login",
  "login_failed",
  "invite_created",
  "invite_revoked",
  "invite_accepted",
  "matter_created",
  "matter_renamed",
  "matter_deleted",
  "member_added",
  "member_role_changed",
  "member_removed",
  "document_uploaded",
  "document_deleted",
  "document_reingested",
  "token_created",
  "token_revoked",
  "ai_access_enabled",
  "ai_access_disabled",
  "mcp_search",
  "mcp_get_content",
  "mcp_get_document",
  "mcp_list_documents",
  "audit_viewed",
  "audit_exported",
] as const
