import { CopyBlock } from "@/components/common/CopyBlock"
import type { MessageKey } from "@/i18n/core"
import { useI18n } from "@/i18n/useI18n"

const SAMPLES = ["connect.sample1", "connect.sample2", "connect.sample3"] as const satisfies readonly MessageKey[]

// Step 4: questions to try once connected, each ready to copy.
export function SampleQuestions() {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-3">
      {SAMPLES.map((key) => (
        <CopyBlock key={key} code={t(key)} />
      ))}
    </div>
  )
}
