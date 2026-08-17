import { Link } from "react-router-dom"
import { Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { PromptDialog } from "@/components/common/PromptDialog"
import type { Collection } from "@/models/collection"

interface CollectionRowProps {
  collection: Collection
  active: boolean
  onToggleActive: (checked: boolean) => void
  onRename: (name: string) => void
  onDelete: () => void
}

export function CollectionRow({
  collection,
  active,
  onToggleActive,
  onRename,
  onDelete,
}: CollectionRowProps) {
  return (
    <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
      <Switch checked={active} onCheckedChange={onToggleActive} />
      <Link
        to={`/collections/${collection.id}/upload`}
        className="flex-1 font-medium hover:underline"
      >
        {collection.name}
      </Link>
      <PromptDialog
        trigger={
          <Button variant="ghost" size="icon-sm" aria-label="Rename collection">
            <Pencil />
          </Button>
        }
        title={`Rename "${collection.name}"`}
        initialValue={collection.name}
        confirmLabel="Save"
        onSubmit={onRename}
      />
      <ConfirmDialog
        trigger={
          <Button variant="ghost" size="icon-sm" aria-label="Delete collection">
            <Trash2 />
          </Button>
        }
        title={`Delete "${collection.name}"?`}
        description="This permanently deletes the collection and every document in it. This can't be undone."
        onConfirm={onDelete}
      />
    </div>
  )
}
