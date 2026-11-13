import { describe, expect, it, vi } from "vitest"
import { apiClient } from "@/services/apiClient"
import { adminService } from "@/services/adminService"
import { inviteService } from "@/services/inviteService"

vi.mock("@/services/apiClient", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

describe("adminService", () => {
  it("createInvite() POSTs the email to /admin/invites", async () => {
    await adminService.createInvite({ email: "ana@firm.mx" })
    expect(apiClient.post).toHaveBeenCalledWith("/admin/invites", { email: "ana@firm.mx" })
  })

  it("revokeInvite() DELETEs /admin/invites/{id}", async () => {
    await adminService.revokeInvite("inv-1")
    expect(apiClient.delete).toHaveBeenCalledWith("/admin/invites/inv-1")
  })
})

describe("inviteService", () => {
  it("URL-encodes the token so a malformed link can't change the request path", async () => {
    await inviteService.get("abc/../admin")
    expect(apiClient.get).toHaveBeenCalledWith("/invites/abc%2F..%2Fadmin")
  })

  it("accept() POSTs the password to /invites/{token}/accept", async () => {
    await inviteService.accept("tok", { password: "a-long-passphrase" })
    expect(apiClient.post).toHaveBeenCalledWith("/invites/tok/accept", {
      password: "a-long-passphrase",
    })
  })
})

describe("adminService audit", () => {
  it("listAudit() sends filters and paging", async () => {
    await adminService.listAudit({ action: "login_failed", actor: "ana" }, 25, 50)
    expect(apiClient.get).toHaveBeenCalledWith(
      "/admin/audit?limit=25&offset=50&action=login_failed&actor=ana"
    )
  })

  it("auditCsvUrl() carries the same filters and no paging", () => {
    expect(adminService.auditCsvUrl({ action: "mcp_search" })).toMatch(
      /\/admin\/audit\.csv\?action=mcp_search$/
    )
    expect(adminService.auditCsvUrl({})).toMatch(/\/admin\/audit\.csv$/)
  })
})
