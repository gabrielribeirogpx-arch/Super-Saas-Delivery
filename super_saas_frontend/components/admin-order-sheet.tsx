"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

export function AdminOrderSheet({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  // Keep the latest callback without reopening the sheet on query updates.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const focus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const overflow = document.body.style.overflow;
    const desktop = window.matchMedia("(min-width: 1680px)");
    const sync = () => {
      if (desktop.matches) {
        if (dialog.open) {
          dialog.close();
          document.body.style.overflow = overflow;
        }
      } else if (!dialog.open) {
        dialog.showModal();
        dialog
          .querySelector<HTMLButtonElement>(
            'button[aria-label="Fechar detalhes"]',
          )
          ?.focus({ preventScroll: true });
        document.body.style.overflow = "hidden";
      }
    };
    sync();
    desktop.addEventListener("change", sync);
    return () => {
      desktop.removeEventListener("change", sync);
      dialog.close();
      document.body.style.overflow = overflow;
      focus?.focus({ preventScroll: true });
    };
  }, []);
  if (typeof document === "undefined") return null;
  return createPortal(
    <dialog
      ref={ref}
      aria-label="Detalhes do pedido"
      onCancel={() => closeRef.current()}
      onClick={(event) => {
        if (event.target === event.currentTarget) closeRef.current();
      }}
      style={{ background: "transparent" }}
      className="admin-shell fixed inset-0 m-0 h-dvh max-h-none w-full max-w-none p-0 backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm"
    >
      {children}
    </dialog>,
    document.body,
  );
}
