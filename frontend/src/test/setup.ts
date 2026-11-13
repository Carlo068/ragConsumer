import "@testing-library/jest-dom/vitest"
import { setFallbackLocale } from "@/i18n/context"

// Component tests render without the provider and assert on text, so they use
// English; the Spanish catalog is covered by its own tests.
setFallbackLocale("en")
