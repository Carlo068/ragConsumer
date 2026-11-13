import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { Navbar } from "@/components/layout/Navbar"
import { I18nProvider } from "@/i18n/I18nProvider"
import { useAuth } from "@/hooks/useAuth"

vi.mock("@/hooks/useAuth")

function renderNav(user: { is_admin: boolean } | null, path = "/collections", locale: "en" | "es" = "en") {
  vi.mocked(useAuth).mockReturnValue({
    user: user ? { id: "u1", email: "ana.gomez@firm.mx", ...user } : null,
    logout: vi.fn(),
  } as never)
  render(
    <I18nProvider locale={locale}>
      <MemoryRouter initialEntries={[path]}>
        <Navbar />
      </MemoryRouter>
    </I18nProvider>
  )
}

describe("Navbar", () => {
  it("shows the matters and Connect links in plain view, without opening any menu", () => {
    renderNav({ is_admin: false })
    expect(screen.getByRole("link", { name: "Collections" })).toHaveAttribute("href", "/collections")
    expect(screen.getByRole("link", { name: "Connect your AI" })).toHaveAttribute("href", "/connect")
  })

  it("uses the words lawyers use, in Spanish", () => {
    renderNav({ is_admin: false }, "/collections", "es")
    expect(screen.getByRole("link", { name: "Asuntos" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Conectar IA" })).toBeInTheDocument()
  })

  it("shows the administration link only to administrators", () => {
    renderNav({ is_admin: false })
    expect(screen.queryByRole("link", { name: "Users & invitations" })).not.toBeInTheDocument()
  })

  it("shows the administration link to an administrator", () => {
    renderNav({ is_admin: true })
    expect(screen.getByRole("link", { name: "Users & invitations" })).toHaveAttribute("href", "/admin")
  })

  it("highlights where you are", () => {
    renderNav({ is_admin: false }, "/connect")
    expect(screen.getByRole("link", { name: "Connect your AI" })).toHaveClass("font-medium")
    expect(screen.getByRole("link", { name: "Collections" })).not.toHaveClass("font-medium")
  })

  it("shows nothing when signed out", () => {
    renderNav(null)
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument()
  })

  it("keeps the language switcher in view", () => {
    renderNav({ is_admin: false })
    expect(screen.getByRole("button", { name: "Español" })).toBeInTheDocument()
  })
})
