# GA4 do funil de assinatura

ID de medição: `G-HDBVG6L1NT`. A landing `fomizero.com.br` é publicada pelo Sites; as páginas comerciais do sistema são servidas pelo frontend em `www.fomizero.com.br`. O checkout pertence à Hotmart.

| Etapa | Local | GA4 do Fomizero |
| --- | --- | --- |
| Visita e escolha do plano | `fomizero.com.br/` | `page_view`, `plan_selected` |
| Cadastro | `www.fomizero.com.br/onboarding` | `page_view`, `sign_up` após criação da loja |
| Saída para pagamento | Mesmo cadastro | `begin_checkout` após validar o link da Hotmart |
| Checkout e pagamento | `pay.hotmart.com` | Depende da configuração de rastreamento na conta Hotmart |
| Retorno opcional | `www.fomizero.com.br/continuar` | `page_view`; **não** indica compra aprovada |

O script do GA4 no frontend só carrega após consentimento nas páginas comerciais do host `www.fomizero.com.br`. Uma nova escolha é solicitada porque o aceite antigo cobria apenas a Meta. URLs enviadas como `page_location` não incluem parâmetros ou fragmentos. Nenhuma página em subdomínios de restaurantes recebe a tag, inclusive `/subscriptions` do proprietário; a Meta pode continuar medindo essa página após consentimento.

## Para completar a medição da compra

Configurar o rastreamento do checkout na **conta Hotmart** para o mesmo fluxo GA4 e conferir quais eventos de pagamento aprovado ela envia. As configurações e nomes dos menus dependem da conta e do produto. O frontend não instala scripts em `pay.hotmart.com` e não cria `purchase` ao abrir o checkout ou ao voltar para `/continuar`. Validar uma compra de teste antes de usar `purchase` como conversão em campanhas.

No GA4, verificar `page_view`, `plan_selected`, `sign_up` e `begin_checkout` em **Relatórios → Engajamento → Eventos**. Em **Explorar → Exploração de funil**, ordenar esses eventos; a confirmação de compra só entra depois da configuração e validação na Hotmart. O parâmetro personalizado `plan` exige uma dimensão personalizada no GA4 para aparecer nos relatórios padrão.
