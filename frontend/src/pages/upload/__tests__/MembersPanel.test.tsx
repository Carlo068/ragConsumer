import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { MembersPanel } from "@/pages/upload/components/MembersPanel"
import type { Member } from "@/models/member"

const members: Member[] = [
  { user_id: "me", email: "me@firm.mx", role: "owner" },
  { user_id: "u2", email: "colega@firm.mx", role: "viewer" },
]

function setup(over: Partial<React.ComponentProps<typeof MembersPanel>> = {}) {
  const props = {
    members,
    currentUserId: "me",
    canManage: true,
    onAdd: vi.fn().mockResolvedValue(undefined),
    onChangeRole: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
    ...over,
  }
  render(<MembersPanel {...props} />)
  return { props, user: userEvent.setup() }
}

describe("MembersPanel", () => {
  it("lets an owner change roles, add people and remove others", () => {
    setup()
    expect(screen.getByLabelText("Role for colega@firm.mx")).toBeInTheDocument()
    expect(screen.getByLabelText("Add someone who already has an account")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument()
  })

  it("is read-only for non-owners: no role pickers, no add form, but they can leave", () => {
    setup({ canManage: false, currentUserId: "u2" })
    expect(screen.queryByLabelText("Role for colega@firm.mx")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Add someone who already has an account")).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Leave" })).toBeInTheDocument()
    expect(screen.getByText("viewer")).toBeInTheDocument()
  })

  it("marks the current user and offers 'Leave' only on their own row", () => {
    setup()
    expect(screen.getByText("(you)")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: "Leave" })).toHaveLength(1)
  })

  it("adds a member with the chosen role", async () => {
    const { props, user } = setup()
    await user.type(screen.getByLabelText("Add someone who already has an account"), "nueva@firm.mx")
    await user.selectOptions(screen.getByLabelText("Role for the new member"), "editor")
    await user.click(screen.getByRole("button", { name: "Add" }))
    expect(props.onAdd).toHaveBeenCalledWith("nueva@firm.mx", "editor")
  })

  it("changes someone's role", async () => {
    const { props, user } = setup()
    await user.selectOptions(screen.getByLabelText("Role for colega@firm.mx"), "editor")
    expect(props.onChangeRole).toHaveBeenCalledWith("u2", "editor")
  })

  it("shows the server's message when a change is refused (e.g. last owner)", async () => {
    const { user } = setup({
      onChangeRole: vi.fn().mockRejectedValue(new Error("A collection must keep at least one owner.")),
    })
    await user.selectOptions(screen.getByLabelText("Role for me@firm.mx"), "viewer")
    expect(await screen.findByText("A collection must keep at least one owner.")).toBeInTheDocument()
  })
})
