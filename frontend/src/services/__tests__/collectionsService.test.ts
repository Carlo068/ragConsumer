import { describe, expect, it, vi } from "vitest"
import { apiClient } from "@/services/apiClient"
import { collectionsService } from "@/services/collectionsService"

vi.mock("@/services/apiClient", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe("collectionsService", () => {
  it("list() GETs /collections", async () => {
    await collectionsService.list()
    expect(apiClient.get).toHaveBeenCalledWith("/collections")
  })

  it("create() POSTs the name to /collections", async () => {
    await collectionsService.create({ name: "Doe Estate" })
    expect(apiClient.post).toHaveBeenCalledWith("/collections", { name: "Doe Estate" })
  })

  it("rename() PATCHes /collections/{id} with the new name", async () => {
    await collectionsService.rename("abc-123", { name: "Renamed" })
    expect(apiClient.patch).toHaveBeenCalledWith("/collections/abc-123", { name: "Renamed" })
  })

  it("remove() DELETEs /collections/{id}", async () => {
    await collectionsService.remove("abc-123")
    expect(apiClient.delete).toHaveBeenCalledWith("/collections/abc-123")
  })

  it("setAiAccess(true) PUTs /collections/{id}/ai-access", async () => {
    await collectionsService.setAiAccess("abc-123", true)
    expect(apiClient.put).toHaveBeenCalledWith("/collections/abc-123/ai-access")
  })

  it("setAiAccess(false) DELETEs /collections/{id}/ai-access", async () => {
    await collectionsService.setAiAccess("abc-123", false)
    expect(apiClient.delete).toHaveBeenCalledWith("/collections/abc-123/ai-access")
  })
})
