import { Link } from "react-router-dom"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher"
import { useAuth } from "@/hooks/useAuth"
import { useI18n } from "@/i18n/useI18n"

function getInitials(email: string): string {
  const localPart = email.split("@")[0]
  const segments = localPart.split(/[._-]+/).filter(Boolean)
  const initials =
    segments.length >= 2 ? segments[0][0] + segments[1][0] : localPart.slice(0, 2)
  return initials.toUpperCase()
}

export function Navbar() {
  const { user, logout } = useAuth()
  const { t } = useI18n()
  if (!user) return null

  return (
    <nav className="flex items-center justify-between border-b px-6 py-3">
      <Link to="/collections" className="font-semibold">
        ragConsumer
      </Link>
      <div className="flex items-center gap-4">
      <LanguageSwitcher />
      <DropdownMenu>
        <DropdownMenuTrigger>
          <Avatar>
            <AvatarFallback>{getInitials(user.email)}</AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem render={<Link to="/collections">{t("nav.collections")}</Link>} />
          <DropdownMenuItem render={<Link to="/connect">{t("nav.connect")}</Link>} />
          {user.is_admin && (
            <DropdownMenuItem render={<Link to="/admin">{t("nav.admin")}</Link>} />
          )}
          <DropdownMenuItem variant="destructive" onClick={() => logout()}>
            {t("nav.signOut")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      </div>
    </nav>
  )
}
