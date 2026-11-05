"""Agente com function calling: `create_openai_tools_agent` + `AgentExecutor`.

Com Claude, o adaptador `ChatClaudeCompat` (config.py) converte as ferramentas do formato
OpenAI para o formato da Anthropic; o restante (tool_calls -> AgentAction) é agnóstico.

Prompt: system PTCF com exemplos few-shot (em texto, rotulados) + histórico + entrada + rascunho.

Os exemplos few-shot ficam DENTRO do system prompt, e não como pares de mensagens
human/ai: na Fase 3 observamos que, como mensagens, o modelo os confundia com turnos reais
da conversa ("as respostas anteriores citaram CVSS 9,1 sem consulta").
"""

from __future__ import annotations

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from fabrica_agentica.config import criar_llm
from fabrica_agentica.ferramentas.catalogo import FERRAMENTAS
from fabrica_agentica.prompts import system_com_exemplos


def prompt_agente(com_memoria_longa: bool = False) -> ChatPromptTemplate:
    sistema = system_com_exemplos()
    if com_memoria_longa:
        sistema += (
            "\n\nMEMÓRIAS DE LONGO PRAZO RELEVANTES (de sessões anteriores; use se ajudarem, respeite as "
            "preferências do usuário e não invente memórias):\n{memorias}"
            "\n\nESTADO DA SESSÃO (intenção e entidades reconhecidas, acumuladas entre turnos):\n{contexto_sessao}"
        )
    return ChatPromptTemplate.from_messages(
        [
            ("system", sistema),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )


def criar_executor(
    ferramentas: list | None = None,
    memoria=None,
    com_memoria_longa: bool = False,
    verbose: bool = False,
    max_iteracoes: int = 10,
) -> AgentExecutor:
    ferramentas = ferramentas or FERRAMENTAS
    agente = create_openai_tools_agent(criar_llm("agente"), ferramentas, prompt_agente(com_memoria_longa))
    return AgentExecutor(
        agent=agente,
        tools=ferramentas,
        memory=memoria,
        verbose=verbose,
        max_iterations=max_iteracoes,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


def trajetoria(resultado: dict) -> list[dict]:
    """Lista (ferramenta, argumentos, resumo da observação) a partir de intermediate_steps."""
    return [
        {"ferramenta": acao.tool, "argumentos": acao.tool_input, "observacao": str(obs)[:200]}
        for acao, obs in resultado.get("intermediate_steps", [])
    ]
