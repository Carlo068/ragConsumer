import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { AuditLogPanel } from "@/pages/admin/components/AuditLogPanel"
import type { AuditEntry } from "@/models/audit"

const entry = (over: Partial<AuditEntry>): AuditEntry => ({
  id: "1",
  occurred_at: "2026-11-13T09:00:00",
  actor_email: "ana@firm.mx",
  action: "mcp_search",
  collection_id: "m1",
  collection_name: "Doe Estate",
  target: null,
  detail: { query: "renta mensual", chunk_ids: ["c1"] },
  ip: null,
  ...over,
})

function setup(items: AuditEntry[] = [entry({})], extra = {}) {
  const props = {
    items,
    total: items.length,
    filters: {},
    loading: false,
    error: null,
    hasNext: false,
    hasPrevious: false,
    csvUrl: "http://api/admin/audit.csv",
    onFilter: vi.fn(),
    onNext: vi.fn(),
    onPrevious: vi.fn(),
    ...extra,
  }
  render(<AuditLogPanel {...props} />)
  return { ...props, user: userEvent.setup() }
}

describe("AuditLogPanel", () => {
  it("describes an AI search in plain language with who, which matter and the question", () => {
    setup()
    expect(screen.getByText("AI searched", { selector: "span" })).toBeInTheDocument()
    expect(screen.getByText(/ana@firm.mx · Doe Estate/)).toBeInTheDocument()
    expect(screen.getByText('"renta mensual"')).toBeInTheDocument()
  })

  it("shows what a non-search entry was about", () => {
    setup([entry({ action: "document_uploaded", detail: null, target: "contrato.pdf" })])
    expect(screen.getByText("File uploaded", { selector: "span" })).toBeInTheDocument()
    expect(screen.getByText("contrato.pdf")).toBeInTheDocument()
  })

  it("labels a failed sign-in even though nobody was signed in", () => {
    setup([entry({ action: "login_failed", actor_email: null, collection_name: null, detail: null, target: "x@firm.mx" })])
    expect(screen.getByText("Not signed in")).toBeInTheDocument()
  })

  it("offers the CSV download and filters by what happened", async () => {
    const { onFilter, user } = setup()
    expect(screen.getByText(/CSV/).closest("a")).toHaveAttribute("href", "http://api/admin/audit.csv")
    await user.selectOptions(screen.getByLabelText("What happened"), "login_failed")
    expect(onFilter).toHaveBeenCalledWith({ action: "login_failed" })
  })

  it("disables paging at the ends", () => {
    setup()
    expect(screen.getByRole("button", { name: "Newer" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Older" })).toBeDisabled()
  })
})
