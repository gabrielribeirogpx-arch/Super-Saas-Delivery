# Revisão das tabelas no painel mobile

As listas que ainda exigiam rolagem horizontal ou espremiam colunas foram adaptadas com `Table mobileCards` e `TableCell mobileLabel`. Abaixo de 1024 px, cada registro tem apresentação de cartão com seus campos rotulados; acima disso, continua uma tabela. Ações ficam numa área própria, com quebra de linha e alvos de toque maiores.

Não há cópia de botões ou de registros entre duas árvores: o mesmo conteúdo, callbacks, estados desabilitados e consultas continuam sendo usados. Cabeçalhos ficam visualmente ocultos no mobile, com papéis semânticos explícitos de tabela/linha/célula. Os rótulos visuais extras são ocultos dos leitores de tela para evitar leitura duplicada do cabeçalho.

## Cobertura

| Área | Listas adaptadas |
| --- | --- |
| Estoque | Itens atuais e movimentações |
| Relatórios | Top itens e baixo estoque |
| Financeiro | Movimentos do caixa e recebimentos manuais |
| Usuários | Contas existentes e suas ações |
| Entregadores | Cadastro e suas ações |
| Auditoria | Registros com usuário, ação, entidade e data |
| WhatsApp | Logs recentes |
| IA | Logs recentes |
| Marketing | Cupons e recompensas |
| Assinaturas | Revisões pendentes |

Total: 14 tabelas em 11 páginas, incluindo o componente compartilhado de recebimentos. Pedidos, clientes e tabelas do início já possuíam apresentação mobile própria e mantêm o modo anterior. Também foram corrigidos os botões de exportação de relatórios e a paginação dos recebimentos, que ultrapassavam a largura do celular.

## Validação

`npm run test:responsive-tables:browser` usa fixtures locais, sem API ou provedores reais. Requer frontend local, Chromium/Chrome e Node compatível com puppeteer-core. Variáveis: `RESPONSIVE_TABLES_TEST_BASE_URL`, `CHROMIUM_PATH` e `RESPONSIVE_TABLES_ARTIFACT_DIR`. O script cobre as 11 rotas em 320, 390, 768 e 1366 px, todos os rótulos e campos, ausência de overflow, estados vazio/erro e abertura/fechamento de ações protegidas sem gravações.

As regressões de pagamentos existentes também foram executadas com fixtures: confirmação, conflito, permissão negada, cancelamento, devolução e falha de devolução. Os seletores desses testes foram delimitados ao dialog de pagamento porque agora existe também o dialog do menu de navegação. Nenhum recebimento ou transferência real é criado.

O workflow Mobile table regression repete essa cobertura em alterações de frontend e disponibiliza capturas com dados sintéticos. O histórico de pedidos e a suíte frontend existente também foram conferidos localmente.

## Implantação

Publicar somente frontend em staging e conferir em celular real, incluindo Safari/iOS e navegação por leitor de tela. Chromium com viewport simulado não substitui essa conferência. Sem migrações, variáveis novas, alterações financeiras, mudanças de permissão ou consultas adicionais. O modo responsivo é opt-in para não modificar tabelas de outros contextos.
