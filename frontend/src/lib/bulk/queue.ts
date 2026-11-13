export type ItemState = "queued" | "uploading" | "done" | "failed" | "cancelled"

export interface QueueItem {
  id: string
  path: string
  file: File
  state: ItemState
  progress: number // 0..1 for this file
  error?: unknown
}

export type Uploader = (
  item: QueueItem,
  onProgress: (fraction: number) => void,
  signal: AbortSignal
) => Promise<void>

export interface QueueOptions {
  concurrency?: number
  onChange?: (items: QueueItem[]) => void
}

// Uploads a batch a few files at a time. One failure never stops the rest, a
// cancel stops what is running and what has not started, and failed or
// cancelled files can be retried without redoing the ones that finished.
export class UploadQueue {
  private items: QueueItem[]
  private readonly concurrency: number
  private readonly onChange?: (items: QueueItem[]) => void
  private readonly upload: Uploader
  private controller = new AbortController()

  constructor(
    files: { id: string; path: string; file: File }[],
    upload: Uploader,
    options: QueueOptions = {}
  ) {
    this.upload = upload
    this.items = files.map((f) => ({ ...f, state: "queued" as const, progress: 0 }))
    this.concurrency = options.concurrency ?? 3
    this.onChange = options.onChange
  }

  snapshot(): QueueItem[] {
    return this.items.map((item) => ({ ...item }))
  }

  private emit() {
    this.onChange?.(this.snapshot())
  }

  private update(id: string, patch: Partial<QueueItem>) {
    this.items = this.items.map((item) => (item.id === id ? { ...item, ...patch } : item))
    this.emit()
  }

  // Resolves when nothing is queued or running any more.
  async start(): Promise<void> {
    this.controller = new AbortController()
    const signal = this.controller.signal
    const worker = async () => {
      for (;;) {
        if (signal.aborted) return
        const next = this.items.find((i) => i.state === "queued")
        if (!next) return
        this.update(next.id, { state: "uploading", progress: 0, error: undefined })
        try {
          await this.upload(
            this.items.find((i) => i.id === next.id)!,
            (fraction) => this.update(next.id, { progress: Math.min(1, Math.max(0, fraction)) }),
            signal
          )
          this.update(next.id, { state: "done", progress: 1 })
        } catch (error) {
          if (signal.aborted) this.update(next.id, { state: "cancelled", progress: 0 })
          else this.update(next.id, { state: "failed", error })
        }
      }
    }
    await Promise.all(Array.from({ length: this.concurrency }, worker))
    // Anything never started because of a cancel is marked as such.
    if (signal.aborted) {
      this.items = this.items.map((i) => (i.state === "queued" ? { ...i, state: "cancelled" } : i))
      this.emit()
    }
  }

  cancel() {
    this.controller.abort()
  }

  // Puts failed and cancelled files back in line and runs again.
  retry(): Promise<void> {
    this.items = this.items.map((i) =>
      i.state === "failed" || i.state === "cancelled"
        ? { ...i, state: "queued", progress: 0, error: undefined }
        : i
    )
    this.emit()
    return this.start()
  }
}

export interface QueueTotals {
  total: number
  done: number
  failed: number
  cancelled: number
  active: number // queued or uploading
  fraction: number // overall progress 0..1, by bytes
}

export function totals(items: QueueItem[]): QueueTotals {
  const count = (state: ItemState) => items.filter((i) => i.state === state).length
  const bytes = items.reduce((sum, i) => sum + i.file.size, 0)
  const sent = items.reduce(
    (sum, i) => sum + i.file.size * (i.state === "done" ? 1 : i.state === "uploading" ? i.progress : 0),
    0
  )
  return {
    total: items.length,
    done: count("done"),
    failed: count("failed"),
    cancelled: count("cancelled"),
    active: count("queued") + count("uploading"),
    fraction: bytes === 0 ? 0 : sent / bytes,
  }
}
