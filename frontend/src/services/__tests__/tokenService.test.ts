import { describe, expect, it, vi } from "vitest"
import { apiClient } from "@/services/apiClient"
import { tokenService } from "@/services/tokenService"

vi.mock("@/services/apiClient", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

describe("tokenService", () => {
  it("create() POSTs the name to /tokens", async () => {
    await tokenService.create({ name: "Laptop" })
    expect(apiClient.post).toHaveBeenCalledWith("/tokens", { name: "Laptop" })
  })

  it("revoke() DELETEs /tokens/{id}", async () => {
    await tokenService.revoke("tok-1")
    expect(apiClient.delete).toHaveBeenCalledWith("/tokens/tok-1")
  })
})
