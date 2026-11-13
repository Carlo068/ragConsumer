import { useCallback, useEffect, useState } from "react"
import { adminService } from "@/services/adminService"
import type { AuditEntry, AuditFilters } from "@/models/audit"
import { useI18n } from "@/i18n/useI18n"

export const AUDIT_PAGE_SIZE = 25

export function useAuditLog() {
  const { errorText } = useI18n()
  const [filters, setFilters] = useState<AuditFilters>({})
  const [offset, setOffset] = useState(0)
  const [items, setItems] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const page = await adminService.listAudit(filters, AUDIT_PAGE_SIZE, offset)
      setItems(page.items)
      setTotal(page.total)
      setError(null)
    } catch (err) {
      setError(errorText(err, "audit.loadFailed"))
    } finally {
      setLoading(false)
    }
  }, [filters, offset, errorText])

  useEffect(() => {
    load()
  }, [load])

  function applyFilters(next: AuditFilters) {
    setOffset(0)
    setFilters(next)
  }

  return {
    items,
    total,
    loading,
    error,
    filters,
    offset,
    applyFilters,
    nextPage: () => setOffset((o) => o + AUDIT_PAGE_SIZE),
    previousPage: () => setOffset((o) => Math.max(0, o - AUDIT_PAGE_SIZE)),
    hasNext: offset + AUDIT_PAGE_SIZE < total,
    hasPrevious: offset > 0,
    csvUrl: adminService.auditCsvUrl(filters),
  }
}
