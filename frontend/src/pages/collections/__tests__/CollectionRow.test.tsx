import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { CollectionRow } from "@/pages/collections/components/CollectionRow"
import type { CollectionRole } from "@/models/collection"

function renderRow(role: CollectionRole, aiEnabled = false, onToggleAi = vi.fn()) {
  render(
    <MemoryRouter>
      <CollectionRow
        collection={{ id: "1", name: "Doe Estate", role, ai_enabled: aiEnabled }}
        onToggleAi={onToggleAi}
        onRename={vi.fn()}
        onDelete={vi.fn()}
      />
    </MemoryRouter>
  )
}

describe("CollectionRow permissions", () => {
  it("shows rename and delete to an owner", () => {
    renderRow("owner")
    expect(screen.getByLabelText("Rename collection")).toBeInTheDocument()
    expect(screen.getByLabelText("Delete collection")).toBeInTheDocument()
  })

  it.each(["editor", "viewer"] as const)(
    "hides rename and delete from a %s, and shows their role instead",
    (role) => {
      renderRow(role)
      expect(screen.queryByLabelText("Rename collection")).not.toBeInTheDocument()
      expect(screen.queryByLabelText("Delete collection")).not.toBeInTheDocument()
      expect(screen.getByText(role)).toBeInTheDocument()
    }
  )

  it("still lets any member open the collection", () => {
    renderRow("viewer")
    expect(screen.getByRole("link", { name: "Doe Estate" })).toBeInTheDocument()
  })
})

describe("CollectionRow AI switch", () => {
  it("reflects whether my AI searches this matter", () => {
    renderRow("viewer", true)
    expect(screen.getByRole("switch", { name: "Let my AI search Doe Estate" })).toBeChecked()
  })

  it("is off when the matter is not enabled", () => {
    renderRow("viewer", false)
    expect(screen.getByRole("switch", { name: "Let my AI search Doe Estate" })).not.toBeChecked()
  })

  it("lets even a viewer turn it on, reporting the new state", async () => {
    const onToggleAi = vi.fn()
    renderRow("viewer", false, onToggleAi)
    await userEvent.click(screen.getByRole("switch", { name: "Let my AI search Doe Estate" }))
    expect(onToggleAi).toHaveBeenCalledWith(true, expect.anything())
  })
})
