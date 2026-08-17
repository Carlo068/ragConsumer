import { useState } from "react"
import { Button } from "@/components/ui/button"

interface ConnectionSnippetProps {
  label: string
  code: string
}

export function ConnectionSnippet({ label, code }: ConnectionSnippetProps) {
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
          {copied ? "Copied!" : "Copy"}
        </Button>
      </div>
      <pre className="bg-muted overflow-x-auto rounded-lg p-3 text-xs">
        <code>{code}</code>
      </pre>
    </div>
  )
}
