import { useCallback, useRef, useState } from "react"
import { expandZips, type Expanded } from "@/lib/bulk/collect"
import { buildPlan, summarizePlan, type PickedFile, type PlanItem, type Rejected } from "@/lib/bulk/plan"
import { UploadQueue, type QueueItem } from "@/lib/bulk/queue"
import { documentsService } from "@/services/documentsService"

export type BulkPhase = "idle" | "preparing" | "review" | "uploading" | "finished"

const CONCURRENCY = 3

interface Options {
  collectionId: string
  // Names already in the matter, to skip files that are already there.
  existingNames: string[]
  maxBytes?: number
  onFinished?: () => void | Promise<void>
}

// Runs the whole bulk upload: collect what was picked (unpacking zips), plan
// it for review, then upload through a small queue. Every file goes through
// the one normal upload endpoint, so the server's checks apply to each.
export function useBulkUpload({ collectionId, existingNames, maxBytes, onFinished }: Options) {
  const [phase, setPhase] = useState<BulkPhase>("idle")
  const [plan, setPlan] = useState<PlanItem[]>([])
  const [zipProblems, setZipProblems] = useState<Expanded["unreadableZips"]>([])
  const [items, setItems] = useState<QueueItem[]>([])

  const picked = useRef<PickedFile[]>([])
  const rejected = useRef<Rejected[]>([])
  const queue = useRef<UploadQueue | null>(null)
  // Always the latest values, without making callbacks change on every render.
  const latest = useRef({ existingNames, maxBytes, onFinished })
  latest.current = { existingNames, maxBytes, onFinished }

  const addPicked = useCallback(async (more: PickedFile[]) => {
    if (more.length === 0) return
    setPhase("preparing")
    const limit = latest.current.maxBytes ?? Number.MAX_SAFE_INTEGER
    const expanded = await expandZips(more, { maxFileBytes: limit })
    picked.current = [...picked.current, ...expanded.files]
    rejected.current = [...rejected.current, ...expanded.rejected]
    setZipProblems((current) => [...current, ...expanded.unreadableZips])
    setPlan(
      buildPlan(picked.current, {
        existingNames: latest.current.existingNames,
        maxBytes: limit,
        rejected: rejected.current,
      })
    )
    setPhase("review")
  }, [])

  const reset = useCallback(() => {
    picked.current = []
    rejected.current = []
    queue.current = null
    setPlan([])
    setItems([])
    setZipProblems([])
    setPhase("idle")
  }, [])

  const run = useCallback(async (job: () => Promise<void>) => {
    setPhase("uploading")
    await job()
    setPhase("finished")
    await latest.current.onFinished?.()
  }, [])

  const confirm = useCallback(async () => {
    const { upload } = summarizePlan(plan)
    if (upload.length === 0) return
    const q = new UploadQueue(
      upload.map((i) => ({ id: i.id, path: i.path, file: i.file! })),
      async (item, onProgress, signal) => {
        await documentsService.uploadWithProgress(collectionId, item.file, item.path, onProgress, signal)
      },
      { concurrency: CONCURRENCY, onChange: setItems }
    )
    queue.current = q
    setItems(q.snapshot())
    await run(() => q.start())
  }, [collectionId, plan, run])

  const stop = useCallback(() => queue.current?.cancel(), [])

  const retryFailed = useCallback(async () => {
    const q = queue.current
    if (q) await run(() => q.retry())
  }, [run])

  return { phase, plan, zipProblems, items, addPicked, confirm, stop, retryFailed, reset }
}
