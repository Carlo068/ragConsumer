import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { collectionsService } from "@/services/collectionsService"
import { useCollections } from "@/hooks/useCollections"

vi.mock("@/services/collectionsService", () => ({
  collectionsService: {
    list: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
  },
}))

const mockedService = vi.mocked(collectionsService)

beforeEach(() => {
  vi.clearAllMocks()
  mockedService.list.mockResolvedValue([{ id: "1", name: "Doe Estate" }])
})

describe("useCollections", () => {
  it("loads collections on mount", async () => {
    const { result } = renderHook(() => useCollections())

    expect(result.current.loading).toBe(true)

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.collections).toEqual([{ id: "1", name: "Doe Estate" }])
    expect(result.current.error).toBeNull()
  })

  it("surfaces a load failure as an error instead of throwing", async () => {
    mockedService.list.mockRejectedValue(new Error("network down"))

    const { result } = renderHook(() => useCollections())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.error).toBe("network down")
  })

  it("createCollection() creates then refreshes the list", async () => {
    const { result } = renderHook(() => useCollections())
    await waitFor(() => expect(result.current.loading).toBe(false))

    mockedService.list.mockResolvedValue([
      { id: "1", name: "Doe Estate" },
      { id: "2", name: "New One" },
    ])

    await act(async () => {
      await result.current.createCollection("New One")
    })

    expect(mockedService.create).toHaveBeenCalledWith({ name: "New One" })
    expect(result.current.collections).toHaveLength(2)
  })

  it("deleteCollection() removes then refreshes the list", async () => {
    const { result } = renderHook(() => useCollections())
    await waitFor(() => expect(result.current.loading).toBe(false))

    mockedService.list.mockResolvedValue([])

    await act(async () => {
      await result.current.deleteCollection("1")
    })

    expect(mockedService.remove).toHaveBeenCalledWith("1")
    expect(result.current.collections).toEqual([])
  })
})
