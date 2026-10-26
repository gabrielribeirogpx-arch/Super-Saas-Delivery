"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, LogOut, Settings, UserRound } from "lucide-react";

import type { AdminUser } from "@/lib/auth";

interface UserIdentityProps {
  user: AdminUser;
  onLogout: () => Promise<void> | void;
  dropdownSide?: "top" | "bottom";
  className?: string;
}

const DROPDOWN_GAP = 10;
const VIEWPORT_PADDING = 12;
const DROPDOWN_WIDTH = 272;
const DROPDOWN_MIN_WIDTH = 240;

interface DropdownPosition {
  left: number;
  top?: number;
  bottom?: number;
  width: number;
  originClass: string;
  maxHeight: number;
}

export function UserIdentity({ user, onLogout, dropdownSide = "bottom", className = "" }: UserIdentityProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState<DropdownPosition>({
    bottom: 0,
    left: 0,
    width: DROPDOWN_WIDTH,
    originClass: "origin-bottom-left",
    maxHeight: 360,
  });
  const capsuleRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const initials = useMemo(() => {
    const trimmedName = user.name?.trim();
    if (!trimmedName) {
      return user.email.slice(0, 1).toUpperCase();
    }
    return trimmedName.slice(0, 1).toUpperCase();
  }, [user.email, user.name]);

  const updateDropdownPosition = useCallback(() => {
    const capsule = capsuleRef.current;
    const trigger = triggerRef.current;
    const menu = menuRef.current;

    if (!capsule || !trigger || !menu) {
      return;
    }

    const capsuleRect = capsule.getBoundingClientRect();
    const triggerRect = trigger.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();
    const boundaryElement = capsule.closest("aside, header") as HTMLElement | null;
    const boundaryRect = boundaryElement?.getBoundingClientRect();
    const viewportLeft = VIEWPORT_PADDING;
    const viewportRight = window.innerWidth - VIEWPORT_PADDING;
    const viewportTop = VIEWPORT_PADDING;
    const viewportBottom = window.innerHeight - VIEWPORT_PADDING;
    const boundaryLeft = Math.max(boundaryRect?.left ?? viewportLeft, viewportLeft);
    const boundaryRight = Math.min(boundaryRect?.right ?? viewportRight, viewportRight);
    const boundaryTop = Math.max(boundaryRect?.top ?? viewportTop, viewportTop);
    const boundaryBottom = Math.min(boundaryRect?.bottom ?? viewportBottom, viewportBottom);
    const availableWidth = Math.max(DROPDOWN_MIN_WIDTH, boundaryRight - boundaryLeft);
    const width = Math.min(DROPDOWN_WIDTH, availableWidth, viewportRight - viewportLeft);

    const preferredLeft = triggerRect.left;
    const clampedLeft = Math.min(Math.max(preferredLeft, boundaryLeft), boundaryRight - width);
    const left = clampedLeft - capsuleRect.left;
    const menuHeight = menuRect.height;
    const availableAbove = triggerRect.top - boundaryTop - DROPDOWN_GAP;
    const availableBelow = boundaryBottom - triggerRect.bottom - DROPDOWN_GAP;
    const shouldOpenAbove =
      dropdownSide === "top"
        ? availableAbove >= Math.min(menuHeight, availableBelow)
        : availableBelow < menuHeight && availableAbove > availableBelow;

    if (shouldOpenAbove) {
      setDropdownPosition({
        bottom: capsuleRect.bottom - triggerRect.top + DROPDOWN_GAP,
        left,
        width,
        originClass: "origin-bottom-left",
        maxHeight: Math.max(160, Math.floor(availableAbove)),
      });
      return;
    }

    setDropdownPosition({
      left,
      top: triggerRect.bottom - capsuleRect.top + DROPDOWN_GAP,
      width,
      originClass: "origin-top-left",
      maxHeight: Math.max(160, Math.floor(availableBelow)),
    });
  }, [dropdownSide]);

  useLayoutEffect(() => {
    if (!isOpen) {
      return;
    }

    updateDropdownPosition();
  }, [isOpen, updateDropdownPosition]);

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
    window.addEventListener("resize", updateDropdownPosition);
    window.addEventListener("scroll", updateDropdownPosition, true);

    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleEscape);
      window.removeEventListener("resize", updateDropdownPosition);
      window.removeEventListener("scroll", updateDropdownPosition, true);
    };
  }, [isOpen, updateDropdownPosition]);

  return (
    <div ref={capsuleRef} className={`relative ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors duration-150 ease-out hover:bg-black/[0.04]"
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-700">
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900">{user.name}</p>
          <p className="truncate text-xs font-medium text-slate-500">{user.role}</p>
        </div>
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-150 ${isOpen ? "rotate-180" : ""}`} />
      </button>

      <div
        ref={menuRef}
        className={`absolute z-30 rounded-2xl border border-black/[0.08] bg-white p-2.5 shadow-[0_18px_45px_rgba(15,23,42,0.16)] ring-1 ring-black/[0.02] overflow-y-auto transition-all duration-150 ease-out ${dropdownPosition.originClass} ${
          isOpen ? "pointer-events-auto scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0"
        }`}
        style={{
          bottom: dropdownPosition.bottom,
          left: dropdownPosition.left,
          top: dropdownPosition.top,
          width: dropdownPosition.width,
          maxHeight: dropdownPosition.maxHeight,
        }}
        role="menu"
        aria-hidden={!isOpen}
      >
        <div className="flex items-center gap-3 rounded-xl px-3 py-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-200 text-base font-semibold text-slate-700 shadow-inner">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold leading-5 text-slate-950">{user.name}</p>
            <p className="truncate text-xs leading-5 text-slate-500">{user.email}</p>
            <p className="mt-1 inline-flex max-w-full rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              <span className="truncate">{user.role}</span>
            </p>
          </div>
        </div>
        <div className="my-2 h-px bg-slate-200/80" />
        <Link
          href="/profile"
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 transition-colors duration-150 hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
          role="menuitem"
          tabIndex={isOpen ? 0 : -1}
          onClick={() => setIsOpen(false)}
        >
          <UserRound className="h-4 w-4 text-slate-500" />
          Meu perfil
        </Link>
        <Link
          href="/settings"
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 transition-colors duration-150 hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
          role="menuitem"
          tabIndex={isOpen ? 0 : -1}
          onClick={() => setIsOpen(false)}
        >
          <Settings className="h-4 w-4 text-slate-500" />
          Configurações
        </Link>
        <div className="my-2 h-px bg-slate-200/80" />
        <button
          type="button"
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-semibold text-red-600 transition-colors duration-150 hover:bg-red-50"
          role="menuitem"
          tabIndex={isOpen ? 0 : -1}
          onClick={async () => {
            setIsOpen(false);
            await onLogout();
          }}
        >
          <LogOut className="h-4 w-4" />
          Sair
        </button>
      </div>
    </div>
  );
}
