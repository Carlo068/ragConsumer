import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ApiError } from "@/services/apiClient"
import { ChangePasswordForm } from "@/pages/account/components/ChangePasswordForm"

function setup(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(<ChangePasswordForm onSubmit={onSubmit} />)
  return { onSubmit, user: userEvent.setup() }
}

async function fill(user: ReturnType<typeof userEvent.setup>, current: string, next: string, again: string) {
  await user.type(screen.getByLabelText("Current password"), current)
  await user.type(screen.getByLabelText("New password"), next)
  await user.type(screen.getByLabelText("Repeat the new password"), again)
  await user.click(screen.getByRole("button", { name: "Change password" }))
}

describe("ChangePasswordForm", () => {
  it("rejects a short new password without submitting", async () => {
    const { onSubmit, user } = setup()
    await fill(user, "old-password-1", "short", "short")
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText("Use at least 12 characters.")).toBeInTheDocument()
  })

  it("rejects mismatched new passwords without submitting", async () => {
    const { onSubmit, user } = setup()
    await fill(user, "old-password-1", "a-long-new-passphrase", "a-different-passphrase")
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText("The two passwords don't match.")).toBeInTheDocument()
  })

  it("submits the current and new password, confirms, and clears the fields", async () => {
    const { onSubmit, user } = setup()
    await fill(user, "old-password-1", "a-long-new-passphrase", "a-long-new-passphrase")

    expect(onSubmit).toHaveBeenCalledWith("old-password-1", "a-long-new-passphrase")
    expect(await screen.findByText("Your password was changed. Other devices were signed out.")).toBeInTheDocument()
    expect(screen.getByLabelText("Current password")).toHaveValue("")
    expect(screen.getByLabelText("New password")).toHaveValue("")
  })

  it("says plainly when the current password is wrong", async () => {
    const { user } = setup(
      vi.fn().mockRejectedValue(new ApiError(400, "The current password is not correct", "wrong_password"))
    )
    await fill(user, "not-mine-at-all", "a-long-new-passphrase", "a-long-new-passphrase")
    expect(await screen.findByText("The current password is not correct.")).toBeInTheDocument()
    expect(screen.queryByText("Your password was changed. Other devices were signed out.")).not.toBeInTheDocument()
  })

  it("tells the person how long to wait when sign-in is paused", async () => {
    const { user } = setup(
      vi.fn().mockRejectedValue(new ApiError(429, "Too many failed attempts", "too_many_attempts", { minutes: 15 }))
    )
    await fill(user, "guess-after-guess", "a-long-new-passphrase", "a-long-new-passphrase")
    expect(await screen.findByText("Too many attempts. Wait 15 minutes and try again.")).toBeInTheDocument()
  })
})
