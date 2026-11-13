import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { CollectionsPage } from "@/pages/collections/CollectionsPage"
import { useCollections } from "@/hooks/useCollections"

vi.mock("@/hooks/useCollections")

const base = {
  loading: false,
  error: null,
  createCollection: vi.fn(),
  renameCollection: vi.fn(),
  deleteCollection: vi.fn(),
  setAiAccess: vi.fn(),
}

function renderPage(over: Partial<ReturnType<typeof useCollections>>) {
  vi.mocked(useCollections).mockReturnValue({ ...base, collections: [], ...over })
  render(
    <MemoryRouter>
      <CollectionsPage />
    </MemoryRouter>
  )
}

describe("CollectionsPage", () => {
  it("explains what to do when there are no collections yet", () => {
    renderPage({})
    expect(screen.getByText(/Create the first one/)).toBeInTheDocument()
  })

  it("does not show that message while loading or after an error", () => {
    renderPage({ loading: true })
    expect(screen.queryByText(/Create the first one/)).not.toBeInTheDocument()
  })

  it("explains what the switch on each matter is for", () => {
    renderPage({})
    expect(screen.getByText(/so your own AI assistant can search its files/)).toBeInTheDocument()
  })
})
