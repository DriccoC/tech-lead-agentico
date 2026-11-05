"""Fase 2 — Agente ReAct clássico: `initialize_agent` + `ZERO_SHOT_REACT_DESCRIPTION`.

O ReAct alterna, em TEXTO, Thought (raciocínio) -> Action (ferramenta) -> Action Input
-> Observation (resultado), até a Final Answer. O tipo ZERO_SHOT_REACT só aceita
ferramentas de UMA entrada (string), por isso as ferramentas estruturadas do catálogo
ganham aqui versões "de texto". Memória básica: ConversationBufferMemory injetada no
prompt como {chat_history}.

Este construto é legado (vive em langchain-classic); o projeto o usa porque a rubrica
pede, e porque deixa o ciclo Thought/Action/Observation explícito e depurável. As fases
seguintes migram para tool calling nativo (create_openai_tools_agent e LangGraph).
"""

from __future__ import annotations

import json

from langchain_classic.agents import AgentType, initialize_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.tools import Tool

from fabrica_agentica.config import criar_llm
from fabrica_agentica.ferramentas import catalogo


def _vulns(texto: str) -> str:
    pacote, _, versao = texto.replace(" ", "").partition("==")
    return catalogo.consultar_vulnerabilidades.invoke({"pacote": pacote, "versao": versao or "0"})


def ferramentas_texto() -> list[Tool]:
    """Ferramentas de entrada única para o ReAct em texto."""
    return [
        Tool(
            name="calcular_capacidade_sprint",
            func=lambda projeto: catalogo.calcular_capacidade_sprint.invoke({"projeto": projeto.strip().strip("'\"")}),
            description="Capacidade e saldo de pontos da próxima sprint planejada. Entrada: nome do projeto (Portal, PagaFacil ou AppCampo).",
        ),
        Tool(
            name="consultar_pypi",
            func=lambda pacote: catalogo.consultar_pypi.invoke({"pacote": pacote.strip().strip("'\"")}),
            description="Versão estável mais recente de um pacote Python no PyPI. Entrada: nome do pacote.",
        ),
        Tool(
            name="consultar_vulnerabilidades",
            func=_vulns,
            description="Vulnerabilidades conhecidas (OSV) de uma versão de pacote. Entrada no formato pacote==versao (ex.: authlib==1.3.0).",
        ),
        Tool(
            name="buscar_manual_engenharia",
            func=lambda consulta: catalogo.buscar_manual_engenharia.invoke({"consulta_otimizada": consulta}),
            description="Busca no Manual de Engenharia (normas MAN-01 a MAN-07). Entrada: consulta com termos formais das normas.",
        ),
        Tool(
            name="consultar_backlog_sql",
            func=lambda consulta: catalogo.consultar_backlog_sql.invoke({"consulta_sql": consulta.strip().strip("`")}),
            description="Executa um SELECT no banco de backlog. Entrada: uma consulta SQL SQLite. " + catalogo.sql.DICIONARIO_DADOS.replace("\n", " "),
        ),
    ]


PREFIXO = (
    "Você é o Tech Lead Agêntico da NovaForja Software (empresa fictícia). Responda em português do Brasil. "
    "Nunca invente números, versões ou regras: use as ferramentas. Você tem acesso às seguintes ferramentas:"
)
SUFIXO = """Histórico da conversa:
{chat_history}

Comece! Lembre-se de escrever a Final Answer em português.

Question: {input}
Thought:{agent_scratchpad}"""


def criar_agente_react(verbose: bool = True, callbacks: list | None = None):
    memoria = ConversationBufferMemory(memory_key="chat_history", input_key="input")
    return initialize_agent(
        tools=ferramentas_texto(),
        llm=criar_llm("agente"),
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        memory=memoria,
        verbose=verbose,
        handle_parsing_errors=True,  # se o LLM sair do formato, o erro vira Observation e ele tenta de novo
        max_iterations=6,
        agent_kwargs={"prefix": PREFIXO, "suffix": SUFIXO, "input_variables": ["input", "agent_scratchpad", "chat_history"]},
        callbacks=callbacks,
        return_intermediate_steps=False,
    )


def resumir_passos(passos: list) -> list[dict]:
    return [{"ferramenta": a.tool, "entrada": a.tool_input, "observacao": str(o)[:160]} for a, o in passos]


__all__ = ["criar_agente_react", "ferramentas_texto", "json"]
