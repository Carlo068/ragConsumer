/// <reference types="node" />
import fs from "node:fs"
import path from "node:path"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher"
import { I18nProvider } from "@/i18n/I18nProvider"
import { catalogs, describeError, interpolate, translate, type Translate } from "@/i18n/core"
import { en } from "@/i18n/messages/en"
import { es } from "@/i18n/messages/es"
import { ApiError } from "@/services/apiClient"
import { LoginForm } from "@/pages/login/components/LoginForm"

// Every string leaf as "a.b.c" -> text.
function flatten(node: unknown, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
    const name = prefix + key
    if (typeof value === "string") out[name] = value
    else Object.assign(out, flatten(value, name + "."))
  }
  return out
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe("message catalogs", () => {
  const english = flatten(en)
  const spanish = flatten(es)

  it("have exactly the same keys in both languages", () => {
    expect(Object.keys(spanish).sort()).toEqual(Object.keys(english).sort())
  })

  it("use the same placeholders in both languages for every message", () => {
    for (const key of Object.keys(english)) {
      expect(placeholders(spanish[key]), key).toEqual(placeholders(english[key]))
    }
  })

  it("have no empty messages", () => {
    for (const [key, text] of [...Object.entries(english), ...Object.entries(spanish)]) {
      expect(text.trim(), key).not.toBe("")
    }
  })

  it("are actually translated: Spanish text differs from English except for known identical ones", () => {
    // Technical terms and product-neutral words that are the same in both.
    const identical = new Set(["connect.jsonLabel", "roles.editor"])
    const untranslated = Object.keys(english).filter(
      (key) => english[key] === spanish[key] && !identical.has(key)
    )
    expect(untranslated).toEqual([])
  })

  it("define a message for every error code the server can send", () => {
    const codes: string[] = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../../../backend/app/error_codes.json"), "utf-8")
    )
    for (const code of codes) {
      expect(english[`errors.${code}`], `en errors.${code}`).toBeTruthy()
      expect(spanish[`errors.${code}`], `es errors.${code}`).toBeTruthy()
    }
    // And no stale ones: every errors.* message is either a server code or a generic fallback.
    const generic = new Set(["status403", "status404", "status409", "status413", "status422", "status5xx", "network", "unknown"])
    for (const key of Object.keys(english).filter((k) => k.startsWith("errors."))) {
      const name = key.slice("errors.".length)
      expect(codes.includes(name) || generic.has(name), key).toBe(true)
    }
  })

  it("define every reason the worker can give for a failed file", () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../../../ingestion_worker/app/failures.py"),
      "utf-8"
    )
    const codes = [...source.matchAll(/^[A-Z_]+ = "([a-z_]+)"$/gm)].map((m) => m[1])
    expect(codes.length).toBeGreaterThanOrEqual(5)
    for (const code of codes) {
      expect(english[`upload.failure.${code}`], `en ${code}`).toBeTruthy()
      expect(spanish[`upload.failure.${code}`], `es ${code}`).toBeTruthy()
    }
  })
})

describe("translate", () => {
  it("fills in placeholders", () => {
    expect(interpolate("Hola {name}, {n} archivos", { name: "Ana", n: 3 })).toBe("Hola Ana, 3 archivos")
  })

  it("leaves an unknown placeholder visible instead of printing 'undefined'", () => {
    expect(interpolate("Hola {name}", {})).toBe("Hola {name}")
  })

  it("returns the key itself for a missing message so a gap is visible", () => {
    expect(translate("es", "nope.nothing")).toBe("nope.nothing")
  })

  it("translates by locale", () => {
    expect(translate("es", "login.submit")).toBe("Iniciar sesión")
    expect(translate("en", "login.submit")).toBe("Sign in")
    expect(catalogs.es.nav.signOut).toBe("Cerrar sesión")
  })
})

describe("describeError", () => {
  const tEs: Translate = (key, params) => translate("es", key, params)

  it("shows the translation of the server's error code, with its values", () => {
    const err = new ApiError(413, "File exceeds the 50 MB upload limit", "file_too_large", { max_mb: 50 })
    expect(describeError(err, tEs)).toBe("Ese archivo es demasiado grande. El límite es de 50 MB.")
  })

  it("never shows the server's English text", () => {
    const err = new ApiError(404, "Collection not found", "matter_not_found")
    expect(describeError(err, tEs)).not.toMatch(/not found/i)
  })

  it("falls back by HTTP status when there is no code", () => {
    expect(describeError(new ApiError(403, "Forbidden"), tEs)).toBe("No tiene permiso para hacer eso.")
    expect(describeError(new ApiError(422, "x"), tEs)).toBe("Revise la información que escribió.")
    expect(describeError(new ApiError(503, "x"), tEs)).toContain("Algo salió mal de nuestro lado")
  })

  it("explains a connection failure", () => {
    expect(describeError(new TypeError("Failed to fetch"), tEs)).toContain("No pudimos comunicarnos")
  })

  it("uses the caller's fallback message for an unknown failure", () => {
    expect(describeError(new Error("weird"), tEs, "login.failed")).toBe("No se pudo iniciar sesión")
  })

  it("ignores a code it has no message for, falling back by status", () => {
    expect(describeError(new ApiError(409, "x", "brand_new_code"), tEs)).toBe(
      "No se puede hacer en este momento."
    )
  })
})

describe("the interface in Spanish", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("is Spanish by default, with no setting at all", () => {
    render(
      <I18nProvider>
        <LoginForm onSubmit={() => {}} submitting={false} error={null} />
      </I18nProvider>
    )
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument()
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument()
    expect(document.documentElement.lang).toBe("es")
  })

  it("switches to English, remembers the choice, and switches back", async () => {
    const user = userEvent.setup()
    const { unmount } = render(
      <I18nProvider>
        <LanguageSwitcher />
        <LoginForm onSubmit={() => {}} submitting={false} error={null} />
      </I18nProvider>
    )
    await user.click(screen.getByRole("button", { name: "English" }))
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe("en")
    expect(localStorage.getItem("locale")).toBe("en")
    unmount()

    // A new visit starts in the saved language.
    render(
      <I18nProvider>
        <LanguageSwitcher />
        <LoginForm onSubmit={() => {}} submitting={false} error={null} />
      </I18nProvider>
    )
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument()

    await userEvent.setup().click(screen.getByRole("button", { name: "Español" }))
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument()
  })

  it("ignores a saved language it does not know", () => {
    localStorage.setItem("locale", "klingon")
    render(
      <I18nProvider>
        <LoginForm onSubmit={() => {}} submitting={false} error={null} />
      </I18nProvider>
    )
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument()
  })

  it("shows a server error in Spanish on the login form", () => {
    render(
      <I18nProvider>
        <LoginForm
          onSubmit={() => {}}
          submitting={false}
          error={describeError(new ApiError(401, "Invalid credentials", "invalid_credentials"), (k, p) =>
            translate("es", k, p)
          )}
        />
      </I18nProvider>
    )
    expect(screen.getByText("El correo o la contraseña no son correctos.")).toBeInTheDocument()
    expect(screen.queryByText("Invalid credentials")).not.toBeInTheDocument()
  })
})
