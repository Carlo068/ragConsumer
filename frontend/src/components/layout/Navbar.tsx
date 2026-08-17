import { Link } from "react-router-dom"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/hooks/useAuth"

function getInitials(email: string): string {
  const localPart = email.split("@")[0]
  const segments = localPart.split(/[._-]+/).filter(Boolean)
  const initials =
    segments.length >= 2 ? segments[0][0] + segments[1][0] : localPart.slice(0, 2)
  return initials.toUpperCase()
}

export function Navbar() {
  const { user, logout } = useAuth()
  if (!user) return null

  return (
    <nav className="flex items-center justify-between border-b px-6 py-3">
      <Link to="/collections" className="font-semibold">
        ragConsumer
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger>
          <Avatar>
            <AvatarFallback>{getInitials(user.email)}</AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem render={<Link to="/collections">Collections</Link>} />
          <DropdownMenuItem render={<Link to="/connect">Connect</Link>} />
          <DropdownMenuItem variant="destructive" onClick={() => logout()}>
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  )
}
