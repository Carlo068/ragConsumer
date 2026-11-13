import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PromptDialog } from "@/components/common/PromptDialog"
import { useCollections } from "@/hooks/useCollections"
import { CollectionRow } from "./components/CollectionRow"

export function CollectionsPage() {
  const {
    collections,
    loading,
    error,
    createCollection,
    renameCollection,
    deleteCollection,
    setAiAccess,
  } = useCollections()

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Collections</h1>
        <PromptDialog
          trigger={
            <Button>
              <Plus />
              New
            </Button>
          }
          title="New collection"
          confirmLabel="Create"
          onSubmit={createCollection}
        />
      </div>

      {loading && <p>Loading...</p>}
      {error && <p className="text-destructive">{error}</p>}

      <div className="flex flex-col gap-3">
        {collections.map((collection) => (
          <CollectionRow
            key={collection.id}
            collection={collection}
            onToggleAi={(enabled) => setAiAccess(collection.id, enabled)}
            onRename={(name) => renameCollection(collection.id, name)}
            onDelete={() => deleteCollection(collection.id)}
          />
        ))}
      </div>
    </div>
  )
}
