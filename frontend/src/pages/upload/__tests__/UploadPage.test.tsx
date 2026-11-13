import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { UploadPage } from "@/pages/upload/UploadPage"
import { useAuth } from "@/hooks/useAuth"
import { useCollections } from "@/hooks/useCollections"
import { useDocuments } from "@/hooks/useDocuments"
import { useLimits } from "@/hooks/useLimits"
import { useMembers } from "@/hooks/useMembers"
import type { CollectionRole } from "@/models/collection"

vi.mock("@/hooks/useAuth")
vi.mock("@/hooks/useCollections")
vi.mock("@/hooks/useDocuments")
vi.mock("@/hooks/useLimits")
vi.mock("@/hooks/useMembers")

function renderPage(role: CollectionRole | null, name = "Smith v. Jones") {
  vi.mocked(useAuth).mockReturnValue({ user: { id: "me", email: "me@firm.mx", is_admin: false } } as never)
  vi.mocked(useLimits).mockReturnValue(null)
  vi.mocked(useMembers).mockReturnValue({
    members: [],
    loading: false,
    error: null,
    addMember: vi.fn(),
    changeRole: vi.fn(),
    removeMember: vi.fn(),
  })
  vi.mocked(useDocuments).mockReturnValue({
    documents: [],
    loading: false,
    error: null,
    uploading: false,
    upload: vi.fn(),
    remove: vi.fn(),
    retry: vi.fn(),
  })
  vi.mocked(useCollections).mockReturnValue({
    collections: role
      ? [{ id: "m1", name, role, ai_enabled: false, document_count: 0, ready_count: 0, failed_count: 0 }]
      : [],
    loading: false,
    error: null,
    createCollection: vi.fn(),
    renameCollection: vi.fn(),
    deleteCollection: vi.fn(),
    setAiAccess: vi.fn(),
  })
  render(
    <MemoryRouter initialEntries={["/collections/m1/upload"]}>
      <Routes>
        <Route path="/collections/:collectionId/upload" element={<UploadPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe("UploadPage", () => {
  it("is titled with the matter's name, not with the word 'Upload'", () => {
    renderPage("owner")
    expect(screen.getByRole("heading", { name: "Smith v. Jones" })).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Upload" })).not.toBeInTheDocument()
  })

  it("shows a loading title until the matter is known", () => {
    renderPage(null)
    expect(screen.getByRole("heading", { name: "Loading collection..." })).toBeInTheDocument()
  })

  it("tells an editor how to add the first file when there are none", () => {
    renderPage("editor")
    expect(screen.getByText(/Choose a file above and press "Upload"/)).toBeInTheDocument()
  })

  it("tells a viewer the matter is empty without offering an upload", () => {
    renderPage("viewer")
    expect(screen.getByText("This collection has no files yet.")).toBeInTheDocument()
    expect(screen.queryByText(/Choose a file above/)).not.toBeInTheDocument()
  })
})
