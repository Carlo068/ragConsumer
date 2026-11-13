import { zipSync } from "fflate"
import { describe, expect, it } from "vitest"
import { expandZips, fromDataTransfer, fromFileList } from "@/lib/bulk/collect"
import { isSupported, isSystemFile, normalizePath } from "@/lib/bulk/filters"
import { buildPlan, summarizePlan, type PickedFile } from "@/lib/bulk/plan"
import { UploadQueue, totals, type QueueItem } from "@/lib/bulk/queue"

const MB = 1024 * 1024
const file = (name: string, size = 10) => {
  const f = new File(["x"], name)
  Object.defineProperty(f, "size", { value: size })
  return f
}
const picked = (path: string, size = 10): PickedFile => ({ file: file(path.split("/").pop()!, size), path })

describe("filters", () => {
  it.each(["a.pdf", "A.PDF", "x/y/z.docx", "carta.doc", "correo.eml", "correo.msg", "notas.txt", "notas.md"])(
    "accepts %s",
    (name) => expect(isSupported(name)).toBe(true)
  )

  it.each(["foto.jpg", "hoja.xlsx", "programa.exe", "sin-extension", "archivo.zip"])(
    "does not accept %s as a document",
    (name) => expect(isSupported(name)).toBe(false)
  )

  it.each([
    "__MACOSX/expediente/._demanda.pdf",
    "expediente/.DS_Store",
    "expediente/Thumbs.db",
    "expediente/desktop.ini",
    "expediente/~$demanda.docx",
    "expediente/._demanda.pdf",
    ".git/config",
    "expediente/.oculto.pdf",
  ])("recognises %s as a system or hidden file", (path) => expect(isSystemFile(path)).toBe(true))

  it("does not mistake a real file for a system file", () => {
    expect(isSystemFile("contratos/2024/arrendamiento.pdf")).toBe(false)
    expect(isSystemFile("tilde~en~medio.docx")).toBe(false)
  })

  it("normalizes paths: backslashes, doubled and leading slashes, dots", () => {
    expect(normalizePath("/a//b\\c/./d.pdf")).toBe("a/b/c/d.pdf")
  })
})

describe("review plan", () => {
  const options = { existingNames: [] as string[], maxBytes: 50 * MB }

  it("uploads supported files and keeps their folder path", () => {
    const plan = buildPlan([picked("contratos/2024/arrendamiento.pdf")], options)
    expect(plan[0].skip).toBeUndefined()
    expect(plan[0].path).toBe("contratos/2024/arrendamiento.pdf")
  })

  it("skips system files, unsupported types and empty files, each with its reason", () => {
    const plan = buildPlan(
      [picked(".DS_Store"), picked("foto.jpg"), picked("vacio.pdf", 0), picked("bien.pdf")],
      options
    )
    expect(plan.map((i) => i.skip)).toEqual(["system", "unsupported", "empty", undefined])
  })

  it("skips files over the size limit", () => {
    const plan = buildPlan([picked("enorme.pdf", 60 * MB)], options)
    expect(plan[0].skip).toBe("too_large")
  })

  it("skips a duplicate within the batch, keeping the first, ignoring case and slash style", () => {
    const plan = buildPlan([picked("A/Demanda.pdf"), picked("a/demanda.PDF"), picked("a\\demanda.pdf")], options)
    expect(plan.map((i) => i.skip)).toEqual([undefined, "duplicate_in_batch", "duplicate_in_batch"])
  })

  it("keeps same-named files from different folders", () => {
    const plan = buildPlan([picked("2023/acta.pdf"), picked("2024/acta.pdf")], options)
    expect(plan.map((i) => i.skip)).toEqual([undefined, undefined])
  })

  it("skips files already in the matter", () => {
    const plan = buildPlan([picked("contratos/a.pdf"), picked("b.pdf")], {
      ...options,
      existingNames: ["Contratos/A.pdf"],
    })
    expect(plan.map((i) => i.skip)).toEqual(["duplicate_existing", undefined])
  })

  it("a skipped copy never hides the one that is kept", () => {
    const plan = buildPlan([picked("a.pdf", 0), picked("a.pdf")], options)
    expect(plan.map((i) => i.skip)).toEqual(["empty", undefined])
  })

  it("lists files left out of a zip for being too large, but not zip clutter", () => {
    const plan = buildPlan([], {
      ...options,
      rejected: [
        { path: "caso/grande.pdf", size: 90 * MB, reason: "too_large" },
        { path: "__MACOSX/caso/._grande.pdf", size: 90 * MB, reason: "too_large" },
      ],
    })
    expect(plan).toHaveLength(1)
    expect(plan[0]).toMatchObject({ path: "caso/grande.pdf", skip: "too_large" })
  })

  it("summarizes what will be uploaded and what is skipped, by reason", () => {
    const summary = summarizePlan(
      buildPlan([picked("a.pdf", 5), picked("b.pdf", 7), picked("c.jpg"), picked("d.jpg"), picked(".DS_Store")], options)
    )
    expect(summary.upload.map((i) => i.path)).toEqual(["a.pdf", "b.pdf"])
    expect(summary.uploadBytes).toBe(12)
    expect(summary.bySkipReason.unsupported).toHaveLength(2)
    expect(summary.bySkipReason.system).toHaveLength(1)
  })
})

describe("collecting files", () => {
  it("uses the folder path the browser reports for a chosen folder", () => {
    const f = new File(["x"], "a.pdf")
    Object.defineProperty(f, "webkitRelativePath", { value: "expediente/pruebas/a.pdf" })
    expect(fromFileList([f])[0].path).toBe("expediente/pruebas/a.pdf")
  })

  it("uses just the name for loose files", () => {
    expect(fromFileList([new File(["x"], "suelto.pdf")])[0].path).toBe("suelto.pdf")
  })

  // A tiny fake of the browser's File System Entry API.
  const fileEntry = (fullPath: string) => ({
    isFile: true,
    isDirectory: false,
    fullPath,
    name: fullPath.split("/").pop()!,
    file: (ok: (f: File) => void) => ok(new File(["x"], fullPath.split("/").pop()!)),
  })
  const dirEntry = (fullPath: string, children: unknown[], batch = 2) => ({
    isFile: false,
    isDirectory: true,
    fullPath,
    name: fullPath.split("/").pop()!,
    createReader: () => {
      let offset = 0
      return {
        readEntries: (ok: (e: unknown[]) => void) => {
          ok(children.slice(offset, offset + batch)) // returns in batches, then []
          offset += batch
        },
      }
    },
  })
  const transferOf = (...entries: unknown[]) =>
    ({
      files: [],
      items: entries.map((entry) => ({ kind: "file", webkitGetAsEntry: () => entry })),
    }) as unknown as DataTransfer

  it("reads a dropped folder recursively, including more files than one read returns", async () => {
    const tree = dirEntry("/expediente", [
      fileEntry("/expediente/a.pdf"),
      dirEntry("/expediente/2024", [fileEntry("/expediente/2024/b.pdf"), fileEntry("/expediente/2024/c.docx")]),
      fileEntry("/expediente/d.txt"),
      fileEntry("/expediente/e.txt"),
    ])
    const out = await fromDataTransfer(transferOf(tree))
    expect(out.map((p) => p.path).sort()).toEqual([
      "expediente/2024/b.pdf",
      "expediente/2024/c.docx",
      "expediente/a.pdf",
      "expediente/d.txt",
      "expediente/e.txt",
    ])
  })

  it("accepts loose files and folders dropped together", async () => {
    const out = await fromDataTransfer(
      transferOf(fileEntry("/suelto.pdf"), dirEntry("/carpeta", [fileEntry("/carpeta/x.pdf")]))
    )
    expect(out.map((p) => p.path).sort()).toEqual(["carpeta/x.pdf", "suelto.pdf"])
  })

  it("falls back to the plain file list when the browser gives no entries", async () => {
    const transfer = { items: [], files: [new File(["x"], "a.pdf")] } as unknown as DataTransfer
    expect((await fromDataTransfer(transfer)).map((p) => p.path)).toEqual(["a.pdf"])
  })
})

describe("zip files", () => {
  const bytes = (n: number) => new Uint8Array(n).fill(65)
  const zipFile = (name: string, entries: Record<string, Uint8Array>) =>
    new File([zipSync(entries) as BlobPart], name)
  const opts = { maxFileBytes: 1000 }

  it("unpacks a zip under a folder named after it, keeping its own folders", async () => {
    const zip = zipFile("Expediente 482.zip", {
      "demanda.pdf": bytes(10),
      "pruebas/contrato.docx": bytes(20),
    })
    const out = await expandZips([{ file: zip, path: "Expediente 482.zip" }], opts)
    expect(out.files.map((p) => p.path).sort()).toEqual([
      "Expediente 482/demanda.pdf",
      "Expediente 482/pruebas/contrato.docx",
    ])
    expect(out.files[0].file.size).toBeGreaterThan(0)
  })

  it("keeps same-named files from two zips apart", async () => {
    const a = zipFile("a.zip", { "acta.pdf": bytes(5) })
    const b = zipFile("b.zip", { "acta.pdf": bytes(5) })
    const out = await expandZips(
      [
        { file: a, path: "a.zip" },
        { file: b, path: "b.zip" },
      ],
      opts
    )
    expect(out.files.map((p) => p.path).sort()).toEqual(["a/acta.pdf", "b/acta.pdf"])
  })

  it("passes non-zip files through untouched", async () => {
    const plain = { file: new File(["x"], "a.pdf"), path: "a.pdf" }
    expect((await expandZips([plain], opts)).files).toEqual([plain])
  })

  it("never unpacks a file over the size limit, and reports it", async () => {
    const zip = zipFile("caso.zip", { "pequeno.pdf": bytes(10), "grande.pdf": bytes(5000) })
    const out = await expandZips([{ file: zip, path: "caso.zip" }], opts)
    expect(out.files.map((p) => p.path)).toEqual(["caso/pequeno.pdf"])
    expect(out.rejected).toEqual([{ path: "caso/grande.pdf", size: 5000, reason: "too_large" }])
  })

  it("stops at a maximum number of entries (a zip of countless tiny files)", async () => {
    const many: Record<string, Uint8Array> = {}
    for (let i = 0; i < 20; i++) many[`f${i}.txt`] = bytes(3)
    const out = await expandZips([{ file: zipFile("muchos.zip", many), path: "muchos.zip" }], {
      ...opts,
      maxEntries: 5,
    })
    expect(out.files).toHaveLength(5)
  })

  it("refuses a zip over the size cap without opening it", async () => {
    const zip = zipFile("enorme.zip", { "a.pdf": bytes(5) })
    const out = await expandZips([{ file: zip, path: "enorme.zip" }], { ...opts, maxZipBytes: 10 })
    expect(out.files).toEqual([])
    expect(out.unreadableZips).toEqual([{ path: "enorme.zip", reason: "too_large" }])
  })

  it("reports a damaged zip instead of failing the whole batch", async () => {
    const broken = new File([new Uint8Array([1, 2, 3, 4, 5])], "roto.zip")
    const good = { file: new File(["x"], "bien.pdf"), path: "bien.pdf" }
    const out = await expandZips([{ file: broken, path: "roto.zip" }, good], opts)
    expect(out.unreadableZips).toEqual([{ path: "roto.zip", reason: "unreadable" }])
    expect(out.files).toEqual([good])
  })
})

describe("upload queue", () => {
  const batch = (n: number) =>
    Array.from({ length: n }, (_, i) => ({ id: `f${i}`, path: `f${i}.pdf`, file: file(`f${i}.pdf`, 100) }))
  const tick = () => new Promise((r) => setTimeout(r, 0))

  it("uploads everything, never more than the concurrency limit at once", async () => {
    let running = 0
    let peak = 0
    const queue = new UploadQueue(
      batch(8),
      async () => {
        running++
        peak = Math.max(peak, running)
        await tick()
        running--
      },
      { concurrency: 3 }
    )
    await queue.start()
    expect(peak).toBe(3)
    expect(queue.snapshot().every((i) => i.state === "done")).toBe(true)
  })

  it("one failure does not stop the others, and keeps its error", async () => {
    const boom = new Error("boom")
    const queue = new UploadQueue(batch(4), async (item) => {
      if (item.id === "f1") throw boom
    })
    await queue.start()
    const states = queue.snapshot().map((i) => i.state)
    expect(states).toEqual(["done", "failed", "done", "done"])
    expect(queue.snapshot()[1].error).toBe(boom)
  })

  it("reports progress per file and overall", async () => {
    const seen: number[] = []
    const queue = new UploadQueue(
      batch(2),
      async (_item, onProgress) => {
        onProgress(0.5)
        onProgress(1)
      },
      { concurrency: 1, onChange: (items) => seen.push(totals(items).fraction) }
    )
    await queue.start()
    expect(Math.max(...seen)).toBe(1)
    expect(seen.some((f) => f > 0 && f < 1)).toBe(true)
  })

  it("cancel stops running and waiting files, which can then be retried", async () => {
    let release: () => void = () => {}
    const gate = new Promise<void>((r) => (release = r))
    const attempts: string[] = []
    const queue = new UploadQueue(
      batch(5),
      async (item, _p, signal) => {
        attempts.push(item.id)
        await Promise.race([
          gate,
          new Promise((_, reject) => signal.addEventListener("abort", () => reject(new Error("aborted")))),
        ])
      },
      { concurrency: 2 }
    )
    const running = queue.start()
    await tick()
    queue.cancel()
    await running
    expect(queue.snapshot().map((i) => i.state)).toEqual(Array(5).fill("cancelled"))
    expect(attempts).toHaveLength(2) // only the two that had started

    release()
    await queue.retry()
    expect(queue.snapshot().every((i) => i.state === "done")).toBe(true)
  })

  it("retry redoes only the failed files, not the ones that finished", async () => {
    const calls: Record<string, number> = {}
    let failOnce = true
    const queue = new UploadQueue(batch(3), async (item) => {
      calls[item.id] = (calls[item.id] ?? 0) + 1
      if (item.id === "f1" && failOnce) {
        failOnce = false
        throw new Error("transient")
      }
    })
    await queue.start()
    await queue.retry()
    expect(calls).toEqual({ f0: 1, f1: 2, f2: 1 })
    expect(queue.snapshot().every((i) => i.state === "done")).toBe(true)
  })

  it("totals count each state and weigh progress by file size", () => {
    const items: QueueItem[] = [
      { id: "a", path: "a", file: file("a", 100), state: "done", progress: 1 },
      { id: "b", path: "b", file: file("b", 100), state: "uploading", progress: 0.5 },
      { id: "c", path: "c", file: file("c", 200), state: "failed", progress: 0 },
      { id: "d", path: "d", file: file("d", 100), state: "queued", progress: 0 },
    ]
    expect(totals(items)).toMatchObject({ total: 4, done: 1, failed: 1, active: 2 })
    expect(totals(items).fraction).toBeCloseTo(150 / 500)
  })
})
