'use client'

import { useEffect, useMemo, useState } from 'react'

type DeliveryStatus = string | null

type DeliveryProgressBarProps = {
  orderId: string
}

const API_BASE = 'https://service-delivery-backend-production.up.railway.app'

export default function DeliveryProgressBar({ orderId }: DeliveryProgressBarProps) {
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<DeliveryStatus>(null)

  useEffect(() => {
    if (!orderId) return

    console.log("SSE connecting...")

    const es = new EventSource(`${API_BASE}/sse/delivery/${orderId}`)

    es.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log("SSE data:", data)

      if (data.status) {
        const rawStatus = data.status

        let normalizedStatus = rawStatus

        if (rawStatus === "Saiu para entrega") {
          normalizedStatus = "OUT_FOR_DELIVERY"
        }

        if (rawStatus === "Entregue") {
          normalizedStatus = "DELIVERED"
        }

        setStatus(normalizedStatus)
      }

      if (data.progress !== undefined) {
        setProgress(Math.max(0, Math.min(1, data.progress)))
      }
    }

    es.onerror = (e) => {
      console.error('SSE error', e)
    }

    return () => es.close()
  }, [orderId])

  const isDelivered = status === 'DELIVERED'

  const normalizedProgress = useMemo(() => {
    if (isDelivered) return 1
    return Math.max(0, Math.min(1, progress))
  }, [isDelivered, progress])

  if (!status) {
    return <div>Carregando rastreamento...</div>
  }

  console.log('STATUS ATUAL:', status)

  return (
    <div className="w-full flex flex-col items-center gap-4">
      <div className="relative w-full max-w-md h-16">
        <div className="absolute top-1/2 left-0 right-0 h-2 -translate-y-1/2 rounded bg-gray-300" />

        <div
          className="absolute top-1/2 -translate-y-1/2 transition-all duration-500 ease-in-out"
          style={{ left: `calc(${normalizedProgress * 100}% - 0.5rem)` }}
        >
          <div
            className={`w-4 h-4 rounded-full ${isDelivered ? 'bg-green-500' : 'bg-emerald-500'}`}
            aria-label={isDelivered ? 'Delivery completed' : 'Delivery in progress'}
          />
        </div>

        <div className="absolute left-0 -top-6 text-xl" aria-hidden="true">
          🏍️
        </div>
        <div className="absolute right-0 -top-6 text-xl" aria-hidden="true">
          🏠
        </div>
      </div>

      {isDelivered ? (
        <div className="text-sm font-medium text-green-600">✅ Delivered</div>
      ) : (
        <div className="text-sm text-gray-600">Your order is on the way</div>
      )}
    </div>
  )
}
