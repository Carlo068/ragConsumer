import { Badge } from "@/components/ui/badge"
import { useI18n } from "@/i18n/useI18n"
import type { DocumentStatus } from "@/models/document"

const STATUS_CONFIG: Record<
  DocumentStatus,
  { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }
> = {
  uploaded: { variant: "secondary" },
  processing: {
    variant: "outline",
    className: "border-amber-500 text-amber-600 dark:text-amber-400",
  },
  ready: {
    variant: "default",
    className: "bg-emerald-600 text-white dark:bg-emerald-500",
  },
  failed: { variant: "destructive" },
}

interface StatusBadgeProps {
  status: DocumentStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const { t } = useI18n()
  const config = STATUS_CONFIG[status]
  return (
    <Badge variant={config.variant} className={config.className}>
      {t(`status.${status}`)}
    </Badge>
  )
}
