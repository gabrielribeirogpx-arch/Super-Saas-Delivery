import { CustomerBottomNav } from "@/components/storefront/CustomerBottomNav";

export default function CustomerAccountLayout({ children }: { children: React.ReactNode }) {
  return <div className="pb-[calc(var(--customer-bottom-nav-height)+var(--customer-safe-bottom)+16px)] md:pb-0">
    {children}
    <CustomerBottomNav />
  </div>;
}
