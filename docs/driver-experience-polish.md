# Experiência do entregador

Painel com a identidade vermelha, indicadores compactos, cards de pedidos com destino e pagamento legíveis e navegação para a entrega ativa. O menu do cabeçalho mantém acesso à conta e saída; atalhos que levavam todos ao mesmo painel foram substituídos por Meu painel e Entrega ativa.

Detalhes usam cabeçalho fixo, painel central rolável e ação principal fora da área de rolagem, acima da navegação inferior. O mapa continua usando a integração existente. Seus controles aparecem acima do painel quando o mapa está pronto; na ausência de mapa, a tela orienta o uso dos links de Google Maps/Waze, sem inventar distância ou previsão.

A entrega é carregada imediatamente a partir das listas que a API já retorna (ativa, atribuídas ou disponíveis). O detalhe de um pedido disponível permite aceitar; depois, iniciar com permissão de GPS; em rota, concluir com confirmação cancelável. Os mesmos endpoints são usados. Falhas mantêm a etapa atual e apresentam feedback; bloqueios de ação evitam envio repetido. Uma ação colocada na fila offline existente não é apresentada como confirmada. Nenhuma alteração foi feita na fila offline, nas regras de atribuição do backend ou nos serviços de GPS.

Botões que apenas exibiam mensagens sem persistência (chegada e problema) foram retirados. Ajuda orienta contato com a loja pelo canal combinado, sem afirmar que houve registro. Links para cliente são opcionais e continuam dependendo de telefone válido. Exibir forma de pagamento não significa confirmação de recebimento.

Testes em navegador com fixtures de sessão, API e GPS cobrem 320/390/768/1366px: offline, duplo clique, conflito de aceite, permissão negada, erro/reenvio de início e conclusão, cancelamento da confirmação, viewport de altura reduzida e detalhes antes de aceitar. Capturas são guardadas pelo workflow Driver experience regression. Nenhuma entrega, mensagem ou localização real é enviada.

Deploy somente frontend, primeiro em staging. Antes de promover produção, validar no celular real a permissão de localização, o mapa configurado e uma entrega completa. O teste sintético não comprova GPS em segundo plano; a orientação continua sendo manter a tela aberta durante a entrega.
