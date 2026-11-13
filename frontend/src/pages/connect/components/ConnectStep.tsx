import type { ReactNode } from "react"
import { Check } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useI18n } from "@/i18n/useI18n"

interface ConnectStepProps {
  number: number
  title: string
  // Shown as a check mark and "Listo" once the step has been completed.
  done?: boolean
  children: ReactNode
}

// One numbered step of the guide.
export function ConnectStep({ number, title, done = false, children }: ConnectStepProps) {
  const { t } = useI18n()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className={
              "flex size-7 shrink-0 items-center justify-center rounded-full text-sm " +
              (done ? "bg-emerald-600 text-white" : "bg-muted")
            }
          >
            {done ? <Check className="size-4" /> : number}
          </span>
          <span className="flex-1">
            <span className="sr-only">{number}. </span>
            {title}
          </span>
          {done && <span className="text-muted-foreground text-xs font-normal">{t("connect.done")}</span>}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  )
}
