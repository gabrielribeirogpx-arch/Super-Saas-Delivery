import { NextRequest } from "next/server"

const BACKEND = process.env.STOREFRONT_BACKEND_URL || "https://service-delivery-backend-production.up.railway.app"
export const dynamic = "force-dynamic"

function buildProxyUrl(req: NextRequest, path: string[]) {
  const proxyPath = path.join("/")
  const url = new URL(req.url)

  return `${BACKEND}/api/${proxyPath}${url.search}`
}

async function proxyRequest(
  req: NextRequest,
  params: { path: string[] },
  method: string,
) {
  const targetUrl = buildProxyUrl(req, params.path)

  const headers = new Headers(req.headers)
  headers.delete("host")

  const hasBody = method !== "GET" && method !== "HEAD"
  const body = hasBody ? await req.arrayBuffer() : undefined

  const res = await fetch(targetUrl, {
    method,
    headers,
    body,
    cache: "no-store",
  })

  const responseHeaders = new Headers(res.headers)
  responseHeaders.set("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate")
  responseHeaders.set("Pragma", "no-cache")
  responseHeaders.set("Expires", "0")

  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: responseHeaders,
  })
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "GET")
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "POST")
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "PUT")
}

export async function PATCH(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "PATCH")
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "DELETE")
}

export async function OPTIONS(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "OPTIONS")
}

export async function HEAD(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params, "HEAD")
}
