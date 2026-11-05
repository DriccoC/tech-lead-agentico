# MAN-07 — Registros de Decisão Arquitetural (ADR)

Código: MAN-07 · Versão 1.9 · Vigência: contínua · Responsável: Guilda de Arquitetura da NovaForja Software (empresa fictícia)

## ADR-004 — Adoção do FastAPI para serviços Python
Status: aceita (2025). Contexto: necessidade de APIs assíncronas com validação de esquema. Decisão: novos serviços Python utilizam FastAPI com Pydantic. Consequência: serviços Flask legados devem ser migrados até o fim de 2026.

## ADR-009 — Mensageria com Kafka para eventos de pagamento
Status: aceita (2025). Decisão: eventos de domínio de pagamento são publicados em tópicos Kafka com esquema registrado. Consequência: consumidores devem ser idempotentes.

## ADR-012 — Provedor de identidade central
Status: aceita (2026). Contexto: múltiplos produtos implementavam autenticação de forma independente. Decisão: o Keycloak corporativo atua como provedor de identidade central; provedores externos (Google, Microsoft) são configurados como provedores de identidade federados no Keycloak, e não diretamente em cada aplicação. Consequência: aplicações integram-se apenas ao Keycloak via OIDC.

## ADR-015 — Observabilidade com OpenTelemetry
Status: aceita (2026). Decisão: rastreamento distribuído, métricas e registros seguem o padrão OpenTelemetry, com exportação para o coletor corporativo.

## ADR-017 — Banco de dados por serviço
Status: proposta (2026). Contexto: o banco compartilhado entre Portal e PagaFacil cria acoplamento. Proposta: cada serviço passa a ter seu próprio esquema PostgreSQL, com integração apenas por API ou eventos.
