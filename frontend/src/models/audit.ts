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

// Plain-language names for the action codes the server records.
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  login: "Signed in",
  login_failed: "Failed sign-in attempt",
  invite_created: "Invitation created",
  invite_revoked: "Invitation revoked",
  invite_accepted: "Invitation accepted",
  matter_created: "Matter created",
  matter_renamed: "Matter renamed",
  matter_deleted: "Matter deleted",
  member_added: "Person added to a matter",
  member_role_changed: "Role changed",
  member_removed: "Person removed from a matter",
  document_uploaded: "File uploaded",
  document_deleted: "File deleted",
  document_reingested: "File retried",
  token_created: "Access key created",
  token_revoked: "Access key revoked",
  ai_access_enabled: "AI turned on for a matter",
  ai_access_disabled: "AI turned off for a matter",
  mcp_search: "AI searched",
  mcp_get_content: "AI read a passage",
  mcp_get_document: "AI read a document",
  mcp_list_documents: "AI listed files",
  audit_viewed: "Activity log opened",
  audit_exported: "Activity log downloaded",
}

export const auditActionLabel = (action: string) => AUDIT_ACTION_LABELS[action] ?? action
