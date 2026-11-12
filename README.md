# Tech Lead Agêntico — o 1º agente de uma fábrica agêntica de software

Projeto de disciplina **Agentes Cognitivos com LangChain** (MBA em Engenharia de IA, Infnet) · Adriano Carvalho

Um agente único que transforma demandas em linguagem natural em **planos de trabalho verificados** (épico → histórias com critérios Gherkin → tarefas), consultando a capacidade da sprint, o Manual de Engenharia, bibliotecas (PyPI/OSV), issues (GitHub) e feriados (BrasilAPI), com memória de curto e longo prazo, verificação automática das respostas (NLI + coerência lógica) e avaliação no LangSmith. Empresa e dados são **fictícios** (NovaForja Software). Na próxima disciplina, este agente será o orquestrador de outros agentes da fábrica.

## Documentação

| Documento | Conteúdo |
|---|---|
| [Manual do usuário](notebooks_doc/manual_agente.md) | Como usar a interface web (cada botão, campo e painel) e o passo a passo do processamento de uma mensagem, do envio à aprovação |
| [Estrutura do projeto](notebooks_doc/estrutura_projeto.md) | Todas as pastas e arquivos: finalidade, tipo, tecnologia e quando são usados |
| [Estrutura de dados](notebooks_doc/estrutura_dados.md) | Bancos SQLite (tabelas e colunas), índice FAISS, esquemas Pydantic e arquivos de registro, com a etapa do processamento em que cada um é usado |
| [Relatório (PDF)](relatorio/adriano_carvalho_ai-agents_langchain-agents.pdf) | Decisões fase a fase, resultados, avaliação e limitações |

## Estrutura

```
fabrica_agentica/
  config.py            # .env, provedor de LLM (anthropic | openai | demo), adaptador ChatClaudeCompat, embeddings
  prompts.py           # templates, prompt PTCF, few-shot e chain-of-thought
  esquemas.py          # contratos Pydantic (AnaliseDemanda, PlanoTrabalho, IntencaoEntidades)
  chains/              # fase1 (LCEL x @chain), fase2 (sequencial, paralela, RouterChain), text_to_query
  ferramentas/         # hardcoded, apis, sql, rag, transformacao_consulta, acoes, catalogo (12 ferramentas)
  memoria/             # curto_prazo (janela+resumo), longo_prazo (CoALA), intencao, historico (SQLite)
  verificacao/         # evidencias, verificador (fact-check + NLI + coerência)
  agentes/             # react_classico, executor, chatbot, recuperacao, integrador, langgraph_agente
  observabilidade/     # callbacks (log JSONL), avaliacao (LangSmith + local)
  demo/                # modelo roteirizado + respostas gravadas das APIs (modo sem credenciais)
dados/                 # backlog.db, manual/ (MAN-01..07), indice_faiss/ (índice existente)
scripts/               # criar_banco.py, construir_indice.py, rodar_avaliacao.py
notebooks_doc/         # notebooks 01 a 05 (evidências de cada fase, executados com Claude) e documentação
app.py                 # interface Streamlit
assets/                # imagens da interface (logomarca)
tests/                 # pytest (modo demo)
relatorio/             # relatório, capturas e resultados da avaliação
```

## Passo a passo no VS Code

1. Instale o **Python 3.12** e, no VS Code, as extensões **Python** e **Jupyter**.
2. Abra a pasta do projeto e crie o ambiente virtual:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copie `.env.example` para `.env` e preencha o que tiver:
   - `ANTHROPIC_API_KEY` (platform.claude.com) — sem ela, o projeto roda em **modo demonstração**;
   - `LANGSMITH_API_KEY` (smith.langchain.com) e `LANGSMITH_TRACING=true` — opcional;
   - `GITHUB_REPO` e `GITHUB_TOKEN` (token *fine-grained* só com Issues) — opcional; a escrita real exige também `GITHUB_ESCRITA_REAL=1`.
4. Dados (já incluídos; para recriar): `python scripts/criar_banco.py` e `python scripts/construir_indice.py`.
5. Na primeira execução, os modelos locais da Hugging Face são baixados (embeddings ~470 MB, NLI ~1,1 GB).

## Como executar

| O quê | Comando |
|---|---|
| Notebooks das fases | abrir `notebooks_doc/0X_*.ipynb` no VS Code (kernel `.venv`) e executar de cima a baixo |
| Interface Streamlit | `streamlit run app.py` |
| Testes (modo demo, sem custo) | `pytest -q` |
| Avaliação (LangSmith ou local) | `python scripts/rodar_avaliacao.py` (ou `--local`) |
| Tudo sem chave (professor) | `LLM_PROVIDER=demo` no `.env` (ou sem `ANTHROPIC_API_KEY`) |
| Alternativa OpenAI | `LLM_PROVIDER=openai` e `OPENAI_API_KEY` no `.env` |

No VS Code, `F5` oferece as configurações de `.vscode/launch.json` (Streamlit, testes e avaliação).

## Modo demonstração (alternativa *dummy*)

Sem credenciais, `fabrica_agentica/demo/modelo_demo.py` substitui o LLM por um modelo roteirizado que fala os mesmos protocolos (tool calling, ReAct em texto, RouterChain, saída estruturada, streaming), e as APIs usam respostas reais gravadas em `demo/fixtures/`. Cálculos, SQL, FAISS, NLI e o fluxo de aprovação são os reais. As respostas do modo demo começam com `[modo demonstração]`.

## Segurança

- Chaves só no `.env` (nunca versionado). O agente acessa o backlog por conexão **somente leitura**, com filtro de comandos.
- Gravações no backlog e issues no GitHub acontecem **só após aprovação humana** (botão na interface, ou `HumanInTheLoopMiddleware` na versão LangGraph). A escrita real no GitHub exige `GITHUB_ESCRITA_REAL=1`.
- O índice FAISS é carregado com `allow_dangerous_deserialization=True` porque foi gerado pelo próprio projeto; nunca carregue índices de terceiros assim.

## Mapa rubrica → evidência

| Competência / item | Onde |
|---|---|
| C1 anatomia, classificação, planejamento e memória (desenho) | `notebooks_doc/01` §2–5 |
| C1 PromptTemplate/ChatPromptTemplate, parser JSON, Runnable, `@chain`, LCEL + justificativa | `notebooks_doc/01` §6–10; `chains/fase1.py`; `prompts.py` |
| C2 comparação de orquestradores | `notebooks_doc/02` §1 |
| C2 ReAct com `initialize_agent` + memória | `notebooks_doc/02` §2; `agentes/react_classico.py` |
| C2 chains sequenciais/paralelas e `RouterChain` | `notebooks_doc/02` §4–5; `chains/fase2.py` |
| C2 API externa via function calling | `notebooks_doc/02` §3 e §7; `ferramentas/apis.py` |
| C2 PTCF + few-shot + CoT | `notebooks_doc/02` §6; `prompts.py` |
| C2 confiabilidade (parsers, memória, FAISS, callbacks) + justificativas | `notebooks_doc/02` §8; `observabilidade/callbacks.py` |
| C3 CoALA, janela de contexto, comparação LangMem/Mem0/Letta | `notebooks_doc/03` §1 |
| C3 chatbot com `ConversationBufferMemory`, intenção/entidades, multi-turno | `notebooks_doc/03` §2–5; `memoria/`; `agentes/chatbot.py` |
| C4 ferramentas por tipo, APIs por tipo de uso, text-to-query | `notebooks_doc/04` §1–3; `ferramentas/catalogo.py`; `chains/text_to_query.py` |
| C4 agente de recuperação com FAISS existente, falha real diagnosticada e corrigida | `notebooks_doc/04` §4–6; `agentes/recuperacao.py`; `ferramentas/transformacao_consulta.py` |
| C5 verificação factual (NLI) e coerência lógica | `notebooks_doc/05` §1; `verificacao/` |
| C5 agente único com `create_openai_tools_agent` + `AgentExecutor` + `RunnableWithMessageHistory` | `notebooks_doc/05` §2; `agentes/integrador.py` |
| C5 Streamlit | `app.py`; `notebooks_doc/05` §4; `relatorio/capturas/` |
| C5 avaliação de qualidade e trajetória no LangSmith | `notebooks_doc/05` §5; `observabilidade/avaliacao.py`; `relatorio/avaliacao/` |
| Extra: versão LangGraph com aprovação humana nativa | `notebooks_doc/05` §3; `agentes/langgraph_agente.py` |

## Uso de IA

Este projeto foi desenvolvido com apoio do **Claude Code** (Anthropic), conforme a política "Sinal Verde" da disciplina; o relatório técnico detalha onde e como a ferramenta foi usada e como os resultados foram verificados.
