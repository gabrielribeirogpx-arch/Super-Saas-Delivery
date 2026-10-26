# Acabamento do cardápio público e checkout

O perfil padrão Fomizero recebe cards com espaçamento mais generoso, categorias em pílulas, alvos de toque maiores e duas colunas a partir de 768px. Os temas legados e personalizados das lojas mantêm seus tokens e suas configurações. A preferência claro/escuro só é persistida depois da leitura inicial, evitando que a montagem da página sobrescreva o tema salvo.

O checkout usa um painel com cabeçalho, área central rolável e rodapé próprio. No celular ocupa a área útil da tela, com safe areas; no desktop aparece em uma janela central. O rodapé mantém os valores discriminados e a ação disponíveis, inclusive em alturas menores. Etapas de identificação compartilham o indicador Dados; o envio mantém o indicador Pagamento e apresenta estado de espera.

Campos possuem rótulos persistentes, autocomplete e fonte de 16px. Retirada, entrega, mesa e métodos de pagamento têm estados selecionados visíveis. Cupom e pontos ficam em uma seção opcional expansível. O resumo de confirmação recebe o mesmo acabamento; o verde continua reservado ao sucesso/acompanhamento. O diálogo contém o foco, restaura o elemento anterior e bloqueia a rolagem de fundo. Animações respeitam prefers-reduced-motion.

Nenhuma integração, endpoint, preço, taxa, método disponível, payload, cálculo, validação, recuperação de tentativa ou regra de cobrança foi alterado. A taxa continua sendo a taxa configurada da loja; não há nova simulação de frete nem cálculo de desconto no cliente.

Validação automatizada usa apenas fixtures: oito combinações entre 320/390/768/1366px e claro/escuro, fluxo de entrega com CEP simulado, validação obrigatória, edição de quantidade/tipo, valores, cupom, foco e viewport reduzido. Regressões existentes conferem meios indisponíveis, falha/recarregamento da política e reenvio com resposta perdida sem duplicação. O workflow Public checkout regression repete esses cenários no PR e disponibiliza capturas.

Deploy somente do frontend, primeiro em staging; sem migrações ou novas variáveis. Conferir uma loja com imagens reais, variações/adicionais, navegação Voltar, endereço, retirada e confirmação antes de promover produção.
