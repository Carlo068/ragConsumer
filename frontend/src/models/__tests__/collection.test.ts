import { describe, expect, it } from "vitest"
import { canEditFiles, canManageCollection } from "@/models/collection"

describe("role helpers", () => {
  it("only editors and owners can change files", () => {
    expect(canEditFiles("owner")).toBe(true)
    expect(canEditFiles("editor")).toBe(true)
    expect(canEditFiles("viewer")).toBe(false)
  })

  it("only owners can rename or delete the collection", () => {
    expect(canManageCollection("owner")).toBe(true)
    expect(canManageCollection("editor")).toBe(false)
    expect(canManageCollection("viewer")).toBe(false)
  })

  it("offers nothing while the role is still unknown (collection not loaded yet)", () => {
    expect(canEditFiles(undefined)).toBe(false)
    expect(canManageCollection(undefined)).toBe(false)
  })
})
