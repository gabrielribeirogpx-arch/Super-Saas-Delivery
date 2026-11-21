import Image from "next/image";
import Link from "next/link";
import { CheckCircle2, Download, ShieldCheck } from "lucide-react";

export const dynamic = "force-dynamic";

function releaseUrl(): string | null {
  const value = process.env.DRIVER_APK_URL?.trim();
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export default function DownloadDriverAppPage() {
  const downloadUrl = releaseUrl();
  const version = process.env.DRIVER_APK_VERSION?.trim();

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-900 sm:py-16">
      <div className="mx-auto max-w-2xl">
        <Link href="/driver/login" className="mb-6 inline-flex text-sm font-medium text-white/80 hover:text-white">← Área do entregador</Link>
        <section className="overflow-hidden rounded-3xl bg-white shadow-2xl">
          <div className="relative isolate overflow-hidden bg-gradient-to-br from-red-600 to-red-800 px-6 py-7 text-white sm:px-10 sm:py-9">
            <Image
              src="/images/driver-download-tracking.webp"
              alt=""
              width={640}
              height={427}
              sizes="(min-width: 704px) 365px, (min-width: 640px) 52vw, 66vw"
              className="pointer-events-none absolute inset-y-0 right-0 h-full w-[69%] object-contain object-right sm:w-[54%]"
              priority
            />
            <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-gradient-to-r from-red-700 via-red-700/65 to-transparent sm:via-red-700/55" />
            <div className="relative sm:max-w-[52%]">
              <Image
                src="/brand/fomizero-monocromatica-branca.svg"
                alt="Fomizero"
                width={172}
                height={48}
                className="mb-10 h-auto w-36 max-w-[45%] sm:mb-7 sm:w-[172px] sm:max-w-full"
                priority
              />
              <h1 className="text-3xl font-extrabold tracking-tight drop-shadow-sm">App Fomizero Entregador</h1>
              <p className="mt-3 text-sm leading-6 text-white/95 drop-shadow-sm">Receba pedidos, acompanhe sua rota e compartilhe sua localização em tempo real.</p>
            </div>
          </div>
          <div className="space-y-7 p-6 sm:p-10">
            <div>
              {downloadUrl ? (
                <a href={downloadUrl} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-5 py-3 text-center font-bold text-white shadow-sm transition hover:bg-red-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 sm:w-auto">
                  <Download className="h-5 w-5" aria-hidden="true" /> Baixar app para Android
                </a>
              ) : (
                <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm font-medium text-amber-900">O download está sendo preparado. Volte a esta página em breve.</p>
              )}
              {downloadUrl && <p className="mt-3 text-xs text-slate-500">Arquivo APK oficial do Fomizero{version ? ` · versão ${version}` : ""} · somente Android</p>}
            </div>
            <div className="border-t border-slate-100 pt-6">
              <h2 className="text-lg font-bold">Como instalar</h2>
              <ol className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
                <li className="flex gap-3"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-red-600" aria-hidden="true" /><span>Baixe o APK no seu celular Android e abra o arquivo após o download.</span></li>
                <li className="flex gap-3"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-red-600" aria-hidden="true" /><span>Se o Android solicitar, permita a instalação pelo navegador usado para baixar o arquivo.</span></li>
                <li className="flex gap-3"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-red-600" aria-hidden="true" /><span>Abra o Fomizero Entregador e entre com o acesso fornecido pelo restaurante.</span></li>
              </ol>
            </div>
            <p className="flex gap-2 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600"><ShieldCheck className="h-4 w-4 shrink-0 text-red-600" aria-hidden="true" /> Instale o app apenas pelo link oficial desta página. Para atualizar depois, baixe a versão nova aqui e instale sobre a anterior.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
