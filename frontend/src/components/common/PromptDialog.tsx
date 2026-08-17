import { useState, type FormEvent, type ReactElement } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

interface PromptDialogProps {
  trigger: ReactElement
  title: string
  description?: string
  initialValue?: string
  confirmLabel?: string
  onSubmit: (value: string) => void | Promise<void>
}

export function PromptDialog({
  trigger,
  title,
  description,
  initialValue = "",
  confirmLabel = "Save",
  onSubmit,
}: PromptDialogProps) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(initialValue)
  const [submitting, setSubmitting] = useState(false)

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (nextOpen) setValue(initialValue)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!value.trim()) return
    setSubmitting(true)
    try {
      await onSubmit(value.trim())
      setOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <Input
            autoFocus
            className="mt-4"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
          <DialogFooter>
            <DialogClose
              render={
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              }
            />
            <Button type="submit" disabled={!value.trim() || submitting}>
              {submitting ? "Saving..." : confirmLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
