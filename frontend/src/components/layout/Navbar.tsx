import { Link, NavLink, useNavigate } from "react-router-dom"
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
  const navigate = useNavigate()
  if (!user) return null

  // The places people actually go, always in view (not hidden in a menu).
  const links = [
    { to: "/collections", label: t("nav.collections") },
    { to: "/connect", label: t("nav.connect") },
    ...(user.is_admin ? [{ to: "/admin", label: t("nav.admin") }] : []),
  ]

  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-3">
      <div className="flex flex-wrap items-center gap-6">
        <Link to="/collections" className="font-semibold">
          ragConsumer
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive ? "font-medium underline underline-offset-4" : "text-muted-foreground hover:text-foreground"
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-4">
        <LanguageSwitcher />
        <DropdownMenu>
          <DropdownMenuTrigger>
            <Avatar>
              <AvatarFallback>{getInitials(user.email)}</AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => navigate("/account")}>
              {t("nav.account")}
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onClick={() => logout()}>
              {t("nav.signOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  )
}
