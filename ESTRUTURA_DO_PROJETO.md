# Estrutura do projeto — Tech Lead Agêntico

Guia de todas as pastas e arquivos do projeto `projeto_fabrica_agentica/`: o que é cada um, de que tipo, com qual tecnologia, o que contém e quando é usado.

> **Legenda da coluna "Git":** ✅ = versionado no GitHub · ⛔ = fica só na máquina (listado no `.gitignore`), porque contém segredos, dados gerados durante o uso ou arquivos temporários.

---

## Visão geral (árvore)

```
projeto_fabrica_agentica/
├── .claude/                     configuração do Claude Code (ferramenta de IA usada no desenvolvimento)
│   └── launch.json
├── .vscode/                     configuração do VS Code
│   └── launch.json
├── .venv/                       ambiente virtual Python (bibliotecas instaladas)
├── .git/                        histórico do repositório Git
├── .env                         chaves e configurações secretas
├── .env.example                 modelo do .env, sem segredos
├── .gitignore                   lista do que o Git deve ignorar
├── README.md                    apresentação e passo a passo
├── ESTRUTURA_DO_PROJETO.md      este guia
├── requirements.txt             lista de bibliotecas Python
├── app.py                       interface web (Streamlit)
├── assets/                      imagens da interface
│   └── infnet_logo.png
├── dados/                       dados da empresa fictícia e bancos gerados pelo agente
│   ├── backlog.db
│   ├── memoria.db
│   ├── historico_conversas.db
│   ├── checkpoints.db  (+ -shm, -wal)
│   ├── manual/                  7 documentos do Manual de Engenharia
│   └── indice_faiss/            índice vetorial do manual (RAG)
├── fabrica_agentica/            o código do agente (pacote Python)
│   ├── config.py · esquemas.py · prompts.py
│   ├── agentes/                 os agentes de cada fase
│   ├── chains/                  as chains das fases 1, 2 e 4
│   ├── ferramentas/             as 12 ferramentas do agente
│   ├── memoria/                 memória de curto e longo prazo, intenção
│   ├── verificacao/             verificador NLI + coerência
│   ├── observabilidade/         logs e avaliação LangSmith
│   └── demo/                    modo demonstração (sem chave, sem custo)
│       └── fixtures/            respostas gravadas das APIs
├── notebooks/                   evidências de cada fase (01 a 05)
├── scripts/                     utilitários executados à parte
├── tests/                       testes automatizados (pytest)
├── relatorio/                   relatório final, PDF, capturas e resultados
│   ├── avaliacao/
│   └── capturas/
└── logs/                        registros de execução
```

---

## 1. Arquivos da raiz

| Arquivo | Tipo / tecnologia | Para que serve | Git |
|---|---|---|---|
| `app.py` | Script **Python** com **Streamlit** (biblioteca que transforma um script Python numa página web, sem HTML/JavaScript) | A **interface do agente**: chat, seletor de motor (AgentExecutor ou LangGraph), botão de verificação, painéis de trajetória/verificação/memórias e os botões **Aprovar/Rejeitar**. É usado na demonstração e no vídeo. Executar com `streamlit run app.py` (abre em `http://localhost:8501`). | ✅ |
| `requirements.txt` | Texto simples, formato do **pip** | Lista das bibliotecas Python e suas versões exatas (LangChain, LangGraph, Anthropic, FAISS, Streamlit...). Usado **uma vez**, na instalação: `pip install -r requirements.txt`. Fixar versões garante que o projeto rode igual em outra máquina. | ✅ |
| `.env` | Texto `CHAVE=valor` (padrão **dotenv**) | Guarda os **segredos**: chave da Anthropic, chave do LangSmith, token do GitHub e opções (provedor, escrita real no GitHub). É lido automaticamente pelo `config.py` quando o agente inicia. **Nunca vai para o GitHub.** | ⛔ |
| `.env.example` | Texto `CHAVE=valor` | Modelo do `.env` **sem os valores**, com comentários explicando cada variável. Quem baixar o projeto copia para `.env` e preenche. | ✅ |
| `.gitignore` | Texto, padrão do **Git** | Lista do que o Git **não** deve enviar: `.env`, `.venv/`, `logs/`, bancos gerados no uso (`memoria.db`, `historico_conversas.db`, `checkpoints.db`), caches. É a proteção contra vazar chaves por engano. | ✅ |
| `README.md` | **Markdown** (texto com formatação leve: `#` títulos, `|` tabelas) | Porta de entrada do repositório: o que é o projeto, estrutura, passo a passo no VS Code, como executar, modo demonstração, segurança, **mapa rubrica → evidência** e declaração do uso de IA. O GitHub o exibe na página inicial. | ✅ |
| `ESTRUTURA_DO_PROJETO.md` | Markdown | Este guia. | — |

### Pastas ocultas da raiz (começam com ponto)

| Pasta | Finalidade | Git |
|---|---|---|
| `.venv/` | **Ambiente virtual Python 3.12**: uma cópia isolada do Python com todas as bibliotecas do `requirements.txt`. Evita conflito com outros projetos do computador. É grande (centenas de MB, inclui PyTorch) e é recriada com `pip install`, por isso não vai para o Git. | ⛔ |
| `.git/` | Banco interno do **Git**: todo o histórico de commits do repositório `DriccoC/tech-lead-agentico`. Não se mexe nela manualmente. | (é o próprio Git) |
| `.vscode/` | Configurações do **VS Code** para este projeto. | ✅ |
| `.claude/` | Configurações do **Claude Code** (a IA usada no desenvolvimento). | ⛔ |

| Arquivo | Tipo / tecnologia | Para que serve |
|---|---|---|
| `.vscode/launch.json` | **JSON** (formato de dados chave/valor) | Cria 3 atalhos no menu "Executar e depurar" do VS Code: **rodar o Streamlit**, **rodar os testes** e **rodar a avaliação**. Cada um já carrega o `.env`. Permite rodar tudo com F5, sem digitar comandos. |
| `.claude/launch.json` | JSON | Diz ao Claude Code como subir o Streamlit (porta 8501) para abrir a interface no navegador do app durante o desenvolvimento. Não é usado pelo agente. |

### `assets/` — imagens da interface

**Finalidade:** arquivos estáticos usados pela interface Streamlit.

| Arquivo | Tipo | Conteúdo | Quando é usado | Git |
|---|---|---|---|---|
| `infnet_logo.png` | **PNG** (imagem com fundo transparente), 128×128 px | Miniatura da logomarca do Instituto Infnet. | Exibida no rodapé da barra lateral do `app.py`, entre "MBA - Engenharia de IA" e "Instituto Infnet" (embutida na página em base64). | ✅ |

---

## 2. `dados/` — os dados da empresa e a memória do agente

**Finalidade:** guardar tudo o que o agente **consulta** (backlog, manual) e tudo o que ele **grava** enquanto trabalha (memórias, histórico, pendências de aprovação). Nada de código aqui: só dados.

**Responsabilidades:** representar a empresa fictícia **NovaForja Software**; persistir a memória entre sessões; guardar o índice do RAG.

### O que é um arquivo `.db`?

Os quatro `.db` desta pasta são bancos de dados **SQLite**. O SQLite é um banco de dados relacional (tabelas, linhas, colunas, consultas SQL) que cabe **inteiro num único arquivo**: não precisa instalar servidor, abrir porta nem criar usuário. O Python já traz o SQLite embutido (`import sqlite3`). Para inspecionar: `sqlite3 dados/backlog.db ".tables"` ou a extensão "SQLite Viewer" do VS Code.

| Arquivo | Tecnologia | Conteúdo | Quando é usado | Git |
|---|---|---|---|---|
| `backlog.db` | SQLite | O "Jira" da empresa fictícia. Tabelas: `desenvolvedores` (8 pessoas, papel e senioridade), `projetos` (Portal, PagaFacil, AppCampo), `sprints` (6, com datas), `alocacoes` (23: quem está em qual sprint, com folgas), `historias` (22 histórias do backlog), `bugs` (5, com severidade e status). | **Leitura:** sempre que o agente usa `consultar_backlog_sql` ou `calcular_capacidade_sprint` (conexão somente leitura). **Escrita:** só depois do clique em **Aprovar** (novas histórias). Criado por `scripts/criar_banco.py`. | ✅ |
| `memoria.db` | SQLite + **vetores de embedding** guardados junto com o texto | **Memória de longo prazo** do agente. Tabela `memorias` (20): 6 **semânticas** (fatos duráveis, ex.: "o Portal atende clientes B2B") e 14 **episódicas** (resumos de sessões anteriores). Cada memória tem o texto, o usuário dono e um vetor numérico para busca por significado. Tabela `pendencias` (5): propostas de registro aguardando aprovação, aprovadas ou rejeitadas. | A cada turno: o agente busca memórias parecidas com a pergunta e, ao final, grava fatos novos. Ao clicar "Encerrar sessão", grava um episódio. As pendências são criadas por `propor_registro_backlog`. Aparece no expander "🧠 Memória de longo prazo" da interface. | ⛔ |
| `historico_conversas.db` | SQLite | **Memória de curto prazo persistente** do motor **AgentExecutor**: tabela `mensagens` (138) com cada mensagem do usuário e do agente, por sessão. Usada pelo `RunnableWithMessageHistory`. | Em toda conversa no motor AgentExecutor: antes de responder, o agente relê o histórico da sessão (recente na íntegra, antigo resumido). | ⛔ |
| `checkpoints.db` | SQLite, formato do **LangGraph** (`SqliteSaver`) | **Estado completo do grafo** do motor **LangGraph**, salvo a cada passo: tabela `checkpoints` (51 "fotografias" do estado) e `writes` (112 gravações intermediárias), por `thread_id`. | Em toda conversa no motor LangGraph. É o que permite **pausar** o agente na aprovação humana e **retomar** do mesmo ponto depois do clique, mesmo que o programa tenha sido fechado. | ⛔ |
| `checkpoints.db-wal` | Arquivo auxiliar do SQLite (**Write-Ahead Log**) | Alterações recentes ainda não incorporadas ao `.db` principal. O SQLite escreve primeiro aqui (mais rápido e seguro contra queda) e depois consolida. | Automaticamente, enquanto o banco está aberto. **Não apagar** com o programa rodando. | ⛔ |
| `checkpoints.db-shm` | Arquivo auxiliar do SQLite (**shared memory**) | Índice de memória compartilhada que coordena o acesso ao `-wal`. | Automaticamente; some quando o banco é fechado corretamente. | ⛔ |

### `dados/manual/` — o Manual de Engenharia da empresa

**Finalidade:** as **regras da empresa**, escritas em linguagem formal, como num manual corporativo real. **Responsabilidade:** ser a base de conhecimento do RAG. São arquivos **Markdown** (`.md`) legíveis por qualquer pessoa.

| Arquivo | Conteúdo |
|---|---|
| `MAN-01_definicao_de_pronto.md` | Definição de Pronto (*Definition of Done*): critérios obrigatórios para uma entrega ser considerada concluída, critérios por tipo de entrega e exceções. |
| `MAN-02_padroes_de_codigo.md` | Padrões de codificação por tecnologia: Python (FastAPI), Java (Quarkus), front-end (React), mobile (Flutter) e convenções gerais. |
| `MAN-03_versionamento_e_implantacao.md` | Modelo de ramificação (branches), ramos de curta duração, **janela de congelamento de mudanças**, procedimento de implantação e versionamento semântico. |
| `MAN-04_seguranca_de_dependencias.md` | Segurança da cadeia de suprimentos: critérios para admitir uma biblioteca, classificação de severidade CVSS v3 e monitoramento contínuo de vulnerabilidades. |
| `MAN-05_autenticacao_e_identidade.md` | Autenticação e identidade: protocolos homologados, provedores federados, bibliotecas homologadas, tokens e sessões, autenticação multifator e revisão de segurança. |
| `MAN-06_planejamento_e_estimativa.md` | Planejamento de sprints: iterações, regras de estimativa, **fórmula de capacidade da sprint**, priorização e decomposição de demandas. |
| `MAN-07_registros_de_decisao_arquitetural.md` | Decisões de arquitetura já tomadas (ADRs): FastAPI para Python, Kafka para eventos de pagamento, provedor de identidade central, OpenTelemetry e banco por serviço. |

**Quando é usado:** só indiretamente. O agente não lê esses arquivos; ele consulta o índice FAISS gerado a partir deles. Se um documento for alterado, é preciso rodar `scripts/construir_indice.py` de novo. Versionados ✅.

### `dados/indice_faiss/` — o índice vetorial (RAG)

**Finalidade:** permitir a **busca por significado** no manual. **Responsabilidade:** responder rapidamente "quais trechos do manual mais se parecem com esta pergunta?".

**Tecnologia:** **FAISS** (*Facebook AI Similarity Search*), biblioteca da Meta para busca de vetores parecidos. Os 7 documentos foram cortados em **42 trechos** (*chunks*); cada trecho virou um vetor de 384 números pelo modelo de embeddings `paraphrase-multilingual-MiniLM-L12-v2` (Hugging Face, roda localmente, sem custo).

| Arquivo | Tipo | Conteúdo | Quando é usado |
|---|---|---|---|
| `index.faiss` | **Binário do FAISS** (não é legível) | Os 42 vetores, organizados para busca rápida. | Carregado na memória quando o agente inicia (`rag.carregar_indice`) e consultado a cada chamada de `buscar_manual_engenharia`. |
| `index.pkl` | **Pickle** (formato binário do Python para salvar objetos) | O texto de cada trecho e seus metadados (documento, seção, `chunk_id`), ligados à posição de cada vetor. | Junto com o `index.faiss`. Por ser pickle, só é seguro carregar arquivos gerados por nós (por isso o código usa `allow_dangerous_deserialization=True` conscientemente). |
| `catalogo.json` | **JSON** (legível) | Lista dos 42 trechos: `chunk_id`, documento, título, seção, arquivo de origem e o início do texto. | Para conferência humana e para o relatório/notebook (mostrar quais trechos existem e citar `CHK_xxx` nas respostas). |

Todos gerados por `scripts/construir_indice.py`. Versionados ✅ (o enunciado pede um índice "já existente").

---

## 3. `fabrica_agentica/` — o código do agente

**Finalidade:** é o **pacote Python** com toda a lógica. Os notebooks, o `app.py`, os scripts e os testes **importam** daqui; nada é duplicado.

**Responsabilidades:** configuração, prompts, ferramentas, memória, agentes, verificação, observabilidade e modo demonstração, cada um na sua subpasta.

> **Sobre os arquivos `__init__.py` (vazios):** existem em `fabrica_agentica/` e em cada subpasta. São a convenção do Python que diz "esta pasta é um pacote importável", permitindo `from fabrica_agentica.ferramentas import rag`. Não têm conteúdo.

Todos os arquivos `.py` são **código Python 3.12** e estão versionados ✅.

### Arquivos da raiz do pacote

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `config.py` | Python + `python-dotenv` + `langchain-anthropic` + `langchain-huggingface` | **Configuração central**: lê o `.env`; escolhe o provedor (Anthropic, OpenAI ou demo); cria os modelos Claude por papel (agente = Sonnet, auxiliar/juiz); cria os embeddings; define caminhos e o modelo NLI. Contém o adaptador `ChatClaudeCompat`, que permite usar `create_openai_tools_agent` (feito para OpenAI) com o Claude. | Em todo lugar, logo no início. |
| `esquemas.py` | Python + **Pydantic** (validação de dados por tipos) | Os **"contratos" das saídas estruturadas**: `AnaliseDemanda`, `Historia`, `PlanoTrabalho`, `IntencaoEntidades`. Obrigam o LLM a devolver JSON num formato exato, validado automaticamente. | Sempre que o agente gera um plano, uma análise ou classifica a intenção. |
| `prompts.py` | Python + `ChatPromptTemplate` (LangChain) | Os **textos de instrução** do agente: system prompt no formato **PTCF** (Persona, Tarefa, Contexto, Formato), exemplos *few-shot*, raciocínio passo a passo, prompts de resumo de memória. | Na montagem de todos os agentes e chains. |

### `fabrica_agentica/agentes/` — os agentes

**Finalidade:** montar os **agentes** (o "cérebro" que decide quais ferramentas usar). **Responsabilidade:** um arquivo por construção exigida em cada fase, evoluindo até o integrador.

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `react_classico.py` | `initialize_agent` + `ZERO_SHOT_REACT_DESCRIPTION` + `ConversationBufferMemory` (**langchain-classic**, legado) | **Fase 2.** Agente ReAct clássico, que raciocina em texto: Pensamento → Ação → Observação → Resposta final. | Notebook 2. |
| `executor.py` | `create_openai_tools_agent` + `AgentExecutor` | **Fase 2/3.** Agente com *function calling* (o modelo chama ferramentas de forma estruturada, sem texto livre). Monta o prompt e extrai a trajetória. | Notebooks 2 e 3; base do integrador. |
| `chatbot.py` | AgentExecutor + memórias + intenção | **Fase 3.** Chatbot multiturno: reconhece intenção, pergunta o que faltar, usa memória curta e longa e grava fatos novos. | Notebook 3. |
| `recuperacao.py` | AgentExecutor + FAISS | **Fase 4.** Agente especialista no manual, em duas versões (sem e com transformação de consulta), para diagnosticar e corrigir a falha do RAG. | Notebook 4. |
| `integrador.py` | AgentExecutor + `RunnableWithMessageHistory` + verificador | **Fase 5 — o agente final.** Classe `TechLeadAgentico`: une todas as 12 ferramentas, as memórias, a verificação e a autocorreção, e expõe `conversar`, `aprovar`, `rejeitar` e `encerrar_sessao`. | Interface Streamlit, notebook 5 e avaliação LangSmith. |
| `langgraph_agente.py` | **LangGraph**: `create_agent` + `SqliteSaver` + `HumanInTheLoopMiddleware` | **Fase 5 — motor alternativo.** O mesmo agente como grafo, com estado salvo em `checkpoints.db` e **pausa nativa** antes de gravar no backlog. Base para a próxima disciplina (multiagente). | Quando o motor "LangGraph" é escolhido na interface; notebook 5. |

### `fabrica_agentica/chains/` — as chains

**Finalidade:** **fluxos fixos** (sem autonomia de decisão), exigidos nas fases iniciais. **Responsabilidade:** mostrar as formas de composição do LangChain.

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `fase1.py` | **LCEL** (`prompt \| modelo \| parser`) e `@chain` + `PydanticOutputParser` | **Fase 1.** A mesma chain "demanda → triagem em JSON" de duas formas: declarativa (LCEL) e imperativa (`@chain`, com nova tentativa se o JSON vier inválido). | Notebook 1. |
| `fase2.py` | `SequentialChain`, `RunnableParallel`, `LLMRouterChain`/`MultiPromptChain` | **Fase 2.** Chain sequencial (demanda → épico → histórias), chain paralela (bibliotecas ∥ normas ∥ capacidade) e roteador por tipo de pedido. | Notebook 2. |
| `text_to_query.py` | LCEL + SQLite | **Fase 4.** Pergunta → SQL → execução → resposta, com **autocorreção** quando o SQL falha (o erro volta ao modelo, até 2 tentativas). | Notebook 4. |

### `fabrica_agentica/ferramentas/` — as ferramentas

**Finalidade:** as **"mãos" do agente**: tudo o que ele consegue consultar ou fazer. **Responsabilidade:** separar a lógica de cada tipo de ferramenta e expô-las ao LLM num catálogo único.

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `catalogo.py` | Decorador `@tool` do LangChain + Pydantic | **O catálogo das 12 ferramentas** que o LLM enxerga: nome, descrição e esquema de argumentos de cada uma, mais o mapa `TIPOS` (hardcoded, API externa, text-to-query, RAG, semântica, ação). Só "embala" a lógica que está nos outros arquivos. | Sempre que o agente é criado. |
| `hardcoded.py` | Python puro (sem IA) | Cálculos **determinísticos**: dias úteis descontando feriados, capacidade da sprint (fórmula do MAN-06), comparação de versões, classificação CVSS. Mesma entrada → mesma saída, sem custo. | `calcular_capacidade_sprint`, `comparar_versoes`, `classificar_cvss`. |
| `apis.py` | **httpx** (cliente HTTP) + APIs REST | Clientes das **APIs externas reais**: BrasilAPI (feriados), PyPI (versões), OSV.dev (vulnerabilidades) e GitHub (buscar e abrir issues). No modo demo, usa as respostas gravadas em `demo/fixtures/`. | Ferramentas de API externa; `abrir_issue_github` só após aprovação. |
| `sql.py` | SQLite (`sqlite3`) | **Text-to-query com guardrails**: conexão somente leitura, aceita só `SELECT`/`WITH`, bloqueia palavras proibidas por palavra inteira (sem bloquear `updated_at`), força `LIMIT 50`. | `consultar_backlog_sql`. |
| `rag.py` | **FAISS** + embeddings Hugging Face | Carrega o índice existente e faz a busca, devolvendo os trechos com a **distância** (score) e a classificação da qualidade do resultado (diagnóstico "open-box"). | `buscar_manual_engenharia`. |
| `transformacao_consulta.py` | LLM auxiliar + FAISS | Corrige o descompasso de vocabulário ("subir na main" × "ramo principal protegido") com 3 técnicas: **reescrita**, **multi-query** e **HyDE** (documento hipotético). | Dentro de `buscar_manual_engenharia` (configuração adotada) e no notebook 4 (comparação). |
| `acoes.py` | SQLite | **Ações com efeito real, só com aprovação humana.** `propor_registro` cria uma pendência; `executar_registro` grava no backlog e abre as issues, e **só é chamada pela interface** depois do clique. O LLM não tem acesso a ela. | Ao propor (agente) e ao aprovar/rejeitar (interface). |

### `fabrica_agentica/memoria/` — a memória

**Finalidade:** fazer o agente **lembrar**. **Responsabilidade:** memória de curto prazo (a conversa atual), longo prazo (entre sessões) e o estado da conversa (intenção e entidades). Segue o modelo **CoALA** (semântica, episódica, procedural).

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `curto_prazo.py` | Subclasse de `ConversationBufferMemory` | Janela deslizante + resumo: as últimas mensagens vão na íntegra, as antigas viram um resumo que preserva projeto, sprint, pessoas e números. | Chatbot da Fase 3. |
| `historico.py` | SQLite + `BaseChatMessageHistory` | Histórico **persistente** das conversas em `historico_conversas.db`, usado pelo `RunnableWithMessageHistory`, com compressão da janela de contexto. | Motor AgentExecutor do integrador (Fase 5). |
| `longo_prazo.py` | SQLite + embeddings + similaridade de cosseno | Memória **semântica** (fatos) e **episódica** (sessões) em `memoria.db`. Busca por significado, e **atualiza** em vez de duplicar quando um fato muda. | A cada turno (buscar e gravar) e ao encerrar a sessão. |
| `intencao.py` | LLM auxiliar com saída estruturada (Pydantic) | Reconhece a **intenção** (planejar, consultar backlog, checar dependência, consultar padrão, conversa geral) e as **entidades** (projeto, sprint, pacote...). Mantém o estado da sessão e pergunta o que faltar (*slot filling*). | No início de cada turno. |

### `fabrica_agentica/verificacao/` — o verificador

**Finalidade:** **conferir a resposta antes de mostrá-la**. **Responsabilidade:** detectar números inventados, afirmações contraditórias com as ferramentas e raciocínio incoerente; acionar a autocorreção.

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `evidencias.py` | Python | Converte as saídas das ferramentas (JSON) em **frases simples em português**, que servem de "premissa" para o NLI, e coleta os números para o fact-check. | A cada verificação. |
| `verificador.py` | LLM auxiliar + **modelo NLI** `mDeBERTa-v3` (Hugging Face, **roda localmente** via `transformers`) + LLM juiz | As 4 etapas: (1) extrai as afirmações da resposta; (2) confere os números contra as evidências; (3) **NLI** decide se cada afirmação é sustentada, contradita ou neutra; (4) juiz LLM avalia a coerência lógica. Se reprovar, gera o *feedback* para a resposta ser corrigida. | Depois de cada resposta que usou ferramentas (quando "Verificar respostas" está ligado). Gera o selo ✅/⚠️ da interface. |

### `fabrica_agentica/observabilidade/` — logs e avaliação

**Finalidade:** **observar e medir** o agente. **Responsabilidade:** registrar o que acontece em cada execução e avaliar a qualidade num conjunto de casos de teste.

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `callbacks.py` | Callbacks do LangChain + **JSON Lines** | `RegistroExecucao`: grava em `logs/execucoes.jsonl` cada chamada ao LLM e a ferramentas, com duração, tokens e erros. Funciona sem internet e alimenta a "trajetória" da interface. | Em todas as execuções. |
| `avaliacao.py` | **LangSmith** (`evaluate`, datasets) | Dataset com **19 casos** e os avaliadores: cobertura de trajetória, trajetória exata, corretude (juiz LLM com saída estruturada) e taxas do verificador. Tem versão LangSmith e versão local (CSV). | Por `scripts/rodar_avaliacao.py` e no notebook 5. |

### `fabrica_agentica/demo/` — modo demonstração

**Finalidade:** permitir que **qualquer pessoa rode o projeto sem chaves e sem custo** (exigência de "alternativas dummy" do enunciado). **Responsabilidade:** imitar o LLM e as APIs externas de forma previsível.

| Arquivo | Tecnologia | Responsabilidade | Quando é usado |
|---|---|---|---|
| `modelo_demo.py` | Subclasse de `BaseChatModel` (LangChain) | Um **modelo de chat falso**: não é inteligente, mas "fala" os mesmos protocolos de um LLM real (chamada de ferramentas, ReAct em texto, roteamento, saída estruturada), para o sistema rodar de ponta a ponta. | Quando `LLM_PROVIDER=demo` ou não há chave da Anthropic; sempre nos testes. |
| `roteiro.py` | Python (regras por palavras-chave) | As **regras de decisão** do modelo falso: extrair projeto/sprint/pacote, escolher ferramentas, montar respostas. Os números exibidos vêm sempre das ferramentas reais. | Junto com `modelo_demo.py`. |

#### `fabrica_agentica/demo/fixtures/` — respostas gravadas das APIs

**Finalidade:** **17 arquivos JSON** com respostas reais das APIs, gravadas uma vez, para o modo demo e os testes funcionarem **sem internet** e sempre com o mesmo resultado.

| Arquivos | Conteúdo |
|---|---|
| `feriados_2026.json`, `feriados_2027.json` | Feriados nacionais da BrasilAPI. |
| `pypi_authlib.json`, `pypi_fastapi.json`, `pypi_pyjwt.json`, `pypi_python-jose.json`, `pypi_requests.json` | Versão mais recente de cada pacote, do PyPI. |
| `osv_<pacote>_<versão>.json` (10 arquivos: authlib, fastapi, pyjwt, python-jose, requests em versões antigas e novas) | Vulnerabilidades conhecidas daquela versão, do OSV.dev (versões antigas têm falhas; as novas, não). |
| `github_issues.json` | Issues de exemplo do repositório-sandbox. |

**Quando é usado:** em modo demo, nos testes, ou com `APIS_OFFLINE=1` no `.env`.

---

## 4. `notebooks/` — evidências por fase

**Finalidade:** a **evidência executável** de cada fase da rubrica, com texto explicativo, código e as saídas reais já gravadas. **Responsabilidade:** demonstrar cada requisito e registrar os resultados (inclusive as falhas e suas correções).

**Tipo:** `.ipynb` = **Jupyter Notebook**, um arquivo JSON que mistura células de texto (Markdown), células de código Python e as **saídas** de cada execução. Abre no VS Code ou no Jupyter. Rodam de cima a baixo.

| Arquivo | Conteúdo | Git |
|---|---|---|
| `01_fase1_chain_mvp.ipynb` | Anatomia e classificação do agente; prompts; chain demanda → JSON com Pydantic; `invoke`/`batch`/`stream`; LCEL × `@chain`. | ✅ |
| `02_fase2_agente_react.ipynb` | Comparação de orquestradores; agente ReAct clássico; chains sequencial/paralela/roteador; APIs reais; PTCF, few-shot, tratamento de erros, memória e callbacks. | ✅ |
| `03_fase3_memoria_chatbot.ipynb` | Estratégia de memória CoALA; janela + resumo; memória longa vetorial; LangMem × Mem0 × Letta; intenção e entidades; conversa multiturno ("e se tirarmos o Bruno?"). | ✅ |
| `04_fase4_ferramentas_rag.ipynb` | Ferramentas por tipo; text-to-query com guardrails; RAG sobre o índice existente; **falha real diagnosticada** pelos scores e corrigida com reescrita/multi-query/HyDE (antes × depois). | ✅ |
| `05_fase5_integrador.ipynb` | Verificador NLI; agente integrador; versão LangGraph com aprovação humana; avaliação LangSmith (experimentos A, B e C) e conclusões. É o maior (1,9 MB) por guardar todas as saídas. | ✅ |

---

## 5. `scripts/` — utilitários executados à parte

**Finalidade:** tarefas que **não fazem parte da conversa** com o agente: preparar dados, avaliar e gerar o relatório. **Responsabilidade:** tornar o projeto reprodutível (qualquer um recria os dados com um comando).

| Arquivo | Tipo / tecnologia | O que faz | Quando é usado | Git |
|---|---|---|---|---|
| `criar_banco.py` | Python + SQLite | Recria `dados/backlog.db` do zero, sempre com os mesmos dados da NovaForja. | Na instalação, ou para restaurar o backlog original. | ✅ |
| `construir_indice.py` | Python + FAISS + embeddings | Lê `dados/manual/`, corta em trechos, gera os vetores e salva `dados/indice_faiss/`. Representa o "pipeline de outro bloco" do enunciado. | **Uma vez**, ou se o manual mudar. | ✅ |
| `rodar_avaliacao.py` | Python + LangSmith | Roda os experimentos de avaliação (A com transformação, B sem, C pós-correção) e salva os CSV e o `resumo.json` em `relatorio/avaliacao/`. Opções `--so` e `--local`. | Na etapa de avaliação (consome API). | ✅ |
| `gerar_pdf.sh` | **Shell script** (zsh) + **pandoc** + **Google Chrome headless** | Converte `relatorio/relatorio.md` em HTML (pandoc, com sumário e `estilo.css`) e depois em PDF (Chrome imprimindo sem abrir janela). | Sempre que o relatório for alterado. | ✅ |

---

## 6. `tests/` — testes automatizados

**Finalidade:** garantir que as peças funcionam e que **nada quebrou** depois de uma mudança. **Responsabilidade:** testar sem chave, sem internet e sem custo (sempre em modo demo, com cópias temporárias dos bancos).

**Tecnologia:** **pytest**. Executar com `pytest -q` (ou o atalho "Testes" do VS Code).

| Arquivo | O que testa | Git |
|---|---|---|
| `conftest.py` | Não é um teste: é a **configuração** do pytest. Força o modo demo e cria cópias temporárias do backlog e das memórias, para os testes não alterarem os dados reais. | ✅ |
| `test_ferramentas.py` | Dias úteis com feriado; fórmula de capacidade do MAN-06; simulação sem o Bruno; comparação de versões; CVSS; **guardrail SQL** (bloqueia `DELETE`, aceita `updated_at`, adiciona `LIMIT`, conexão somente leitura); APIs offline. | ✅ |
| `test_agente.py` | Chains LCEL e imperativa; parser rejeitando JSON incompleto; lacunas de intenção; memória longa que atualiza em vez de duplicar; histórico com resumo; **NLI detecta contradição**; verificador reprova resposta forjada; **nada é gravado sem aprovação**; avaliadores de trajetória; agente de ponta a ponta. | ✅ |

---

## 7. `relatorio/` — o relatório final

**Finalidade:** os **entregáveis escritos** da disciplina. **Responsabilidade:** documentar decisões, resultados, comparação, limitações e evidências; gerar o PDF exigido.

| Arquivo | Tipo / tecnologia | Conteúdo | Git |
|---|---|---|---|
| `relatorio.md` | **Markdown** | O **texto-fonte** do relatório: problema e domínio, decisões fase a fase, resultados (verificação, LangSmith A/B/C, sessão real com issues), limitações, evidências e citação do uso de IA. É o arquivo que se edita. | ✅ |
| `estilo.css` | **CSS** (linguagem de estilo das páginas web) | Fontes, margens, cores das tabelas e quebra de página usadas na conversão para PDF. | ✅ |
| `relatorio.html` | **HTML** (página web) | Versão intermediária gerada pelo pandoc a partir do `.md`. É regerada a cada `gerar_pdf.sh`, por isso não é versionada. | ⛔ |
| `adriano_carvalho_ai-agents_langchain-agents.pdf` | **PDF** | O **relatório final entregue** (13 páginas), com o nome exigido pelo enunciado. | ✅ |

### `relatorio/avaliacao/` — resultados da avaliação

**Finalidade:** guardar os **números** dos experimentos LangSmith localmente, para o relatório e para quem não tiver acesso ao LangSmith.

| Arquivo | Tipo | Conteúdo |
|---|---|---|
| `resultados_com-transformacao.csv` | **CSV** (tabela em texto, colunas separadas por vírgula; abre no Excel) | Experimento A: uma linha por caso (19), com resposta, ferramentas chamadas e as notas de cada avaliador. |
| `resultados_sem-transformacao.csv` | CSV | Experimento B: os mesmos 19 casos sem a transformação de consulta. |
| `resultados_pos-correcao.csv` | CSV | Experimento C: só os 4 casos afetados pela correção (para economizar API). |
| `resumo.json` | JSON | Médias de cada experimento e os **links** para as comparações no LangSmith. |

Gerados por `scripts/rodar_avaliacao.py`. Versionados ✅.

### `relatorio/capturas/` — imagens da interface

**Finalidade:** as **evidências visuais** citadas na seção 4.5 do relatório. Arquivos **PNG** (imagem), capturados da sessão real no Streamlit.

| Arquivo | Mostra |
|---|---|
| `01_ferramentas_em_execucao.png` | O agente chamando as ferramentas ao vivo. |
| `02_resposta_planejamento.png` | A resposta com o plano (épico, histórias, pontos). |
| `03_trajetoria.png` | O painel com as ferramentas usadas e seus tipos. |
| `04_verificacao.png` | O painel de verificação (afirmações, NLI, coerência). |
| `05_memoria_turno_bruno.png` | O uso da memória no turno "e se tirarmos o Bruno?". |
| `06_autocorrecao.png` | Um rascunho reprovado e corrigido automaticamente. |
| `07_aprovacao_humana.png` | O pedido de aprovação antes de gravar. |
| `08_aprovado_issues.png` | Depois da aprovação: histórias gravadas e issues reais #1–#3 no GitHub. |

Versionadas ✅.

---

## 8. `logs/` — registros de execução

**Finalidade:** **rastro** do que aconteceu durante o desenvolvimento e o uso. **Responsabilidade:** auditoria e depuração. Toda a pasta fica fora do Git ⛔ (pode conter dados de sessões e é recriada no uso).

| Arquivo | Tipo | Conteúdo | Quando é gerado |
|---|---|---|---|
| `execucoes.jsonl` | **JSON Lines** (um objeto JSON por linha; fácil de acrescentar e de ler aos poucos) | 747 eventos: início/fim de cada chamada ao LLM e a ferramentas, com sessão, modelo, duração e tokens. | A cada execução do agente (por `callbacks.py`). |
| `avaliacao.log` | Texto | Saída da execução de `rodar_avaliacao.py`, com os links dos experimentos no LangSmith e avisos. | Ao rodar a avaliação. |
| `streamlit.log` | Texto | Saída do servidor Streamlit (inicialização, avisos, erros). | Ao rodar a interface em segundo plano. |
| `issues_simuladas.json` | JSON | Issues "abertas" em **modo simulado** (numeradas a partir de 1001), quando a escrita real no GitHub está desligada. | Ao aprovar um registro com `GITHUB_ESCRITA_REAL=0` (ex.: no notebook 5). |
| `backlog_antes_da_fase5.db` | SQLite | **Cópia de segurança** do `backlog.db` antes dos testes da Fase 5, para poder restaurar o estado original. | Uma vez, manualmente, antes da Fase 5. |

---

## Resumo: o caminho de uma pergunta pelos arquivos

1. Você digita no **`app.py`** (Streamlit).
2. **`agentes/integrador.py`** recebe; **`memoria/intencao.py`** identifica a intenção; **`memoria/longo_prazo.py`** busca lembranças em **`dados/memoria.db`**; o histórico vem de **`dados/historico_conversas.db`**.
3. O Claude (configurado em **`config.py`**, instruído por **`prompts.py`**) escolhe ferramentas de **`ferramentas/catalogo.py`**, que consultam **`dados/backlog.db`**, **`dados/indice_faiss/`** e as APIs externas.
4. **`verificacao/verificador.py`** confere a resposta; se reprovar, ela é corrigida.
5. **`observabilidade/callbacks.py`** registra tudo em **`logs/execucoes.jsonl`**.
6. Se houver algo a gravar, **`ferramentas/acoes.py`** cria uma pendência; só depois do seu clique em **Aprovar** o backlog é alterado e as issues são abertas no GitHub.
