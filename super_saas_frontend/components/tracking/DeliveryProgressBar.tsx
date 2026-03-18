"use client";

import { useEffect, useMemo, useState } from "react";

type DeliveryProgressBarProps = {
  status: string | null | undefined;
  statusStep?: number | null;
  progress?: number | null;
  distanceKm?: number | null;
  etaSeconds?: number | null;
};

const MAX_STEP = 5;
const SMOOTHING_FACTOR = 0.2;

function formatEtaLabel(etaSeconds: number | null | undefined) {
  if (!Number.isFinite(Number(etaSeconds))) return null;
  const totalSeconds = Math.max(0, Math.round(Number(etaSeconds)));
  if (totalSeconds <= 0) return "Agora";

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes <= 0) {
    return `${seconds}s`;
  }

  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function getStatus(progress: number) {
  if (progress >= 1) return "Chegou! 🎉";
  if (progress < 0.2) return "Pedido saiu para entrega 🚀";
  if (progress < 0.5) return "Entregador a caminho 🛵";
  if (progress < 0.8) return "Chegando perto 📍";
  if (progress < 0.95) return "Quase aí 🔥";
  return "Chegou! 🎉";
}

function smooth(current: number, target: number) {
  return current + (target - current) * SMOOTHING_FACTOR;
}

export default function DeliveryProgressBar({ status, statusStep, progress, distanceKm, etaSeconds }: DeliveryProgressBarProps) {
  const safeStep = Math.max(0, Math.min(MAX_STEP, Number(statusStep || 0)));
  const isDelivered = String(status || "").toUpperCase() === "DELIVERED" || safeStep >= MAX_STEP;

  const normalizedProgress = useMemo(() => {
    if (isDelivered) return 1;
    if (Number.isFinite(Number(progress))) return Math.max(0, Math.min(1, Number(progress)));
    if (safeStep <= 0) return 0;
    return (safeStep - 1) / (MAX_STEP - 1);
  }, [isDelivered, progress, safeStep]);

  const [smoothedProgress, setSmoothedProgress] = useState(normalizedProgress);
  const [eta, setEta] = useState(() => Math.max(0, Math.round(Number(etaSeconds) || 0)));

  useEffect(() => {
    setEta(Math.max(0, Math.round(Number(etaSeconds) || 0)));
  }, [etaSeconds]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setEta((prev) => Math.max(prev - 1, 0));
    }, 1000);

    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (Math.abs(smoothedProgress - normalizedProgress) < 0.001) {
      setSmoothedProgress(normalizedProgress);
      return undefined;
    }

    const frame = window.requestAnimationFrame(() => {
      setSmoothedProgress((current) => {
        const next = smooth(current, normalizedProgress);
        return Math.abs(next - normalizedProgress) < 0.001 ? normalizedProgress : next;
      });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [normalizedProgress, smoothedProgress]);

  const liveProgress = isDelivered ? 1 : smoothedProgress;
  const formattedEta = formatEtaLabel(eta);
  const formattedDistance = Number.isFinite(Number(distanceKm)) ? `${Number(distanceKm).toFixed(2)} km` : null;
  const statusLabel = isDelivered ? "Chegou! 🎉" : getStatus(liveProgress);

  if (!status && safeStep <= 0) {
    return <div>Carregando rastreamento...</div>;
  }

  return (
    <div className="tracking-shell flex w-full flex-col gap-4 rounded-[28px] border border-slate-200/80 bg-white/95 p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)] backdrop-blur sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Rastreamento premium</p>
          <h2 className="mt-1 text-base font-semibold text-slate-900 sm:text-lg">{statusLabel}</h2>
          {formattedDistance || formattedEta ? (
            <p className="mt-1 text-xs text-slate-500 sm:text-sm">
              {[formattedDistance, formattedEta ? `ETA ${formattedEta}` : null].filter(Boolean).join(" • ")}
            </p>
          ) : null}
        </div>

        <div className="live-indicator shrink-0">
          <span className="dot" />
          Atualizando em tempo real
        </div>
      </div>

      <div className="relative px-1 pb-5 pt-8">
        <div className="track-base" aria-hidden="true" />
        <div className="progress-fill" style={{ width: `${liveProgress * 100}%` }} aria-hidden="true" />

        <div className="live-dot" style={{ left: `${liveProgress * 100}%` }} aria-hidden="true" />

        <div className={`motorcycle ${isDelivered ? "arrived" : ""}`} style={{ left: `${liveProgress * 100}%` }} aria-hidden="true">
          🏍️
        </div>

        <div className={`destination ${isDelivered ? "arrived" : ""}`} aria-hidden="true">
          🏠
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs sm:text-sm">
        <div className="metric-card">
          <span className="metric-label">Progresso</span>
          <span className="metric-value">{Math.round(liveProgress * 100)}%</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Previsão</span>
          <span className="metric-value">{formattedEta || (isDelivered ? "Concluído" : "Calculando")}</span>
        </div>
      </div>

      <style jsx>{`
        .tracking-shell {
          overflow: hidden;
        }

        .track-base {
          position: absolute;
          inset: 50% 0 auto;
          height: 6px;
          transform: translateY(-50%);
          border-radius: 999px;
          background: linear-gradient(90deg, rgba(226, 232, 240, 0.9), rgba(203, 213, 225, 0.9));
        }

        .progress-fill {
          position: absolute;
          inset: 50% auto auto 0;
          height: 6px;
          transform: translateY(-50%);
          border-radius: 999px;
          background: linear-gradient(90deg, #facc15, #22c55e);
          transition: width 0.6s ease;
          box-shadow: 0 0 24px rgba(34, 197, 94, 0.35);
          will-change: width;
        }

        .motorcycle {
          position: absolute;
          top: -12px;
          transform: translateX(-50%);
          transition: left 0.8s cubic-bezier(0.4, 0, 0.2, 1);
          animation: subtleShake 2s infinite;
          font-size: 1.65rem;
          filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.18));
          will-change: left, transform;
          z-index: 3;
        }

        .live-dot {
          width: 10px;
          height: 10px;
          background: #22c55e;
          border-radius: 50%;
          position: absolute;
          top: 50%;
          transform: translate(-50%, -50%);
          animation: pulse 1.5s infinite;
          box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.14);
          transition: left 0.8s cubic-bezier(0.4, 0, 0.2, 1);
          z-index: 2;
        }

        .destination {
          position: absolute;
          right: 0;
          top: -12px;
          font-size: 1.55rem;
          filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.14));
        }

        .motorcycle.arrived {
          animation: arriveMotorcycle 0.6s ease;
        }

        .destination.arrived {
          animation: arrive 0.6s ease;
        }

        .live-indicator {
          font-size: 12px;
          color: #16a34a;
          display: flex;
          align-items: center;
          gap: 6px;
          border-radius: 999px;
          background: rgba(34, 197, 94, 0.08);
          padding: 8px 10px;
          white-space: nowrap;
        }

        .dot {
          width: 6px;
          height: 6px;
          background: #16a34a;
          border-radius: 50%;
          animation: pulseDot 1s infinite;
        }

        .metric-card {
          display: flex;
          flex-direction: column;
          gap: 4px;
          border-radius: 18px;
          border: 1px solid rgba(226, 232, 240, 0.9);
          background: linear-gradient(180deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.85));
          padding: 12px 14px;
        }

        .metric-label {
          color: #64748b;
        }

        .metric-value {
          color: #0f172a;
          font-weight: 600;
        }

        @keyframes pulse {
          0% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 1;
          }
          50% {
            transform: translate(-50%, -50%) scale(1.6);
            opacity: 0.5;
          }
          100% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 1;
          }
        }

        @keyframes pulseDot {
          0% {
            transform: scale(1);
            opacity: 1;
          }
          50% {
            transform: scale(1.4);
            opacity: 0.55;
          }
          100% {
            transform: scale(1);
            opacity: 1;
          }
        }

        @keyframes subtleShake {
          0%,
          100% {
            transform: translateX(-50%) rotate(0deg);
          }
          50% {
            transform: translateX(-50%) rotate(1deg);
          }
        }

        @keyframes arriveMotorcycle {
          0% {
            transform: translateX(-50%) scale(1);
          }
          50% {
            transform: translateX(-50%) scale(1.2);
          }
          100% {
            transform: translateX(-50%) scale(1);
          }
        }

        @keyframes arrive {
          0% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.2);
          }
          100% {
            transform: scale(1);
          }
        }

        @media (max-width: 420px) {
          .live-indicator {
            padding: 6px 8px;
            font-size: 11px;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .progress-fill,
          .motorcycle,
          .live-dot,
          .dot,
          .arrived {
            animation: none;
            transition-duration: 0.01ms;
          }
        }
      `}</style>
    </div>
  );
}
