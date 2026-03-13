import { NextRequest } from "next/server"

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

async function proxy(req: NextRequest, { params }: RouteContext) {
  const path = (params.path || []).join("/")
  const query = req.nextUrl.search
  const backendUrl = `${normalizeBackendBaseUrl(BACKEND_URL)}/api/${path}${query}`

  const requestHeaders = new Headers(req.headers)
  requestHeaders.delete("host")
  requestHeaders.delete("content-length")

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
