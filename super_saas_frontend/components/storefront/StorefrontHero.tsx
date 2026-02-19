import { resolveMediaUrl } from "@/lib/media";

interface StorefrontHeroProps {
  name: string;
  slug: string;
  coverImageUrl?: string | null;
  coverVideoUrl?: string | null;
  logoUrl?: string | null;
  slogan?: string | null;
  showLogoOnCover?: boolean;
  isPreview?: boolean;
  isOpen?: boolean;
}

export function StorefrontHero({
  name,
  slug,
  coverImageUrl,
  coverVideoUrl,
  logoUrl,
  slogan,
  showLogoOnCover = true,
  isPreview = false,
  isOpen = false,
}: StorefrontHeroProps) {
  const coverImage = resolveMediaUrl(coverImageUrl);
  const coverVideo = resolveMediaUrl(coverVideoUrl);
  const logo = resolveMediaUrl(logoUrl);

  return (
    <header className="relative">
      {coverVideo ? (
        <video
          className="h-[220px] w-full object-cover md:h-[280px]"
          src={coverVideo}
          autoPlay
          muted
          loop
          playsInline
        />
      ) : coverImage ? (
        <img
          className="h-[220px] w-full object-cover md:h-[280px]"
          src={coverImage}
          alt={`Capa ${name}`}
        />
      ) : (
        <div className="h-[220px] w-full bg-slate-900 md:h-[280px]" />
      )}

      <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/35 to-black/70" />

      <div className="absolute inset-x-0 bottom-0 mx-auto flex w-full max-w-6xl translate-y-10 flex-col items-center px-4 text-white md:translate-y-12">
        {logo && showLogoOnCover && (
          <img
            src={logo}
            alt={`Logo ${name}`}
            className="h-20 w-20 rounded-full border-4 border-white object-cover shadow-xl md:h-24 md:w-24"
          />
        )}
        <div className="mt-3 text-center">
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{name}</h1>
          <p className="text-sm text-white/85">{slogan || `@${slug}`}</p>
        </div>
        <div className="mt-3 flex items-center gap-2">
          {isOpen && (
            <span className="rounded-full bg-emerald-500/90 px-3 py-1 text-xs font-semibold text-white">
              Aberto agora
            </span>
          )}
          {isPreview && (
            <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-semibold text-white backdrop-blur">
              Prévia
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
