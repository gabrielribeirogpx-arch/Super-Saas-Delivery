import { NextRequest } from "next/server"

const TENANT_PATH_PATTERNS = [/\/loja\/([^/]+)/, /^\/([^/]+)\/mobile(?:\/|$)/]

const BACKEND_URL =
  process.env.STOREFRONT_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"

function normalizeBackendBaseUrl(url: string) {
  return url.replace(/\/+$/, "").replace(/\/api$/, "")
}

const METHODS_WITHOUT_BODY = new Set(["GET", "HEAD"])

type RouteContext = {
  params: {
    path: string[]
  }
}

function normalizeTenantCandidate(value?: string | null) {
  const normalized = value?.trim()
  return normalized ? decodeURIComponent(normalized) : null
}

function resolveTenantFromPathname(pathname: string) {
  for (const pattern of TENANT_PATH_PATTERNS) {
    const tenant = normalizeTenantCandidate(pathname.match(pattern)?.[1])
    if (tenant) {
      return tenant
    }
  }

  return null
}

function resolveTenantFromHostname(hostname: string) {
  const normalizedHost = hostname.trim().toLowerCase()
  if (!normalizedHost || normalizedHost === "localhost") {
    return null
  }

  const labels = normalizedHost.split(".").filter(Boolean)
  if (labels.length < 3) {
    return null
  }

  const candidate = labels.at(-3)
  if (!candidate || candidate === "www" || candidate === "m") {
    return null
  }

  return normalizeTenantCandidate(candidate)
}

function resolveTenantFromUrl(urlValue?: string | null) {
  if (!urlValue) {
    return null
  }

  try {
    const parsed = new URL(urlValue)
    return resolveTenantFromPathname(parsed.pathname) || resolveTenantFromHostname(parsed.hostname)
  } catch {
    return null
  }
}

function resolveTenantFromRequest(req: NextRequest) {
  return (
    normalizeTenantCandidate(req.headers.get("x-tenant-id")) ||
    normalizeTenantCandidate(req.nextUrl.searchParams.get("tenant_id")) ||
    resolveTenantFromUrl(req.headers.get("referer")) ||
    resolveTenantFromUrl(req.headers.get("origin")) ||
    resolveTenantFromPathname(req.nextUrl.pathname) ||
    resolveTenantFromHostname(req.headers.get("x-forwarded-host") || req.headers.get("host") || "")
  )
}

const PUBLIC_API_COMPAT_PREFIXES = ["public/order/", "public/track/", "public/sse/"]

function buildBackendPath(path: string) {
  const shouldUseApiPrefix =
    !path.startsWith("public/") || PUBLIC_API_COMPAT_PREFIXES.some((prefix) => path.startsWith(prefix))

  return shouldUseApiPrefix ? `/api/${path}` : `/${path}`
}

async function proxy(req: NextRequest, { params }: RouteContext) {
  const path = (params.path || []).join("/")
  const query = req.nextUrl.search
  const backendUrl = `${normalizeBackendBaseUrl(BACKEND_URL)}${buildBackendPath(path)}${query}`

  const requestHeaders = new Headers(req.headers)
  const tenantId = resolveTenantFromRequest(req)
  requestHeaders.delete("host")
  requestHeaders.delete("content-length")
  if (tenantId) {
    requestHeaders.set("x-tenant-id", tenantId)
  }

  const upstreamResponse = await fetch(backendUrl, {
    method: req.method,
    headers: requestHeaders,
    body: METHODS_WITHOUT_BODY.has(req.method) ? undefined : req.body,
    duplex: METHODS_WITHOUT_BODY.has(req.method) ? undefined : "half",
    redirect: "manual",
  } as RequestInit & { duplex?: "half" })

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: new Headers(upstreamResponse.headers),
  })
}

export { proxy as GET }
export { proxy as POST }
export { proxy as PUT }
export { proxy as PATCH }
export { proxy as DELETE }
export { proxy as OPTIONS }
export { proxy as HEAD }
