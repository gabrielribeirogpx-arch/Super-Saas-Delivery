# Recuperação de acesso do entregador

Na tela `/driver/login`, **Esqueci minha senha** abre `/driver/esqueci-senha`. O entregador informa o e-mail cadastrado pelo restaurante e o identificador da loja (preenchido pelo subdomínio quando disponível). A resposta pública é a mesma para conta inexistente, inativa, cargo incompatível, cooldown ou falha de entrega.

O Resend envia o modelo com logo, nome e restaurante. O botão abre `https://<loja>.<PASSWORD_RESET_BASE_DOMAIN>/driver/redefinir-senha#token=...`, com validade de 15 minutos e uso único. O token fica somente na memória da página e o fragmento é removido do endereço. A senha é alterada apenas após submissão válida; o e-mail seguinte confirma a troca e volta para `/driver/login`. Não há login automático, senha no e-mail, acesso administrativo ou liberação de assinatura.

## Contrato e segurança

- `POST /api/driver/auth/forgot-password`: `tenant_slug`, `email`, resposta 202 genérica.
- `POST /api/driver/auth/reset-password`: `tenant_slug`, `token`, `password` (8–72 caracteres), resposta 200 após troca válida; 400 para link inválido/expirado/usado.
- Somente `AdminUser` ativo com cargo `driver` ou `delivery` da loja ativa. O processo administrativo continua excluindo esses cargos. Tokens usam salt separado por público: links de um fluxo não funcionam no outro.
- Reutiliza o cooldown atômico no banco (60 s), limite público por processo, HMAC do hash atual, versão da credencial e atualização condicional para impedir dois consumos concorrentes. Auditoria não guarda e-mail, corpo, senha ou token.
- Login de entregador e alias legado emitem `credential_version`; APIs validam a versão atual, cargo, atividade e tenant. Tokens antigos sem versão são compatíveis apenas enquanto a conta estiver na versão 0.
- Os três sockets de entregador verificam a credencial na abertura e em cada mensagem recebida. Conexões antigas fecham na próxima mensagem; não há desconexão instantânea por push. Um socket de status ocioso pode permanecer aberto até enviar outra mensagem ou desconectar.
- Após reset bem-sucedido no navegador, remove a sessão local, estado em cache e ações pendentes. A confirmação administrativa de senha também usa `/driver/login` para entregadores.
- Recuperação pública não exige sessão nem envia o bearer antigo. As novas telas não montam os auxiliares do PWA; o service worker atualizado usa NetworkOnly para recuperação, sem fallback para dashboard. Recuperar a senha requer internet, com ou sem PWA instalado.

## Configuração e deploy

Reutiliza `RESEND_API_KEY`, `ADMIN_SESSION_SECRET`, `JWT_SECRET_KEY`, `PASSWORD_RESET_BASE_DOMAIN` e o domínio de envio já verificado. Produção: `fomizero.com.br`; staging: `staging.fomizero.com.br`. Não precisa nova chave, provedor ou migração: usa as colunas da migração administrativa existente `20261023_01_admin_recovery`.

Publicar backend e frontend. Em PWAs instalados, usar **Atualizar** quando a nova versão do service worker for oferecida. Não alterar DNS nem criar cobranças para testar.

## Verificação após deploy

1. Com um entregador ativo e e-mail seu, solicitar recuperação pelo login de entregas, em uma loja de teste.
2. Confirmar nome/loja, botão e rota `/driver/redefinir-senha` no e-mail; não compartilhar o link/token em capturas.
3. Alterar a senha, receber confirmação com `/driver/login`, entrar com a nova senha e confirmar acesso apenas às entregas.
4. Conferir que o link consumido é recusado e a senha antiga não autentica. Sessões anteriores devem exigir novo login na próxima chamada/mensagem.

O envio usa tarefa em processo, sem fila durável ou retentativa automática; falha de notificação não desfaz a senha. Entrega real depende da configuração do ambiente, Resend e caixa do destinatário. Não há recuperação por SMS/WhatsApp, criação de e-mail ou boas-vindas de funcionário neste escopo. O responsável continua podendo redefinir senhas no painel.

Teste de navegador com APIs simuladas: iniciar frontend na porta 3027 e executar `node tests/smoke/driverRecovery.browser.cjs` (ou definir `DRIVER_RECOVERY_TEST_BASE_URL`). Nenhuma mensagem real é enviada pelos testes.
