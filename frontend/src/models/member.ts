import type { CollectionRole } from "@/models/collection"

export interface Member {
  user_id: string
  email: string
  role: CollectionRole
}

export interface AddMemberRequest {
  email: string
  role: CollectionRole
}

export interface UpdateMemberRoleRequest {
  role: CollectionRole
}
