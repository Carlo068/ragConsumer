// What the system accepts, and what is just clutter that comes along with a
// folder or a zip (macOS and Windows system files, Office temp files).

export const SUPPORTED_EXTENSIONS = ["pdf", "docx", "doc", "eml", "msg", "txt", "md"] as const

// For the file picker: the formats we read, plus .zip (unpacked in the browser).
export const PICKER_ACCEPT = [...SUPPORTED_EXTENSIONS, "zip"].map((e) => `.${e}`).join(",")

export function normalizePath(path: string): string {
  return path
    .replace(/\\/g, "/")
    .split("/")
    .filter((segment) => segment !== "" && segment !== ".")
    .join("/")
}

export function baseName(path: string): string {
  const normalized = normalizePath(path)
  return normalized.slice(normalized.lastIndexOf("/") + 1)
}

export function extensionOf(path: string): string {
  const name = baseName(path)
  const dot = name.lastIndexOf(".")
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ""
}

export function isZip(path: string): boolean {
  return extensionOf(path) === "zip"
}

export function isSupported(path: string): boolean {
  return (SUPPORTED_EXTENSIONS as readonly string[]).includes(extensionOf(path))
}

const SYSTEM_NAMES = new Set([".ds_store", "thumbs.db", "desktop.ini", "ehthumbs.db"])

// Files nobody meant to upload: macOS resource folders and AppleDouble files,
// .DS_Store, Thumbs.db, Office lock files (~$...), and anything hidden.
export function isSystemFile(path: string): boolean {
  const segments = normalizePath(path).split("/")
  const name = segments[segments.length - 1] ?? ""
  if (segments.some((s) => s === "__MACOSX")) return true
  if (SYSTEM_NAMES.has(name.toLowerCase())) return true
  if (name.startsWith("~$") || name.startsWith("._")) return true
  return segments.some((s) => s.startsWith("."))
}
