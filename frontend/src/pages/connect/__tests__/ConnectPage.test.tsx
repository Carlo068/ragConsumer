import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { I18nProvider } from "@/i18n/I18nProvider"
import { ConnectPage } from "@/pages/connect/ConnectPage"
import { useCollections } from "@/hooks/useCollections"
import { useTokens } from "@/hooks/useTokens"
import type { Collection } from "@/models/collection"
import type { ApiToken } from "@/models/token"

vi.mock("@/hooks/useCollections")
vi.mock("@/hooks/useTokens")

const matter = (id: string, name: string, ai_enabled: boolean): Collection => ({
  id,
  name,
  role: "owner",
  ai_enabled,
  document_count: 0,
  ready_count: 0,
  failed_count: 0,
})

const existingToken: ApiToken = {
  id: "t1",
  name: "Mi laptop",
  prefix: "rag_AbCd",
  created_at: "2026-11-01T10:00:00",
  expires_at: "2027-01-30T10:00:00",
  last_used_at: null,
}

const setAiAccess = vi.fn()
const createToken = vi.fn()

function renderPage(
  over: { collections?: Collection[]; tokens?: ApiToken[]; locale?: "en" | "es" } = {}
) {
  vi.mocked(useCollections).mockReturnValue({
    collections: over.collections ?? [],
    loading: false,
    error: null,
    createCollection: vi.fn(),
    renameCollection: vi.fn(),
    deleteCollection: vi.fn(),
    setAiAccess,
  })
  vi.mocked(useTokens).mockReturnValue({
    tokens: over.tokens ?? [],
    loading: false,
    error: null,
    createToken,
    revokeToken: vi.fn(),
  })
  render(
    <I18nProvider locale={over.locale ?? "en"}>
      <MemoryRouter>
        <ConnectPage />
      </MemoryRouter>
    </I18nProvider>
  )
  return userEvent.setup()
}

beforeEach(() => {
  setAiAccess.mockReset()
  createToken.mockReset()
})

describe("ConnectPage", () => {
  it("is a guide in four numbered steps, in order", () => {
    renderPage()
    const titles = screen.getAllByText(/^\d\.$/).map((el) => el.parentElement?.textContent ?? "")
    expect(titles.map((t) => t.replace(/^\d\. /, "").trim())).toEqual([
      "Choose which matters your AI can see",
      "Create your personal access key",
      "Paste it into your AI assistant",
      "Try a question",
    ])
  })

  it("uses no technical jargon in the steps themselves", () => {
    renderPage()
    const page = document.body.textContent ?? ""
    const outsideAdvanced = page.replace(document.querySelector("details")?.textContent ?? "", "")
    // 'MCP' only appears as a name the assistant might use for the connection, never as a to-do.
    expect(outsideAdvanced).not.toMatch(/\.mcp\.json|claude mcp add|Bearer/)
  })

  it("step 1 lists the matters with a switch each, and turning one on tells the server", async () => {
    const user = renderPage({ collections: [matter("m1", "Doe Estate", false), matter("m2", "Smith v. Jones", true)] })
    const switches = screen.getAllByRole("switch")
    expect(switches).toHaveLength(2)
    await user.click(screen.getByRole("switch", { name: "Let my AI search Doe Estate" }))
    expect(setAiAccess).toHaveBeenCalledWith("m1", true)
  })

  it("step 1 says what to do when there are no matters", () => {
    renderPage({ collections: [] })
    expect(screen.getByText(/You don't have access to any matters yet/)).toBeInTheDocument()
  })

  it("marks steps done as they are completed", () => {
    renderPage({ collections: [matter("m1", "Doe", true)], tokens: [existingToken] })
    expect(screen.getAllByText("Done")).toHaveLength(2) // steps 1 and 2
  })

  it("does not mark steps done before they are", () => {
    renderPage({ collections: [matter("m1", "Doe", false)], tokens: [] })
    expect(screen.queryByText("Done")).not.toBeInTheDocument()
  })

  it("step 3 shows the server address and waits for a key to be created", () => {
    renderPage()
    expect(screen.getByText("Server address")).toBeInTheDocument()
    expect(screen.getByText(/\/mcp$/)).toBeInTheDocument()
    expect(screen.getByText(/Create a key in step 2 and it will appear here/)).toBeInTheDocument()
  })

  it("a key created in step 2 appears ready to copy in step 3", async () => {
    createToken.mockResolvedValue({ ...existingToken, id: "t2", name: "Phone", token: "rag_FRESH_KEY_123" })
    const user = renderPage()
    await user.type(screen.getByLabelText(/Name \(for example/), "Phone")
    await user.click(screen.getByRole("button", { name: "Create access key" }))

    const step3 = screen.getByText("Paste it into your AI assistant").closest("[data-slot=card]") as HTMLElement
    expect(await within(step3).findByText("rag_FRESH_KEY_123")).toBeInTheDocument()
    expect(within(step3).queryByText(/will appear here/)).not.toBeInTheDocument()
  })

  it("step 4 offers sample questions to try", () => {
    renderPage()
    expect(screen.getByText("Which files do I have in my matters?")).toBeInTheDocument()
    expect(screen.getAllByRole("button", { name: "Copy" }).length).toBeGreaterThanOrEqual(3)
  })

  it("keeps the raw configuration collapsed under Advanced", () => {
    renderPage()
    const advanced = screen.getByText("Advanced: connection commands").closest("details")!
    expect(advanced.open).toBe(false)
    expect(within(advanced).getByText("claude mcp add (command line)")).toBeInTheDocument()
    expect(within(advanced).getByText(".mcp.json")).toBeInTheDocument()
  })

  it("reads naturally in Spanish", () => {
    renderPage({ locale: "es" })
    expect(screen.getByText("Elija qué asuntos puede ver su IA")).toBeInTheDocument()
    expect(screen.getByText("Cree su llave de acceso personal")).toBeInTheDocument()
    expect(screen.getByText("Avanzado: comandos de conexión")).toBeInTheDocument()
    expect(screen.getByText("¿Qué archivos tengo en mis asuntos?")).toBeInTheDocument()
  })
})
