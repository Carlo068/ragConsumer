import { useRef, useState, type DragEvent } from "react"
import { Button } from "@/components/ui/button"
import { fromDataTransfer, fromFileList } from "@/lib/bulk/collect"
import { PICKER_ACCEPT } from "@/lib/bulk/filters"
import type { PickedFile } from "@/lib/bulk/plan"
import { useI18n } from "@/i18n/useI18n"

interface DropZoneProps {
  onPicked: (files: PickedFile[]) => void
  maxUploadBytes?: number
  busy?: boolean
}

const MB = 1024 * 1024

// One place to hand over files, folders or a .zip: drag them in, or use the
// two buttons (a folder picker needs its own input).
export function DropZone({ onPicked, maxUploadBytes, busy = false }: DropZoneProps) {
  const { t } = useI18n()
  const [dragging, setDragging] = useState(false)
  const filesInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)

  async function handleDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    if (busy) return
    onPicked(await fromDataTransfer(event.dataTransfer))
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!busy) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      data-testid="drop-zone"
      className={
        "flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 text-center transition-colors " +
        (dragging ? "border-primary bg-muted" : "border-border")
      }
    >
      <p className="font-medium">{busy ? t("bulk.preparing") : t("bulk.dropTitle")}</p>
      <p className="text-muted-foreground text-xs">
        {maxUploadBytes
          ? t("bulk.dropHint", { mb: Math.round(maxUploadBytes / MB) })
          : t("bulk.dropHintNoLimit")}
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button type="button" variant="outline" disabled={busy} onClick={() => filesInput.current?.click()}>
          {t("bulk.chooseFiles")}
        </Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => folderInput.current?.click()}>
          {t("bulk.chooseFolder")}
        </Button>
      </div>
      <input
        ref={filesInput}
        data-testid="file-input"
        type="file"
        multiple
        hidden
        accept={PICKER_ACCEPT}
        onChange={(e) => {
          onPicked(fromFileList(e.target.files ?? []))
          e.target.value = "" // so choosing the same files again still fires
        }}
      />
      <input
        ref={folderInput}
        data-testid="folder-input"
        type="file"
        multiple
        hidden
        {...({ webkitdirectory: "" } as object)}
        onChange={(e) => {
          onPicked(fromFileList(e.target.files ?? []))
          e.target.value = ""
        }}
      />
    </div>
  )
}
