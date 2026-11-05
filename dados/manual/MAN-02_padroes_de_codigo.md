# MAN-02 — Padrões de Codificação

Código: MAN-02 · Versão 2.4 · Vigência: 01/06/2026 · Responsável: Guilda de Arquitetura da NovaForja Software (empresa fictícia)

## 1. Python (serviços FastAPI)
- Versão de referência: Python 3.12. Anotações de tipo obrigatórias em funções públicas.
- Formatação e análise estática com ruff; checagem de tipos com mypy em modo estrito nos módulos de domínio.
- Testes com pytest; dados de teste construídos por fábricas, nunca por cópias de produção.
- Configuração lida de variáveis de ambiente; é vedado registrar segredos no repositório.

## 2. Java (serviços Quarkus)
- Versão de referência: Java 21 com Quarkus 3. Formatação com Spotless e regras do Checkstyle corporativo.
- Testes com JUnit 5 e Testcontainers para integração com banco de dados e mensageria.
- Objetos de valor imutáveis no domínio; entidades expõem comportamento, não apenas acessores.

## 3. Front-end (React) e Mobile (Flutter)
- React com TypeScript em modo estrito; componentes acessíveis por padrão.
- Flutter com análise estática do pacote de lints corporativo e testes de widget para telas críticas.

## 4. Convenções gerais
- Mensagens de commit no padrão Conventional Commits (feat, fix, chore, docs, refactor, test).
- Nomes de ramificações de trabalho: tipo/numero-da-historia-descricao-curta (ex.: feat/132-mfa-aplicativo).
- Registros de log estruturados em JSON, sem dados pessoais em texto aberto.
- Toda dependência nova precisa ser registrada no inventário de componentes (SBOM) do serviço.
