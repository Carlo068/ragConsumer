import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { CollectionRow } from "@/pages/collections/components/CollectionRow"
import type { CollectionRole } from "@/models/collection"

function renderRow(role: CollectionRole) {
  render(
    <MemoryRouter>
      <CollectionRow
        collection={{ id: "1", name: "Doe Estate", role }}
        active={false}
        onToggleActive={vi.fn()}
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
