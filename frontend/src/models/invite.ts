export interface Invite {
  id: string
  email: string
  created_at: string
  expires_at: string
}

// Only returned at creation: the server stores just a hash of the token, so
// this link can't be fetched again later.
export interface InviteCreated extends Invite {
  invite_url: string
}

export interface InviteInfo {
  email: string
}

export interface CreateInviteRequest {
  email: string
}

export interface AcceptInviteRequest {
  password: string
}
