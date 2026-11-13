import { isSupported, isSystemFile, normalizePath } from "./filters"

// One thing the person picked, with the folders it came from kept in `path`
// (for example "contratos/2024/arrendamiento.pdf").
export interface PickedFile {
  file: File
  path: string
}

// Something that was left out before the review (e.g. a file inside a zip that
// is over the size limit, which is never unpacked).
export interface Rejected {
  path: string
  size: number
  reason: "too_large"
}

export type SkipReason =
  | "system"
  | "unsupported"
  | "empty"
  | "too_large"
  | "duplicate_in_batch"
  | "duplicate_existing"

export interface PlanItem {
  id: string
  path: string
  size: number
  file?: File // absent for items that were never unpacked
  skip?: SkipReason
}

export interface PlanOptions {
  // Names already in the matter (they include folders, like the new paths).
  existingNames: Iterable<string>
  maxBytes: number
  rejected?: Rejected[]
}

const key = (path: string) => normalizePath(path).toLowerCase()

// Decides what will be uploaded and what is skipped, and why. Order is kept so
// the review reads the way the files were picked.
export function buildPlan(picked: PickedFile[], options: PlanOptions): PlanItem[] {
  const existing = new Set([...options.existingNames].map(key))
  const seen = new Set<string>()
  const items: PlanItem[] = []

  picked.forEach((entry, index) => {
    const path = normalizePath(entry.path)
    const item: PlanItem = { id: `${index}:${path}`, path, size: entry.file.size, file: entry.file }

    if (isSystemFile(path)) item.skip = "system"
    else if (!isSupported(path)) item.skip = "unsupported"
    else if (entry.file.size === 0) item.skip = "empty"
    else if (entry.file.size > options.maxBytes) item.skip = "too_large"
    else if (seen.has(key(path))) item.skip = "duplicate_in_batch"
    else if (existing.has(key(path))) item.skip = "duplicate_existing"

    // Only files that will really be uploaded count as "seen", so a skipped
    // copy never hides the one that is kept.
    if (!item.skip) seen.add(key(path))
    items.push(item)
  })

  options.rejected?.forEach((r, i) => {
    const path = normalizePath(r.path)
    const system = isSystemFile(path)
    if (system) return // clutter inside a zip is not worth mentioning
    items.push({ id: `rejected:${i}:${path}`, path, size: r.size, skip: r.reason })
  })

  return items
}

export interface PlanSummary {
  upload: PlanItem[]
  skipped: PlanItem[]
  bySkipReason: Partial<Record<SkipReason, PlanItem[]>>
  uploadBytes: number
}

export function summarizePlan(plan: PlanItem[]): PlanSummary {
  const upload = plan.filter((i) => !i.skip && i.file)
  const skipped = plan.filter((i) => i.skip)
  const bySkipReason: PlanSummary["bySkipReason"] = {}
  for (const item of skipped) (bySkipReason[item.skip!] ??= []).push(item)
  return { upload, skipped, bySkipReason, uploadBytes: upload.reduce((sum, i) => sum + i.size, 0) }
}
