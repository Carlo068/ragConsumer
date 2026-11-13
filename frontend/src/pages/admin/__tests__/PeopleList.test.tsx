import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ApiError } from "@/services/apiClient"
import { PeopleList } from "@/pages/admin/components/PeopleList"
import type { AdminUser } from "@/models/user"
import type { InviteCreated } from "@/models/invite"

const admin: AdminUser = {
  id: "a1",
  email: "admin@firm.mx",
  is_admin: true,
  is_active: true,
  created_at: "2026-01-01T00:00:00",
}
const ana: AdminUser = { ...admin, id: "u1", email: "ana@firm.mx", is_admin: false }
const gone: AdminUser = { ...ana, id: "u2", email: "gone@firm.mx", is_active: false }

function setup(users: AdminUser[], overrides: Partial<Parameters<typeof PeopleList>[0]> = {}) {
  const props = {
    users,
    currentUserId: admin.id,
    onDisable: vi.fn().mockResolvedValue(undefined),
    onEnable: vi.fn().mockResolvedValue(undefined),
    onEndSessions: vi.fn().mockResolvedValue(undefined),
    onCreateReset: vi.fn(),
    ...overrides,
  }
  render(<PeopleList {...props} />)
  return { props, user: userEvent.setup() }
}

function row(email: string) {
  return screen.getByTestId(`person-${email}`)
}

describe("PeopleList", () => {
  it("marks disabled accounts and offers to enable them instead of the other actions", () => {
    setup([admin, ana, gone])
    const disabledRow = row("gone@firm.mx")
    expect(within(disabledRow).getByText("Disabled")).toBeInTheDocument()
    expect(within(disabledRow).getByRole("button", { name: "Enable" })).toBeInTheDocument()
    expect(within(disabledRow).queryByRole("button", { name: "Disable" })).not.toBeInTheDocument()
    expect(within(disabledRow).queryByRole("button", { name: "Reset password" })).not.toBeInTheDocument()
  })

  it("does not offer to disable your own account", () => {
    setup([admin, ana])
    expect(within(row("admin@firm.mx")).queryByRole("button", { name: "Disable" })).not.toBeInTheDocument()
    expect(within(row("ana@firm.mx")).getByRole("button", { name: "Disable" })).toBeInTheDocument()
  })

  it("asks before disabling, says what it does, and only then acts", async () => {
    const { props, user } = setup([admin, ana])
    await user.click(within(row("ana@firm.mx")).getByRole("button", { name: "Disable" }))

    expect(await screen.findByText("Disable ana@firm.mx?")).toBeInTheDocument()
    expect(screen.getByText(/signed out at once/)).toBeInTheDocument()
    expect(props.onDisable).not.toHaveBeenCalled()

    await user.click(screen.getByRole("button", { name: "Disable", hidden: false }))
    expect(props.onDisable).toHaveBeenCalledWith("u1")
  })

  it("cancelling a confirmation does nothing", async () => {
    const { props, user } = setup([admin, ana])
    await user.click(within(row("ana@firm.mx")).getByRole("button", { name: "Sign out everywhere" }))
    await user.click(await screen.findByRole("button", { name: "Cancel" }))
    expect(props.onEndSessions).not.toHaveBeenCalled()
  })

  it("shows a one-use reset link once it is created, next to the right person", async () => {
    const created: InviteCreated = {
      id: "i1",
      email: "ana@firm.mx",
      created_at: "2026-11-13T10:00:00",
      expires_at: "2026-11-16T10:00:00",
      kind: "reset",
      invite_url: "https://matters.firm.mx/invite/abc123",
    }
    const { user } = setup([admin, ana], { onCreateReset: vi.fn().mockResolvedValue(created) })

    await user.click(within(row("ana@firm.mx")).getByRole("button", { name: "Reset password" }))
    await user.click(await screen.findByRole("button", { name: "Reset password", hidden: false }))

    expect(await screen.findByText("https://matters.firm.mx/invite/abc123")).toBeInTheDocument()
    expect(within(row("ana@firm.mx")).getByText(/Send this link to ana@firm.mx/)).toBeInTheDocument()
    expect(within(row("admin@firm.mx")).queryByText(/Send this link/)).not.toBeInTheDocument()
  })

  it("explains a failure in plain language, never showing raw server text", async () => {
    const { user } = setup([admin, ana], {
      onDisable: vi.fn().mockRejectedValue(new ApiError(409, "You cannot disable your own account", "cannot_disable_self")),
    })
    await user.click(within(row("ana@firm.mx")).getByRole("button", { name: "Disable" }))
    await user.click(await screen.findByRole("button", { name: "Disable", hidden: false }))

    expect(await screen.findByText("You can't disable your own account.")).toBeInTheDocument()
    expect(screen.queryByText("You cannot disable your own account")).not.toBeInTheDocument()
  })
})
