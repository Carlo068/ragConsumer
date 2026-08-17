import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"

function setup(onConfirm = vi.fn()) {
  render(
    <ConfirmDialog
      trigger={<button>Delete</button>}
      title="Delete this collection?"
      description="This can't be undone."
      onConfirm={onConfirm}
    />
  )
  return { onConfirm }
}

// jsdom doesn't load real CSS, so the dialog's data-closed:hidden styling
// (see components/ui/alert-dialog.tsx) never actually hides anything here --
// the underlying DOM node stays present either way. What Base UI *does*
// reliably toggle regardless of CSS is the data-open attribute, so that's
// what closed-state assertions check instead of DOM presence.
function isOpen() {
  return document.querySelector('[data-slot="alert-dialog-content"]')?.hasAttribute("data-open") ?? false
}

describe("ConfirmDialog", () => {
  it("is closed until the trigger is clicked", () => {
    setup()
    expect(screen.queryByText("Delete this collection?")).not.toBeInTheDocument()
  })

  it("opens on trigger click and shows title/description", async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole("button", { name: "Delete" }))

    expect(screen.getByText("Delete this collection?")).toBeInTheDocument()
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument()
  })

  it("calls onConfirm and closes when the confirm action is clicked", async () => {
    const user = userEvent.setup()
    const { onConfirm } = setup()

    await user.click(screen.getByRole("button", { name: "Delete" }))
    // Two "Delete" buttons exist once open: the trigger and the destructive
    // confirm action -- the confirm action is the last one in the dialog.
    const deleteButtons = screen.getAllByRole("button", { name: "Delete" })
    await user.click(deleteButtons[deleteButtons.length - 1])

    expect(onConfirm).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(isOpen()).toBe(false))
  })

  it("does not call onConfirm and closes when Cancel is clicked", async () => {
    const user = userEvent.setup()
    const { onConfirm } = setup()

    await user.click(screen.getByRole("button", { name: "Delete" }))
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    expect(onConfirm).not.toHaveBeenCalled()
    await waitFor(() => expect(isOpen()).toBe(false))
  })
})
