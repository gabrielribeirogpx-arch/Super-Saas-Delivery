# Lojas sintéticas para carga no staging

`scripts/prepare_load_stores.py` cria carga-01 a carga-05, cada uma com 3 categorias,
18 produtos e um proprietário `carga@example.com`. Uma senha exclusiva de teste,
fornecida em prompt oculto, é usada nos cinco administradores. Nada é enviado por email.

O CLI exige os IDs exatos do projeto e serviço Railway de staging e conexão PostgreSQL.
O ambiente Railway pode chamar-se production; a proteção usa identidade do projeto e
serviço, não esse nome. Se os IDs mudarem, revise a configuração; não remova a proteção.
Como qualquer script no serviço, ele usa o DATABASE_URL já configurado nesse backend;
a separação do banco staging/produção deve estar correta nas referências do Railway.

## Dados e limites

- Meu Burger e outros tenants não são alterados. Slugs já usados por dados diferentes
  causam falha, sem sobrescrita. Todas as inserções ficam em uma transação.
- Reexecução valida as fixtures, não redefine senhas, não renova assinaturas e não
  duplica produtos. PostgreSQL advisory lock serializa duas execuções simultâneas.
- Requer plano operation ativo já existente; não muda catálogo ou limites globais.
- Assinatura sintética local ativa por 7 dias, provider hotmart para exercitar as regras
  normais de acesso/cota, identificador fomizero-load-stores-v1:... e auditoria pelo
  SubscriptionService. Não cria binding HotmartSubscription, checkout, evento de
  pagamento ou chamada à Hotmart. Não representa venda ou pagamento real.
- WhatsApp explicitamente mock/desativado, sem credenciais, waba ou telefone; pontos
  desativados. O roteiro de carga usa retirada/dinheiro e cliente sem contato/endereço.
- Exige ao menos 100 pedidos restantes na cota por loja. A cota real depende do plano
  operation configurado no staging. Não a aumenta nem contorna sua aplicação.
- Pedidos de teste persistem e consomem a cota. Não há limpeza ou renovação automática.

## Executar no SSH do Backend - Staging

Com o arquivo já no backend após deploy:

```sh
/app/.venv/bin/python /app/scripts/prepare_load_stores.py
/app/.venv/bin/python /app/scripts/prepare_load_stores.py --apply
```

Sem deploy, baixe a versão revisada do script para /tmp e use o mesmo intérprete:

```sh
/app/.venv/bin/python /tmp/prepare_load_stores.py
/app/.venv/bin/python /tmp/prepare_load_stores.py --apply
```

Sem --apply, o comando apenas inspeciona. Com --apply, pede a senha duas vezes e
imprime relatório sem senha/hash/URL de conexão. Não passe senha pela linha de comando.

## Primeira rodada multiloja

Após conferir o relatório de criação, saia do SSH e use os scripts do PR #841:

```powershell
Set-Location "$HOME\Fomizero-Carga"
powershell -NoProfile -ExecutionPolicy Bypass -Command "& .\Start-OrdersKitchen.ps1 -Lojas carga-01,carga-02,carga-03,carga-04,carga-05 -Pedidos 50 -Fluxos 10"
```

São 50 pedidos no total, distribuídos em 5 lojas, não 50 por loja. Use carga@example.com
e a senha escolhida em cada prompt. Confira reconciliação final por tenant, HTTP
falhas/p95, métricas do backend/Postgres e stats da outbox antes/depois.
Isso ainda é lote curto; teste sustentado e escala maior requerem roteiro adicional.

## Verificação local

`pytest -q tests/test_prepare_load_stores.py`: guarda de destino, preview sem escrita,
criação/reexecução sem duplicar ou mudar senha/validade, rollback em colisão e fluxo
real de rotas FastAPI (checkout, replay, login, histórico, status, acesso negado a outra
loja) com SQLite isolado. Não substitui execução no Postgres do staging.
