import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/hooks/useAuth"
import { LoginForm } from "./components/LoginForm"

export function LoginPage() {
  const { login, error } = useAuth()
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(email: string, password: string) {
    setSubmitting(true)
    try {
      await login({ email, password })
      navigate("/collections")
    } catch {
      // error is already surfaced via useAuth().error
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center">
      <LoginForm onSubmit={handleSubmit} submitting={submitting} error={error} />
    </div>
  )
}
