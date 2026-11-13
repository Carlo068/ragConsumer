import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "@/hooks/useAuth"

// Nested inside ProtectedRoute, so the user is already known to be logged in.
// This only hides the admin screens; the backend enforces admin rights on
// every /admin request regardless.
export function AdminRoute() {
  const { user } = useAuth()
  if (!user?.is_admin) return <Navigate to="/collections" replace />
  return <Outlet />
}
