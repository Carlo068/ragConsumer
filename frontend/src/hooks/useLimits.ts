import { useEffect, useState } from "react"
import { limitsService, type Limits } from "@/services/limitsService"

// The server's limits (for now, the largest upload). If they can't be loaded
// the UI just doesn't show or pre-check them; the server still enforces them.
export function useLimits() {
  const [limits, setLimits] = useState<Limits | null>(null)

  useEffect(() => {
    limitsService
      .get()
      .then(setLimits)
      .catch(() => setLimits(null))
  }, [])

  return limits
}
