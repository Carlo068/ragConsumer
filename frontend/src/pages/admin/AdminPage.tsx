import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { useAdmin } from "@/hooks/useAdmin"
import { InviteUserForm } from "./components/InviteUserForm"

export function AdminPage() {
  const { users, invites, loading, error, createInvite, revokeInvite } = useAdmin()

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold">Users & invitations</h1>
        <p className="text-muted-foreground text-sm">
          New people can only join by invitation. Inviting someone doesn't give them access to
          any matter. They have to be added to each one separately.
        </p>
      </div>

      {loading && <p>Loading...</p>}
      {error && <p className="text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Invite someone</CardTitle>
        </CardHeader>
        <CardContent>
          <InviteUserForm onInvite={createInvite} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pending invitations</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {invites.length === 0 && (
            <p className="text-muted-foreground text-sm">No pending invitations.</p>
          )}
          {invites.map((invite) => (
            <div key={invite.id} className="flex items-center justify-between gap-3 text-sm">
              <div>
                <p>{invite.email}</p>
                <p className="text-muted-foreground text-xs">
                  Expires {new Date(invite.expires_at + "Z").toLocaleString()}
                </p>
              </div>
              <ConfirmDialog
                trigger={
                  <Button variant="ghost" size="sm">
                    Revoke
                  </Button>
                }
                title={`Revoke the invitation for ${invite.email}?`}
                description="The link stops working immediately. You can send a new invitation later."
                confirmLabel="Revoke"
                onConfirm={() => revokeInvite(invite.id)}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>People with an account</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {users.map((user) => (
            <div key={user.id} className="flex items-center justify-between text-sm">
              <span>{user.email}</span>
              {user.is_admin && <Badge variant="secondary">Administrator</Badge>}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
