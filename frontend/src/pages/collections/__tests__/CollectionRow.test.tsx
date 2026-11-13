import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { CollectionRow } from "@/pages/collections/components/CollectionRow"
import type { CollectionRole } from "@/models/collection"

function renderRow(
  role: CollectionRole,
  aiEnabled = false,
  onToggleAi = vi.fn(),
  counts = { document_count: 0, ready_count: 0, failed_count: 0 }
) {
  render(
    <MemoryRouter>
      <CollectionRow
        collection={{ id: "1", name: "Doe Estate", role, ai_enabled: aiEnabled, ...counts }}
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
      expect(screen.getByText(role === "editor" ? "Editor" : "Viewer")).toBeInTheDocument()
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

describe("CollectionRow plain-language details", () => {
  it("says what the AI switch does in words, not just with a switch", () => {
    renderRow("viewer", true)
    expect(screen.getByText("AI on")).toBeInTheDocument()
  })

  it("says the AI is off when it is off", () => {
    renderRow("viewer", false)
    expect(screen.getByText("AI off")).toBeInTheDocument()
  })

  it("shows how many files the matter has and how many are ready", () => {
    renderRow("owner", false, vi.fn(), { document_count: 12, ready_count: 10, failed_count: 0 })
    expect(screen.getByText("12 files · 10 ready")).toBeInTheDocument()
  })

  it("mentions files that could not be read, only when there are some", () => {
    renderRow("owner", false, vi.fn(), { document_count: 12, ready_count: 10, failed_count: 2 })
    expect(screen.getByText("12 files · 10 ready · 2 couldn't be read")).toBeInTheDocument()
  })

  it("uses the singular for one file", () => {
    renderRow("owner", false, vi.fn(), { document_count: 1, ready_count: 1, failed_count: 0 })
    expect(screen.getByText("1 file · 1 ready")).toBeInTheDocument()
  })

  it("tells you when there are no files yet", () => {
    renderRow("owner")
    expect(screen.getByText("No files yet")).toBeInTheDocument()
  })
})
