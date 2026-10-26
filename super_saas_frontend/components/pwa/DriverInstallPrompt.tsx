"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

type NavigatorWithStandalone = Navigator & { standalone?: boolean };
type NavigatorWithUserAgentData = Navigator & { userAgentData?: { mobile?: boolean } };

const IOS_INSTALL_HINT_DISMISSED_KEY = "driverPwaIosInstallHintDismissed";

const isIos = () =>
  /iphone|ipad|ipod/i.test(window.navigator.userAgent) ||
  (window.navigator.platform === "MacIntel" && window.navigator.maxTouchPoints > 1);
const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  Boolean((window.navigator as NavigatorWithStandalone).standalone);
const isDriverRoute = (pathname: string | null) =>
  pathname === "/driver" || Boolean(pathname?.startsWith("/driver/"));

export const isMobileDevice = () => {
  const userAgentDataMobile = (window.navigator as NavigatorWithUserAgentData).userAgentData?.mobile;
  if (typeof userAgentDataMobile === "boolean") return userAgentDataMobile;

  const userAgent = window.navigator.userAgent.toLowerCase();
  const hasMobileUserAgent = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/i.test(
    userAgent,
  );
  const hasCoarsePointer = window.matchMedia("(pointer: coarse)").matches;
  const hasNoHover = window.matchMedia("(hover: none)").matches;
  const hasMobileViewport = window.innerWidth > 0 && window.innerWidth <= 768;

  return (
    hasMobileUserAgent ||
    (hasCoarsePointer && hasNoHover) ||
    (hasMobileViewport && (hasCoarsePointer || hasNoHover))
  );
};

export default function DriverInstallPrompt() {
  const pathname = usePathname();
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [standalone, setStandalone] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [ios, setIos] = useState(false);
  const [iosHintDismissed, setIosHintDismissed] = useState(true);

  useEffect(() => {
    setStandalone(isStandalone());
    setMobile(isMobileDevice());
    setIos(isIos());
    setIosHintDismissed(localStorage.getItem(IOS_INSTALL_HINT_DISMISSED_KEY) === "true");

    const onDisplayModeChange = () => setStandalone(isStandalone());
    const standaloneMedia = window.matchMedia("(display-mode: standalone)");
    standaloneMedia.addEventListener("change", onDisplayModeChange);

    return () => standaloneMedia.removeEventListener("change", onDisplayModeChange);
  }, []);

  useEffect(() => {
    const onBeforeInstallPrompt = (event: Event) => {
      if (isStandalone() || !isMobileDevice() || isIos() || !isDriverRoute(window.location.pathname)) {
        return;
      }

      event.preventDefault();
      console.info("[PWA] beforeinstallprompt received.");
      setInstallEvent(event as BeforeInstallPromptEvent);
    };
    const onAppInstalled = () => {
      console.info("[PWA] appinstalled received.");
      setInstallEvent(null);
      setStandalone(true);
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  useEffect(() => {
    if (!isDriverRoute(pathname)) setInstallEvent(null);
  }, [pathname]);

  if (standalone || !mobile || !isDriverRoute(pathname)) return null;

  if (installEvent && !ios) {
    return (
      <button
        type="button"
        className="fixed bottom-4 right-4 z-[9997] rounded-full bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-xl"
        onClick={async () => {
          await installEvent.prompt();
          const choice = await installEvent.userChoice;
          console.info("[PWA] install prompt choice.", choice);
          setInstallEvent(null);
        }}
      >
        Instalar aplicativo
      </button>
    );
  }

  if (ios && !iosHintDismissed) {
    return (
      <div
        className="fixed bottom-4 right-4 z-[9997] max-w-xs rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs font-medium text-slate-800 shadow-xl"
        role="status"
        aria-live="polite"
      >
        <button
          type="button"
          className="absolute right-2 top-1 text-base leading-none text-slate-500"
          aria-label="Fechar orientação de instalação"
          onClick={() => {
            localStorage.setItem(IOS_INSTALL_HINT_DISMISSED_KEY, "true");
            setIosHintDismissed(true);
          }}
        >
          ×
        </button>
        <p className="pr-4">
          No Safari, toque em Compartilhar e depois em Adicionar à Tela de Início.
        </p>
      </div>
    );
  }

  return null;
}
