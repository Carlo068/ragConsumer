import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { UploadForm } from "@/pages/upload/components/UploadForm"

const MB = 1024 * 1024

function fileOfSize(bytes: number, name = "demanda.pdf") {
  const file = new File(["x"], name, { type: "application/pdf" })
  Object.defineProperty(file, "size", { value: bytes })
  return file
}

function setup(maxUploadBytes?: number) {
  const onUpload = vi.fn().mockResolvedValue(undefined)
  render(<UploadForm onUpload={onUpload} uploading={false} maxUploadBytes={maxUploadBytes} />)
  return { onUpload, user: userEvent.setup() }
}

describe("UploadForm size limit", () => {
  it("tells people the largest file they can upload", () => {
    setup(50 * MB)
    expect(screen.getByText(/up to 50 MB/)).toBeInTheDocument()
  })

  it("refuses an oversized file before uploading anything, saying how big it is", async () => {
    const { onUpload, user } = setup(50 * MB)
    await user.upload(screen.getByLabelText(/Document/), fileOfSize(75 * MB))
    await user.click(screen.getByRole("button", { name: "Upload" }))

    expect(onUpload).not.toHaveBeenCalled()
    expect(screen.getByText("This file is 75.0 MB. The limit is 50 MB.")).toBeInTheDocument()
  })

  it("uploads a file within the limit", async () => {
    const { onUpload, user } = setup(50 * MB)
    const file = fileOfSize(10 * MB)
    await user.upload(screen.getByLabelText(/Document/), file)
    await user.click(screen.getByRole("button", { name: "Upload" }))
    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it("still works when the limit could not be loaded (the server enforces it)", async () => {
    const { onUpload, user } = setup(undefined)
    expect(screen.queryByText(/up to/)).not.toBeInTheDocument()
    const file = fileOfSize(200 * MB)
    await user.upload(screen.getByLabelText(/Document/), file)
    await user.click(screen.getByRole("button", { name: "Upload" }))
    expect(onUpload).toHaveBeenCalledWith(file)
  })
})
