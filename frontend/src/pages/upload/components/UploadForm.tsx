import { useRef, useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface UploadFormProps {
  onUpload: (file: File) => Promise<void>
  uploading: boolean
}

export function UploadForm({ onUpload, uploading }: UploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedFile) return

    setError(null)
    try {
      await onUpload(selectedFile)
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ""
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex items-end gap-3">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="file">Document</Label>
          <Input
            id="file"
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt,.md"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button type="submit" disabled={!selectedFile || uploading}>
          {uploading ? "Uploading..." : "Upload"}
        </Button>
      </div>
      {error && <p className="text-destructive text-sm">{error}</p>}
    </form>
  )
}
