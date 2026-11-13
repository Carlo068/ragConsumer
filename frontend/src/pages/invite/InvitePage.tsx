import { useNavigate, useParams } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/hooks/useAuth"
import { useInvite } from "@/hooks/useInvite"
import { AcceptInviteForm } from "./components/AcceptInviteForm"

export function InvitePage() {
  const { token } = useParams<{ token: string }>()
  const { invite, loading, invalid, accept } = useInvite(token!)
  const { refresh } = useAuth()
  const navigate = useNavigate()

  async function handleAccept(password: string) {
    await accept(password)
    await refresh()
    navigate("/collections", { replace: true })
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm">Checking your invitation...</p>}
          {invalid && (
            <p className="text-sm">
              This invitation link is invalid or has expired. Ask your firm's administrator to
              send you a new one.
            </p>
          )}
          {invite && <AcceptInviteForm email={invite.email} onSubmit={handleAccept} />}
        </CardContent>
      </Card>
    </div>
  )
}
