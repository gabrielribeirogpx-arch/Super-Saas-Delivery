"use client";
import { useEffect, useRef } from "react";
type TurnstileApi = { render: (element: HTMLElement, options: Record<string, unknown>) => string; remove: (id: string) => void };
declare global { interface Window { turnstile?: TurnstileApi } }
export default function Turnstile({ siteKey, onToken, attempt }: { siteKey: string; onToken: (token: string) => void; attempt: number }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let id: string | undefined; let stopped = false;
    const render = () => {
      if (stopped || id || !container.current || !window.turnstile) return;
      id = window.turnstile.render(container.current, { sitekey: siteKey, action: "signup", callback: onToken,
        "expired-callback": () => onToken(""), "error-callback": () => onToken("") });
    };
    let script = document.querySelector<HTMLScriptElement>("script[data-turnstile]");
    if (!script) {
      script = document.createElement("script"); script.dataset.turnstile = "1";
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true; document.head.appendChild(script);
    }
    script.addEventListener("load", render); render();
    return () => { stopped = true; script?.removeEventListener("load", render); if (id) window.turnstile?.remove(id); };
  }, [siteKey, onToken, attempt]);
  return <div><div ref={container} /><p className="text-xs text-slate-500">Se a verificação não aparecer, recarregue a página.</p></div>;
}
