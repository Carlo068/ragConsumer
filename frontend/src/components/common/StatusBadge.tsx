import { Badge } from "@/components/ui/badge"
import type { DocumentStatus } from "@/models/document"

const STATUS_CONFIG: Record<
  DocumentStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
  uploaded: { label: "Uploaded", variant: "secondary" },
  processing: {
    label: "Processing",
    variant: "outline",
    className: "border-amber-500 text-amber-600 dark:text-amber-400",
  },
  ready: {
    label: "Ready",
    variant: "default",
    className: "bg-emerald-600 text-white dark:bg-emerald-500",
  },
  failed: { label: "Failed", variant: "destructive" },
}

interface StatusBadgeProps {
  status: DocumentStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status]
  return (
    <Badge variant={config.variant} className={config.className}>
      {config.label}
    </Badge>
  )
}
