import { unzip, type UnzipFileInfo } from "fflate"
import { baseName, isZip, normalizePath } from "./filters"
import type { PickedFile, Rejected } from "./plan"

// ---- from a file picker ----------------------------------------------------

// Files from <input type="file"> (and, with webkitdirectory, a whole folder).
// For a folder, the browser tells us each file's path inside it.
export function fromFileList(files: FileList | File[]): PickedFile[] {
  return Array.from(files).map((file) => ({
    file,
    path: normalizePath(file.webkitRelativePath || file.name),
  }))
}

// ---- from a drag and drop --------------------------------------------------

// The subset of the (non-standard but universal) File System Entry API we use.
interface FsEntry {
  isFile: boolean
  isDirectory: boolean
  fullPath: string
  name: string
}
interface FsFileEntry extends FsEntry {
  file(success: (file: File) => void, failure: (error: unknown) => void): void
}
interface FsDirectoryEntry extends FsEntry {
  createReader(): { readEntries(success: (entries: FsEntry[]) => void, failure: (e: unknown) => void): void }
}

const readFile = (entry: FsFileEntry) =>
  new Promise<File>((resolve, reject) => entry.file(resolve, reject))

// readEntries returns results in batches (about 100 at a time) until it
// returns an empty one, so keep asking.
async function readDirectory(directory: FsDirectoryEntry): Promise<FsEntry[]> {
  const reader = directory.createReader()
  const all: FsEntry[] = []
  for (;;) {
    const batch = await new Promise<FsEntry[]>((resolve, reject) => reader.readEntries(resolve, reject))
    if (batch.length === 0) return all
    all.push(...batch)
  }
}

async function walk(entry: FsEntry, out: PickedFile[]): Promise<void> {
  if (entry.isFile) {
    const file = await readFile(entry as FsFileEntry)
    out.push({ file, path: normalizePath(entry.fullPath || file.name) })
  } else if (entry.isDirectory) {
    for (const child of await readDirectory(entry as FsDirectoryEntry)) await walk(child, out)
  }
}

// Everything dropped, including folders (read recursively). The entries must
// be taken from the DataTransfer straight away: the browser invalidates it as
// soon as the drop handler yields.
export async function fromDataTransfer(transfer: DataTransfer): Promise<PickedFile[]> {
  const items = Array.from(transfer.items ?? [])
  const entries = items
    .map((item) =>
      item.kind === "file" ? ((item.webkitGetAsEntry?.() ?? null) as unknown as FsEntry | null) : null
    )
    .filter((entry): entry is FsEntry => entry !== null)

  if (entries.length === 0) return fromFileList(Array.from(transfer.files ?? []))

  const out: PickedFile[] = []
  for (const entry of entries) await walk(entry, out)
  return out
}

// ---- zip files -------------------------------------------------------------

// Zips are unpacked here in the browser, so every file inside still goes
// through the one normal upload (same checks, same limits).
export const MAX_ZIP_BYTES = 500 * 1024 * 1024
export const MAX_ZIP_ENTRIES = 5000

export interface ExpandOptions {
  maxFileBytes: number // a file bigger than this is never unpacked
  maxZipBytes?: number
  maxEntries?: number
}

export interface Expanded {
  files: PickedFile[]
  rejected: Rejected[]
  // Zips we could not open (damaged, protected, too big): shown in the review.
  unreadableZips: { path: string; reason: "too_large" | "unreadable" }[]
}

const unzipAsync = (data: Uint8Array, filter: (f: UnzipFileInfo) => boolean) =>
  new Promise<Record<string, Uint8Array>>((resolve, reject) =>
    unzip(data, { filter }, (error, result) => (error ? reject(error) : resolve(result)))
  )

// Replaces every .zip in the list by the files inside it, each under a folder
// named after the zip ("Expediente 482/demanda.pdf") so two zips holding a
// file with the same name don't collide.
export async function expandZips(picked: PickedFile[], options: ExpandOptions): Promise<Expanded> {
  const maxZipBytes = options.maxZipBytes ?? MAX_ZIP_BYTES
  const maxEntries = options.maxEntries ?? MAX_ZIP_ENTRIES
  const result: Expanded = { files: [], rejected: [], unreadableZips: [] }

  for (const entry of picked) {
    if (!isZip(entry.path)) {
      result.files.push(entry)
      continue
    }
    if (entry.file.size > maxZipBytes) {
      result.unreadableZips.push({ path: entry.path, reason: "too_large" })
      continue
    }

    const folder = normalizePath(entry.path).replace(/\.zip$/i, "")
    let count = 0
    const oversized: Rejected[] = []
    try {
      const data = new Uint8Array(await entry.file.arrayBuffer())
      const unpacked = await unzipAsync(data, (info) => {
        if (info.name.endsWith("/")) return false // a folder entry, nothing to read
        if (++count > maxEntries) return false // a zip bomb of tiny files
        if (info.originalSize > options.maxFileBytes) {
          oversized.push({ path: `${folder}/${info.name}`, size: info.originalSize, reason: "too_large" })
          return false // never inflated
        }
        return true
      })
      for (const [name, bytes] of Object.entries(unpacked)) {
        result.files.push({
          path: normalizePath(`${folder}/${name}`),
          file: new File([bytes as BlobPart], baseName(name)),
        })
      }
      result.rejected.push(...oversized)
    } catch {
      result.unreadableZips.push({ path: entry.path, reason: "unreadable" })
    }
  }
  return result
}
