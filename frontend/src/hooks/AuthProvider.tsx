import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { useI18n } from "@/i18n/useI18n"
import { authService } from "@/services/authService"
import type { LoginRequest } from "@/models/auth"
import type { User } from "@/models/user"

interface AuthContextValue {
  user: User | null
  loading: boolean
  error: string | null
  login: (payload: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  // Re-reads the session, e.g. after accepting an invite logs the user in
  // server-side without going through login().
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { errorText } = useI18n()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    authService
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  async function login(payload: LoginRequest) {
    setError(null)
    try {
      const loggedInUser = await authService.login(payload)
      setUser(loggedInUser)
    } catch (err) {
      setError(errorText(err, "login.failed"))
      throw err
    }
  }

  async function logout() {
    await authService.logout()
    setUser(null)
  }

  async function refresh() {
    try {
      setUser(await authService.me())
    } catch {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuthContext() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuthContext must be used within an AuthProvider")
  }
  return ctx
}
