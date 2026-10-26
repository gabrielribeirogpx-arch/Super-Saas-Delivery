import Image from "next/image";

type LoadingExperienceProps = {
  label: string;
  variant?: "admin" | "storefront";
  compact?: boolean;
};

export function LoadingExperience({ label, variant = "admin", compact = false }: LoadingExperienceProps) {
  if (variant === "storefront") {
    return (
      <div className={`loading-experience loading-experience-storefront mx-auto max-w-xl bg-[#f8f5ef] ${compact ? "py-5" : "min-h-[70dvh] pb-24"}`} role="status" aria-label={label}>
        {!compact && <div className="loading-storefront-hero">
          <div className="loading-storefront-mark" aria-hidden="true"><span /><span /><span /></div>
          <div className="loading-storefront-name" aria-hidden="true" />
          <div className="loading-storefront-subtitle" aria-hidden="true" />
        </div>}
        <div className="space-y-5 px-5 pt-5" aria-hidden="true">
          {!compact && <><div className="loading-skeleton h-[74px] rounded-2xl" /><div className="loading-skeleton h-12 rounded-full" /><div className="loading-skeleton h-6 w-40 rounded-lg" /></>}
          <div className="loading-skeleton h-36 rounded-3xl" />
          <div className="loading-skeleton h-36 rounded-3xl" />
        </div>
        <p className="px-5 pt-6 text-center text-sm font-medium text-stone-600">{label}</p>
      </div>
    );
  }

  if (compact) {
    return (
      <div className="loading-experience loading-experience-admin flex items-center gap-4 py-6" role="status" aria-label={label}>
        <div className="loading-brand-mark !m-0 !h-12 !w-12 !rounded-2xl" aria-hidden="true"><Image src="/brand/fomizero-avatar-app.svg" alt="" width={28} height={28} /></div>
        <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-700">{label}</p><div className="loading-skeleton mt-2 h-3 w-2/3 max-w-52 rounded-full" aria-hidden="true" /></div>
      </div>
    );
  }

  return (
    <div className="loading-experience loading-experience-admin mx-auto min-h-[55dvh] w-full max-w-5xl py-8" role="status" aria-label={label}>
      <div className="loading-brand-mark" aria-hidden="true"><Image src="/brand/fomizero-avatar-app.svg" alt="" width={40} height={40} priority /></div>
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
