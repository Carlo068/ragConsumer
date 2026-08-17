import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
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
      <CardFooter className="gap-2">
        <Button
          variant="outline"
          size="sm"
          nativeButton={false}
          render={<Link to={`/collections/${collection.id}/upload`}>Upload</Link>}
        />
        <Button
          variant="outline"
          size="sm"
          nativeButton={false}
          render={<Link to={`/collections/${collection.id}/connect`}>Connect</Link>}
        />
      </CardFooter>
    </Card>
  )
}
