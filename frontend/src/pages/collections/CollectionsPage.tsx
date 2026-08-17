import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/useAuth"
import { useCollections } from "@/hooks/useCollections"
import { CollectionCard } from "./components/CollectionCard"

export function CollectionsPage() {
  const { user, logout } = useAuth()
  const { collections, loading, error } = useCollections()

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Collections</h1>
          <p className="text-muted-foreground text-sm">Signed in as {user?.email}</p>
        </div>
        <Button variant="outline" onClick={() => logout()}>
          Sign out
        </Button>
      </div>

      {loading && <p>Loading...</p>}
      {error && <p className="text-destructive">{error}</p>}

      <div className="flex flex-col gap-3">
        {collections.map((collection) => (
          <CollectionCard key={collection.id} collection={collection} />
        ))}
      </div>
    </div>
  )
}
