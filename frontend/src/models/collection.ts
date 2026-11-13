export type CollectionRole = "viewer" | "editor" | "owner"

export interface Collection {
  id: string
  name: string
  // The signed-in user's own role on this collection.
  role: CollectionRole
  // Whether the signed-in user's own AI searches this matter. Per person:
  // switching it never affects a colleague.
  ai_enabled: boolean
}

// The server enforces these same rules on every request; these helpers only
// decide which buttons to offer, so nobody is shown an action that would be
// refused.
export const canEditFiles = (role: CollectionRole | undefined) =>
  role === "editor" || role === "owner"
export const canManageCollection = (role: CollectionRole | undefined) => role === "owner"

export interface CreateCollectionRequest {
  name: string
}

export interface UpdateCollectionRequest {
  name: string
}
