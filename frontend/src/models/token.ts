export interface ApiToken {
  id: string
  name: string
  prefix: string
  created_at: string
  expires_at: string
  last_used_at: string | null
}

// Only returned at creation: the server keeps just a hash, so the full token
// can't be shown again.
export interface ApiTokenCreated extends ApiToken {
  token: string
}

export interface CreateTokenRequest {
  name: string
}
