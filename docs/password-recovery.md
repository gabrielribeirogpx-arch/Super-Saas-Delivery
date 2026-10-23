# Recuperação de acesso administrativo — Resend

Escopo: proprietários e demais usuários administrativos do restaurante. Não redefine senhas de consumidores do cardápio, contas Hotmart nem contas de entregadores.

## Configuração e deploy

1. Domínio `fomizero.com.br` verificado no Resend; chave com Sending access, limitada ao domínio. O usuário já confirmou ter salvo `RESEND_API_KEY` nas variáveis do backend. O código não acessa, imprime nem valida essa chave real durante os testes.
2. Manter `ADMIN_SESSION_SECRET` forte e persistente. Ele assina as sessões e os links de recuperação com salts separados.
3. Definir `PASSWORD_RESET_BASE_DOMAIN=fomizero.com.br` no backend real ou `PASSWORD_RESET_BASE_DOMAIN=staging.fomizero.com.br` no Backend - Staging. Esse valor é uma base de domínio sem HTTPS/caminho, usada para formar `https://<loja>.<base>/redefinir-senha`. Não confiar no Host/Origin enviados pelo visitante para construir e-mails. Em staging, a ausência da variável impede solicitar recuperação, para não mandar links para produção por engano.
4. Aplicar `alembic upgrade head` até `20261023_01_admin_recovery` **antes** de iniciar o backend atualizado. A migração acrescenta `credential_version` (zero nas contas existentes) e `recovery_sent_at`, preservando as senhas atuais. O frontend pode ser publicado em seguida.
5. O remetente é `Fomizero <acesso@fomizero.com.br>`. Layout HTML, texto alternativo, logo PNG inline e confirmação após a troca estão descritos em `transactional-emails.md`. Não é preciso ativar recebimento de e-mail no Resend para enviar. Esse remetente não cria uma caixa postal de suporte. Manter o rastreamento de cliques e aberturas desativado para o domínio usado na recuperação.
6. Confirmar DNS/TLS dos subdomínios das lojas, proxy/API e CORS do ambiente. A chave fica apenas no backend, nunca em `NEXT_PUBLIC_*`.

## Jornada e proteção

Login → “Esqueci minha senha” → identificador da loja (preenchido automaticamente no subdomínio) + e-mail → resposta genérica → e-mail com link de 15 minutos → senha e confirmação → login normal.

A resposta não indica se a conta existe, está inativa, está em cooldown ou se o provedor falhou. O envio roda em tarefa de fundo após a resposta pública para evitar expor a existência de uma conta pelo tempo de resposta do Resend. Configuração ausente e limite global podem retornar 503/429 de forma independente do e-mail.

A assinatura do link tem finalidade exclusiva, inclui loja, usuário, versão de credencial e uma impressão HMAC do hash atual da senha. Não contém nome, e-mail, senha ou hash de senha. A validade é verificada no servidor. Trocar a senha invalida links anteriores. Uma atualização SQL condicional garante que somente uma tentativa consuma a versão da credencial, mesmo com solicitações concorrentes. A senha é guardada pelo serviço de hashing existente, nunca em texto.

O token vai no **fragmento** (`#token=…`), removido ao carregar e mantido somente na memória da página. Abrir o link não troca a senha e não o consome; verificadores de e-mail podem visitar a página sem invalidá-lo. A confirmação envia token e senha pelo corpo de um POST HTTPS. Não há Pixel Meta, PWA ou persistência do token nessas telas. Recarregar após remover o fragmento exige abrir novamente o link recebido.

O banco limita o envio por conta a uma solicitação a cada 60 segundos, inclusive entre réplicas. Existe também um freio global de 60 operações por minuto por processo para solicitar/consumir links; configurar rate limit compartilhado no proxy/WAF em escala. O login bloqueado por tentativas é desbloqueado após uma recuperação bem-sucedida. Pedir o link não troca a senha e não encerra sessões.

Após redefinir, a versão de credencial é incrementada e os cookies administrativos anteriores são rejeitados na próxima verificação HTTP ou no WebSocket administrativo de entregas. Novos logins recebem a versão atual. Sessões existentes de usuários que não redefiniram a senha continuam compatíveis com a versão zero. Não há login automático após recuperação.

## Envio, operação e limites

O backend usa `https://api.resend.com/emails`, timeout de 8 segundos e sem redirecionamentos. A auditoria registra somente envio aceito/falho, sem token, endereço, corpo do e-mail ou resposta do provedor. “Accepted” significa aceitação pela API, **não comprova chegada à caixa de entrada**. Consultar Logs/Emails do Resend para falhas, rejeições e entrega; nunca compartilhar chaves ou links de recuperação em capturas.

A tarefa em segundo plano não é uma fila durável: reinício do processo ou indisponibilidade pode interromper um envio. O usuário pode solicitar novamente após 60 segundos. Não há retentativa automática que possa enviar um link já expirado. A franquia diária do provedor deve ser monitorada; atingir a quota pode impedir a recuperação até restabelecer a capacidade. O envio não foi testado na conta real por esta implementação; os testes usam provedor simulado e nenhum e-mail real foi disparado.

Após deploy/migração, validar com um administrador de teste da loja no ambiente correto: solicitar link, verificar Resend e caixa/spam, abrir, trocar senha, entrar com nova senha, confirmar rejeição da anterior e do link reutilizado. Isso é um teste de acesso, não cria checkout nem transaciona assinatura. A recuperação não modifica plano, pagamento, tenant ou papel do usuário.
