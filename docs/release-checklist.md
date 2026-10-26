# Checklist de Release

## Critérios obrigatórios antes de deploy

- [ ] CI em PR está **100% verde** para os jobs:
  - [ ] `backend-tests` (`pytest` focado em auth admin, pedidos, pagamentos e autorização por tenant)
  - [ ] `frontend-smoke` (smoke de login e páginas admin críticas)
- [ ] Cenários com fixtures de **happy-path** e **negação de acesso** executados sem regressões.
- [ ] Nenhum teste crítico foi marcado como skip no branch de release.
- [ ] Mudanças com impacto de autenticação/autorização revisadas por pelo menos 1 pessoa do time.
- [ ] Evidências de execução dos testes anexadas ao PR (logs do GitHub Actions).

## Gate de deploy

> Deploy para staging e produção só pode ocorrer quando a suíte obrigatória deste checklist estiver verde no PR correspondente.
