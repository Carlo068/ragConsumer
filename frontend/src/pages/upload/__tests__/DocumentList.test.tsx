import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { DocumentList } from "@/pages/upload/components/DocumentList"
import type { Document } from "@/models/document"

const doc = (over: Partial<Document>): Document => ({
  id: "d1",
  collection_id: "m1",
  source_filename: "escaneo.pdf",
  status: "ready",
  error_message: null,
  created_at: "2026-11-13T09:00:00",
  ...over,
})

function setup(documents: Document[], extra = {}) {
  const onRetry = vi.fn()
  render(
    <DocumentList
      documents={documents}
      onDelete={vi.fn()}
      canDelete
      canRetry
      onRetry={onRetry}
      {...extra}
    />
  )
  return { onRetry, user: userEvent.setup() }
}

describe("DocumentList failures", () => {
  it("explains why a file failed, in the stored plain-language reason", () => {
    setup([doc({ status: "failed", error_message: "No text could be found in this file." })])
    expect(screen.getByText("No text could be found in this file.")).toBeInTheDocument()
  })

  it("offers Try again only on failed files, and calls retry with that file", async () => {
    const { onRetry, user } = setup([
      doc({ id: "ok", source_filename: "bien.pdf" }),
      doc({ id: "bad", status: "failed", error_message: "x" }),
    ])
    expect(screen.getAllByRole("button", { name: "Try again" })).toHaveLength(1)
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(onRetry).toHaveBeenCalledWith("bad")
  })

  it("hides Try again from people who can't edit files", () => {
    setup([doc({ status: "failed", error_message: "x" })], { canRetry: false })
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument()
  })

  it("shows no error text for files that are fine", () => {
    setup([doc({ status: "ready" })])
    expect(screen.queryByText(/could/)).not.toBeInTheDocument()
  })
})
