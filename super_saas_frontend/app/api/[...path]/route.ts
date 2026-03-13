import { NextRequest } from "next/server"

const BACKEND_URL =
  process.env.STOREFRONT_BACKEND_URL ||
  "https://service-delivery-backend-production.up.railway.app"

async function proxy(req: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join("/")
  const cleanPath = path.replace(/^api\//, "")

  const url = `${BACKEND_URL}/api/${cleanPath}`

  const response = await fetch(url, {
    method: req.method,
    headers: {
      "Content-Type": "application/json",
    },
    body: req.method !== "GET" ? await req.text() : undefined,
  })

  return new Response(await response.text(), {
    status: response.status,
    headers: {
      "Content-Type": "application/json",
    },
  })
}

export { proxy as GET }
export { proxy as POST }
export { proxy as PUT }
export { proxy as PATCH }
export { proxy as DELETE }
