import { Card, CardHeader, CardTitle } from "@/components/ui/card"
import type { Collection } from "@/models/collection"

interface CollectionCardProps {
  collection: Collection
}

export function CollectionCard({ collection }: CollectionCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{collection.name}</CardTitle>
      </CardHeader>
    </Card>
  )
}
