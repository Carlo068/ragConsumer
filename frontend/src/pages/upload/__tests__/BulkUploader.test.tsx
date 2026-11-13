import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { zipSync } from "fflate"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { I18nProvider } from "@/i18n/I18nProvider"
import { BulkUploader } from "@/pages/upload/components/BulkUploader"
import { ApiError } from "@/services/apiClient"
import { documentsService } from "@/services/documentsService"

vi.mock("@/services/documentsService", () => ({
  documentsService: { uploadWithProgress: vi.fn() },
}))

const upload = vi.mocked(documentsService.uploadWithProgress)
const MB = 1024 * 1024

function pdf(name: string, size = 100) {
  const f = new File(["x"], name, { type: "application/pdf" })
  Object.defineProperty(f, "size", { value: size })
  return f
}

function renderUploader(over: { existingNames?: string[]; locale?: "es" | "en" } = {}) {
  const onFinished = vi.fn()
  render(
    <I18nProvider locale={over.locale ?? "en"}>
      <BulkUploader
        collectionId="m1"
        existingNames={over.existingNames ?? []}
        maxUploadBytes={50 * MB}
        onFinished={onFinished}
      />
    </I18nProvider>
  )
  // A drop bypasses the picker's accept list, so the test user must too.
  return { onFinished, user: userEvent.setup({ applyAccept: false }) }
}

beforeEach(() => {
  upload.mockReset()
  upload.mockImplementation(async (_c, _f, _p, onProgress) => {
    onProgress(1)
    return {} as never
  })
})

describe("BulkUploader", () => {
  it("offers files, a folder, and tells people what is accepted", () => {
    renderUploader()
    expect(screen.getByText("Drag files, folders or a .zip here")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Choose files" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Choose folder" })).toBeInTheDocument()
    expect(screen.getByText(/Up to 50 MB each/)).toBeInTheDocument()
  })

  it("lets a person review the files, then uploads each under its own name", async () => {
    const { user, onFinished } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf("demanda.pdf"), pdf("contrato.pdf")])

    expect(await screen.findByText("Review before uploading")).toBeInTheDocument()
    expect(screen.getByText(/2 files will be uploaded/)).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled() // nothing is sent before they confirm

    await user.click(screen.getByRole("button", { name: "Upload 2 files" }))

    expect(await screen.findByText("Upload finished")).toBeInTheDocument()
    expect(upload.mock.calls.map((c) => c[2]).sort()).toEqual(["contrato.pdf", "demanda.pdf"])
    expect(upload.mock.calls.every((c) => c[0] === "m1")).toBe(true)
    expect(screen.getByText(/2 files uploaded/)).toBeInTheDocument()
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it("keeps the folder path of a chosen folder in each file's name", async () => {
    const { user } = renderUploader()
    const a = pdf("arrendamiento.pdf")
    Object.defineProperty(a, "webkitRelativePath", { value: "contratos/2024/arrendamiento.pdf" })
    const b = pdf("acta.pdf")
    Object.defineProperty(b, "webkitRelativePath", { value: "contratos/acta.pdf" })
    await user.upload(screen.getByTestId("folder-input"), [a, b])
    await user.click(await screen.findByRole("button", { name: "Upload 2 files" }))
    await screen.findByText("Upload finished")
    expect(upload.mock.calls.map((c) => c[2]).sort()).toEqual([
      "contratos/2024/arrendamiento.pdf",
      "contratos/acta.pdf",
    ])
  })

  it("unpacks a .zip in the browser and uploads the files inside it", async () => {
    const { user } = renderUploader()
    const zip = new File(
      [zipSync({ "demanda.pdf": new Uint8Array(20).fill(65), "pruebas/foto.docx": new Uint8Array(30).fill(66) }) as BlobPart],
      "Expediente 482.zip"
    )
    await user.upload(screen.getByTestId("file-input"), zip)

    expect(await screen.findByText(/2 files will be uploaded/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Upload 2 files" }))
    await screen.findByText("Upload finished")
    expect(upload.mock.calls.map((c) => c[2]).sort()).toEqual([
      "Expediente 482/demanda.pdf",
      "Expediente 482/pruebas/foto.docx",
    ])
    // Each is a real file with the right content, not an empty placeholder.
    expect(upload.mock.calls.every((c) => c[1].size > 0)).toBe(true)
  })

  it("leaves out system files, unsupported types and files already in the collection, and says so", async () => {
    const { user } = renderUploader({ existingNames: ["ya-esta.pdf"] })
    await user.upload(screen.getByTestId("file-input"), [
      pdf("nuevo.pdf"),
      pdf(".DS_Store"),
      pdf("foto.jpg"),
      pdf("ya-esta.pdf"),
      pdf("repetido.pdf"),
      pdf("repetido.pdf"),
    ])

    expect(await screen.findByText(/2 files will be uploaded/)).toBeInTheDocument()
    expect(screen.getByText(/4 files left out/)).toBeInTheDocument()
    const details = screen.getByText(/4 files left out/).closest("details")!
    expect(within(details).getByText(/System or hidden files/)).toBeInTheDocument()
    expect(within(details).getByText(/Types we can't read/)).toBeInTheDocument()
    expect(within(details).getByText(/Already in this collection/)).toBeInTheDocument()
    expect(within(details).getByText(/Repeated in this selection/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Upload 2 files" }))
    await screen.findByText("Upload finished")
    expect(upload.mock.calls.map((c) => c[2]).sort()).toEqual(["nuevo.pdf", "repetido.pdf"])
  })

  it("skips a file over the size limit", async () => {
    const { user } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf("grande.pdf", 80 * MB), pdf("normal.pdf")])
    expect(await screen.findByText(/1 file will be uploaded/)).toBeInTheDocument()
    expect(screen.getByText(/Larger than 50 MB/)).toBeInTheDocument()
  })

  it("says so when there is nothing to upload, and offers no upload button", async () => {
    const { user } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf(".DS_Store")])
    expect(await screen.findByText("There is nothing to upload from this selection.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Upload 0 files" })).toBeDisabled()
  })

  it("cancelling the review sends nothing and returns to the drop box", async () => {
    const { user } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf("a.pdf")])
    await user.click(await screen.findByRole("button", { name: "Cancel" }))
    expect(screen.getByText("Drag files, folders or a .zip here")).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled()
  })

  it("keeps going when one file fails, explains why in plain language, and retries only that one", async () => {
    let failFirst = true
    upload.mockImplementation(async (_c, _f, path, onProgress) => {
      if (path === "malo.pdf" && failFirst) {
        failFirst = false
        throw new ApiError(413, "File exceeds the 50 MB upload limit", "file_too_large", { max_mb: 50 })
      }
      onProgress(1)
      return {} as never
    })
    const { user, onFinished } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf("bueno.pdf"), pdf("malo.pdf"), pdf("otro.pdf")])
    await user.click(await screen.findByRole("button", { name: "Upload 3 files" }))

    expect(await screen.findByText("1 file could not be uploaded.")).toBeInTheDocument()
    expect(screen.getByText(/That file is too large. The limit is 50 MB/)).toBeInTheDocument()
    expect(screen.queryByText(/File exceeds the 50 MB upload limit/)).not.toBeInTheDocument()
    expect(upload).toHaveBeenCalledTimes(3)

    await user.click(screen.getByRole("button", { name: "Retry the ones that failed" }))
    await waitFor(() => expect(screen.queryByText("1 file could not be uploaded.")).not.toBeInTheDocument())
    expect(upload).toHaveBeenCalledTimes(4) // only the failed one again
    expect(upload.mock.calls.filter((c) => c[2] === "malo.pdf")).toHaveLength(2)
    expect(onFinished).toHaveBeenCalledTimes(2)
  })

  it("lets a person stop an upload in progress", async () => {
    upload.mockImplementation(
      (_c, _f, _p, _on, signal) =>
        new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")))
        })
    )
    const { user } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf("a.pdf"), pdf("b.pdf")])
    await user.click(await screen.findByRole("button", { name: "Upload 2 files" }))
    await user.click(await screen.findByRole("button", { name: "Stop uploading" }))

    expect(await screen.findByText("Upload finished")).toBeInTheDocument()
    expect(screen.getByText("2 files could not be uploaded.")).toBeInTheDocument()
    expect(screen.getAllByText("Cancelled")).toHaveLength(2)
  })

  it("starts over with 'Upload more'", async () => {
    const { user } = renderUploader()
    await user.upload(screen.getByTestId("file-input"), [pdf("a.pdf")])
    await user.click(await screen.findByRole("button", { name: "Upload 1 file" }))
    await user.click(await screen.findByRole("button", { name: "Upload more" }))
    expect(screen.getByText("Drag files, folders or a .zip here")).toBeInTheDocument()
  })

  it("works in Spanish, with the right singular and plural forms", async () => {
    const { user } = renderUploader({ locale: "es" })
    expect(screen.getByText("Arrastre aquí archivos, carpetas o un .zip")).toBeInTheDocument()
    await user.upload(screen.getByTestId("file-input"), [pdf("a.pdf")])
    expect(await screen.findByText(/Se subirá 1 archivo/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Subir 1 archivo" }))
    expect(await screen.findByText("Subida terminada")).toBeInTheDocument()
    expect(screen.getByText(/Se subió 1 archivo/)).toBeInTheDocument()
  })
})
