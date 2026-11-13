import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { AcceptInviteForm } from "@/pages/invite/components/AcceptInviteForm"

function setup(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(<AcceptInviteForm email="ana@firm.mx" onSubmit={onSubmit} />)
  return { onSubmit, user: userEvent.setup() }
}

describe("AcceptInviteForm", () => {
  it("shows which email the invitation is for", () => {
    setup()
    expect(screen.getByText("ana@firm.mx")).toBeInTheDocument()
  })

  it("rejects a password shorter than 12 characters without submitting", async () => {
    const { onSubmit, user } = setup()
    await user.type(screen.getByLabelText("Password"), "short")
    await user.type(screen.getByLabelText("Repeat password"), "short")
    await user.click(screen.getByRole("button", { name: "Create account" }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText("Use at least 12 characters.")).toBeInTheDocument()
  })

  it("rejects mismatched passwords without submitting", async () => {
    const { onSubmit, user } = setup()
    await user.type(screen.getByLabelText("Password"), "a-long-passphrase")
    await user.type(screen.getByLabelText("Repeat password"), "a-different-one!")
    await user.click(screen.getByRole("button", { name: "Create account" }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText("The two passwords don't match.")).toBeInTheDocument()
  })

  it("submits a valid, matching password", async () => {
    const { onSubmit, user } = setup()
    await user.type(screen.getByLabelText("Password"), "a-long-passphrase")
    await user.type(screen.getByLabelText("Repeat password"), "a-long-passphrase")
    await user.click(screen.getByRole("button", { name: "Create account" }))

    expect(onSubmit).toHaveBeenCalledWith("a-long-passphrase")
  })

  it("shows the server's error if account creation fails", async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error("A user with this email already exists")))
    await user.type(screen.getByLabelText("Password"), "a-long-passphrase")
    await user.type(screen.getByLabelText("Repeat password"), "a-long-passphrase")
    await user.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("A user with this email already exists")).toBeInTheDocument()
  })
})
