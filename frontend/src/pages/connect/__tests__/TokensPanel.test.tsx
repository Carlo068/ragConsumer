import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { TokensPanel } from "@/pages/connect/components/TokensPanel"
import type { ApiToken, ApiTokenCreated } from "@/models/token"

const token: ApiToken = {
  id: "t1",
  name: "Claude on my laptop",
  prefix: "rag_AbCd",
  created_at: "2026-11-01T10:00:00",
  expires_at: "2027-01-30T10:00:00",
  last_used_at: null,
}

function setup(tokens: ApiToken[] = []) {
  const created: ApiTokenCreated = { ...token, id: "t2", name: "Phone", token: "rag_SECRET_VALUE" }
  const onCreate = vi.fn().mockResolvedValue(created)
  const onRevoke = vi.fn().mockResolvedValue(undefined)
  const onCreated = vi.fn()
  render(
    <TokensPanel tokens={tokens} onCreate={onCreate} onRevoke={onRevoke} onCreated={onCreated} />
  )
  return { onCreate, onRevoke, onCreated, user: userEvent.setup() }
}

describe("TokensPanel", () => {
  it("lists keys by name and prefix, never a full secret", () => {
    setup([token])
    expect(screen.getByText("Claude on my laptop")).toBeInTheDocument()
    expect(screen.getByText("(rag_AbCd…)")).toBeInTheDocument()
    expect(screen.getByText(/Never used/)).toBeInTheDocument()
  })

  it("shows the new key once after creating it and reports it to the page", async () => {
    const { onCreate, onCreated, user } = setup()
    await user.type(screen.getByLabelText(/Name/), "Phone")
    await user.click(screen.getByRole("button", { name: "Create access key" }))

    expect(onCreate).toHaveBeenCalledWith("Phone")
    expect(await screen.findByText("rag_SECRET_VALUE")).toBeInTheDocument()
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ token: "rag_SECRET_VALUE" }))
  })

  it("cannot submit without a name", () => {
    setup()
    expect(screen.getByRole("button", { name: "Create access key" })).toBeDisabled()
  })

  it("revokes only after confirming", async () => {
    const { onRevoke, user } = setup([token])
    await user.click(screen.getByRole("button", { name: "Revoke" }))
    expect(onRevoke).not.toHaveBeenCalled()
    await user.click(screen.getAllByRole("button", { name: "Revoke" }).at(-1)!)
    expect(onRevoke).toHaveBeenCalledWith("t1")
  })
})

describe("TokensPanel empty state", () => {
  it("tells you what to do when you have no access keys yet", () => {
    render(
      <TokensPanel tokens={[]} onCreate={vi.fn()} onRevoke={vi.fn()} />
    )
    expect(screen.getByText(/Create one above to connect your AI assistant/)).toBeInTheDocument()
  })
})
