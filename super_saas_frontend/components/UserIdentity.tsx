"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import type { AdminUser } from "@/lib/auth";

interface UserIdentityProps {
  user: AdminUser;
  onLogout: () => Promise<void> | void;
}

export function UserIdentity({ user, onLogout }: UserIdentityProps) {
  const [isOpen, setIsOpen] = useState(false);
  const capsuleRef = useRef<HTMLDivElement | null>(null);

  const initials = useMemo(() => {
    const trimmedName = user.name?.trim();
    if (!trimmedName) {
      return user.email.slice(0, 1).toUpperCase();
    }
    return trimmedName.slice(0, 1).toUpperCase();
  }, [user.email, user.name]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (!capsuleRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    window.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  return (
    <div ref={capsuleRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors duration-[120ms] hover:bg-black/[0.04]"
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-700">
          {initials}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{user.name}</p>
          <p className="truncate text-xs font-medium text-slate-500">{user.role}</p>
        </div>
        <ChevronDown className="h-4 w-4 text-slate-500" />
      </button>

      <div
        className={`absolute right-0 z-30 mt-2 w-64 origin-top-right rounded-xl border border-black/[0.08] bg-white p-2 shadow-[0_8px_24px_rgba(15,23,42,0.10)] transition-all duration-[120ms] ${
          isOpen ? "pointer-events-auto scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0"
        }`}
        role="menu"
      >
        <div className="rounded-lg px-3 py-2">
          <p className="text-sm font-semibold text-slate-900">{user.name}</p>
          <p className="text-xs text-slate-500">{user.email}</p>
          <p className="mt-1 text-xs font-medium text-slate-600">{user.role}</p>
        </div>
        <div className="my-2 h-px bg-slate-200" />
        <button
          type="button"
          className="flex w-full rounded-lg px-3 py-2 text-sm text-slate-700 transition-colors duration-[120ms] hover:bg-slate-100"
          role="menuitem"
          onClick={() => setIsOpen(false)}
        >
          Meu perfil
        </button>
        <button
          type="button"
          className="flex w-full rounded-lg px-3 py-2 text-sm text-slate-700 transition-colors duration-[120ms] hover:bg-slate-100"
          role="menuitem"
          onClick={() => setIsOpen(false)}
        >
          Configurações
        </button>
        <button
          type="button"
          className="mt-1 flex w-full rounded-lg px-3 py-2 text-sm text-red-600 transition-colors duration-[120ms] hover:bg-red-50"
          role="menuitem"
          onClick={async () => {
            setIsOpen(false);
            await onLogout();
          }}
        >
          Sair
        </button>
      </div>
    </div>
  );
}
