export interface SubscriptionOffer {
  code: string; name: string; price_cents: number;
  features: { code: string; enabled: boolean; limit: number | null }[];
}
export interface MySubscription {
  enabled: boolean; provider: string | null; status: string; plan_name: string | null;
  period_end: string | null; cancel_at_period_end: boolean; cancel_pending: boolean;
  can_cancel: boolean; can_checkout: boolean; checkout_pending: boolean;
  offers: SubscriptionOffer[];
  events: { type: string; received_at: string; status: string }[];
}
export const subscriptionStatuses: Record<string,string> = {
  not_contracted: "Ainda não contratada", inactive: "Aguardando contratação", trialing: "Em teste",
  active: "Ativa", past_due: "Pagamento pendente", canceled: "Cancelada", expired: "Período encerrado",
};
export const subscriptionFeatureNames: Record<string,string> = {
  orders_monthly: "Pedidos por mês", admin_users: "Usuários da equipe", delivery_users: "Entregadores",
  tracking: "Acompanhamento de entregas", whatsapp: "Integração com WhatsApp", inventory: "Estoque",
  coupons: "Cupons", loyalty: "Fidelidade", custom_domain: "Domínio próprio", advanced_reports: "Relatórios avançados",
};
export function validatedHotmartCheckout(value: string) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.hostname !== "pay.hotmart.com" || url.port || url.username || url.password || url.hash) {
    throw new Error("Endereço de contratação inválido. Atualize a página ou fale com o suporte.");
  }
  return url.href;
}
