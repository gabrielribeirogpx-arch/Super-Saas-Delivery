"use client";

import AppearancePanel from "@/components/admin/AppearancePanel";
import { PreviewRedirectBanner } from "@/components/admin/PreviewRedirectBanner";

export default function AppearancePage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-6 py-2">
      <PreviewRedirectBanner storageKey="redirect-banner:appearance" />
      <AppearancePanel />
    </div>
  );
}
