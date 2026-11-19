import Image from "next/image";

type LoadingExperienceProps = {
  label: string;
  variant?: "admin" | "storefront" | "driver";
  compact?: boolean;
};

export function LoadingExperience({ label, variant = "admin", compact = false }: LoadingExperienceProps) {
  if (variant === "driver") {
    return (
      <div className={`loading-experience loading-experience-driver mx-auto w-full max-w-xl bg-slate-950 text-white ${compact ? "rounded-2xl p-4" : "min-h-[70dvh] px-5 py-16"}`} role="status" aria-label={label}>
        <div className="flex items-center gap-3">
          <Image src="/brand/fomizero-simbolo.svg" alt="" width={compact ? 40 : 56} height={compact ? 40 : 56} aria-hidden="true" />
          <p className="text-sm font-semibold text-slate-100">{label}</p>
        </div>
        <div className="mt-7 space-y-4" aria-hidden="true">
          <div className="loading-skeleton h-20 rounded-2xl" />
          {!compact && <><div className="loading-skeleton h-32 rounded-2xl" /><div className="loading-skeleton h-32 rounded-2xl" /></>}
        </div>
      </div>
    );
  }

  if (variant === "storefront") {
    return (
      <div className={`loading-experience loading-experience-storefront flex flex-col items-center justify-center text-center ${compact ? "min-h-32 px-5 py-6" : "min-h-[100dvh] px-6 pb-[env(safe-area-inset-bottom)]"}`} role="status" aria-label={label}>
        <div className={`loading-storefront-icon ${compact ? "h-12 w-12 rounded-xl" : "h-20 w-20 rounded-2xl"}`} aria-hidden="true" />
        <p className={`font-medium ${compact ? "mt-3 text-sm" : "mt-5 text-base"}`}>{label}</p>
        <div className="loading-storefront-progress mt-4 h-1 w-24 overflow-hidden rounded-full" aria-hidden="true">
          <span className="block h-full w-1/2 rounded-full" />
        </div>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="loading-experience loading-experience-admin flex items-center gap-4 py-6" role="status" aria-label={label}>
        <div className="loading-brand-mark !m-0 !h-12 !w-12" aria-hidden="true"><Image src="/brand/fomizero-simbolo.svg" alt="" width={30} height={30} /></div>
        <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-700">{label}</p><div className="loading-skeleton mt-2 h-3 w-2/3 max-w-52 rounded-full" aria-hidden="true" /></div>
      </div>
    );
  }

  return (
    <div className="loading-experience loading-experience-admin mx-auto min-h-[55dvh] w-full max-w-5xl py-8" role="status" aria-label={label}>
      <div className="loading-brand-mark" aria-hidden="true"><Image src="/brand/fomizero-simbolo.svg" alt="" width={42} height={42} priority /></div>
      <p className="mt-4 text-center text-sm font-semibold text-slate-700">{label}</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-3" aria-hidden="true">
        <div className="loading-skeleton h-24 rounded-2xl" />
        <div className="loading-skeleton h-24 rounded-2xl" />
        <div className="loading-skeleton h-24 rounded-2xl" />
      </div>
      <div className="loading-skeleton mt-4 h-48 rounded-2xl" aria-hidden="true" />
    </div>
  );
}

export function LoadingLine({ label }: { label: string }) {
  return (
    <span className="loading-line inline-flex items-center gap-2 text-sm" role="status">
      <span className="loading-line-dots inline-flex items-center gap-1" aria-hidden="true"><i /><i /><i /></span>
      {label}
    </span>
  );
}
