export interface Invite {
  id: string
  email: string
  created_at: string
  expires_at: string
  // "invite" creates an account; "reset" sets a new password on an existing one.
  kind: "invite" | "reset"
}

// Only returned at creation: the server stores just a hash of the token, so
// this link can't be fetched again later.
export interface InviteCreated extends Invite {
  invite_url: string
}

export interface InviteInfo {
  email: string
  kind: "invite" | "reset"
}

export interface CreateInviteRequest {
  email: string
}

export interface AcceptInviteRequest {
  password: string
}
