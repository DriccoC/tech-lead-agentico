# MAN-05 — Padrão de Autenticação e Gestão de Identidade

Código: MAN-05 · Versão 2.1 · Vigência: 01/08/2026 · Responsável: Time de Segurança da Informação da NovaForja Software (empresa fictícia)

## 1. Protocolos homologados
A autenticação de usuários finais deve utilizar OpenID Connect sobre OAuth 2.0, com fluxo de código de autorização e extensão PKCE. Fluxos implícitos e de senha do proprietário do recurso são proibidos.

## 2. Provedores de identidade federada
O acesso por provedores de identidade externos (login social, como Google ou Microsoft) é permitido apenas para clientes pessoa física, sempre com vinculação a uma conta interna e verificação do e-mail. Para clientes corporativos (B2B), utiliza-se federação SAML 2.0 ou OIDC com o provedor do próprio cliente.

## 3. Bibliotecas homologadas
- Python: authlib, na versão estável mais recente, observadas as regras do MAN-04.
- Java: extensão quarkus-oidc.
- É vedada a implementação própria de protocolos criptográficos ou de validação de tokens.

## 4. Tokens e sessões
- Tokens de acesso com validade máxima de 15 minutos; tokens de renovação com rotação obrigatória e validade máxima de 8 horas.
- Sessões encerradas após 30 minutos de inatividade.
- Bloqueio temporário da conta após 5 tentativas de autenticação malsucedidas.

## 5. Autenticação multifator
A autenticação multifator é obrigatória para operações sensíveis (alteração de dados cadastrais, pagamentos) e para todos os usuários administrativos.

## 6. Revisão de segurança
Toda alteração em autenticação ou autorização requer revisão do time de segurança antes da incorporação ao tronco (ver MAN-01).
