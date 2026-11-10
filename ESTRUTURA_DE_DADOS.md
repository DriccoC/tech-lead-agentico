# Estrutura de Dados — Tech Lead Agêntico

Este documento descreve **todas as estruturas de dados** usadas pelo agente: os bancos SQL (tabelas, colunas e relacionamentos), o índice vetorial do RAG, os formatos estruturados que circulam durante o processamento e os arquivos de registro. Para cada estrutura, explica **para que serve** e **em que etapa do processamento** é usada.

> As etapas citadas (1 a 10 e 6.x) são as do [MANUAL_DO_AGENTE.md](MANUAL_DO_AGENTE.md), seção 5 ("O que acontece quando você envia uma mensagem") e seção 6 ("Registrar no backlog"). Todos os dados são da empresa **fictícia** NovaForja Software.

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Banco do backlog — `dados/backlog.db`](#2-banco-do-backlog--dadosbacklogdb)
3. [Banco de memória — `dados/memoria.db`](#3-banco-de-memória--dadosmemoriadb)
4. [Banco do histórico de conversas — `dados/historico_conversas.db`](#4-banco-do-histórico-de-conversas--dadoshistorico_conversasdb)
5. [Banco de checkpoints do LangGraph — `dados/checkpoints.db`](#5-banco-de-checkpoints-do-langgraph--dadoscheckpointsdb)
6. [Índice vetorial do manual — `dados/indice_faiss/`](#6-índice-vetorial-do-manual--dadosindice_faiss)
7. [Estruturas em memória (esquemas Pydantic e dicionários)](#7-estruturas-em-memória-esquemas-pydantic-e-dicionários)
8. [Arquivos de registro e de apoio (JSON)](#8-arquivos-de-registro-e-de-apoio-json)
9. [Mapa: etapa do processamento × estrutura de dados](#9-mapa-etapa-do-processamento--estrutura-de-dados)

---

## 1. Visão geral

O agente trabalha com **quatro bancos SQLite**, **um índice vetorial FAISS**, um conjunto de **esquemas estruturados** (Pydantic) que dão forma às saídas do modelo e alguns **arquivos JSON** de registro.

> **SQLite** é um banco de dados relacional (tabelas, colunas, SQL) que cabe inteiro num único arquivo `.db`, sem servidor. O Python já o traz embutido. Para inspecionar: `sqlite3 dados/backlog.db ".schema"` ou a extensão "SQLite Viewer" do VS Code.

| Estrutura | Arquivo | Natureza | O agente... |
|---|---|---|---|
| Backlog da empresa | `dados/backlog.db` | SQLite relacional, 6 tabelas | **lê** a cada consulta; **escreve** só após aprovação |
| Memória de longo prazo e pendências | `dados/memoria.db` | SQLite, 2 tabelas (texto + vetor) | lê e escreve a cada turno |
| Histórico das conversas | `dados/historico_conversas.db` | SQLite, 1 tabela (mensagens em JSON) | lê e escreve a cada turno (motor AgentExecutor) |
| Estado do grafo | `dados/checkpoints.db` | SQLite, 2 tabelas (formato do LangGraph) | lê e escreve a cada passo (motor LangGraph) |
| Manual de Engenharia indexado | `dados/indice_faiss/` | Índice vetorial FAISS + metadados | só lê |
| Saídas estruturadas | (em memória) | Esquemas Pydantic | cria a cada etapa |
| Registros de execução | `logs/*.json*` | JSON / JSON Lines | só escreve |

```
                         ┌───────────────────────────┐
   sua mensagem ───────▶ │  Etapa 1  IntencaoEntidades│──▶ estado da sessão (dict)
                         └─────────────┬─────────────┘
                                       ▼
   memoria.db ◀──────── Etapa 3  memórias de longo prazo (busca vetorial)
   historico_conversas.db / checkpoints.db ◀── Etapa 4  histórico
                                       ▼
                         ┌───────────────────────────┐
                         │ Etapa 5  ferramentas       │
   backlog.db ◀──────────│  SQL, capacidade (leitura) │
   indice_faiss/ ◀───────│  manual (RAG)              │
   APIs externas ◀───────│  PyPI, OSV, GitHub, feriados│
                         │  decompor → PlanoTrabalho   │
   memoria.db ◀──────────│  propor → pendencias        │
                         └─────────────┬─────────────┘
                                       ▼
                         Etapas 6–8  RelatorioVerificacao
                                       ▼
   memoria.db ◀──────── Etapa 9  FatosExtraidos → memorias
                                       ▼
                         Etapa 10  TurnoIntegrado → interface
                                       ▼ (clique em Aprovar)
   backlog.db ◀──────── 6.3  INSERT historias  +  issues GitHub / issues_simuladas.json
```

---

## 2. Banco do backlog — `dados/backlog.db`

**Função:** é o "Jira" da empresa fictícia. Representa a equipe, os projetos, as sprints, quem trabalha em cada sprint, as histórias e os bugs. É a **fonte de verdade** para tudo o que envolve pessoas, capacidade e trabalho planejado.

**Criação:** `python scripts/criar_banco.py` recria o banco do zero, sempre com os mesmos dados (reprodutível).

**Acesso pelo agente:**
- **Leitura:** pelas ferramentas `consultar_backlog_sql` e `calcular_capacidade_sprint`, sempre por uma **conexão somente leitura** (o próprio SQLite recusa qualquer escrita).
- **Escrita:** apenas pela função `executar_registro`, fora do alcance do modelo, chamada quando a pessoa clica em **Aprovar** (etapa 6.3).

### 2.1 Diagrama de relacionamentos

```
┌──────────────┐ 1      N ┌──────────────┐ 1      N ┌──────────────┐ N      1 ┌──────────────────┐
│   projetos   │─────────▶│   sprints    │─────────▶│  alocacoes   │◀─────────│ desenvolvedores  │
│ projeto_id PK│          │ sprint_id PK │          │ sprint_id PK │          │ dev_id PK        │
└──────┬───────┘          │ projeto_id FK│          │ dev_id    PK │          └────────┬─────────┘
       │                  └──────┬───────┘          └──────────────┘                   │
       │ 1                       │ 1 (opcional)                                         │ 1 (opcional)
       │                         ▼ N                                                    │
       │ N                ┌──────────────┐  N                                           │
       ├─────────────────▶│  historias   │◀──────────────────────────────────────────────┘
       │                  │historia_id PK│   responsavel_id
       │                  └──────────────┘
       │ N
       └─────────────────▶┌──────────────┐
                          │     bugs     │
                          │ bug_id PK    │
                          └──────────────┘
```

- Um **projeto** tem várias **sprints**, **histórias** e **bugs**.
- Uma **sprint** tem várias **alocações**; cada alocação liga **um desenvolvedor** a **uma sprint**.
- Uma **história** pertence a um projeto, pode estar numa sprint (ou no backlog, sem sprint) e pode ter um responsável.

**PK** = chave primária (identifica a linha). **FK** = chave estrangeira (aponta para outra tabela).

### 2.2 Tabela `projetos`

**Função:** cadastro dos sistemas da empresa. Diz ao agente qual é a **stack** de cada projeto, o que orienta normas e bibliotecas.

| Coluna | Tipo | Chave | Descrição |
|---|---|---|---|
| `projeto_id` | INTEGER | PK | Identificador do projeto |
| `nome` | TEXT | único | Nome do projeto |
| `descricao` | TEXT | | Descrição curta |
| `stack` | TEXT | | Tecnologias usadas |
| `repositorio` | TEXT | | Repositório de código (fictício) |

**Conteúdo (3 linhas):**

| projeto_id | nome | stack | descrição |
|---|---|---|---|
| 1 | Portal | Python 3.12, FastAPI, PostgreSQL, React | Portal do cliente (web) com autoatendimento e área logada |
| 2 | PagaFacil | Java 21, Quarkus, PostgreSQL, Kafka | API de pagamentos e conciliação |
| 3 | AppCampo | Flutter, Firebase, FastAPI | Aplicativo móvel para equipes de campo |

**Usada em:**
- **Etapa 5a** (capacidade): para localizar as sprints do projeto pedido.
- **Etapa 5 / SQL**: perguntas como "qual a stack do PagaFacil?".
- **Etapa 6.3** (aprovação): para converter o nome do projeto em `projeto_id` ao gravar as histórias.

### 2.3 Tabela `desenvolvedores`

**Função:** cadastro da equipe.

| Coluna | Tipo | Chave | Descrição | Valores |
|---|---|---|---|---|
| `dev_id` | INTEGER | PK | Identificador da pessoa | |
| `nome` | TEXT | | Nome completo | |
| `papel` | TEXT | | Especialidade | `backend`, `frontend`, `fullstack`, `qa`, `mobile` |
| `senioridade` | TEXT | | Nível | `junior`, `pleno`, `senior` |

**Conteúdo (8 linhas):** Ana Souza (backend, sênior), Bruno Lima (backend, pleno), Carla Mendes (frontend, pleno), Diego Rocha (qa, pleno), Eduarda Nunes (fullstack, sênior), Felipe Araujo (backend, sênior), Gabriela Torres (mobile, pleno), Henrique Dias (backend, júnior).

**Usada em:**
- **Etapa 5a** (capacidade): junto com `alocacoes`, para saber quem está na sprint; também para **retirar alguém** na simulação ("e se tirarmos o Bruno?").
- **Etapa 5 / SQL**: "quem são os backend sênior?", "quem é responsável pela história X?".

### 2.4 Tabela `sprints`

**Função:** as iterações de trabalho de cada projeto, com período e situação.

| Coluna | Tipo | Chave | Descrição | Valores |
|---|---|---|---|---|
| `sprint_id` | INTEGER | PK | Identificador interno | |
| `projeto_id` | INTEGER | FK → `projetos` | Projeto da sprint | |
| `numero` | INTEGER | | Número da sprint, como o time a chama | |
| `inicio` | TEXT | | Data de início | `AAAA-MM-DD` |
| `fim` | TEXT | | Data de fim | `AAAA-MM-DD` |
| `status` | TEXT | | Situação | `concluida`, `em_andamento`, `planejada` |

**Conteúdo (6 linhas):**

| sprint_id | projeto | número | período | status |
|---|---|---|---|---|
| 11 | Portal | 11 | 12/10 a 23/10/2026 | concluida |
| 12 | Portal | 12 | 26/10 a 06/11/2026 | em_andamento |
| 13 | Portal | 13 | 09/11 a 20/11/2026 | **planejada** |
| 21 | PagaFacil | 21 | 19/10 a 30/10/2026 | concluida |
| 22 | PagaFacil | 22 | 02/11 a 13/11/2026 | em_andamento |
| 31 | AppCampo | 5 | 02/11 a 13/11/2026 | em_andamento |

Note que `sprint_id` (chave interna) e `numero` (como o time chama) são diferentes: a sprint 31 é a "sprint 5" do AppCampo.

**Usada em:**
- **Etapa 5a** (capacidade): "próxima sprint" = a primeira com `status = 'planejada'` do projeto. O período (`inicio`, `fim`) define os dias úteis e quais feriados da BrasilAPI caem dentro dele.
- **Etapa 6.3** (aprovação): converte o número da sprint em `sprint_id` para gravar as histórias.

### 2.5 Tabela `alocacoes`

**Função:** quem trabalha em cada sprint e **quanto**. É a base do cálculo de capacidade.

| Coluna | Tipo | Chave | Descrição |
|---|---|---|---|
| `sprint_id` | INTEGER | PK, FK → `sprints` | Sprint |
| `dev_id` | INTEGER | PK, FK → `desenvolvedores` | Pessoa |
| `fator_foco` | REAL | | Fração do dia dedicada à sprint (0 a 1); o resto vai para reuniões, suporte etc. |
| `dias_ausencia` | INTEGER | | Dias de folga/ausência no período (padrão 0) |

A chave primária é o **par** (`sprint_id`, `dev_id`): uma pessoa aparece no máximo uma vez por sprint.

**Conteúdo:** 23 linhas (5 por sprint do Portal, 3 por sprint do PagaFacil, 2 na do AppCampo). Exemplo, sprint 13 do Portal:

| Pessoa | fator_foco | dias_ausencia |
|---|---|---|
| Ana Souza | 0,70 | 0 |
| Bruno Lima | 0,80 | 2 |
| Carla Mendes | 0,80 | 0 |
| Diego Rocha | 0,60 | 0 |
| Eduarda Nunes | 0,75 | 0 |

**Usada em:** **Etapa 5a** (capacidade), pela ferramenta `calcular_capacidade_sprint`.

#### Exemplo completo do cálculo (sprint 13 do Portal)

1. Período 09/11 a 20/11/2026 = 10 dias de semana; a BrasilAPI informa o feriado de **20/11** → **9 dias úteis**.
2. Contribuição de cada pessoa = (dias úteis − ausências) × fator de foco × 1 ponto/dia:

   | Pessoa | Cálculo | Pontos |
   |---|---|---|
   | Ana | 9 × 0,70 | 6,30 |
   | Bruno | (9 − 2) × 0,80 | 5,60 |
   | Carla | 9 × 0,80 | 7,20 |
   | Diego | 9 × 0,60 | 5,40 |
   | Eduarda | 9 × 0,75 | 6,75 |
   | **Capacidade bruta** | | **31,25** |

3. **Capacidade líquida** = 31,25 × 80% = 25,0 → **25 pontos** (20% reservados para defeitos, regra do MAN-06).
4. **Pontos já comprometidos** (soma de `historias.pontos` da sprint 13) = 5 + 3 + 3 = **11**.
5. **Saldo disponível** = 25 − 11 = **14 pontos**.

### 2.6 Tabela `historias`

**Função:** o backlog propriamente dito: histórias de usuário de cada projeto, já planejadas em sprints ou aguardando (backlog). É também a **única tabela em que o agente escreve** (após aprovação).

| Coluna | Tipo | Chave | Descrição | Valores |
|---|---|---|---|---|
| `historia_id` | INTEGER | PK | Identificador | Portal 101+, PagaFacil 201+, AppCampo 301+; criadas pelo agente: próximo número livre |
| `projeto_id` | INTEGER | FK → `projetos` | Projeto | |
| `sprint_id` | INTEGER | FK → `sprints`, **opcional** | Sprint; `NULL` = está no backlog, sem sprint | |
| `epico` | TEXT | | Agrupador maior da história | ex.: "Login com Google no Portal" |
| `titulo` | TEXT | | Título ("Como ..., quero ..., para ...") | |
| `pontos` | INTEGER | | Estimativa | Fibonacci: 1, 2, 3, 5, 8, 13 |
| `prioridade` | TEXT | | Prioridade | `alta`, `media`, `baixa` |
| `status` | TEXT | | Situação | `backlog`, `a_fazer`, `em_andamento`, `concluida` |
| `responsavel_id` | INTEGER | FK → `desenvolvedores`, opcional | Responsável | |
| `criado_em` | TEXT | | Data de criação | `AAAA-MM-DD` |
| `updated_at` | TEXT | | Data da última alteração | `AAAA-MM-DD` |

**Conteúdo original (22 linhas):** 8 concluídas, 4 em andamento, 7 a fazer e 3 no backlog. As 3 do backlog do Portal são relevantes para o cenário de login: *Integração com SSO corporativo dos clientes B2B* (13 pts), *Autenticação em dois fatores (MFA)* (8 pts) e *Pagamento de fatura por Pix* (8 pts).

**Usada em:**
- **Etapa 5a** (capacidade): soma dos pontos da sprint = pontos comprometidos.
- **Etapa 5 / SQL**: "o que está na sprint 13?", "quantos pontos estão em andamento?", "o que há no backlog do Portal?".
- **Etapa 6.3** (aprovação): `INSERT` de uma linha por história do plano aprovado, com prioridade `media`, status `a_fazer` (se houver sprint) ou `backlog` (sem sprint) e responsável vazio.

> A coluna `updated_at` foi escolhida de propósito: ela contém a palavra "update" e serve de teste para o guardrail SQL, que bloqueia comandos de escrita **por palavra inteira** (não bloqueia `updated_at`).

### 2.7 Tabela `bugs`

**Função:** defeitos registrados em cada projeto. Permite ao agente considerar a saúde do projeto e responder sobre problemas abertos.

| Coluna | Tipo | Chave | Descrição | Valores |
|---|---|---|---|---|
| `bug_id` | INTEGER | PK | Identificador | |
| `projeto_id` | INTEGER | FK → `projetos` | Projeto | |
| `titulo` | TEXT | | Descrição curta | |
| `severidade` | TEXT | | Gravidade | `critica`, `alta`, `media`, `baixa` |
| `status` | TEXT | | Situação | `aberto`, `em_correcao`, `resolvido` |
| `aberto_em` | TEXT | | Data de abertura | `AAAA-MM-DD` |

**Conteúdo (5 linhas):**

| # | Projeto | Título | Severidade | Status |
|---|---|---|---|---|
| 1 | Portal | Sessão expira antes do tempo configurado | alta | aberto |
| 2 | Portal | Botão de segunda via some no Safari | media | em_correcao |
| 3 | Portal | Erro 500 ao salvar endereço sem complemento | alta | resolvido |
| 4 | PagaFacil | Duplicidade em conciliação de boletos de fim de mês | critica | em_correcao |
| 5 | AppCampo | Sincronização falha com fotos acima de 10 MB | media | aberto |

**Usada em:** **Etapa 5 / SQL**, em perguntas como "quais bugs de severidade alta ou crítica estão abertos ou em correção?".

### 2.8 Como o agente consulta o banco (text-to-query)

Na **etapa 5**, quando a pergunta envolve o backlog, o modelo **escreve o SQL** e chama `consultar_backlog_sql`. A descrição dessa ferramenta inclui o esquema acima, para o modelo saber quais tabelas e colunas existem. Exemplo:

> Pergunta: *"Quais bugs de severidade alta ou crítica estão abertos ou em correção?"*
> ```sql
> SELECT p.nome AS projeto, b.titulo, b.severidade, b.status
> FROM bugs b JOIN projetos p USING (projeto_id)
> WHERE b.severidade IN ('alta', 'critica') AND b.status IN ('aberto', 'em_correcao')
> LIMIT 50
> ```

**Guardrails (camadas de proteção):**
1. Conexão aberta em **modo somente leitura** (`?mode=ro`): o SQLite recusa escrita mesmo que um comando passe pelo filtro.
2. Só aceita **uma** instrução, começando com `SELECT` ou `WITH`; recusa `INSERT`, `UPDATE`, `DELETE`, `DROP` etc. comparando **palavras inteiras**.
3. Acrescenta `LIMIT 50` se não houver limite, para não sobrecarregar o contexto do modelo.

---

## 3. Banco de memória — `dados/memoria.db`

**Função:** guardar o que o agente **aprende** sobre cada usuário entre sessões (memória de longo prazo) e as **propostas de registro** que aguardam aprovação humana.

### 3.1 Tabela `memorias`

**Função:** memória de longo prazo, no modelo CoALA:
- **semântica:** fatos e preferências duráveis ("Adriano prefere histórias de no máximo 3 pontos");
- **episódica:** o que aconteceu em sessões anteriores ("Em 05/11/2026, sessão sobre o login com Google...").

(A memória **procedural**, as regras de como trabalhar, fica no prompt do sistema e nas ferramentas de cálculo, não nesta tabela.)

| Coluna | Tipo | Chave | Descrição |
|---|---|---|---|
| `memoria_id` | INTEGER | PK (autoincremento) | Identificador |
| `tipo` | TEXT | | `semantica` ou `episodica` |
| `escopo` | TEXT | | **Dono** da memória: o valor do campo *Usuário* da interface (ex.: `adriano`) |
| `conteudo` | TEXT | | A frase lembrada, autocontida, em português |
| `vetor` | TEXT | | **Embedding** do conteúdo: lista JSON com 384 números (ex.: `[0.0222, -0.0781, ...]`), que representa o significado da frase |
| `criado_em` | TEXT | | Data/hora de criação (ISO 8601) |
| `atualizado_em` | TEXT | | Data/hora da última atualização |
| `acessos` | INTEGER | | Quantas vezes a memória foi recuperada (padrão 0) |

**Conteúdo atual:** 20 memórias (6 semânticas e 14 episódicas), de vários escopos: `adriano` (10), `adriano-f5` (3), `adriano-f5-lg` (2), `teste_demo` (4), `visitante` (1). Os escopos `adriano-f5*` e `teste_demo` foram criados pelos notebooks e testes, para não misturar com as memórias do uso real.

**Como funciona a busca (etapa 3):**
1. A mensagem + o estado da sessão viram um vetor (modelo de embeddings local).
2. Calcula-se a **similaridade de cosseno** entre esse vetor e o `vetor` de cada memória do `escopo` atual (os vetores são normalizados, então é um produto escalar).
3. Ficam as memórias com similaridade **≥ 0,35**, até **4**, das mais parecidas para as menos.
4. O **episódio mais recente** sempre é incluído, mesmo com baixa similaridade (para perguntas como "o que fizemos da última vez?").
5. `acessos` é incrementado nas escolhidas.

**Usada em:**
- **Etapa 3** (lembrar): leitura por similaridade.
- **Etapa 7** (verificação): as memórias usadas também entram como evidência ("Memória de sessão anterior: ...").
- **Etapa 9** (aprender): o modelo auxiliar extrai fatos (`FatosExtraidos`) e, para cada um, decide (`DecisaoAtualizacao`) se **adiciona** uma linha nova ou **atualiza** uma existente sobre o mesmo assunto (evita duplicar e contradizer).
- **Botão 💾 Encerrar sessão**: grava um episódio (resumo de uma frase da sessão).
- **Painel 🧠 Memória de longo prazo** da barra lateral: lista as memórias do escopo.

### 3.2 Tabela `pendencias`

**Função:** a "fila de aprovação". Cada linha é um registro que o agente **propôs** e que só será gravado no backlog se uma pessoa aprovar. É a peça que separa *propor* de *executar*.

| Coluna | Tipo | Chave | Descrição | Valores |
|---|---|---|---|---|
| `pendencia_id` | TEXT | PK | Identificador curto (8 caracteres hexadecimais) | ex.: `3bd3b1dc` |
| `criada_em` | TEXT | | Data/hora da proposta | ISO 8601 |
| `projeto` | TEXT | | Nome do projeto | ex.: `Portal` |
| `numero_sprint` | INTEGER | | Número da sprint (ou vazio = backlog) | ex.: `13` |
| `plano_json` | TEXT | | O plano completo (`PlanoTrabalho`, ver 7.3) em JSON | |
| `abrir_issues` | INTEGER | | Se deve abrir issues no GitHub | `1` sim, `0` não |
| `status` | TEXT | | Situação | `aguardando_aprovacao`, `executada`, `rejeitada` |
| `resultado_json` | TEXT | | Resultado da execução: histórias criadas, issues abertas, quem aprovou | preenchido ao executar |

**Ciclo de vida de uma pendência:**

```
 propor_registro_backlog            clique ✅ Aprovar            
 (agente, etapa 6.2)                (pessoa, etapa 6.3)          
        │                                  │                     
        ▼                                  ▼                     
  aguardando_aprovacao ──────────────▶  executada   (resultado_json preenchido;
        │                                            histórias no backlog; issues abertas)
        │  clique ❌ Rejeitar (6.4)
        └─────────────────────────────▶  rejeitada  (nada gravado)
```

Uma pendência só pode ser executada **uma vez**: a execução confere que o status ainda é `aguardando_aprovacao`.

**Exemplo de `resultado_json`:**
```json
{
  "historias_criadas": [{"historia_id": 303, "titulo": "Como administrador de identidade, quero ...", "pontos": 3}],
  "issues": [{"numero": 1, "url": "https://github.com/.../issues/1", "titulo": "Como administrador de identidade, ...", "modo": "ao vivo"}],
  "aprovado_por": "adriano"
}
```

**Conteúdo atual:** 5 pendências, todas `executada` (dos testes da Fase 5 e da sessão real que abriu as issues #1–#3).

**Usada em:**
- **Etapa 5 / 6.2**: criada por `propor_registro_backlog` (motor AgentExecutor) ou internamente por `registrar_no_backlog` (motor LangGraph).
- **Etapa 10**: o retorno da proposta vira a caixa **📝 Aprovação humana necessária**.
- **Etapas 6.3 e 6.4**: lida e atualizada ao aprovar ou rejeitar.

### 3.3 Tabela `sqlite_sequence`

Tabela **interna do SQLite**, criada automaticamente quando uma tabela usa `AUTOINCREMENT`. Guarda o último número usado em `memorias.memoria_id`. Não é usada diretamente pelo agente.

---

## 4. Banco do histórico de conversas — `dados/historico_conversas.db`

**Função:** a **memória de curto prazo persistente** do motor **AgentExecutor**: todas as mensagens de cada sessão, para o agente "lembrar" o que foi dito antes na mesma conversa, mesmo que a interface seja recarregada.

### 4.1 Tabela `mensagens`

| Coluna | Tipo | Chave | Descrição |
|---|---|---|---|
| `id` | INTEGER | PK (autoincremento) | Ordem de gravação |
| `sessao_id` | TEXT | | Sessão a que a mensagem pertence (ex.: `adriano-3f9a1c`) |
| `mensagem` | TEXT | | A mensagem serializada em JSON, preservando o **tipo** (`human` = usuário, `ai` = agente) |
| `criado_em` | TEXT | | Data/hora (ISO 8601) |

**Formato da coluna `mensagem`:**
```json
{"type": "human",
 "data": {"content": "Quero login com Google no projeto Portal na próxima sprint.",
          "additional_kwargs": {}, "response_metadata": {}, "type": "human"}}
```

**Conteúdo atual:** 138 mensagens de 54 sessões.

**Usada em:**
- **Etapa 2**: quando o agente faz uma pergunta de esclarecimento, a pergunta e a mensagem são gravadas aqui.
- **Etapa 4** (contexto): o `RunnableWithMessageHistory` lê as mensagens da sessão. As **6 mais recentes** vão na íntegra; as mais antigas são **resumidas** (resumo guardado em cache por sessão).
- **Fim da etapa 5**: a pergunta e a resposta são gravadas.
- **Etapa 8** (autocorreção): a última resposta do agente é **substituída** pela versão corrigida.
- **Botão 💾 Encerrar sessão**: a transcrição completa é lida para gerar o episódio.

### 4.2 Tabela `sqlite_sequence`

Interna do SQLite (contador do autoincremento de `mensagens.id`).

---

## 5. Banco de checkpoints do LangGraph — `dados/checkpoints.db`

**Função:** guardar o **estado completo do grafo** do motor **LangGraph** a cada passo. É o que permite **pausar** o agente antes de gravar (aprovação humana) e **retomar exatamente do mesmo ponto** depois do clique, mesmo que o programa tenha sido reiniciado. Também serve como histórico da conversa nesse motor.

O formato é definido pela biblioteca `langgraph-checkpoint-sqlite` (classe `SqliteSaver`); o projeto não cria essas tabelas, apenas as usa.

### 5.1 Tabela `checkpoints`

Cada linha é uma **"fotografia" do estado** do grafo após um passo.

| Coluna | Tipo | Chave | Descrição |
|---|---|---|---|
| `thread_id` | TEXT | PK | Conversa (no projeto, = identificador da sessão) |
| `checkpoint_ns` | TEXT | PK | Espaço de nomes (vazio para o grafo principal; usado por subgrafos) |
| `checkpoint_id` | TEXT | PK | Identificador da fotografia (ordenável no tempo) |
| `parent_checkpoint_id` | TEXT | | Fotografia anterior (forma uma corrente: permite voltar no tempo) |
| `type` | TEXT | | Formato de serialização (`msgpack`, binário compacto) |
| `checkpoint` | BLOB | | O estado em si: as mensagens da conversa e os canais do grafo |
| `metadata` | BLOB | | Origem (`input`, `loop`), número do passo (`step`) etc. |

### 5.2 Tabela `writes`

Gravações **intermediárias** de cada tarefa dentro de um passo (o que cada nó do grafo produziu), usadas para retomar com segurança.

| Coluna | Tipo | Chave | Descrição |
|---|---|---|---|
| `thread_id`, `checkpoint_ns`, `checkpoint_id` | TEXT | PK | A fotografia a que a gravação pertence |
| `task_id` | TEXT | PK | Tarefa (nó) que gravou |
| `task_path` | TEXT | | Caminho da tarefa no grafo |
| `idx` | INTEGER | PK | Ordem da gravação na tarefa |
| `channel` | TEXT | | Canal do estado que foi alterado |
| `type` | TEXT | | Formato de serialização |
| `value` | BLOB | | Valor gravado |

**Canais mais relevantes (coluna `channel`):**

| Canal | Significado |
|---|---|
| `messages` | Mensagens adicionadas à conversa (usuário, modelo, ferramentas) |
| `branch:to:model` | O grafo seguiu para o nó do modelo |
| `branch:to:HumanInTheLoopMiddleware.after_model` | O grafo passou pelo ponto de checagem de aprovação humana |
| `__interrupt__` | **O grafo pausou** aguardando aprovação |
| `__resume__` | **O grafo foi retomado** com a decisão (aprovar/rejeitar) |
| `hitl_edited_tool_calls` | Chamadas de ferramenta após a decisão humana |

**Conteúdo atual:** 51 checkpoints e 112 gravações, de 3 conversas (testes e notebook 5).

**Usada em (somente no motor LangGraph):**
- **Etapas 4 e 5**: a cada passo, o estado é lido e uma nova fotografia é gravada.
- **Etapa 6.2**: na tentativa de chamar `registrar_no_backlog`, o grafo grava um `__interrupt__` e pausa.
- **Etapa 6.3/6.4**: o clique gera um `__resume__`; o grafo carrega a última fotografia e continua.

### 5.3 Arquivos `checkpoints.db-wal` e `checkpoints.db-shm`

Não são tabelas: são arquivos auxiliares do SQLite no modo **WAL** (*Write-Ahead Log*). O `-wal` guarda as alterações recentes ainda não consolidadas no `.db`; o `-shm` coordena o acesso a ele. São criados e removidos automaticamente; não devem ser apagados com o programa rodando.

---

## 6. Índice vetorial do manual — `dados/indice_faiss/`

**Função:** permitir a **busca por significado** no Manual de Engenharia (RAG). Não é um banco SQL: é um índice de vetores.

**Criação:** `python scripts/construir_indice.py`, uma vez.
1. Lê os 7 documentos `dados/manual/MAN-0x_*.md` e separa por seção.
2. Corta o texto em **trechos (chunks) de até 600 caracteres**, com **100 de sobreposição** (para não perder o sentido nas bordas).
3. Converte cada trecho em um **vetor de 384 números** com o modelo `paraphrase-multilingual-MiniLM-L12-v2` (local).
4. Salva os vetores e os metadados. Resultado: **42 trechos**.

### 6.1 Estrutura de um trecho (chunk)

| Campo | Descrição | Exemplo |
|---|---|---|
| `chunk_id` | Identificador do trecho | `CHK_026` |
| `doc_id` | Documento de origem | `MAN-05` |
| `titulo` | Título do documento | `MAN-05 — Padrão de Autenticação e Gestão de Identidade` |
| `secao` | Seção do documento | `3. Bibliotecas homologadas` |
| `arquivo` | Arquivo de origem | `MAN-05_autenticacao_e_identidade.md` |
| conteúdo | O texto do trecho (até 600 caracteres) | |
| vetor | 384 números | |

### 6.2 Arquivos

| Arquivo | Formato | Conteúdo |
|---|---|---|
| `index.faiss` | Binário FAISS | Os 42 vetores, organizados para busca rápida por distância |
| `index.pkl` | Pickle (binário Python) | Texto e metadados de cada trecho, ligados à posição de cada vetor |
| `catalogo.json` | JSON legível | Lista dos 42 trechos com `chunk_id`, metadados e o início do texto (para conferência humana) |

### 6.3 Resultado de uma busca

A ferramenta `buscar_manual_engenharia` devolve, para cada trecho encontrado:

```json
{"chunk_id": "CHK_026", "doc_id": "MAN-05", "secao": "3. Bibliotecas homologadas",
 "distancia_l2": 0.712, "similaridade": "alta", "trecho": "..."}
```

A **distância L2** mede quão longe o trecho está da pergunta (0 = idêntico). A classificação usa faixas calibradas:

| Distância | Similaridade | Interpretação |
|---|---|---|
| < 0,80 | alta | Trecho muito relacionado |
| 0,80 a 1,10 | moderada | Possivelmente relacionado |
| > 1,10 | baixa | Provavelmente irrelevante; se todos forem baixos, o manual não cobre o assunto |

**Usado em:**
- **Etapa 5b** (regras da empresa): busca com a consulta reescrita, variações (multi-query) e documento hipotético (HyDE), mantendo a menor distância de cada trecho.
- **Etapa 7** (verificação): os trechos retornados viram evidências contra as quais a resposta é conferida.

---

## 7. Estruturas em memória (esquemas Pydantic e dicionários)

Estas estruturas **não ficam gravadas em arquivo** (exceto quando indicado): existem durante o processamento de cada mensagem. Os **esquemas Pydantic** são "contratos": obrigam o modelo a devolver dados num formato exato, validado automaticamente; se vier algo fora do padrão, é rejeitado.

### 7.1 `IntencaoEntidades` — o pedido entendido

**Etapa 1.** Saída do classificador (modelo auxiliar) para cada mensagem.

| Campo | Tipo | Descrição |
|---|---|---|
| `intencao` | uma de: `planejar_demanda`, `consultar_backlog`, `checar_dependencia`, `consultar_padrao`, `conversa_geral` | Intenção principal |
| `projeto` | texto, opcional | Portal, PagaFacil ou AppCampo |
| `sprint` | inteiro, opcional | Número da sprint |
| `pacote` | texto, opcional | Biblioteca de software |
| `versao` | texto, opcional | Versão da biblioteca |
| `prioridade` | `alta` / `media` / `baixa`, opcional | Prioridade |
| `pessoa` | texto, opcional | Integrante do time |

### 7.2 Estado da sessão — o contexto acumulado

**Etapas 1, 2 e 5.** Dicionário que acumula as entidades ao longo da conversa: `{"projeto": "Portal", "sprint": 13, "pessoa": "Bruno"}`. Campos possíveis: `projeto`, `sprint`, `pacote`, `versao`, `prioridade`, `pessoa`.

- Atualizado com as entidades de cada mensagem (etapa 1) e com as que o agente usou nas ferramentas (fim da etapa 5; ex.: o pacote que ele consultou).
- Consultado na etapa 2 para decidir se falta informação, e enviado ao modelo na etapa 4.
- Zerado ao clicar em **🆕 Nova sessão**.

### 7.3 `PlanoTrabalho` e `Historia` — o plano de trabalho

**Etapa 5e** (criado por `decompor_demanda`), **6.2** (gravado em `pendencias.plano_json`) e **6.3** (convertido em linhas de `historias` e em issues).

**`PlanoTrabalho`**

| Campo | Tipo | Descrição |
|---|---|---|
| `epico` | texto | Nome curto do épico |
| `objetivo` | texto | Objetivo de negócio |
| `historias` | lista de `Historia` | Histórias independentes e pequenas |
| `riscos` | lista de textos | Riscos e dependências técnicas |

**`Historia`**

| Campo | Tipo | Descrição |
|---|---|---|
| `titulo` | texto | "Como <papel>, quero <ação>, para <benefício>" |
| `criterios_aceite` | lista de textos | Formato Gherkin: "Dado ..., quando ..., então ..." |
| `pontos` | inteiro | Fibonacci (1, 2, 3, 5, 8) |
| `tarefas` | lista de textos | Tarefas técnicas de até um dia cada |

**Exemplo (resumido):**
```json
{"epico": "Login com Google no Portal",
 "objetivo": "Permitir que clientes pessoa física entrem com a conta Google, reduzindo atrito no acesso.",
 "historias": [
   {"titulo": "Como administrador de identidade, quero configurar o Google como provedor federado no Keycloak, para centralizar a autenticação (ADR-012)",
    "criterios_aceite": ["Dado o Keycloak de homologação, quando o provedor Google for configurado, então o fluxo OIDC com PKCE deve concluir com sucesso"],
    "pontos": 3,
    "tarefas": ["Registrar aplicação no Google Cloud", "Configurar provedor no Keycloak", "Documentar ADR de configuração"]}],
 "riscos": ["..."]}
```

**Correspondência com o backlog na aprovação (6.3):**

| PlanoTrabalho / Historia | → `historias` (backlog.db) | → issue no GitHub |
|---|---|---|
| `epico` | `epico` | "**Épico:**" no corpo |
| `objetivo` | — | "**Objetivo:**" no corpo |
| `titulo` | `titulo` | título da issue |
| `pontos` | `pontos` | citado no corpo |
| `criterios_aceite` | — | lista "**Critérios de aceite**" |
| `tarefas` | — | lista de verificação "**Tarefas**" |
| (fixo) | `prioridade = media`, `status = a_fazer`/`backlog` | rótulo `tech-lead-agentico` |

### 7.4 Saída da capacidade da sprint

**Etapa 5a.** JSON devolvido por `calcular_capacidade_sprint`:

| Campo | Descrição |
|---|---|
| `projeto`, `sprint`, `periodo` | Sprint calculada |
| `dias_uteis` | Dias úteis descontando feriados |
| `feriados_em_dia_util`, `fonte_feriados` | Feriados descontados e a fonte (BrasilAPI) |
| `capacidade_bruta` | Soma das contribuições |
| `reserva_defeitos` | 20% da bruta |
| `capacidade_liquida` | Bruta − reserva, arredondada para baixo |
| `pontos_comprometidos` | Já planejados na sprint |
| `saldo_disponivel` | Líquida − comprometidos |
| `detalhe` | Por pessoa: dias disponíveis, fator de foco, pontos |

### 7.5 Estruturas da memória de longo prazo

**Etapa 9.**

| Esquema | Campos | Função |
|---|---|---|
| `Fato` | `tipo` (`semantica`/`episodica`), `conteudo` | Um fato durável extraído do turno |
| `FatosExtraidos` | `fatos` (lista de `Fato`) | Tudo o que vale lembrar do turno (pode ser vazio) |
| `DecisaoAtualizacao` | `acao` (`adicionar`/`atualizar`), `memoria_id` | Se o fato é novo ou atualiza uma memória existente |
| `Memoria` | `memoria_id`, `tipo`, `escopo`, `conteudo`, `atualizado_em`, `similaridade` | Uma memória recuperada na etapa 3 (com a similaridade calculada) |

### 7.6 Estruturas da verificação

**Etapas 7 e 8.**

| Esquema | Campos | Função |
|---|---|---|
| `Afirmacao` | `texto`, `tipo` (`fato`/`conclusao`) | Uma afirmação verificável extraída da resposta |
| `ListaAfirmacoes` | `afirmacoes` (até 10) | Todas as afirmações da resposta |
| `AfirmacaoVerificada` | `texto`, `tipo`, `numeros_rastreados`, `nli` (`sustentada`/`neutra`/`contradição`/...), `prob_sustentacao`, `prob_contradicao`, `premissa` | Resultado da checagem de uma afirmação |
| `RelatorioCoerencia` | `veredito` (`APOIA`/`REFUTA`/`NEUTRA`), `coerente`, `falhas`, `justificativa` | Avaliação do juiz de coerência |
| `RelatorioVerificacao` | `aprovado`, `motivos`, `alertas`, `afirmacoes`, `coerencia` | O relatório completo, exibido no painel 🛡️ Verificação |

Falhas possíveis em `RelatorioCoerencia.falhas`: `contradicao_premissa_conclusao` e `erro_de_calculo` (graves, reprovam), `afirmacao_sem_evidencia` e `violacao_de_escopo` (leves, viram alerta), ou `nenhuma`.

**Evidências:** antes da verificação, as saídas das ferramentas são convertidas em **frases simples** (lista de textos), que servem de premissa para o modelo NLI. Ex.: `{"saldo_disponivel": 14}` → "o saldo disponível da sprint é de 14 pontos". As evidências se acumulam durante a sessão.

### 7.7 Trajetória e `TurnoIntegrado` — o resultado do turno

**Etapa 10.** Tudo o que a interface precisa para exibir uma resposta.

**Item da trajetória** (uma ferramenta chamada):
```json
{"ferramenta": "calcular_capacidade_sprint", "tipo": "hardcoded",
 "argumentos": {"projeto": "Portal", "numero_sprint": 13}, "observacao": "{...saída da ferramenta...}"}
```

**`TurnoIntegrado`**

| Campo | Descrição | Onde aparece na interface |
|---|---|---|
| `mensagem`, `resposta` | Pergunta e resposta final | Conversa |
| `motor` | `executor` ou `langgraph` | — |
| `intencao`, `estado_sessao` | Resultado das etapas 1–2 | — |
| `memorias_usadas` | Textos das memórias da etapa 3 | Painel 🧠 Memórias usadas |
| `trajetoria` | Lista de itens acima | Painel 🔧 Trajetória |
| `verificacao` | `RelatorioVerificacao` da resposta final | Selo ✅/⚠️ e painel 🛡️ |
| `verificacao_rascunho`, `resposta_rascunho`, `corrigida` | Rascunho reprovado e seu relatório, se houve autocorreção | Painel 🛡️ ("Rascunho reprovado") |
| `pendencias` | Propostas de registro | Caixa 📝 Aprovação humana |
| `pediu_esclarecimento` | Se o turno parou na etapa 2 | — |
| `duracao_s` | Tempo total | ⏱️ |

### 7.8 `AnaliseDemanda` — triagem da Fase 1

Usada apenas na chain da Fase 1 (notebook 1), não no fluxo da interface. Campos: `resumo`, `tipo` (`nova_funcionalidade`/`correcao`/`melhoria_tecnica`/`duvida`), `projeto`, `componentes_afetados`, `complexidade` (`baixa`/`media`/`alta`), `riscos`, `perguntas_em_aberto`, `proximos_passos`.

---

## 8. Arquivos de registro e de apoio (JSON)

### 8.1 `logs/execucoes.jsonl` — log técnico de execução

**Formato:** JSON Lines (um objeto JSON por linha). **Gravado** em todas as etapas que chamam o modelo ou ferramentas.

| `tipo` do evento | Campos | Quando |
|---|---|---|
| `llm_inicio` | `ts`, `sessao`, `modelo`, `n_mensagens` | Início de uma chamada ao modelo |
| `llm_fim` | `ts`, `sessao`, `duracao_s`, `tokens` (entrada, saída, total) | Fim da chamada |
| `llm_erro` | `ts`, `sessao`, erro | Falha da chamada (ex.: créditos esgotados) |
| `decisao` | `ts`, `sessao`, `ferramenta`, `entrada` | O agente decidiu chamar uma ferramenta |
| `tool_inicio` / `tool_fim` | `ts`, `sessao`, `ferramenta`, `entrada` / saída e duração | Execução da ferramenta |
| `resposta` | `ts`, `sessao`, `saida` | Resposta final do agente |

Conteúdo atual: 747 eventos. Serve para auditoria, cálculo de custo (tokens) e depuração, sem depender de internet. O LangSmith, quando ligado, registra as mesmas informações na nuvem.

### 8.2 `logs/issues_simuladas.json` — issues em modo simulado

**Etapa 6.3**, quando a escrita real no GitHub está desligada (`GITHUB_ESCRITA_REAL=0`). Lista de issues com: `numero` (a partir de 1001), `titulo`, `estado`, `url` ("(simulada) issue #1001"), `corpo`, `rotulos`, `criada_em`. Mesmo formato de uma issue real, sem tocar no GitHub.

### 8.3 `fabrica_agentica/demo/fixtures/*.json` — respostas gravadas das APIs

**Etapa 5** (5a, 5c, 5d), no modo demonstração, nos testes ou com `APIS_OFFLINE=1`. São 17 arquivos com respostas reais gravadas da BrasilAPI (`feriados_<ano>.json`), PyPI (`pypi_<pacote>.json`), OSV (`osv_<pacote>_<versao>.json`) e GitHub (`github_issues.json`). Permitem rodar o agente sem internet e com resultado sempre igual.

### 8.4 `relatorio/avaliacao/` — resultados da avaliação

Não usados no processamento de mensagens: são a saída dos experimentos LangSmith. `resultados_*.csv` (uma linha por caso de teste, com ferramentas chamadas e notas de cada avaliador) e `resumo.json` (médias por experimento e links).

---

## 9. Mapa: etapa do processamento × estrutura de dados

**L** = leitura · **E** = escrita

| Etapa | backlog.db | memoria.db | historico_conversas.db | checkpoints.db | indice_faiss | Estruturas em memória | Logs |
|---|---|---|---|---|---|---|---|
| 1. Entender o pedido | | | | | | `IntencaoEntidades` → estado da sessão | E |
| 2. Falta informação? | | | E (pergunta) | | | estado da sessão | |
| 3. Lembrar | | **L** `memorias` (+ `acessos`) | | | | `Memoria` | |
| 4. Montar o contexto | | | **L** `mensagens` | **L/E** (LangGraph) | | estado da sessão | |
| 5a. Capacidade | **L** `projetos`, `sprints`, `alocacoes`, `desenvolvedores`, `historias` | | | L/E (LangGraph) | | saída da capacidade | E |
| 5b. Regras da empresa | | | | L/E (LangGraph) | **L** | trechos com distância | E |
| 5c/5d. Bibliotecas, GitHub | | | | L/E (LangGraph) | | (fixtures no modo demo) | E |
| 5e. Criar atividades | | | | L/E (LangGraph) | | `PlanoTrabalho`, `Historia` | E |
| 5 / SQL | **L** (qualquer tabela) | | | L/E (LangGraph) | | | E |
| Fim da etapa 5 | | | **E** pergunta e resposta | | | trajetória, estado da sessão | |
| 6. Rascunho | | | | | | `TurnoIntegrado` (rascunho) | E |
| 7. Verificar | | L (memórias como evidência) | | | | evidências, `Afirmacao`, `RelatorioVerificacao` | E |
| 8. Autocorrigir | | | **E** substitui a resposta | | | `RelatorioVerificacao` | E |
| 9. Aprender | | **E** `memorias` | | | | `FatosExtraidos`, `DecisaoAtualizacao` | E |
| 10. Mostrar | | L (painel da barra lateral) | | | | `TurnoIntegrado` | |
| 6.2 Propor registro | | **E** `pendencias` (aguardando) | | **E** `__interrupt__` (LangGraph) | | `PlanoTrabalho` | E |
| 6.3 Aprovar | **E** `historias` (+ L `projetos`, `sprints`) | **L/E** `pendencias` (executada) | | **E** `__resume__` (LangGraph) | | | issues_simuladas.json (modo simulado) |
| 6.4 Rejeitar | | **E** `pendencias` (rejeitada) | | **E** `__resume__` (LangGraph) | | | |
| 💾 Encerrar sessão | | **E** `memorias` (episódio) | **L** `mensagens` | | | | |
