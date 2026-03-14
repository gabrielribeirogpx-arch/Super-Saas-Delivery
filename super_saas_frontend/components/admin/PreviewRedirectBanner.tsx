"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

interface PreviewRedirectBannerProps {
  storageKey: string;
}

export function PreviewRedirectBanner({ storageKey }: PreviewRedirectBannerProps) {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    const hidden = window.localStorage.getItem(storageKey) === "1";
    setDismissed(hidden);
  }, [storageKey]);

  if (dismissed) {
    return null;
  }

  return (
    <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <p>
        ⚡ Agora você pode editar e visualizar tudo em tempo real em Prévia do Cardápio.
      </p>
      <div className="flex items-center gap-2">
        <Button asChild size="sm" variant="outline">
          <Link href="/storefront-preview">Ir para Prévia</Link>
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            window.localStorage.setItem(storageKey, "1");
            setDismissed(true);
          }}
        >
          Fechar
        </Button>
      </div>
    </div>
  );
}
