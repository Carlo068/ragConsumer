export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number
  // Stable machine-readable reason from the server (and any values its message
  // needs). The UI shows its own translation of the code; `message` is the
  // server's English text, kept for logs and debugging only.
  code?: string
  params?: Record<string, string | number>

  constructor(
    status: number,
    message: string,
    code?: string,
    params?: Record<string, string | number>
  ) {
    super(message)
    this.status = status
    this.code = code
    this.params = params
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // Skip Content-Type for FormData bodies -- fetch needs to set its own
  // multipart boundary, which a manually-set Content-Type would break.
  const isFormData = options.body instanceof FormData
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(
      response.status,
      typeof body?.detail === "string" ? body.detail : response.statusText,
      typeof body?.code === "string" ? body.code : undefined,
      body?.params
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  // Separate from post() because a multipart body must NOT be JSON-stringified.
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, {
      method: "POST",
      body: form,
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: (path: string) => request<void>(path, { method: "DELETE" }),
}
