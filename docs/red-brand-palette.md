# Paleta institucional vermelha

O vermelho é a cor de marca e de destaque do Fomizero. A escala `brand` continua sendo a base, com primária #dc2626 e hover #b91c1c. Os aliases `accent` e `--color-accent` agora apontam para a mesma família vermelha.

Foram retirados amarelo/âmbar e laranja dos componentes padrão: VIP, promoções, cupom, gráfico, cozinha, pedidos, entregas, mapas, recebimentos, assinatura, avisos, checkout e indicadores de conexão. VIP e destaques usam tons de vermelho; avisos comuns usam neutros. Rótulos, ícones, critérios, mensagens, permissões e transições de status permanecem iguais.

Estados de sucesso continuam verdes e estados informativos podem usar azul. A personalização dos restaurantes mantém seu funcionamento. Os tokens dourados de `styles/menu-tokens.css` pertencem aos temas legados/customizados das lojas; o perfil padrão Fomizero sobrescreve esses valores em modo claro e escuro. Os arquivos oficiais da nova logo foram preservados.

Contrastes conferidos: branco/primária 4,83:1; vermelho escuro/fundo rosa 5,89:1; branco/aviso neutro 10,35:1; destaque claro/fundo escuro acima de 9:1. Os botões de ação antes laranja com texto branco passam para o vermelho principal.

Validação: TypeScript da aplicação, suíte frontend, navegação mobile/desktop, clientes com filtros e paginação, tabelas responsivas e perfil padrão do cardápio nos dois temas. Nenhum dado real foi alterado durante os testes.

Publicação somente do frontend, inicialmente em staging. Sem novas variáveis ou migrações. A alteração não regrava cores configuradas por lojas nem muda regras de negócio.
