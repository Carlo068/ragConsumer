export interface User {
  id: string
  email: string
  is_admin: boolean
}

export interface AdminUser extends User {
  created_at: string
}
