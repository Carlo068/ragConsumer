import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { authService } from "@/services/authService"
import type { LoginRequest } from "@/models/auth"
import type { User } from "@/models/user"

interface AuthContextValue {
  user: User | null
  loading: boolean
  error: string | null
  login: (payload: LoginRequest) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
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
      setError(err instanceof Error ? err.message : "Login failed")
      throw err
    }
  }

  async function logout() {
    await authService.logout()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
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
