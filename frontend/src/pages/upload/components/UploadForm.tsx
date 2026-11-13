import { useRef, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useI18n } from "@/i18n/useI18n"

interface UploadFormProps {
  onUpload: (file: File) => Promise<void>
  uploading: boolean
  // Largest file the server accepts. Checked here too so a person finds out
  // before waiting for a big upload to be refused.
  maxUploadBytes?: number
}

const MB = 1024 * 1024

export function UploadForm({ onUpload, uploading, maxUploadBytes }: UploadFormProps) {
  const { t, errorText } = useI18n()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedFile) return

    if (maxUploadBytes && selectedFile.size > maxUploadBytes) {
      setError(
        t("upload.tooBig", {
          size: (selectedFile.size / MB).toFixed(1),
          limit: Math.round(maxUploadBytes / MB),
        })
      )
      return
    }
    setError(null)
    try {
      await onUpload(selectedFile)
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ""
    } catch (err) {
      setError(errorText(err, "upload.failed"))
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex items-end gap-3">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="file">
            {t("upload.document")}
            {maxUploadBytes ? (
              <span className="text-muted-foreground font-normal">
                {" "}
                {t("upload.upTo", { mb: Math.round(maxUploadBytes / MB) })}
              </span>
            ) : null}
          </Label>
          <Input
            id="file"
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.doc,.eml,.msg,.txt,.md"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button type="submit" disabled={!selectedFile || uploading}>
          {uploading ? t("upload.submitting") : t("upload.submit")}
        </Button>
      </div>
      {error && <p className="text-destructive text-sm">{error}</p>}
    </form>
  )
}
