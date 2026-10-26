# Travas comerciais dos contratos Hotmart

A política é aplicada no backend, independentemente do menu, da flag que habilita
o checkout e de IDs fornecidos pelo navegador. Contratos de outros provedores e
lojas sem assinatura seguem a compatibilidade anterior; não há migração implícita.
RBAC e isolamento de tenant permanecem obrigatórios e não são substituídos pelo plano.

| Recurso | Essencial | Operação | Pro |
|---|---:|---:|---:|
| Pedidos por mês | 300 | 1500 | 5000 |
| Usuários ativos da equipe, incluindo proprietário | 1 | 3 | 10 |
| Entregadores ativos | 1 | 5 | 15 |
| Estoque, cupons, WhatsApp, GPS | não | sim | sim |
| Fidelidade/recompensas, domínio próprio, relatórios | não | não | sim |

O catálogo existente continua sendo a fonte dos valores; esta mudança não
re-semeia nem sobrescreve edições comerciais. Pedidos são contados por mês civil
UTC, conforme regra existente, e não pelo aniversário da cobrança.

## Usuários

Criar usuário/entregador, reativar ou mover entregador para equipe exige capacidade
da categoria de destino. O proprietário ocupa uma vaga; contas inativas não contam.
Todas essas admissões, incluindo bootstrap administrativo, bloqueiam a linha da
loja até commit antes de contar vagas. PostgreSQL testa criação e reativação
concorrentes para a última vaga.

Editar um usuário já ativo sem mudar de categoria, desativar e recuperar senha
continuam possíveis após vencimento ou downgrade. Não se excluem usuários ou dados
para caber no plano menor: bloqueia-se crescimento enquanto exceder o limite. Não
há expulsão arbitrária de pessoas já ativas; RBAC continua controlando suas ações.

## Recursos

- Estoque: todas as rotas de itens, movimentos e receitas exigem `inventory`.
  Baixa automática de estoque não roda para contratos sem o recurso. Movimentos
  anteriores não são revertidos.
- Relatórios: `/api/reports` exige `advanced_reports`. Financeiro e histórico não
  dependem dessa permissão e permanecem disponíveis para conferência de valores.
- Cupons: gestão, validação pública e aplicação no checkout exigem `coupons`.
- Fidelidade: gestão/recompensas, resgate e geração de novos pontos exigem `loyalty`.
  Saldos e dados históricos não são apagados.
- WhatsApp: configuração/testes/logs administrativos exigem `whatsapp`; entrada
  não inicia conversas/IA quando indisponível, e a camada de saída não chama o
  provedor, inclusive em ações automáticas.
- Domínio próprio: configurar ou usar domínio customizado exige `custom_domain`.
  Removê-lo continua permitido. O subdomínio padrão Fomizero segue disponível para
  login, histórico e regularização. Onboarding não cadastra domínio pago antes da assinatura.
- GPS: aquisição HTTP e publicação WebSocket, mapas e fluxos alternativos são
  protegidos. O resumo público e a linha do tempo continuam funcionando no
  Essencial, mas sem coordenadas ou métricas de rota. Streams revalidam o plano
  durante a conexão; mudanças no contrato são observadas no próximo ciclo de leitura.

Integrações externas ainda exigem suas configurações reais: um plano não cria
credenciais WhatsApp/Maps nem garante disponibilidade desses serviços. A IA não
possui entitlement próprio nesta matriz; este trabalho não cria uma nova oferta de IA.

## Sem assinatura ativa

Inativo, vencido, cancelado ou estornado não recebe novos pedidos nem usa recursos
pagos ou adiciona vagas. Fim de período é avaliado em cada acesso; não depende de o
cron já ter marcado a expiração. Cancelamento agendado conserva o período pago.
Não há tolerância inventada; `past_due` só permite uso se houver `grace_until`
explícito e válido conforme política existente (Hotmart não cria esse prazo).

Login, assinatura/pagamento, financeiro, listagem de usuários e pedidos existentes
continuam disponíveis. Menus mostram `Exige plano`; acesso direto à página exibe
explicação e link para assinatura. Erro ao consultar acesso não libera a página.
Limites de criação aparecem nos controles de equipe/entregadores, enquanto o
backend continua sendo a autoridade mesmo se o navegador usar dados antigos.

`GET /api/admin/billing/access` é autenticado, com `Cache-Control: private, no-store`,
e usa apenas a loja da sessão. Retorna capacidade/uso e motivos, sem dados pessoais,
credenciais ou possibilidade de escolher outro tenant por query/header.

## Verificação em staging

1. Em loja Hotmart sem pagamento, tentar novo pedido e criar usuário/entregador:
   negar, mantendo listagens/financeiro/assinatura acessíveis.
2. Em contratos de teste com período pago válido, verificar valores e flags dos
   três planos. Não ativar uma loja de vendas por alteração manual no banco.
3. Conferir limite na criação e reativação, troca de função, exclusão lógica e
   resposta 403 estruturada mesmo chamando a API diretamente.
4. Abrir recurso não contratado pelo menu e por URL. Em celular, conferir o aviso.
5. Confirmar linha do tempo sem GPS no Essencial e funcionamento de pedidos
   existentes após vencimento, sem novos pedidos ou crescimento de equipe.
6. Rotação de credenciais após incidente e homologação real Hotmart continuam
   etapas separadas. Estes testes não efetuam cobranças.
