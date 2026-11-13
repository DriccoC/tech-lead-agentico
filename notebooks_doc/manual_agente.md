# Manual do usuário — Tech Lead Agêntico

Este manual explica como usar o **Tech Lead Agêntico** pela interface web: o que faz cada botão, campo e painel, e **o que acontece por dentro, passo a passo**, desde o clique em enviar até a resposta final e o registro no backlog.

> **Em uma frase:** o Tech Lead Agêntico é um líder técnico virtual da NovaForja Software (empresa fictícia). Você descreve uma demanda em português comum e ele consulta a equipe, as regras da empresa, as bibliotecas e o GitHub; monta um plano de trabalho; confere a própria resposta; e só grava algo depois da sua aprovação.

---

## Sumário

1. [Como abrir a interface](#1-como-abrir-a-interface)
2. [Visão geral da tela](#2-visão-geral-da-tela)
3. [Barra lateral: configurações e sessão](#3-barra-lateral-configurações-e-sessão)
4. [Área principal: a conversa](#4-área-principal-a-conversa)
5. [O que acontece quando você envia uma mensagem](#5-o-que-acontece-quando-você-envia-uma-mensagem)
6. [Registrar no backlog e abrir issues (aprovação humana)](#6-registrar-no-backlog-e-abrir-issues-aprovação-humana)
7. [Exemplos de perguntas](#7-exemplos-de-perguntas)
8. [Boas práticas](#8-boas-práticas)
9. [Solução de problemas](#9-solução-de-problemas)
10. [Onde ficam os dados gravados](#10-onde-ficam-os-dados-gravados)

---

## 1. Como abrir a interface

1. Abra um terminal na pasta do projeto e ative o ambiente virtual:
   ```bash
   source .venv/bin/activate
   ```
2. Inicie a interface:
   ```bash
   streamlit run app.py
   ```
   No VS Code, também dá para usar o atalho **"Streamlit: Tech Lead Agêntico"** no menu *Executar e depurar* (F5).
3. O navegador abre em **http://localhost:8501**.
4. Na primeira abertura aparece a mensagem **"Carregando modelos locais (embeddings, NLI e índice FAISS)..."**. É o carregamento, no seu computador, dos modelos que fazem a busca no manual e a verificação das respostas. Leva alguns segundos e só acontece uma vez enquanto o servidor estiver ligado.

> **Sem chave de API?** O agente entra sozinho em **modo demonstração**: funciona de ponta a ponta, sem custo, com um modelo roteirizado (ver [seção 9](#9-solução-de-problemas)).

---

## 2. Visão geral da tela

```
┌──────────────────────────────┬────────────────────────────────────────────────────┐
│ BARRA LATERAL                │ ÁREA PRINCIPAL                  [Stop] Deploy  ⋮  │
│                              │                                                    │
│ 🛠️ Tech Lead Agêntico         │ Planeje demandas, consulte o backlog, normas e     │
│ (aviso de modo demonstração) │ bibliotecas                                        │
│                              │ Provedor: anthropic · motor: executor · verif.: on │
│ Usuário        [adriano    ] │                                                    │
│ Motor do agente              │  👤 sua mensagem                                    │
│  (•) AgentExecutor + ...     │  🤖 resposta do agente                              │
│  ( ) LangGraph (...)         │     ⏱️ tempo · ✅ Verificação: APROVADA              │
│ [■] Verificar respostas      │     [🔧 Trajetória] [🛡️ Verificação] [🧠 Memórias]   │
│                              │     ┌ 📝 Aprovação humana necessária ┐             │
│ [ 🆕 Nova sessão           ]  │     │ [✅ Aprovar e gravar] [❌ Rejeitar]│             │
│ [ 💾 Encerrar sessão       ]  │     └──────────────────────────────────┘           │
│ > ⚙️ Ambiente                │                                                    │
│ > 🧠 Memória de longo prazo  │                                                    │
│                              │                                                    │
│   MBA - Engenharia de IA     │ ┌────────────────────────────────────────────┐    │
│      [logo Infnet]           │ │ Ex.: Quero login com Google (Google Ide... │ ➤  │
│   Instituto Infnet           │ └────────────────────────────────────────────┘    │
│   ©2026 Adriano de Carvalho  │                                                    │
└──────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Barra lateral (esquerda):** *como* o agente vai trabalhar (quem é você, qual motor, se verifica as respostas) e o controle da sessão.
- **Área principal (direita):** a conversa, as respostas e os painéis que mostram o que o agente fez.

Em telas estreitas a barra lateral pode vir recolhida: clique em **»** no canto superior esquerdo para abri-la e em **«** para fechá-la.

---

## 3. Barra lateral: configurações e sessão

### 3.1 Título e aviso de modo demonstração

- **🛠️ Tech Lead Agêntico:** título, com a legenda *"1º agente da fábrica agêntica de software · NovaForja (empresa fictícia)"*.
- **Faixa amarela "Modo demonstração":** só aparece quando não há chave de API configurada (ou quando `LLM_PROVIDER=demo` no `.env`). Indica que as respostas vêm de um modelo roteirizado, sem custo. As ferramentas (cálculos, banco, manual) continuam reais.

### 3.2 Campo "Usuário (escopo da memória de longo prazo)"

| Tipo | Valor padrão |
|---|---|
| Campo de texto | `adriano` |

**Para que serve:** identifica quem está usando o agente. Tem dois efeitos:

1. **Memória separada por pessoa.** Cada usuário tem as próprias memórias de longo prazo (preferências, decisões, sessões anteriores). Se você digitar `bruno`, o agente não verá o que lembrou do `adriano`.
2. **Autoria das aprovações.** O nome aparece como "aprovada por ..." no texto das issues abertas no GitHub.

**Atenção:** alterar o nome **inicia uma sessão nova** (a conversa da tela é apagada).

### 3.3 Seletor "Motor do agente"

| Tipo | Opções |
|---|---|
| Botões de opção (*radio*) | **AgentExecutor + RunnableWithMessageHistory** (padrão) · **LangGraph (create_agent + HITL)** |

**Para que serve:** escolhe a "engrenagem" que conduz o raciocínio. As ferramentas, a memória de longo prazo, a verificação e o modelo Claude são **os mesmos** nas duas opções.

| | AgentExecutor (padrão) | LangGraph |
|---|---|---|
| O que é | Forma clássica do LangChain, exigida pela rubrica da disciplina | Forma moderna, base da próxima disciplina (multiagente) |
| Histórico da conversa | `dados/historico_conversas.db` | `dados/checkpoints.db` (o estado completo do grafo a cada passo) |
| Aprovação humana | O agente **propõe** o registro; a gravação é um código separado, acionado pelo botão | O grafo **pausa** antes de executar a gravação e só continua depois do botão |
| Caixa de aprovação | Legível: projeto, sprint, pontos, histórias | Técnica: o pedido de ferramenta em JSON |

**Recomendação:** use o **AgentExecutor** no dia a dia. Use o LangGraph para demonstrar a pausa nativa de aprovação.

**Atenção:** trocar o motor **inicia uma sessão nova**.

### 3.4 Chave "Verificar respostas (NLI + coerência)"

| Tipo | Valor padrão |
|---|---|
| Interruptor (*toggle*) | Ligado |

**Para que serve:** liga ou desliga a **camada de verificação**, que confere cada resposta contra o que as ferramentas retornaram antes de mostrá-la (explicada na [etapa 7](#etapa-7--verificação-da-resposta)).

- **Ligado:** respostas mais confiáveis, com o selo ✅/⚠️ e o painel 🛡️ Verificação. Mais lento e consome mais chamadas ao modelo.
- **Desligado:** respostas mais rápidas e baratas, sem conferência.

**Atenção:** alterar a chave **inicia uma sessão nova**.

### 3.5 Botão "🆕 Nova sessão"

**Para que serve:** começa uma conversa do zero.

**O que acontece ao clicar:**
- a conversa da tela é apagada;
- é criado um novo identificador de sessão (ex.: `adriano-3f9a1c`), com histórico próprio;
- o estado da sessão (projeto, sprint, pessoas citadas) é zerado;
- **a memória de longo prazo é mantida**: o agente continua lembrando suas preferências e sessões anteriores.

Use quando mudar de assunto (ex.: terminou o planejamento do Portal e vai tratar do PagaFacil).

### 3.6 Botão "💾 Encerrar sessão (gravar episódio)"

**Para que serve:** guardar um **resumo da sessão** na memória de longo prazo, para o agente lembrar dela em conversas futuras.

**O que acontece ao clicar:**
1. o agente lê toda a conversa da sessão;
2. o modelo auxiliar resume em **uma frase**, começando pela data, com projeto, sprint, decisões e números finais. Exemplo: *"09/11/2026: planejado login com Google no Portal, sprint 13, 3 histórias e 11 pontos; Bruno fora da sprint."*;
3. a frase é gravada como **memória episódica** em `dados/memoria.db`;
4. aparece uma faixa verde *"Episódio gravado: ..."*.

A conversa continua na tela; para começar outra, clique em **🆕 Nova sessão**. Se a sessão estiver vazia, a mensagem será *"sessão vazia"*.

### 3.7 Painel recolhível "⚙️ Ambiente"

Clique para abrir. Mostra a configuração em uso (sem exibir chaves):

| Linha | Significado |
|---|---|
| Provedor de LLM | `anthropic` (Claude), `openai` ou `demo` |
| APIs externas | `rede (ao vivo)` ou `respostas gravadas (offline)` |
| Embeddings | Modelo local que transforma textos em vetores (busca no manual e nas memórias) |
| Modelo NLI | Modelo local que verifica se uma afirmação é sustentada ou contradita |
| LangSmith | `ligado` (as execuções são registradas no LangSmith) ou `desligado` |
| Repositório GH | Repositório onde as issues são abertas, ou aviso de modo simulado |
| Sessão | Identificador da sessão atual |

Útil para confirmar, antes de uma demonstração, que tudo está no modo esperado.

### 3.8 Painel recolhível "🧠 Memória de longo prazo"

Clique para abrir. Lista **todas as memórias** do usuário atual, cada uma com seu tipo:

- `semantica`: fatos e preferências duráveis. Ex.: *"o Portal atende clientes B2B"*, *"o usuário prefere a biblioteca authlib"*.
- `episodica`: resumos de sessões anteriores (gravados pelo botão 💾 ou ao longo do uso).

O painel é atualizado a cada interação. É uma forma de ver o que o agente "sabe" sobre você.

### 3.9 Rodapé

Créditos do projeto: *MBA - Engenharia de IA*, logomarca e nome do *Instituto Infnet* e *©2026 Adriano de Carvalho*. Não tem função interativa.

### 3.10 Canto superior direito (controles do Streamlit)

Não fazem parte do agente; são do Streamlit, a ferramenta que gera a página.

| Elemento | Função |
|---|---|
| Ícone animado + **Stop** | Aparece enquanto o agente está processando. **Stop** interrompe o processamento atual. |
| **Deploy** | Publica o app na nuvem do Streamlit. **Não use**: as chaves de API ficariam expostas para terceiros. |
| **⋮** (menu) | Opções da página: *Rerun* (recarregar; atalho tecla **R**), *Settings* (tema claro/escuro), imprimir, gravar a tela e limpar cache. |

---

## 4. Área principal: a conversa

### 4.1 Cabeçalho

- **Título:** *"Planeje demandas, consulte o backlog, normas e bibliotecas"*.
- **Linha de status:** `Provedor: anthropic · motor: executor · verificação: ligada`. Confirma de relance a configuração da barra lateral.

### 4.2 Campo de mensagem e botão enviar (➤)

- **Campo:** fica no rodapé da área principal, com o exemplo *"Ex.: Quero login com Google (Google Identity Services) no projeto Portal na próxima sprint."*.
- **Enviar:** pressione **Enter** ou clique em **➤**.
- Escreva como falaria com um colega: não é preciso usar comandos nem palavras-chave.
- **Campo bloqueado:** o campo fica desativado em duas situações, e o texto dentro dele diz o motivo:
  - *"⏳ Aguarde: o agente está trabalhando na sua demanda..."*: enquanto o agente processa a mensagem anterior. Os controles da barra lateral também ficam desativados, porque no Streamlit qualquer envio ou clique reiniciaria a página e interromperia a resposta no meio. Só o botão **🆕 Nova sessão** continua ativo, como saída de emergência;
  - *"📝 Aprove ou rejeite o registro pendente acima para continuar a conversa."*: no motor LangGraph, quando há uma aprovação pendente. O grafo fica pausado até a decisão e não processaria uma nova mensagem.
- Se o processamento falhar ou for interrompido, a conversa mostra um aviso ⚠️ no lugar da resposta e o campo volta a funcionar: basta enviar a mensagem de novo.

### 4.3 Durante o processamento

Logo após o envio:

1. sua mensagem aparece com o ícone 👤;
2. surge a mensagem do agente 🤖 com um **painel de progresso**. O título do painel mostra a etapa em andamento, e cada etapa aparece **ao vivo**, em linguagem natural, marcada com ✓ quando termina. Por exemplo:
   - 🧭 Entendendo o pedido (intenção e entidades)
   - 🧠 Lembrando o contexto (memórias de longo prazo)
   - 📅 Calculando a capacidade da sprint 13 do Portal (equipe, folgas e feriados da BrasilAPI)
   - 📘 Buscando no Manual de Engenharia: "…"
   - 📦 Consultando a versão mais recente de authlib no PyPI · 🔐 Checando vulnerabilidades na base OSV
   - ✍️ Criando o épico, as histórias (critérios Gherkin) e as tarefas
   - 🛡️ Verificando a resposta (fatos, NLI e coerência lógica) e, se reprovada, ↻ corrigindo a resposta
   - 💾 Guardando decisões e preferências na memória
3. ao final, o painel se recolhe com o resumo **"Concluído em X s · N etapas"** e continua na conversa: clique nele para rever as etapas. Os nomes técnicos e os argumentos de cada ferramenta ficam no painel **🔧 Trajetória**;
4. no canto superior direito aparece **Stop**.

Uma pergunta simples leva poucos segundos. Um planejamento completo (várias ferramentas + verificação) pode levar **um a dois minutos**.

### 4.4 A resposta e seus painéis

Ao terminar, a mensagem do agente mostra:

**a) Texto da resposta.** Em Markdown: primeiro a conclusão, depois os fundamentos com a fonte de cada número ou regra entre parênteses (ex.: *"saldo de 14 pontos (calcular_capacidade_sprint, MAN-06 §3)"*) e, quando houver, os próximos passos.

**b) ⏱️ Tempo total** do processamento, em segundos.

**c) Selo da verificação** (quando a verificação está ligada e houve algo a conferir):

| Selo | Significado |
|---|---|
| ✅ Verificação: APROVADA | Nenhuma contradição ou incoerência encontrada. |
| ✅ Verificação: APROVADA (resposta corrigida automaticamente) | O primeiro rascunho foi reprovado; o agente corrigiu e a versão final foi aprovada. |
| ⚠️ Verificação: REPROVADA | Mesmo após a correção, ainda há problema. **Leia a resposta com cautela** e veja os motivos no painel 🛡️. |

**d) Três painéis recolhíveis, lado a lado:**

**🔧 Trajetória (N ferramentas)**: o caminho que o agente percorreu, em ordem.

| Coluna | Conteúdo |
|---|---|
| tipo | Categoria da ferramenta: `hardcoded`, `API externa`, `text-to-query`, `RAG (FAISS)`, `semântica`, `ação (aprovação humana)` |
| ferramenta | Nome da ferramenta chamada |
| argumentos | O que o agente enviou (ex.: `{"projeto": "Portal", "numero_sprint": 13}`) |

Se o agente respondeu sem consultar nada, o painel diz *"Nenhuma ferramenta usada neste turno."*.

**🛡️ Verificação**: o relatório do verificador.

| Elemento | Conteúdo |
|---|---|
| Tabela de afirmações | Cada frase verificável da resposta, com o **tipo** (fato ou conclusão), o resultado **NLI** (`sustentada`, `neutra`, `contradição`, `conclusão (juiz)`, `sem evidência`) e a **probabilidade de contradição** |
| Coerência lógica | Veredito do juiz e falhas encontradas (ex.: `erro_de_calculo`) |
| Motivos da reprovação | Só aparece se houve reprovação |
| Justificativa | Explicação do juiz em texto |
| Rascunho reprovado + Motivos | Só aparece se houve autocorreção: mostra a versão original e por que foi reprovada (útil para auditar a correção) |

**🧠 Memórias usadas (N)**: as memórias de longo prazo que o agente recuperou e levou em conta nesta resposta. Ex.: *"o Portal atende clientes B2B"*.

**e) Caixa "📝 Aprovação humana necessária"**: só aparece quando você pediu para registrar algo. Detalhada na [seção 6](#6-registrar-no-backlog-e-abrir-issues-aprovação-humana).

---

## 5. O que acontece quando você envia uma mensagem

Esta seção acompanha, etapa por etapa, o processamento do exemplo:

> **"Quero login com Google (Google Identity Services) no projeto Portal na próxima sprint."**

### Fluxo resumido

```
 Você clica em ➤
      │
      ▼
 [1] Entender o pedido ............ intenção + entidades (projeto, sprint, pacote...)
      │
      ▼
 [2] Falta informação? ── sim ──▶ o agente PERGUNTA e para aqui (ex.: "Para qual projeto?")
      │ não
      ▼
 [3] Lembrar ...................... busca memórias de longo prazo relevantes
      │
      ▼
 [4] Montar o contexto ............ instruções + histórico da conversa + memórias + estado
      │
      ▼
 [5] Raciocinar e consultar ....... ciclo: pensar → chamar ferramenta → ler resultado → pensar...
      │   5a capacidade da sprint (banco + feriados + fórmula)
      │   5b regras da empresa (manual, RAG)
      │   5c bibliotecas e vulnerabilidades (PyPI, OSV)
      │   5d issues existentes (GitHub)
      │   5e criar épico, histórias e tarefas
      │   5f comparar pontos × saldo da sprint
      ▼
 [6] Rascunho da resposta
      │
      ▼
 [7] Verificar .................... fact-check + NLI + juiz de coerência
      │
      ├── reprovada ──▶ [8] Autocorrigir (uma vez) e verificar de novo
      │
      ▼
 [9] Aprender ..................... grava fatos duráveis na memória de longo prazo
      │
      ▼
 [10] Mostrar ..................... resposta + tempo + selo + painéis (+ caixa de aprovação)
```

### Etapa 0 — A interface recebe a mensagem

- A mensagem é exibida na conversa.
- A interface conecta ao agente o painel de progresso (`fabrica_agentica/observabilidade/progresso.py`): um "observador" (`ProgressoCallback`) traduz cada ferramenta chamada numa frase, e o próprio agente avisa as demais etapas (entender, lembrar, verificar, corrigir, aprender) pelo atributo `ao_progresso`. É isso que faz as etapas aparecerem **ao vivo** na tela.
- Outro observador grava cada passo em `logs/execucoes.jsonl` (horário, duração, tokens) e, se ligado, no **LangSmith**.

### Etapa 1 — Entender o pedido (intenção e entidades)

Um **modelo auxiliar** (mais rápido e barato que o principal) lê a mensagem e devolve, em formato estruturado:

- **Intenção**, uma de cinco:

  | Intenção | Quando |
  |---|---|
  | `planejar_demanda` | Pedido de algo novo a ser construído |
  | `consultar_backlog` | Pergunta sobre histórias, bugs, sprints, pessoas |
  | `checar_dependencia` | Pergunta sobre uma biblioteca, versão ou vulnerabilidade |
  | `consultar_padrao` | Pergunta sobre uma regra da empresa |
  | `conversa_geral` | Cumprimentos e assuntos gerais |

- **Entidades:** projeto, sprint, pacote, versão, prioridade, pessoa.

No exemplo: intenção `planejar_demanda`, entidade `projeto = Portal`.

As entidades vão para o **estado da sessão**, que se acumula entre mensagens. Por isso, depois, você pode dizer apenas *"e se tirarmos o Bruno?"*: o agente sabe que ainda se trata do Portal e da mesma sprint. O classificador também resolve referências como *"a biblioteca que você sugeriu"*, olhando a última resposta.

### Etapa 2 — Falta alguma informação essencial?

Algumas intenções exigem uma entidade obrigatória:

| Intenção | Exige | Pergunta feita se faltar |
|---|---|---|
| `planejar_demanda` | projeto | *"Para qual projeto é essa demanda: Portal, PagaFacil ou AppCampo?"* |
| `checar_dependencia` | pacote | *"Qual biblioteca (pacote) você quer que eu verifique?"* |

Se faltar, o agente **pergunta e para aqui**, sem acionar o modelo principal nem ferramentas (rápido e barato). Quando você responde (ex.: *"Portal"*), ele retoma a intenção que estava pendente.

No exemplo, o projeto foi informado, então segue.

### Etapa 3 — Lembrar (memória de longo prazo)

O agente busca em `dados/memoria.db` as **até 4 memórias mais parecidas** com a mensagem e o estado da sessão (descartando as pouco relacionadas) e acrescenta sempre o **resumo da sessão mais recente**. A busca é por significado (vetores calculados localmente), não por palavras iguais.

No exemplo, pode recuperar *"o Portal atende clientes B2B"* ou *"o usuário prefere authlib"*. Essas memórias aparecerão no painel **🧠 Memórias usadas**.

### Etapa 4 — Montar o contexto para o modelo principal

O Claude recebe, de uma vez:

1. **Instruções fixas (system prompt no formato PTCF):** *Persona* (líder técnico rigoroso), *Tarefa*, *Contexto* (projetos, fontes de verdade e regras de raciocínio) e *Formato* da resposta. Entre as regras: nunca inventar números, versões ou regras; capacidade sempre pela ferramenta de cálculo; biblioteca com CVSS ≥ 7,0 bloqueia a adoção; e só propor registro quando você pedir.
2. **Exemplos de raciocínio (few-shot):** três casos ilustrativos que ensinam o padrão esperado.
3. **Histórico da conversa:** as **6 mensagens mais recentes** na íntegra; as mais antigas, resumidas (preservando projeto, sprint, pessoas, números e decisões). Assim a conversa pode ser longa sem estourar o limite do modelo.
4. **Memórias de longo prazo** da etapa 3.
5. **Estado da sessão:** intenção atual e entidades acumuladas.
6. **Sua mensagem.**
7. **A lista das 12 ferramentas**, cada uma com nome, descrição e argumentos.

### Etapa 5 — Raciocinar e consultar as ferramentas

Aqui o agente trabalha em **ciclo**: decide qual ferramenta chamar, recebe o resultado, pensa de novo e decide a próxima, até ter informação suficiente para responder. **É o próprio modelo que escolhe** as ferramentas e a ordem; o código não impõe uma sequência fixa.

Para uma demanda nova, as instruções pedem que ele **planeje antes de agir**, seguindo esta ordem:

#### 5a. Verificar os recursos: capacidade da sprint

**Ferramenta:** `calcular_capacidade_sprint` (tipo *hardcoded*, cálculo exato, sem IA).

1. Localiza no backlog a **próxima sprint planejada** do Portal (ou a sprint pedida).
2. Lê quem está alocado, o **fator de foco** de cada pessoa e os **dias de ausência** (folgas).
3. Consulta os **feriados nacionais** na **BrasilAPI** (ex.: 20/11) e conta os **dias úteis** do período.
4. Aplica a fórmula do manual (MAN-06 §3):
   - **capacidade bruta** = soma de (dias úteis − ausências) × fator de foco × 1 ponto/dia, para cada pessoa;
   - **capacidade líquida** = bruta × 80% (20% reservados para defeitos e imprevistos), arredondada para baixo;
   - **saldo disponível** = líquida − pontos já comprometidos na sprint.
5. Devolve o saldo, o detalhe por pessoa e os feriados descontados.

Se você pedir *"e se tirarmos o Bruno?"*, a mesma ferramenta recalcula sem ele.

#### 5b. Verificar as regras da empresa

**Ferramenta:** `buscar_manual_engenharia` (tipo *RAG*).

1. O agente **reescreve** a pergunta no vocabulário formal do manual (ex.: "login com Google" → "autenticação federada OIDC, provedores homologados").
2. A ferramenta gera **variações** da consulta e um **trecho hipotético** de norma (técnicas multi-query e HyDE), para não perder resultados por diferença de palavras.
3. Busca no **índice FAISS** os trechos do manual de significado mais próximo e devolve cada um com seu **score de similaridade** e identificador (`MAN-05`, `CHK_xxx`).
4. Se todos os trechos tiverem similaridade baixa, o agente deve dizer que **o manual não cobre o assunto**, em vez de inventar.

No exemplo: as regras de autenticação (MAN-05: protocolos e bibliotecas homologados, autenticação multifator) e de planejamento (MAN-06).

#### 5c. Verificar as bibliotecas

**Ferramentas:** `consultar_pypi`, `consultar_vulnerabilidades` (tipo *API externa*), `comparar_versoes` e `classificar_cvss` (tipo *hardcoded*).

1. **PyPI:** versão estável mais recente da biblioteca indicada pela norma (ex.: `authlib`).
2. **OSV.dev:** vulnerabilidades conhecidas daquela versão.
3. **classificar_cvss:** converte a nota de cada falha em gravidade (baixa, média, alta, crítica).
4. **comparar_versoes:** diz se uma versão em uso está desatualizada.
5. Regra do MAN-04: **CVSS ≥ 7,0 na versão pretendida bloqueia a adoção**.

#### 5d. Verificar o que já existe no GitHub

**Ferramenta:** `buscar_issues_github` (tipo *API externa*).

Procura issues já abertas sobre o assunto no repositório-sandbox. Se existirem, o agente **alerta sobre duplicação** em vez de propor tudo de novo.

#### 5e. Criar as atividades: épico, histórias e tarefas

**Ferramenta:** `decompor_demanda` (tipo *semântica*, usa IA).

Com as restrições descobertas (saldo, normas, biblioteca), gera um **plano estruturado**:
- **épico** e objetivo;
- **histórias** no formato "Como ..., quero ..., para ...", cada uma com **critérios de aceite em Gherkin** (*Dado / Quando / Então*), **tarefas** técnicas e **pontos** estimados.

O formato é validado automaticamente (esquema Pydantic `PlanoTrabalho`): se o modelo devolver algo fora do padrão, é rejeitado.

#### 5f. Comparar o plano com a capacidade

O agente soma os pontos das histórias e compara com o **saldo da sprint** (5a). Se não couber, ele sugere alternativas: reduzir o escopo, dividir entre sprints ou retirar outra história.

#### Outras ferramentas, conforme a pergunta

| Ferramenta | Quando entra |
|---|---|
| `consultar_backlog_sql` (*text-to-query*) | Perguntas sobre o backlog ("quais bugs críticos estão abertos?"). O agente escreve o SQL; a ferramenta só aceita leitura (`SELECT`), bloqueia comandos de escrita e limita a 50 linhas. |
| `consultar_feriados` (*API externa*) | Perguntas diretas sobre feriados. |
| `resumir_texto_tecnico` (*semântica*) | Resumir um texto longo (issue, alerta de segurança) com foco em riscos e decisões. |
| `propor_registro_backlog` (*ação*) | Só quando você pede para registrar (ver [seção 6](#6-registrar-no-backlog-e-abrir-issues-aprovação-humana)). |

Perguntas simples usam uma ou duas ferramentas. Um planejamento completo costuma usar de **6 a 10**.

### Etapa 6 — Rascunho da resposta

Com os resultados das ferramentas, o Claude escreve o **rascunho**: conclusão primeiro, depois os fundamentos com fonte, depois os próximos passos. Esse texto **ainda não é mostrado** se a verificação estiver ligada.

### Etapa 7 — Verificação da resposta

Executada quando a chave **Verificar respostas** está ligada e houve evidências a conferir (ferramentas usadas na sessão). São quatro passos:

1. **Coletar as evidências:** as saídas das ferramentas são convertidas em **frases simples** em português (ex.: `{"saldo_disponivel": 14}` → "o saldo disponível da sprint é de 14 pontos"). Entram também as regras procedurais do manual e as memórias usadas.
2. **Extrair as afirmações:** o modelo auxiliar separa a resposta em afirmações verificáveis, classificadas como **fato** (algo que deve estar nas evidências) ou **conclusão** (raciocínio do agente).
3. **Fact-check dos números:** todo número de uma afirmação precisa aparecer nas evidências. Número ausente vira **alerta** ("número não encontrado nas evidências").
4. **NLI (inferência em linguagem natural):** um modelo especializado, **rodando no seu computador**, compara cada **fato** com as evidências mais parecidas e decide:
   - **sustentada:** as evidências confirmam (probabilidade ≥ 0,60);
   - **contradição:** as evidências desmentem;
   - **neutra:** as evidências não dizem nem que sim nem que não.
5. **Juiz de coerência:** um modelo avalia se o raciocínio fecha do começo ao fim (ex.: se a conclusão bate com as premissas, se há erro de conta).

**Critério de reprovação:**
- uma afirmação **contradita** com probabilidade **≥ 0,80**; ou
- **incoerência grave** (conclusão que contradiz as premissas, erro de cálculo); ou
- o juiz concluir que as evidências **refutam** a resposta.

Números não rastreados e detalhes sem evidência viram **alertas**, mas não reprovam sozinhos.

### Etapa 8 — Autocorreção (só se reprovada)

1. O agente recebe o rascunho, os **motivos da reprovação** e as evidências.
2. Reescreve a resposta **corrigindo só o que foi apontado**, usando somente as evidências.
3. A nova versão passa **de novo** pela verificação.
4. A versão corrigida substitui a original no histórico da conversa.

A correção é feita **uma única vez** (para limitar tempo e custo). O selo indica *"resposta corrigida automaticamente"*, e o painel 🛡️ mostra o rascunho reprovado e os motivos.

### Etapa 9 — Aprender (gravar memória de longo prazo)

O modelo auxiliar lê sua mensagem e a resposta final e extrai **fatos que valham para conversas futuras**: preferências, convenções do time, decisões tomadas (planos, pessoas retiradas da sprint, bibliotecas escolhidas). Regras do manual e dados do backlog **não** são gravados, porque já têm fonte própria.

Se um fato novo atualiza um antigo (ex.: mudou a biblioteca escolhida), a memória é **atualizada em vez de duplicada**.

### Etapa 10 — Mostrar o resultado

A interface exibe a resposta final, o tempo, o selo e os três painéis ([seção 4.4](#44-a-resposta-e-seus-painéis)). Se o agente propôs um registro, aparece também a caixa de aprovação.

---

## 6. Registrar no backlog e abrir issues (aprovação humana)

O agente **nunca grava nada sozinho**. O registro tem duas fases separadas: o agente **propõe**, você **decide**.

### 6.1 Pedir o registro

Depois de revisar o plano, peça explicitamente. Exemplos:

- *"Pode registrar no backlog e abrir as issues."*
- *"Registre só no backlog, sem abrir issue."*
- *"Fico com a opção 3: registre a história 'Login com Google via OIDC' com 5 pontos na sprint 13."*

### 6.2 O que o agente faz

**No motor AgentExecutor:**
1. O agente chama `propor_registro_backlog` com projeto, sprint, plano e se deve abrir issues.
2. A ferramenta **apenas cria uma pendência** (tabela `pendencias` em `dados/memoria.db`), com status `aguardando_aprovacao`, e devolve *"Registro PROPOSTO. Nada foi gravado"*.
3. A interface mostra a caixa **📝 Aprovação humana necessária** com projeto, sprint, total de pontos, se abrirá issues e a lista de histórias.

**No motor LangGraph:**
1. O agente tenta chamar a ferramenta de gravação `registrar_no_backlog`.
2. O grafo **pausa antes da execução** (mecanismo *human-in-the-loop* nativo) e salva o estado em `dados/checkpoints.db`.
3. A caixa de aprovação mostra o pedido técnico (JSON) com os argumentos que seriam usados.

### 6.3 Botão "✅ Aprovar e gravar"

Ao clicar (aparece *"Gravando no backlog e abrindo issues..."*):

1. **Confere a pendência:** precisa existir e ainda estar aguardando aprovação (uma pendência não pode ser executada duas vezes).
2. **Grava as histórias em `dados/backlog.db`:** uma linha por história, com épico, título, pontos, prioridade média e status **"a fazer"** (se houver sprint) ou **"backlog"** (sem sprint).
3. **Abre uma issue por história no GitHub** (se pedido), com o rótulo `tech-lead-agentico` e o corpo contendo épico, objetivo, critérios de aceite, tarefas em lista de verificação, número da história no backlog, pontos e *"aprovada por ..."* (o nome do campo Usuário).
4. **Marca a pendência como executada**, guardando o resultado.
5. A caixa fica verde: *"Aprovado: N histórias gravadas · issues: #1, #2, #3"*, com **links clicáveis** para as issues.

No LangGraph, o clique **retoma o grafo** do ponto em que parou; a gravação acontece e o agente escreve uma mensagem final, exibida na caixa.

> **Issues reais ou simuladas?** Depende da configuração `GITHUB_ESCRITA_REAL` no `.env`. Com `1`, as issues são abertas de verdade no repositório configurado. Com `0` (ou sem token), são **simuladas**: gravadas em `logs/issues_simuladas.json`, numeradas a partir de 1001, sem tocar no GitHub.

### 6.4 Botão "❌ Rejeitar"

- A pendência é marcada como **rejeitada**; **nada é gravado**.
- A caixa mostra *"Rejeitado: nada foi gravado."*.
- No LangGraph, o agente é informado da rejeição e pode responder a ela.

Você pode continuar a conversa normalmente e pedir um novo plano ou ajustes.

### 6.5 Por que é seguro

A gravação está em um código separado, **ao qual o modelo não tem acesso**: só o clique na interface o executa. Mesmo que o modelo se confunda ou alguém tente induzi-lo por texto, ele não consegue gravar no backlog nem abrir issues sem a sua aprovação.

---

## 7. Exemplos de perguntas

| Objetivo | Pergunta | Ferramentas típicas |
|---|---|---|
| Planejar uma demanda | *Quero login com Google (Google Identity Services) no projeto Portal na próxima sprint.* | capacidade, manual, PyPI, OSV, GitHub, decompor |
| Simular mudança na equipe | *E se tirarmos o Bruno da sprint?* | capacidade (sem o Bruno) |
| Capacidade | *Cabe mais uma história de 8 pontos na sprint 13 do Portal?* | capacidade |
| Backlog | *Quais bugs de severidade alta ou crítica estão abertos ou em correção?* | SQL |
| Equipe | *Quem são os desenvolvedores backend sênior?* | SQL |
| Biblioteca | *Posso usar a pyjwt 2.8.0?* | PyPI, OSV, CVSS |
| Regra da empresa | *Posso subir direto na main na sexta?* | manual |
| Regra da empresa | *Quem precisa revisar meu PR?* | manual |
| Fora do manual | *O manual fala sobre trabalho remoto?* | manual (resposta: não cobre) |
| GitHub | *Existe alguma issue no GitHub sobre login social?* | GitHub |
| Feriados | *Quais feriados caem em novembro de 2026?* | feriados |
| Registrar | *Pode registrar no backlog e abrir as issues.* | propor registro → aprovação |

---

## 8. Boas práticas

- **Seja específico:** projeto, sprint e biblioteca na mensagem evitam perguntas de esclarecimento.
- **Aproveite o contexto:** não é preciso repetir o projeto a cada mensagem; o agente lembra.
- **Revise antes de aprovar:** confira histórias e pontos na caixa de aprovação. Na dúvida, rejeite e peça ajustes.
- **Olhe o selo:** se aparecer ⚠️ REPROVADA, abra o painel 🛡️ para ver o que não bateu.
- **Encerre a sessão** com 💾 quando o planejamento terminar, para o agente lembrar dele depois.
- **Use 🆕 Nova sessão** ao mudar de assunto, para não misturar contextos.
- **Custo:** cada mensagem consome chamadas ao Claude (mais ainda com a verificação ligada). Para testes de interface sem custo, use o modo demonstração.
- **Não clique em Deploy.**

---

## 9. Solução de problemas

| Situação | Causa provável | O que fazer |
|---|---|---|
| Faixa amarela "Modo demonstração" | Sem `ANTHROPIC_API_KEY` no `.env`, ou `LLM_PROVIDER=demo` | Preencha a chave no `.env` e reinicie o Streamlit. |
| Erro de crédito ou de autenticação da API | Créditos esgotados ou chave inválida | Verifique a conta em platform.claude.com. |
| Primeira resposta muito lenta | Carregamento dos modelos locais | Normal; as seguintes são mais rápidas. |
| Issues com número 1001+ e "(simulada)" | `GITHUB_ESCRITA_REAL=0` ou sem token | Ajuste o `.env` se quiser issues reais. |
| "Repositório GH: (não configurado...)" no ⚙️ Ambiente | `GITHUB_REPO` vazio | Preencha `GITHUB_REPO` e `GITHUB_TOKEN` no `.env`. |
| Feriados não descontados | BrasilAPI fora do ar | A ferramenta avisa *"feriados não descontados"*; tente mais tarde. |
| A conversa sumiu | Mudou usuário, motor ou a chave de verificação (inicia sessão nova) | Comportamento esperado; a memória de longo prazo continua. |
| Mudança no código não aparece | A página não recarregou | Pressione **R** ou use ⋮ → *Rerun*; se persistir, recarregue a página do navegador. |
| Processamento travado | Resposta lenta de uma API externa | Clique em **Stop** e reenvie. |

---

## 10. Onde ficam os dados gravados

| O quê | Onde | Gravado quando |
|---|---|---|
| Histórias aprovadas | `dados/backlog.db` (tabela `historias`) | Clique em ✅ Aprovar |
| Issues | GitHub (repositório do `.env`) ou `logs/issues_simuladas.json` | Clique em ✅ Aprovar, se pedido |
| Pendências de aprovação | `dados/memoria.db` (tabela `pendencias`) | Agente propõe; status muda ao aprovar/rejeitar |
| Memórias de longo prazo | `dados/memoria.db` (tabela `memorias`) | A cada resposta (fatos) e no 💾 Encerrar sessão (episódio) |
| Histórico da conversa (AgentExecutor) | `dados/historico_conversas.db` | A cada mensagem |
| Estado do grafo (LangGraph) | `dados/checkpoints.db` | A cada passo do grafo |
| Log técnico de execução | `logs/execucoes.jsonl` | A cada chamada ao modelo e a ferramentas |
| Rastreamento completo | LangSmith (se ligado) | A cada mensagem |

Para restaurar o backlog original da empresa fictícia: `python scripts/criar_banco.py`.

Para a descrição de todos os arquivos do projeto, consulte o [estrutura_projeto.md](estrutura_projeto.md).
