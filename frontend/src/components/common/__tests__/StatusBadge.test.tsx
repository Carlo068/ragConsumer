import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { StatusBadge } from "@/components/common/StatusBadge"
import { I18nProvider } from "@/i18n/I18nProvider"
import type { DocumentStatus } from "@/models/document"

const SPANISH: Record<DocumentStatus, string> = {
  uploaded: "En espera",
  processing: "Leyendo…",
  ready: "Listo para buscar",
  failed: "No se pudo leer",
}
const ENGLISH: Record<DocumentStatus, string> = {
  uploaded: "Waiting",
  processing: "Reading…",
  ready: "Ready to search",
  failed: "Couldn't be read",
}

describe("StatusBadge says what is happening to the file, in plain words", () => {
  it.each(Object.entries(SPANISH))("shows %s in Spanish as '%s'", (status, label) => {
    render(
      <I18nProvider locale="es">
        <StatusBadge status={status as DocumentStatus} />
      </I18nProvider>
    )
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it.each(Object.entries(ENGLISH))("shows %s in English as '%s'", (status, label) => {
    render(
      <I18nProvider locale="en">
        <StatusBadge status={status as DocumentStatus} />
      </I18nProvider>
    )
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
