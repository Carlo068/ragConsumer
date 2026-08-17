import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { PromptDialog } from "@/components/common/PromptDialog"

// jsdom loads no real CSS, so data-closed:hidden never actually hides
// anything here -- check the data-open attribute Base UI toggles instead.
function isOpen() {
  return document.querySelector('[data-slot="dialog-content"]')?.hasAttribute("data-open") ?? false
}

describe("PromptDialog", () => {
  it("opens on trigger click, pre-filled with initialValue", async () => {
    const user = userEvent.setup()
    render(
      <PromptDialog
        trigger={<button>Rename</button>}
        title='Rename "Doe Estate"'
        initialValue="Doe Estate"
        onSubmit={vi.fn()}
      />
    )

    await user.click(screen.getByRole("button", { name: "Rename" }))

    expect(screen.getByText('Rename "Doe Estate"')).toBeInTheDocument()
    expect(screen.getByRole("textbox")).toHaveValue("Doe Estate")
  })

  it("submits the edited, trimmed value and closes", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <PromptDialog
        trigger={<button>Rename</button>}
        title="Rename"
        initialValue="Doe Estate"
        confirmLabel="Save"
        onSubmit={onSubmit}
      />
    )

    await user.click(screen.getByRole("button", { name: "Rename" }))
    const input = screen.getByRole("textbox")
    await user.clear(input)
    await user.type(input, "  Renamed Estate  ")
    await user.click(screen.getByRole("button", { name: "Save" }))

    expect(onSubmit).toHaveBeenCalledWith("Renamed Estate")
    await waitFor(() => expect(isOpen()).toBe(false))
  })

  it("does not submit when Cancel is clicked", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <PromptDialog trigger={<button>New</button>} title="New collection" onSubmit={onSubmit} />
    )

    await user.click(screen.getByRole("button", { name: "New" }))
    await user.type(screen.getByRole("textbox"), "Won't be saved")
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("disables the confirm button when the value is empty", async () => {
    const user = userEvent.setup()
    render(
      <PromptDialog
        trigger={<button>New</button>}
        title="New collection"
        confirmLabel="Create"
        onSubmit={vi.fn()}
      />
    )

    await user.click(screen.getByRole("button", { name: "New" }))

    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled()
  })
})
