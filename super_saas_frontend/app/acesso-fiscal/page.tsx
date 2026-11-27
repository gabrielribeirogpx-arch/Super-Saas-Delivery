import type { Metadata } from "next";

import { FiscalAccess } from "./fiscal-access";

export const metadata: Metadata = {
  title: "Acesso fiscal | Fomizero",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function FiscalAccessPage() {
  return <FiscalAccess />;
}
