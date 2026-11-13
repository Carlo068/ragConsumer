import { useState } from "react"
import { Button } from "@/components/ui/button"
import { useI18n } from "@/i18n/useI18n"

interface CopyBlockProps {
  label?: string
  code: string
}

export function CopyBlock({ label, code }: CopyBlockProps) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? t("common.copied") : t("common.copy")}
        </Button>
      </div>
      <pre className="bg-muted overflow-x-auto rounded-lg p-3 text-xs">
        <code>{code}</code>
      </pre>
    </div>
  )
}
